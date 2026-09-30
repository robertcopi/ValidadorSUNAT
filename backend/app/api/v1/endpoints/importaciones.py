from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_empresa, require_role
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.importacion import ImportacionPreviewResponse
from app.schemas.proceso_masivo import CrearProcesoMasivoRequest, ProcesoMasivoResponse
from app.services.excel_parser_service import ExcelParserService, ExcelParserException
from app.services.proceso_masivo_service import proceso_masivo_service, ProcesoMasivoException

router = APIRouter()


@router.post(
    "/preview",
    response_model=ImportacionPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Previsualización y validación local de Registro de Compras Excel",
    description="""
    Analiza un archivo Excel (.xlsx) correspondiente al Formato 8.1 Registro de Compras.
    Realiza detección dinámica de encabezados, normalización contable, detección de duplicados
    y clasificación preliminar (LISTO, ERROR, DUPLICADO, NO_SOPORTADO).

    NO realiza consultas ni peticiones a la API de SUNAT.
    """
)
async def preview_importacion_excel(
    archivo: UploadFile = File(..., description="Archivo Excel (.xlsx) del Registro de Compras"),
    current_user: Usuario = Depends(get_current_user),
    empresa_actual: Empresa = Depends(get_current_empresa),
) -> ImportacionPreviewResponse:
    """
    Endpoint para carga y previsualización de comprobantes desde Excel.
    """
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe tener extensión .xlsx (formato Excel moderno).",
        )

    try:
        contenido = await archivo.read()
        resultado = ExcelParserService.parse_excel(
            file_bytes=contenido,
            filename=archivo.filename,
        )
        return resultado
    except ExcelParserException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al procesar el archivo Excel: {str(e)}",
        )


@router.post(
    "/validar-masivo",
    response_model=ProcesoMasivoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear e iniciar validación masiva de comprobantes en SUNAT",
    description="""
    Inicia la validación asíncrona en segundo plano para un conjunto dinámico de N comprobantes seleccionados.
    Persiste el proceso y los comprobantes en PostgreSQL y responde de inmediato con el ID del proceso.
    """
)
async def validar_comprobantes_masivo(
    request_data: CrearProcesoMasivoRequest,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> ProcesoMasivoResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada o seleccionada para realizar consultas masivas a SUNAT."
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
            detail=pe.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado durante la validación masiva: {str(e)}",
        )


@router.get(
    "/proceso-masivo/{proceso_id}",
    response_model=ProcesoMasivoResponse,
    summary="Consultar estado de un proceso masivo",
    description="Permite consultar el estado actual, avance porcentual y resultados de un proceso masivo por su ID."
)
async def obtener_estado_proceso_masivo(
    proceso_id: str,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> ProcesoMasivoResponse:
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe tener una empresa asociada para consultar procesos masivos."
        )

    proceso = await proceso_masivo_service.obtener_proceso(db=db, proceso_id=proceso_id, empresa_id=empresa.id)
    if not proceso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el proceso masivo con ID '{proceso_id}'.",
        )
    return proceso
