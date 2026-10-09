from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from app.schemas.empresa import EmpresaResponse


class UsuarioBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario único para acceso")
    email: str = Field(..., min_length=3, max_length=150)
    nombre_completo: str = Field(..., min_length=2, max_length=150)
    rol: str = Field(..., pattern=r"^(ADMINISTRADOR|CONTADOR)$")
    empresa_id: Optional[int] = None
    activo: bool = True

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        clean = v.strip().lower()
        if len(clean) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
        return clean

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean:
            raise ValueError("El correo electrónico debe ser válido.")
        return clean


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=6, max_length=100)

    @model_validator(mode="after")
    def validate_empresa_for_contador(self) -> "UsuarioCreate":
        if self.rol == "CONTADOR" and not self.empresa_id:
            raise ValueError("Un usuario con rol CONTADOR debe pertenecer obligatoriamente a una empresa.")
        return self


class UsuarioUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, min_length=3, max_length=150)
    nombre_completo: Optional[str] = Field(None, min_length=2, max_length=150)
    empresa_id: Optional[int] = None
    rol: Optional[str] = Field(None, pattern=r"^(ADMINISTRADOR|CONTADOR)$")

    @field_validator("username")
    @classmethod
    def normalize_username_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if len(clean) < 3:
                raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
            return clean
        return v

    @field_validator("email")
    @classmethod
    def normalize_email_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if "@" not in clean:
                raise ValueError("El correo electrónico debe ser válido.")
            return clean
        return v


class UsuarioEstadoUpdate(BaseModel):
    activo: bool


class UsuarioResetPasswordRequest(BaseModel):
    temporary_password: Optional[str] = Field(None, min_length=6, max_length=100)


class UsuarioResponse(BaseModel):
    id: int
    username: str
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

