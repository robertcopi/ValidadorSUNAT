from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import require_role, get_current_empresa
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.dashboard import DashboardResumenResponse
from app.services.proceso_masivo_service import proceso_masivo_service

router = APIRouter()


@router.get(
    "/resumen",
    response_model=DashboardResumenResponse,
    summary="Resumen estadístico para el Dashboard del contador",
    description="""
    Calcula dinámicamente en PostgreSQL los totales y porcentajes de comprobantes
    para la empresa autenticada. Soporta filtros opcionales por fecha_desde,
    fecha_hasta, estado y proceso_id.
    """
)
async def obtener_resumen_dashboard(
    fecha_desde: Optional[date] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
    estado: Optional[str] = Query(None, description="Filtrar por estado interno: VALIDO, NO_VALIDO, OBSERVADO, ERROR"),
    proceso_id: Optional[str] = Query(None, description="Filtrar por proceso masivo específico"),
    current_user: Usuario = Depends(require_role(["CONTADOR", "ADMINISTRADOR"])),
    empresa: Optional[Empresa] = Depends(get_current_empresa),
    db: AsyncSession = Depends(get_db),
) -> DashboardResumenResponse:
    if current_user.rol == "CONTADOR":
        if not empresa:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El contador debe tener una empresa asociada para consultar el dashboard."
            )
        target_empresa_id = empresa.id
    else:
        # Rol ADMINISTRADOR: Si seleccionó empresa por cabecera X-Empresa-Id usa esa, si no usa None (Visión Consolidada)
        target_empresa_id = empresa.id if empresa else None

    return await proceso_masivo_service.obtener_resumen_dashboard(
        db=db,
        empresa_id=target_empresa_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado=estado,
        proceso_id=proceso_id,
    )
