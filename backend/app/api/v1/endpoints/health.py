from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def check_health(db: AsyncSession = Depends(get_db)):
    """Verifica el estado del servicio y la conectividad con PostgreSQL."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "Sistema de Validación de Comprobantes SUNAT",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def check_health_ready(db: AsyncSession = Depends(get_db)):
    """
    Verifica si el backend y PostgreSQL están operativos para recibir tráfico operacional.
    No ejecuta consultas externas a SUNAT.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "ok"
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "unavailable"}
        )
