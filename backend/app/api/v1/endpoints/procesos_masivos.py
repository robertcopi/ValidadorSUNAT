from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import export_rate_limiter
from app.api.deps import get_current_user, get_current_empresa, require_role
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.proceso_masivo import (
    CrearProcesoMasivoRequest,
    ProcesoMasivoResponse,
    PaginatedProcesoMasivoItemsResponse,
    PaginatedProcesosMasivosResponse,
    ReintentarErroresResponse,
)
from app.services.proceso_masivo_service import (
    proceso_masivo_service,
    ProcesoMasivoException,
)
from app.services.audit_service import audit_service

router = APIRouter()


@router.post(
    "",
    response_model=ProcesoMasivoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear e iniciar un nuevo proceso masivo de validación",
    description="""
    Registra el proceso y sus comprobantes individualmente en PostgreSQL y responde de inmediato.
    El procesamiento de consultas contra SUNAT se ejecuta en segundo plano (asíncrono).
    Soporta Idempotency-Key para evitar duplicidad de lotes ante doble clic.
    """
)
async def crear_proceso_masivo(
    request: Request,
    request_data: CrearProcesoMasivoRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> ProcesoMasivoResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada o seleccionada para crear procesos masivos."
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
            idempotency_key=idempotency_key,
        )

        if not fue_creado:
            response.status_code = status.HTTP_200_OK

        # Si fue creado nuevo y está PENDIENTE, lanzar worker en segundo plano
        if fue_creado and proceso.estado == "PENDIENTE":
            client_ip = request.client.host if request.client else None
            await audit_service.registrar_evento(
                db=db,
                accion="PROCESO_MASIVO_CREADO",
                entidad="proceso_masivo",
                entidad_id=proceso.id,
                usuario_id=current_user.id,
                empresa_id=empresa.id,
                detalle={
                    "nombre_archivo": proceso.nombre_archivo,
                    "total_registros": proceso.total_registros,
                },
                ip=client_ip
            )
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
        raise HTTPException(status_code=pe.status_code, detail=pe.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al crear proceso masivo: {str(e)}"
        )


@router.get(
    "",
    response_model=PaginatedProcesosMasivosResponse,
    summary="Listar procesos masivos de la empresa",
    description="Devuelve el listado paginado de procesos masivos pertenecientes a la empresa autenticada con filtros opcionales."
)
async def listar_procesos_masivos(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(10, ge=1, le=100, description="Tamaño de página"),
    fecha_desde: Optional[date] = Query(None, description="Filtrar por fecha de creación desde"),
    fecha_hasta: Optional[date] = Query(None, description="Filtrar por fecha de creación hasta"),
    nombre_archivo: Optional[str] = Query(None, description="Filtrar por nombre de archivo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado del proceso"),
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> PaginatedProcesosMasivosResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada para listar procesos masivos."
        )

    return await proceso_masivo_service.listar_procesos(
        db=db,
        empresa_id=empresa.id,
        page=page,
        page_size=page_size,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        nombre_archivo=nombre_archivo,
        estado=estado,
    )


@router.get(
    "/{id}",
    response_model=ProcesoMasivoResponse,
    summary="Consultar estado y avance de un proceso masivo",
    description="Permite al frontend consultar el progreso y contadores dinámicos del proceso en ejecución."
)
async def obtener_proceso_masivo(
    id: str,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> ProcesoMasivoResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada para consultar procesos masivos."
        )

    proceso = await proceso_masivo_service.obtener_proceso(db=db, proceso_id=id, empresa_id=empresa.id)
    if not proceso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el proceso masivo con ID '{id}' para su empresa."
        )
    return proceso


@router.get(
    "/{id}/items",
    response_model=PaginatedProcesoMasivoItemsResponse,
    summary="Listar items paginados y filtrables de un proceso masivo",
    description="Devuelve los comprobantes individuales del proceso con soporte de paginación y búsqueda."
)
async def listar_items_de_proceso(
    id: str,
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=200, description="Tamaño de página"),
    estado: Optional[str] = Query(None, description="Filtrar por estado interno: VALIDO, NO_VALIDO, OBSERVADO, ERROR, PENDIENTE"),
    estado_sunat: Optional[str] = Query(None, description="Filtrar por estado o código SUNAT"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por RUC, serie, número o razón social"),
    ruc: Optional[str] = Query(None, description="Filtrar por RUC"),
    serie: Optional[str] = Query(None, description="Filtrar por serie"),
    numero: Optional[str] = Query(None, description="Filtrar por número correlativo"),
    razon_social: Optional[str] = Query(None, description="Filtrar por razón social del emisor"),
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> PaginatedProcesoMasivoItemsResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada para consultar items."
        )

    try:
        return await proceso_masivo_service.listar_items_proceso(
            db=db,
            proceso_id=id,
            empresa_id=empresa.id,
            page=page,
            page_size=page_size,
            estado=estado,
            estado_sunat=estado_sunat,
            busqueda=busqueda,
            ruc=ruc,
            serie=serie,
            numero=numero,
            razon_social=razon_social,
        )
    except ProcesoMasivoException as pe:
        raise HTTPException(status_code=pe.status_code, detail=pe.message)


@router.post(
    "/{id}/reintentar-errores",
    response_model=ReintentarErroresResponse,
    summary="Reintentar comprobantes que fallaron por error técnico",
    description="Reinicia el procesamiento en segundo plano únicamente para los comprobantes en estado ERROR."
)
async def reintentar_errores_proceso(
    id: str,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> ReintentarErroresResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada para reintentar errores."
        )

    try:
        resultado = await proceso_masivo_service.reintentar_errores(
            db=db,
            proceso_id=id,
            empresa=empresa,
            usuario=current_user,
        )
        await audit_service.registrar_evento(
            db=db,
            accion="REINTENTO_PROCESO",
            entidad="proceso_masivo",
            entidad_id=id,
            usuario_id=current_user.id,
            empresa_id=empresa.id,
            detalle={"items_reintentados": resultado.total_reintentados},
        )
        return resultado
    except ProcesoMasivoException as pe:
        raise HTTPException(status_code=pe.status_code, detail=pe.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al reintentar errores: {str(e)}"
        )


@router.get(
    "/{id}/exportar",
    summary="Exportar resultados del proceso masivo a Excel (.xlsx)",
    description="Genera y descarga un archivo Excel con los datos originales y resultados oficiales de SUNAT.",
    response_class=Response,
)
async def exportar_proceso_excel(
    id: str,
    request: Request,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
):
    """
    Exportación de resultados a Excel:
    - Preserva monto_original y monto
    - Aplica protección contra Excel Formula Injection
    - Aislamiento estricto por empresa (404 si es de otra empresa)
    - 0 consultas a SUNAT (lee datos ya persistidos en PostgreSQL)
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{current_user.id}"
    if export_rate_limiter.is_rate_limited(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Ha excedido el límite de exportaciones permitidas por minuto. Por favor espere."
        )

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada para exportar procesos."
        )

    try:
        excel_bytes, filename = await proceso_masivo_service.exportar_proceso_excel(
            db=db,
            proceso_id=id,
            empresa_id=empresa.id,
        )
        await audit_service.registrar_evento(
            db=db,
            accion="EXPORTACION_EXCEL",
            entidad="proceso_masivo",
            entidad_id=id,
            usuario_id=current_user.id,
            empresa_id=empresa.id,
            detalle={"archivo": filename},
        )
        return Response(
            content=excel_bytes.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except ProcesoMasivoException as pe:
        raise HTTPException(status_code=pe.status_code, detail=pe.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al exportar proceso a Excel: {str(e)}"
        )

