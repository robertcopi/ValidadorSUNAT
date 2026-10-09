from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ItemProcesoMasivo(BaseModel):
    """Representa un comprobante individual que forma parte del proceso masivo."""
    fila_excel: Optional[int] = None
    num_ruc: str = Field(..., min_length=11, max_length=11, description="RUC del emisor (11 dígitos)")
    cod_comp: str = Field(..., min_length=2, max_length=2, description="Código de comprobante SUNAT (01, 03, 07, 08, 14)")
    numero_serie: str = Field(..., max_length=10, description="Serie del comprobante")
    numero: str = Field(..., max_length=20, description="Número correlativo del comprobante")
    fecha_emision: str = Field(..., description="Fecha de emisión en formato DD/MM/YYYY")
    monto_original: Optional[Decimal] = Field(None, description="Monto contable original (conserva signo ej. notas de crédito)")
    monto: Decimal = Field(..., ge=0, description="Monto en valor absoluto positivo para SUNAT (abs(monto_base_igv))")
    razon_social: Optional[str] = None
    base_imponible: Optional[Decimal] = None
    igv: Optional[Decimal] = None
    monto_base_igv: Optional[Decimal] = None
    valor_adquisiciones_no_gravadas: Optional[Decimal] = None
    monto_calculado_original: Optional[Decimal] = None
    tipo_cambio: Optional[Decimal] = None
    monto_convertido: Optional[Decimal] = None
    importe_total_excel: Optional[Decimal] = None
    otros_tributos: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class CrearProcesoMasivoRequest(BaseModel):
    """Solicitud para crear e iniciar la validación masiva con N items seleccionados."""
    nombre_archivo: Optional[str] = None
    idempotency_key: Optional[str] = None
    items: List[ItemProcesoMasivo] = Field(..., description="Lista dinámica de comprobantes seleccionados")

    model_config = ConfigDict(from_attributes=True)


class ProcesoMasivoItemResponse(BaseModel):
    """Detalle persistido de un comprobante dentro del proceso masivo."""
    id: int
    proceso_id: str
    fila_excel: Optional[int] = None
    num_ruc: str
    cod_comp: str
    numero_serie: str
    numero: str
    fecha_emision: str
    monto_original: Optional[Decimal] = None
    monto: Decimal
    razon_social: Optional[str] = None
    tipo_cambio: Optional[Decimal] = None
    monto_convertido: Optional[Decimal] = None
    estado: str  # PENDIENTE | PROCESANDO | VALIDO | NO_VALIDO | OBSERVADO | ERROR
    estado_sunat: Optional[str] = None
    codigo_sunat: Optional[str] = None
    mensaje_sunat: Optional[str] = None
    intentos: int = 0
    consulta_cpe_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProcesoMasivoResponse(BaseModel):
    """Resumen y estado completo del proceso masivo persistido en PostgreSQL."""
    id: str
    empresa_id: Optional[int] = None
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    nombre_archivo: Optional[str] = None
    idempotency_key: Optional[str] = None
    estado: str = "PENDIENTE"  # PENDIENTE | PROCESANDO | COMPLETADO | COMPLETADO_CON_ERRORES | ERROR
    total_registros: int = Field(..., description="Cantidad real de comprobantes seleccionados para el proceso")
    total_procesados: int = 0
    porcentaje: float = 0.0
    total_validos: int = 0
    total_no_validos: int = 0
    total_observados: int = 0
    total_errores: int = 0
    mensaje_error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Opcional para respuestas completas con resultados
    items: Optional[List[ProcesoMasivoItemResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedProcesoMasivoItemsResponse(BaseModel):
    """Respuesta paginada para la consulta de items de un proceso masivo."""
    items: List[ProcesoMasivoItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedProcesosMasivosResponse(BaseModel):
    """Respuesta paginada para el listado de procesos masivos de la empresa."""
    items: List[ProcesoMasivoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class ReintentarErroresResponse(BaseModel):
    """Respuesta tras solicitar el reintento de items con error técnico."""
    proceso_id: str
    total_reintentados: int
    mensaje: str
    estado: str

    model_config = ConfigDict(from_attributes=True)


class EliminarProcesoMasivoResponse(BaseModel):
    """Respuesta tras eliminar exitosamente un proceso masivo y sus registros asociados."""
    success: bool = True
    mensaje: str = "Lote eliminado correctamente."
    proceso_id: str
    nombre_archivo: Optional[str] = None
    items_eliminados: int = 0
    consultas_cpe_eliminadas: int = 0

    model_config = ConfigDict(from_attributes=True)

