from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_empresa, require_role
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.consulta_cpe import ConsultaCPE
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.schemas.sunat import (
    ComprobanteValidarRequest,
    ConsultaCPEResponse,
    EliminarConsultaCPEResponse,
    EmpresaInfo,
    TIPO_COMPROBANTE_MAP
)
from app.schemas.proceso_masivo import CrearProcesoMasivoRequest, ProcesoMasivoResponse
from app.services.sunat_service import sunat_service, SunatException, SunatCredentialsError
from app.services.proceso_masivo_service import proceso_masivo_service, ProcesoMasivoException
from app.services.audit_service import audit_service

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
    if current_user.rol == "CONTADOR":
        if not empresa:
            return []
        stmt = (
            select(ConsultaCPE)
            .where(ConsultaCPE.empresa_id == empresa.id)
            .order_by(desc(ConsultaCPE.created_at))
            .limit(min(limit, 50))
        )
    else:
        # Administrador: si seleccionó empresa filtra por esa, si no consolida todas
        stmt = select(ConsultaCPE)
        if empresa:
            stmt = stmt.where(ConsultaCPE.empresa_id == empresa.id)
        stmt = stmt.order_by(desc(ConsultaCPE.created_at)).limit(min(limit, 50))

    result = await db.execute(stmt)
    consultas = result.scalars().all()

    response = []
    for c in consultas:
        tipo_desc = TIPO_COMPROBANTE_MAP.get(c.tipo_comprobante, c.tipo_comprobante)
        emp_ruc = c.empresa.ruc if c.empresa else (empresa.ruc if empresa else "-")
        emp_razon = c.empresa.razon_social if c.empresa else (empresa.razon_social if empresa else "General")
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
                    ruc=emp_ruc,
                    razon_social=emp_razon
                ),
                created_at=c.created_at
            )
        )
    return response


@router.delete(
    "/consultas/{consulta_id}",
    response_model=EliminarConsultaCPEResponse,
    summary="Eliminar consulta individual de comprobante",
    description="""
    Elimina permanentemente una consulta individual específica de consultas_cpe.
    - Valida pertenencia multiempresa de forma estricta mediante el JWT o contexto administrativo.
    - Impide eliminar consultas vinculadas a procesos masivos (HTTP 409).
    - Si no existe o pertenece a otra empresa, responde HTTP 404 (evita enumeración de IDs).
    - Registra auditoría inmutable en auditoria_eventos con acción ELIMINAR_CONSULTA_INDIVIDUAL.
    - CERO llamadas HTTP a SUNAT.
    """
)
async def eliminar_consulta_individual(
    consulta_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> EliminarConsultaCPEResponse:
    # 1. Buscar la consulta por ID
    stmt = select(ConsultaCPE).where(ConsultaCPE.id == consulta_id)
    result = await db.execute(stmt)
    consulta = result.scalar_one_or_none()

    if not consulta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la consulta de comprobante solicitada."
        )

    # 2. Validación multiempresa estricta
    if current_user.rol == "CONTADOR":
        if not empresa or consulta.empresa_id != empresa.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró la consulta de comprobante solicitada."
            )
    else:
        # ADMINISTRADOR: si seleccionó un contexto de empresa (X-Empresa-Id o empresa asignada)
        if empresa and consulta.empresa_id != empresa.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró la consulta de comprobante solicitada."
            )

    # 3. Validar que NO esté vinculada a un proceso masivo
    stmt_masivo = select(ProcesoMasivoItem.id).where(ProcesoMasivoItem.consulta_cpe_id == consulta_id).limit(1)
    res_masivo = await db.execute(stmt_masivo)
    if res_masivo.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta consulta pertenece a un lote masivo y no puede eliminarse individualmente."
        )

    try:
        # 4. Registrar auditoría inmutable
        await audit_service.registrar_evento(
            db=db,
            accion="ELIMINAR_CONSULTA_INDIVIDUAL",
            entidad="consultas_cpe",
            entidad_id=str(consulta.id),
            usuario_id=current_user.id,
            empresa_id=consulta.empresa_id,
            detalle={
                "consulta_id": consulta.id,
                "usuario_email": current_user.email,
                "empresa_id": consulta.empresa_id,
                "tipo_comprobante": consulta.tipo_comprobante,
                "serie": consulta.serie,
                "numero": consulta.numero,
                "ruc_emisor": consulta.ruc_emisor,
                "fecha_emision": consulta.fecha_emision.isoformat() if consulta.fecha_emision else None,
                "monto": str(consulta.monto) if consulta.monto is not None else None,
                "estado": consulta.estado,
            },
            ip=request.client.host if request.client else None,
            commit=False,
        )

        # 5. Eliminar registro de consultas_cpe
        await db.delete(consulta)

        # 6. Commit transaccional atómico
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al eliminar la consulta de comprobante: {str(e)}"
        )

    return EliminarConsultaCPEResponse(message="Consulta eliminada correctamente")



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
