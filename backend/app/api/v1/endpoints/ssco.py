from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_empresa, require_role
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.ssco import SSCOConsultaResponse, SSCOEstadoResponse, SSCOSyncResponse
from app.services.ssco_service import ssco_service

router = APIRouter()


@router.get(
    "/consultar/{ruc}",
    response_model=SSCOConsultaResponse,
    summary="Verificar RUC en el padrón de Sujetos Sin Capacidad Operativa (SSCO)",
    description="Consulta exclusivamente en el padrón local de PostgreSQL si el RUC del proveedor figura con resolución firme de SSCO."
)
async def consultar_ssco(
    ruc: str,
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint principal para Contabilidad:
    - No consulta servicios externos ni comprobantes CPE.
    - Requiere únicamente el RUC de 11 dígitos.
    - Aísla la trazabilidad según la empresa autenticada o seleccionada.
    """
    return await ssco_service.consultar_ruc(
        ruc=ruc,
        current_user=current_user,
        empresa=empresa,
        db=db
    )


@router.get(
    "/estado",
    response_model=SSCOEstadoResponse,
    summary="Obtener estado actual del padrón SSCO local",
    description="Informa si hay un padrón cargado, el total de RUCs registrados y la fecha oficial de corte informada por SUNAT."
)
async def obtener_estado_ssco(
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    return await ssco_service.obtener_estado(db)


@router.post(
    "/sincronizar",
    response_model=SSCOSyncResponse,
    summary="Sincronizar padrón SSCO desde la fuente oficial de SUNAT",
    description="Descarga el archivo Excel oficial desde el portal web de SUNAT y actualiza el padrón atómicamente. Exclusivo para ADMINISTRADOR."
)
async def sincronizar_ssco_desde_sunat(
    current_user: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    return await ssco_service.sincronizar_desde_sunat(
        current_user=current_user,
        db=db
    )


@router.post(
    "/cargar-excel",
    response_model=SSCOSyncResponse,
    summary="Cargar manualmente archivo Excel oficial del padrón SSCO",
    description="Permite subir el archivo .xlsx oficial descargado previamente como contingencia ante caídas del portal. Exclusivo para ADMINISTRADOR."
)
async def cargar_excel_manual_ssco(
    file: UploadFile = File(..., description="Archivo Excel .xlsx oficial descargado de SUNAT"),
    current_user: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe tener extensión .xlsx correspondiente a un libro de cálculo oficial."
        )

    file_bytes = await file.read()
    return await ssco_service.cargar_excel_manual(
        file_bytes=file_bytes,
        current_user=current_user,
        db=db
    )
