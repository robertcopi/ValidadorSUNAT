from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.schemas.usuario import UsuarioResponse


class LoginRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=150, description="Nombre de usuario")
    email: Optional[str] = Field(None, min_length=1, max_length=150, description="Correo electrónico (compatibilidad)")
    password: str = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        if not (self.username and self.username.strip()) and not (self.email and self.email.strip()):
            raise ValueError("Debe ingresar su nombre de usuario o correo electrónico.")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UsuarioResponse


class TokenPayload(BaseModel):
    sub: str
    empresa_id: Optional[int] = None
    rol: str
    exp: Optional[int] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)
    confirm_password: str = Field(..., min_length=6, max_length=100)

    @model_validator(mode="after")
    def validate_passwords(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("La nueva contraseña y su confirmación no coinciden.")
        if self.current_password == self.new_password:
            raise ValueError("La nueva contraseña no puede ser idéntica a la contraseña actual.")
        return self


class ResetPasswordResponse(BaseModel):
    message: str
    temporary_password: str
    must_change_password: bool = True
