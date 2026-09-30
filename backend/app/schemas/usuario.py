from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.security import normalize_username, validate_username
from app.schemas.empresa import EmpresaResponse


class UsuarioBase(BaseModel):
    email: str = Field(..., min_length=3, max_length=150)
    nombre_completo: str = Field(..., min_length=2, max_length=150)
    rol: str = Field(..., pattern=r"^(ADMINISTRADOR|CONTADOR)$")
    empresa_id: Optional[int] = None
    activo: bool = True


class UsuarioCreate(UsuarioBase):
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)

    @field_validator("username", mode="before")
    @classmethod
    def clean_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return normalize_username(v)
        return v

    @model_validator(mode="after")
    def validate_user_fields(self) -> "UsuarioCreate":
        if self.rol == "CONTADOR" and not self.empresa_id:
            raise ValueError("Un usuario con rol CONTADOR debe pertenecer obligatoriamente a una empresa.")
        if not self.username and self.email:
            self.username = normalize_username(self.email.split("@")[0])
        if self.username:
            self.username = validate_username(self.username)
        return self


class UsuarioUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = Field(None, min_length=3, max_length=150)
    nombre_completo: Optional[str] = Field(None, min_length=2, max_length=150)
    empresa_id: Optional[int] = None
    rol: Optional[str] = Field(None, pattern=r"^(ADMINISTRADOR|CONTADOR)$")

    @field_validator("username", mode="before")
    @classmethod
    def clean_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_username(v)
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
