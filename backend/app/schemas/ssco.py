from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SSCOConsultaResponse(BaseModel):
    """Respuesta a la verificación de un RUC en el padrón SSCO."""
    ruc: str = Field(..., description="RUC del contribuyente consultado (11 dígitos)")
    estado: str = Field(..., description="ENCONTRADO_SSCO, NO_ENCONTRADO o NO_VERIFICADO")
    es_ssco: bool = Field(..., description="Indica si el RUC figura con resolución firme en el padrón")
    mensaje: str = Field(..., description="Mensaje explicativo del resultado")
    razon_social: Optional[str] = Field(None, description="Razón social o denominación del sujeto")
    domicilio_fiscal: Optional[str] = Field(None, description="Domicilio fiscal registrado en SUNAT")
    resolucion_atribucion: Optional[str] = Field(None, description="Resolución de atribución firme de SSCO")
    fecha_emision_resolucion: Optional[str] = Field(None, description="Fecha de emisión de la resolución")
    fecha_firmeza: Optional[str] = Field(None, description="Fecha en que la resolución quedó firme")
    doc_representante: Optional[str] = Field(None, description="Documento de identidad del representante legal")
    nombre_representante: Optional[str] = Field(None, description="Apellidos y nombres del representante legal")
    fecha_publicacion: Optional[str] = Field(None, description="Fecha de publicación oficial")
    fecha_padron: Optional[str] = Field(None, description="Fecha de corte o vigencia del padrón consultado")


class SSCOEstadoResponse(BaseModel):
    """Estado y métricas actuales del padrón SSCO en la base de datos."""
    padron_disponible: bool = Field(..., description="Indica si existe un padrón cargado para consultas")
    total_registros: int = Field(..., description="Cantidad de RUCs registrados en el padrón local")
    ultima_sincronizacion_exitosa: Optional[datetime] = Field(None, description="Timestamp de la última sincronización")
    fecha_padron_sunat: Optional[str] = Field(None, description="Fecha oficial de corte informada por SUNAT")
    origen: Optional[str] = Field(None, description="Origen de la última sincronización (AUTO_DESCARGA o MANUAL_EXCEL)")
    estado: Optional[str] = Field(None, description="Estado de la última sincronización")


class SSCOSyncResponse(BaseModel):
    """Respuesta de la operación de sincronización o carga del padrón SSCO."""
    mensaje: str = Field(..., description="Detalle del resultado de la sincronización")
    total_registros: int = Field(..., description="Total de registros importados exitosamente")
    fecha_padron_sunat: Optional[str] = Field(None, description="Fecha oficial de corte de SUNAT")
    origen: str = Field(..., description="AUTO_DESCARGA o MANUAL_EXCEL")
    estado: str = Field(..., description="EXITOSO o ERROR")
