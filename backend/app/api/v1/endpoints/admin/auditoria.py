import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_role, get_db
from app.models.auditoria_evento import AuditoriaEvento
from app.schemas.auditoria import AuditoriaEventoResponse, AuditoriaPaginadaResponse

router = APIRouter(dependencies=[Depends(require_role(["ADMINISTRADOR"]))])


@router.get("", response_model=AuditoriaPaginadaResponse)
async def list_auditoria(
    usuario_id: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
    empresa_id: Optional[int] = Query(None, description="Filtrar por ID de empresa"),
    accion: Optional[str] = Query(None, description="Filtrar por tipo de acción"),
    fecha_desde: Optional[datetime] = Query(None, description="Fecha de inicio (ISO 8601)"),
    fecha_hasta: Optional[datetime] = Query(None, description="Fecha de fin (ISO 8601)"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Cantidad de registros por página"),
    db: AsyncSession = Depends(get_db)
):
    """
    Visor de auditoría inmutable de eventos del sistema.
    Acceso exclusivo para el Administrador.
    Ordenado estrictamente del más reciente al más antiguo.
    """
    base_query = select(AuditoriaEvento)

    if usuario_id is not None:
        base_query = base_query.where(AuditoriaEvento.usuario_id == usuario_id)
    if empresa_id is not None:
        base_query = base_query.where(AuditoriaEvento.empresa_id == empresa_id)
    if accion:
        base_query = base_query.where(AuditoriaEvento.accion == accion.upper())
    if fecha_desde is not None:
        base_query = base_query.where(AuditoriaEvento.created_at >= fecha_desde)
    if fecha_hasta is not None:
        base_query = base_query.where(AuditoriaEvento.created_at <= fecha_hasta)

    # Contar total de registros
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    # Paginación
    offset = (page - 1) * page_size
    query = base_query.order_by(AuditoriaEvento.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    eventos = result.scalars().all()

    items = []
    for ev in eventos:
        item = AuditoriaEventoResponse(
            id=ev.id,
            usuario_id=ev.usuario_id,
            usuario_nombre=ev.usuario.nombre_completo if ev.usuario else None,
            usuario_email=ev.usuario.email if ev.usuario else None,
            empresa_id=ev.empresa_id,
            empresa_razon_social=ev.empresa.razon_social if ev.empresa else None,
            accion=ev.accion,
            entidad=ev.entidad,
            entidad_id=ev.entidad_id,
            detalle=ev.detalle,
            ip=ev.ip,
            created_at=ev.created_at
        )
        items.append(item)

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return AuditoriaPaginadaResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items
    )
