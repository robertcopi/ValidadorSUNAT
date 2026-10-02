from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.empresa import EmpresaResponse


class UsuarioBase(BaseModel):
    email: str = Field(..., min_length=3, max_length=150)
    nombre_completo: str = Field(..., min_length=2, max_length=150)
    rol: str = Field(..., pattern=r"^(ADMINISTRADOR|CONTADOR)$")
    empresa_id: Optional[int] = None
    activo: bool = True


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=6, max_length=100)

    @model_validator(mode="after")
    def validate_empresa_for_contador(self) -> "UsuarioCreate":
        if self.rol == "CONTADOR" and not self.empresa_id:
            raise ValueError("Un usuario con rol CONTADOR debe pertenecer obligatoriamente a una empresa.")
        return self


class UsuarioUpdate(BaseModel):
    email: Optional[str] = Field(None, min_length=3, max_length=150)
    nombre_completo: Optional[str] = Field(None, min_length=2, max_length=150)
    empresa_id: Optional[int] = None
    rol: Optional[str] = Field(None, pattern=r"^(ADMINISTRADOR|CONTADOR)$")


class UsuarioEstadoUpdate(BaseModel):
    activo: bool


class UsuarioResetPasswordRequest(BaseModel):
    temporary_password: Optional[str] = Field(None, min_length=6, max_length=100)


class UsuarioResponse(BaseModel):
    id: int
    email: str
    nombre_completo: str
    rol: str
    empresa_id: Optional[int] = None
    activo: bool
    must_change_password: bool = False
    created_at: datetime
    updated_at: datetime
    empresa: Optional[EmpresaResponse] = None

    model_config = ConfigDict(from_attributes=True)
