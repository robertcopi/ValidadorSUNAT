from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class AuditoriaEventoResponse(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    usuario_email: Optional[str] = None
    empresa_id: Optional[int] = None
    empresa_razon_social: Optional[str] = None
    accion: str
    entidad: str
    entidad_id: Optional[str] = None
    detalle: Optional[Dict[str, Any]] = None
    ip: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditoriaPaginadaResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[AuditoriaEventoResponse]
