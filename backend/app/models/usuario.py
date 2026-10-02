from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.consulta_cpe import ConsultaCPE


class Usuario(Base, TimestampMixin):
    """Modelo ORM para usuarios del sistema (ADMINISTRADOR y CONTADOR)."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    
    # Para el Administrador Global es NULL (alcance global en todo el sistema).
    # Para los Contadores es obligatorio y apunta a su empresa asignada.
    empresa_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="CONTADOR", index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relación inversa con Empresa
    empresa: Mapped[Optional["Empresa"]] = relationship(
        "Empresa",
        back_populates="usuarios",
        lazy="selectin"
    )

    # Relación uno a muchos con consultas SUNAT realizadas por este usuario
    consultas_cpe: Mapped[List["ConsultaCPE"]] = relationship(
        "ConsultaCPE",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("idx_usuarios_empresa_rol", "empresa_id", "rol"),
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email} rol={self.rol} empresa_id={self.empresa_id}>"
