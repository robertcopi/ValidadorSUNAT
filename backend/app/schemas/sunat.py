from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Union
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict


TIPO_COMPROBANTE_MAP = {
    "01": "FACTURA",
    "03": "BOLETA DE VENTA",
    "07": "NOTA DE CRÉDITO",
    "08": "NOTA DE DÉBITO",
}


class ComprobanteValidarRequest(BaseModel):
    """Schema para solicitud de validación individual de comprobante electrónico en SUNAT."""
    num_ruc: str = Field(..., description="RUC del emisor del comprobante (11 dígitos)")
    cod_comp: str = Field(..., description="Código de tipo de comprobante SUNAT (01, 03, 07, 08)")
    numero_serie: str = Field(..., description="Serie del comprobante (ej. F006, E001, B001)")
    numero: str = Field(..., description="Número correlativo del comprobante (ej. 0053117 o 53117)")
    fecha_emision: Union[date, str] = Field(..., description="Fecha de emisión en formato DD/MM/YYYY o YYYY-MM-DD")
    monto: Decimal = Field(..., ge=Decimal("0.00"), description="Importe total del comprobante con hasta 2 decimales")

    @field_validator("num_ruc", mode="before")
    @classmethod
    def validate_ruc(cls, v: Any) -> str:
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not re.match(r"^\d{11}$", v):
            raise ValueError("El RUC del emisor debe tener exactamente 11 dígitos numéricos.")
        return v

    @field_validator("cod_comp", mode="before")
    @classmethod
    def validate_tipo_comp(cls, v: Any) -> str:
        if not isinstance(v, str):
            v = str(v)
        v = v.strip().zfill(2)
        if v not in TIPO_COMPROBANTE_MAP:
            valid_codes = ", ".join([f"{k} ({desc})" for k, desc in TIPO_COMPROBANTE_MAP.items()])
            raise ValueError(f"Tipo de comprobante inválido ({v}). Códigos soportados: {valid_codes}")
        return v

    @field_validator("numero_serie", mode="before")
    @classmethod
    def validate_serie(cls, v: Any) -> str:
        if not isinstance(v, str):
            v = str(v)
        v = v.strip().upper()
        if not v:
            raise ValueError("La serie del comprobante es requerida.")
        if len(v) > 10:
            raise ValueError("La serie del comprobante no puede superar 10 caracteres.")
        return v

    @field_validator("numero", mode="before")
    @classmethod
    def validate_numero(cls, v: Any) -> str:
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not v:
            raise ValueError("El número correlativo es requerido.")
        if len(v) > 20:
            raise ValueError("El número correlativo no puede exceder 20 caracteres.")
        return v

    @field_validator("fecha_emision", mode="before")
    @classmethod
    def validate_fecha(cls, v: Any) -> date:
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            v = v.strip()
            # Probar DD/MM/YYYY
            try:
                dt = datetime.strptime(v, "%d/%m/%Y")
                return dt.date()
            except ValueError:
                pass
            # Probar YYYY-MM-DD
            try:
                dt = datetime.strptime(v, "%Y-%m-%d")
                return dt.date()
            except ValueError:
                pass
        raise ValueError("Fecha de emisión inválida. Debe ser una fecha real en formato DD/MM/YYYY o YYYY-MM-DD.")

    @field_validator("monto", mode="before")
    @classmethod
    def validate_monto(cls, v: Any) -> Decimal:
        try:
            d = Decimal(str(v)).quantize(Decimal("0.01"))
        except Exception:
            raise ValueError("El monto debe ser un valor decimal numérico válido.")
        if d < Decimal("0.00"):
            raise ValueError("El monto no puede ser negativo.")
        return d

    @property
    def fecha_emision_sunat(self) -> str:
        """Formatea la fecha como dd/MM/yyyy para la API de SUNAT."""
        if isinstance(self.fecha_emision, date):
            return self.fecha_emision.strftime("%d/%m/%Y")
        return str(self.fecha_emision)

    @property
    def monto_sunat(self) -> str:
        """Formatea el monto como string con 2 decimales para SUNAT."""
        return f"{self.monto:.2f}"

    model_config = ConfigDict(extra="forbid")


class EmpresaInfo(BaseModel):
    ruc: str
    razon_social: str


class ConsultaCPEResponse(BaseModel):
    id: int
    empresa_id: int
    usuario_id: int
    ruc_emisor: str
    tipo_comprobante: str
    tipo_comprobante_descripcion: str
    serie: str
    numero: str
    fecha_emision: date
    monto: Decimal
    estado: str  # VALIDO, NO_VALIDO, OBSERVADO, ERROR
    codigo_sunat: Optional[str] = None
    mensaje_sunat: Optional[str] = None
    empresa_consultora: EmpresaInfo
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EliminarConsultaCPEResponse(BaseModel):
    """Schema de respuesta para la eliminación de una consulta individual."""
    message: str
