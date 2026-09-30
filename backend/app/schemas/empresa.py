from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EmpresaBase(BaseModel):
    ruc: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    razon_social: str = Field(..., min_length=2, max_length=255)
    activo: bool = True


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    razon_social: Optional[str] = Field(None, min_length=2, max_length=255)


class EmpresaEstadoUpdate(BaseModel):
    activo: bool


class EmpresaSunatStatusResponse(BaseModel):
    configurado: bool
    client_id_configurado: bool
    client_secret_configurado: bool


class EmpresaResponse(EmpresaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    total_usuarios: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
