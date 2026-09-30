from typing import List, TYPE_CHECKING
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.usuario import Usuario
    from app.models.consulta_cpe import ConsultaCPE


class Empresa(Base, TimestampMixin):
    """Modelo ORM para empresas soportadas en el sistema multiempresa."""
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    ruc: Mapped[str] = mapped_column(String(11), unique=True, index=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relación uno a muchos con usuarios
    usuarios: Mapped[List["Usuario"]] = relationship(
        "Usuario",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Relación uno a muchos con consultas SUNAT
    consultas_cpe: Mapped[List["ConsultaCPE"]] = relationship(
        "ConsultaCPE",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Empresa id={self.id} ruc={self.ruc} razon_social={self.razon_social}>"
