from typing import Optional, Any, Dict, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, DateTime, JSON, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario
    from app.models.empresa import Empresa


class AuditoriaEvento(Base):
    """Modelo ORM para registro de auditoría de acciones del sistema."""
    __tablename__ = "auditoria_eventos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    
    usuario_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    empresa_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("empresas.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    accion: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entidad: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entidad_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    detalle: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Relaciones para joins y consultas de auditoría
    usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[usuario_id],
        lazy="selectin"
    )
    
    empresa: Mapped[Optional["Empresa"]] = relationship(
        "Empresa",
        foreign_keys=[empresa_id],
        lazy="selectin"
    )

    __table_args__ = (
        Index("idx_auditoria_empresa_accion", "empresa_id", "accion"),
        Index("idx_auditoria_created_at_desc", created_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<AuditoriaEvento id={self.id} accion={self.accion} entidad={self.entidad} usuario_id={self.usuario_id}>"
