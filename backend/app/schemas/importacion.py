from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class FilaComprobantePreview(BaseModel):
    """Representa el resultado del análisis y normalización de una fila del Registro de Compras."""
    fila_excel: int
    num_ruc: Optional[str] = None
    tipo_doc_identidad: Optional[str] = None
    cod_comp: Optional[str] = None
    tipo_descripcion: str
    numero_serie: Optional[str] = None
    numero: Optional[str] = None
    fecha_emision: Optional[str] = None  # Formateada DD/MM/YYYY para SUNAT
    monto_original: Optional[Decimal] = None  # Importe contable original (puede ser negativo ej. notas de crédito)
    monto: Optional[Decimal] = None  # Importe normalizado positivo para consulta en SUNAT (monto_sunat = abs(monto_base_igv))
    base_imponible: Optional[Decimal] = None  # Base imponible de adquisiciones gravadas
    igv: Optional[Decimal] = None  # IGV de adquisiciones gravadas
    monto_base_igv: Optional[Decimal] = None  # Base imponible + IGV con signo contable
    valor_adquisiciones_no_gravadas: Optional[Decimal] = None  # Valor de las adquisiciones no gravadas
    monto_calculado_original: Optional[Decimal] = None  # monto_base_igv + valor_adquisiciones_no_gravadas con signo contable
    tipo_cambio: Optional[Decimal] = None  # Tipo de cambio original del comprobante (si aplica)
    monto_convertido: Optional[Decimal] = None  # monto_calculado_original / tipo_cambio con signo contable original
    importe_total_excel: Optional[Decimal] = None  # Columna IMPORTE TOTAL del Excel original (para trazabilidad/historial)
    otros_tributos: Optional[Decimal] = None  # Otros tributos y cargos del comprobante
    razon_social_emisor: Optional[str] = None
    estado_archivo: str  # LISTO | ERROR | DUPLICADO | NO_SOPORTADO
    errores: List[str] = []
    es_seleccionable: bool = False

    @property
    def monto_sunat(self) -> Optional[Decimal]:
        """Alias conceptual explícito: monto enviado a la consulta SUNAT."""
        return self.monto

    model_config = ConfigDict(from_attributes=True)


class DiagnosticoImportacion(BaseModel):
    """Información diagnóstica sobre la detección de la estructura del Excel."""
    hoja_detectada: str
    fila_inicio_encabezado: int
    fila_fin_encabezado: int
    columnas_mapeadas: Dict[str, str]

    model_config = ConfigDict(from_attributes=True)


class ImportacionPreviewResponse(BaseModel):
    """Resumen completo devuelto al contador para previsualizar los comprobantes cargados."""
    nombre_archivo: str
    diagnostico: DiagnosticoImportacion
    total_filas_detectadas: int
    total_listos: int
    total_errores: int
    total_duplicados: int
    total_no_soportados: int
    filas: List[FilaComprobantePreview]

    model_config = ConfigDict(from_attributes=True)
