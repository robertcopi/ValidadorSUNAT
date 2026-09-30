from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, Index, Date, Numeric, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.usuario import Usuario


class ConsultaCPE(Base, TimestampMixin):
    """Modelo ORM para auditoría y persistencia de consultas individuales de comprobantes en SUNAT."""
    __tablename__ = "consultas_cpe"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    
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
    
    ruc_emisor: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    tipo_comprobante: Mapped[str] = mapped_column(String(2), nullable=False)
    serie: Mapped[str] = mapped_column(String(10), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Estados consistentes: VALIDO, NO_VALIDO, OBSERVADO, ERROR
    estado: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    codigo_sunat: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mensaje_sunat: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    respuesta_sunat: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relaciones ORM
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="consultas_cpe", lazy="selectin")
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="consultas_cpe", lazy="selectin")

    __table_args__ = (
        Index("idx_consultas_cpe_empresa_created", "empresa_id", "created_at"),
        Index("idx_consultas_cpe_empresa_emisor", "empresa_id", "ruc_emisor"),
        Index("idx_consultas_cpe_emisor_fecha", "ruc_emisor", "fecha_emision"),
    )

    def __repr__(self) -> str:
        return (
            f"<ConsultaCPE id={self.id} empresa_id={self.empresa_id} "
            f"comprobante={self.tipo_comprobante}-{self.serie}-{self.numero} estado={self.estado}>"
        )
