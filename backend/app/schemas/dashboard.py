from decimal import Decimal
from typing import Optional, Dict
from pydantic import BaseModel, ConfigDict


class DashboardResumenResponse(BaseModel):
    """Resumen estadístico agregado para el Dashboard del contador."""
    total: int = 0
    validos: int = 0
    no_validos: int = 0
    observados: int = 0
    errores: int = 0
    porcentaje_validos: float = 0.0
    porcentaje_no_validos: float = 0.0
    porcentaje_observados: float = 0.0
    porcentaje_errores: float = 0.0

    model_config = ConfigDict(from_attributes=True)
