from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, Index, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.proceso_masivo import ProcesoMasivo
    from app.models.consulta_cpe import ConsultaCPE


class ProcesoMasivoItem(Base, TimestampMixin):
    """
    Modelo ORM para persistencia individual de cada comprobante dentro de un proceso masivo.
    Registra el estado de procesamiento, estado SUNAT funcional, reintentos y vinculación
    con la auditoría general de consultas_cpe.
    """
    __tablename__ = "proceso_masivo_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    
    proceso_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("procesos_masivos.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    fila_excel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_ruc: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    cod_comp: Mapped[str] = mapped_column(String(2), nullable=False)
    numero_serie: Mapped[str] = mapped_column(String(10), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    monto_original: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    razon_social: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Estado del item: PENDIENTE, PROCESANDO, VALIDO, NO_VALIDO, OBSERVADO, ERROR
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDIENTE", index=True)
    
    # Detalle devuelto por SUNAT
    estado_sunat: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    codigo_sunat: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mensaje_sunat: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Control de reintentos técnicos
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Vinculación con auditoría global de consultas_cpe
    consulta_cpe_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("consultas_cpe.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relaciones ORM
    proceso: Mapped["ProcesoMasivo"] = relationship("ProcesoMasivo", back_populates="items")
    consulta_cpe: Mapped[Optional["ConsultaCPE"]] = relationship("ConsultaCPE", lazy="selectin")

    __table_args__ = (
        Index("idx_proceso_items_proceso_estado", "proceso_id", "estado"),
        Index("idx_proceso_items_ruc_comp", "num_ruc", "cod_comp", "numero_serie", "numero"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProcesoMasivoItem id={self.id} proceso_id={self.proceso_id} "
            f"cpe={self.cod_comp}-{self.numero_serie}-{self.numero} estado={self.estado}>"
        )
