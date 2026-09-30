from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, Index, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.usuario import Usuario
    from app.models.proceso_masivo_item import ProcesoMasivoItem


class ProcesoMasivo(Base, TimestampMixin):
    """
    Modelo ORM para persistencia y auditoría de procesos de validación masiva.
    Almacena el estado global del lote, contadores dinámicos y seguimiento de ejecución.
    """
    __tablename__ = "procesos_masivos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    empresa_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    nombre_archivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Estados del proceso: PENDIENTE, PROCESANDO, COMPLETADO, COMPLETADO_CON_ERRORES, ERROR
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDIENTE", index=True)
    
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_procesados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_validos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_no_validos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_observados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_errores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    mensaje_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relaciones ORM
    empresa: Mapped["Empresa"] = relationship("Empresa", lazy="selectin")
    usuario: Mapped["Usuario"] = relationship("Usuario", lazy="selectin")
    items: Mapped[List["ProcesoMasivoItem"]] = relationship(
        "ProcesoMasivoItem",
        back_populates="proceso",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProcesoMasivoItem.id"
    )

    __table_args__ = (
        Index("idx_procesos_masivos_empresa_created", "empresa_id", "created_at"),
        Index("idx_procesos_masivos_idempotency", "empresa_id", "idempotency_key"),
        Index("idx_procesos_masivos_estado", "estado"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProcesoMasivo id={self.id} empresa_id={self.empresa_id} "
            f"estado={self.estado} procesados={self.total_procesados}/{self.total_registros}>"
        )
