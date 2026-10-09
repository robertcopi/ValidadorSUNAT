from datetime import date, datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Date, DateTime, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.usuario import Usuario


class PadronSSCO(Base, TimestampMixin):
    """
    Padrón oficial global de Sujetos Sin Capacidad Operativa (SSCO) publicado por SUNAT.
    Este registro es normativo y compartido para todas las empresas del sistema.
    """
    __tablename__ = "padron_ssco"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    ruc: Mapped[str] = mapped_column(String(11), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    domicilio_fiscal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolucion_atribucion: Mapped[str] = mapped_column(String(255), nullable=False)
    fecha_emision_resolucion: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_firmeza: Mapped[date] = mapped_column(Date, nullable=False)
    doc_representante: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nombre_representante: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fecha_publicacion: Mapped[date] = mapped_column(Date, nullable=False)

    def __repr__(self) -> str:
        return f"<PadronSSCO ruc={self.ruc} razon_social={self.razon_social}>"


class PadronSSCOSincronizacion(Base):
    """
    Historial inmutable de sincronizaciones y actualizaciones del padrón SSCO.
    Permite auditar descargas automáticas desde SUNAT o cargas manuales de contingencia.
    """
    __tablename__ = "padron_ssco_sincronizaciones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    origen: Mapped[str] = mapped_column(String(20), nullable=False)  # 'AUTO_DESCARGA' | 'MANUAL_EXCEL'
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_padron_sunat: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False)  # 'EXITOSO' | 'ERROR'
    mensaje: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relación con el usuario que ejecutó la sincronización
    usuario: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="selectin")

    def __repr__(self) -> str:
        return f"<PadronSSCOSincronizacion id={self.id} origen={self.origen} estado={self.estado}>"


class ConsultaSSCO(Base):
    """
    Registro multiempresa de trazabilidad de consultas de RUC individuales en el padrón SSCO.
    Permite a Contabilidad auditar qué proveedores fueron consultados por cada empresa y usuario.
    """
    __tablename__ = "consultas_ssco"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    empresa_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    ruc_consultado: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    es_ssco: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detalle_ssco: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fecha_padron_consultado: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relaciones ORM
    empresa: Mapped[Optional["Empresa"]] = relationship("Empresa", lazy="selectin")
    usuario: Mapped["Usuario"] = relationship("Usuario", lazy="selectin")

    __table_args__ = (
        Index("idx_consultas_ssco_empresa_ruc", "empresa_id", "ruc_consultado"),
        Index("idx_consultas_ssco_empresa_created", "empresa_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ConsultaSSCO id={self.id} ruc={self.ruc_consultado} es_ssco={self.es_ssco}>"
