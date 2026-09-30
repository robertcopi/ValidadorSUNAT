from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_empresa, require_role
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.consulta_cpe import ConsultaCPE
from app.schemas.sunat import (
    ComprobanteValidarRequest,
    ConsultaCPEResponse,
    EmpresaInfo,
    TIPO_COMPROBANTE_MAP
)
from app.schemas.proceso_masivo import CrearProcesoMasivoRequest, ProcesoMasivoResponse
from app.services.sunat_service import sunat_service, SunatException, SunatCredentialsError
from app.services.proceso_masivo_service import proceso_masivo_service, ProcesoMasivoException

router = APIRouter()


@router.post(
    "/validar",
    response_model=ConsultaCPEResponse,
    summary="Validar comprobante electrónico individual en SUNAT",
    description="Valida un comprobante contra los servicios de SUNAT utilizando la empresa autenticada por JWT."
)
async def validar_comprobante(
    request_data: ComprobanteValidarRequest,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db)
):
    """
    Paso 5 y 6: Aislamiento y validación en SUNAT.
    La empresa se resuelve exclusivamente desde el contexto del usuario autenticado (JWT).
    El usuario CONTADOR únicamente puede validar con la empresa asignada.
    El usuario ADMINISTRADOR requiere tener una empresa asignada o seleccionada.
    """
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada o seleccionada para realizar consultas a SUNAT."
        )

    if not empresa.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"La empresa {empresa.razon_social} (RUC: {empresa.ruc}) se encuentra inactiva."
        )

    try:
        resultado = await sunat_service.validar_comprobante(
            empresa=empresa,
            usuario=current_user,
            request_data=request_data,
            db=db
        )
        return resultado
    except SunatCredentialsError as ce:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ce.message
        )
    except SunatException as se:
        raise HTTPException(
            status_code=se.status_code,
            detail=se.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado al procesar la validación con SUNAT."
        )


@router.get(
    "/consultas",
    response_model=List[ConsultaCPEResponse],
    summary="Listar últimas consultas de comprobantes de la empresa",
    description="Obtiene las consultas recientes realizadas para la empresa activa del usuario."
)
async def listar_consultas_recientes(
    limit: int = 10,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db)
):
    if not empresa:
        return []

    stmt = (
        select(ConsultaCPE)
        .where(ConsultaCPE.empresa_id == empresa.id)
        .order_by(desc(ConsultaCPE.created_at))
        .limit(min(limit, 50))
    )
    result = await db.execute(stmt)
    consultas = result.scalars().all()

    response = []
    for c in consultas:
        tipo_desc = TIPO_COMPROBANTE_MAP.get(c.tipo_comprobante, c.tipo_comprobante)
        response.append(
            ConsultaCPEResponse(
                id=c.id,
                empresa_id=c.empresa_id,
                usuario_id=c.usuario_id,
                ruc_emisor=c.ruc_emisor,
                tipo_comprobante=c.tipo_comprobante,
                tipo_comprobante_descripcion=tipo_desc,
                serie=c.serie,
                numero=c.numero,
                fecha_emision=c.fecha_emision,
                monto=c.monto,
                estado=c.estado,
                codigo_sunat=c.codigo_sunat,
                mensaje_sunat=c.mensaje_sunat,
                empresa_consultora=EmpresaInfo(
                    ruc=empresa.ruc,
                    razon_social=empresa.razon_social
                ),
                created_at=c.created_at
            )
        )
    return response


@router.post(
    "/validar-masivo",
    response_model=ProcesoMasivoResponse,
    summary="Validar conjunto masivo de comprobantes en SUNAT",
    description="Valida un lote dinámico de comprobantes aplicando el límite de seguridad MAX_MASSIVE_ITEMS."
)
async def validar_comprobantes_masivo_sunat(
    request_data: CrearProcesoMasivoRequest,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db)
) -> ProcesoMasivoResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada o seleccionada para realizar consultas a SUNAT."
        )

    if not empresa.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"La empresa {empresa.razon_social} (RUC: {empresa.ruc}) se encuentra inactiva."
        )

    try:
        proceso, fue_creado = await proceso_masivo_service.crear_proceso(
            db=db,
            empresa=empresa,
            usuario=current_user,
            request=request_data,
        )

        if fue_creado and proceso.estado == "PENDIENTE":
            proceso_masivo_service.iniciar_worker_asincrono(
                proceso_id=proceso.id,
                empresa_id=empresa.id,
                usuario_id=current_user.id,
            )

        return ProcesoMasivoResponse(
            id=proceso.id,
            empresa_id=proceso.empresa_id,
            usuario_id=proceso.usuario_id,
            nombre_archivo=proceso.nombre_archivo,
            idempotency_key=proceso.idempotency_key,
            estado=proceso.estado,
            total_registros=proceso.total_registros,
            total_procesados=proceso.total_procesados,
            porcentaje=float(proceso.porcentaje),
            total_validos=proceso.total_validos,
            total_no_validos=proceso.total_no_validos,
            total_observados=proceso.total_observados,
            total_errores=proceso.total_errores,
            mensaje_error=proceso.mensaje_error,
            started_at=proceso.started_at,
            finished_at=proceso.finished_at,
            created_at=proceso.created_at,
            updated_at=proceso.updated_at,
        )
    except ProcesoMasivoException as pe:
        raise HTTPException(
            status_code=pe.status_code,
            detail=pe.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al validar lote de comprobantes: {str(e)}"
        )
