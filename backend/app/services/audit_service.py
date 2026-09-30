import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.auditoria_evento import AuditoriaEvento

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "password", "password_hash", "new_password", "confirm_password",
    "current_password", "temporary_password", "client_secret",
    "access_token", "token", "authorization", "secret", "jwt",
    "clave_sol", "sol_password", "sol_user"
}


def sanitize_audit_detail(data: Any) -> Any:
    """Elimina recursivamente cualquier clave o dato sensible antes de guardar en auditoría."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                cleaned[k] = sanitize_audit_detail(v)
            else:
                cleaned[k] = v
        return cleaned
    elif isinstance(data, list):
        return [sanitize_audit_detail(item) for item in data]
    return data


class AuditService:
    """Servicio para registrar eventos de auditoría inmutables en la base de datos."""

    async def registrar_evento(
        self,
        db: AsyncSession,
        accion: str,
        entidad: str,
        entidad_id: Optional[str] = None,
        usuario_id: Optional[int] = None,
        empresa_id: Optional[int] = None,
        detalle: Optional[Dict[str, Any]] = None,
        ip: Optional[str] = None,
        commit: bool = True,
    ) -> Optional[AuditoriaEvento]:
        """
        Registra un evento de auditoría sanitizado.
        Garantiza que nunca se almacenen contraseñas, tokens ni credenciales.
        """
        try:
            sanitized = sanitize_audit_detail(detalle) if detalle else None
            evento = AuditoriaEvento(
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                accion=accion,
                entidad=entidad,
                entidad_id=str(entidad_id) if entidad_id is not None else None,
                detalle=sanitized,
                ip=ip,
            )
            db.add(evento)
            if commit:
                await db.commit()
                await db.refresh(evento)
            return evento
        except Exception as e:
            logger.error("Error al registrar evento de auditoría '%s': %s", accion, str(e))
            return None


audit_service = AuditService()
