import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.services.proceso_masivo_service import proceso_masivo_service

# Inicializar configuración de logging estructurado con sanitización de secretos
setup_logging()
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware que inyecta cabeceras HTTP de endurecimiento (hardening) de seguridad."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS solo aplicable si es HTTPS o entorno de producción
        if settings.ENVIRONMENT != "development" and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Recuperación automática de procesos interrumpidos al iniciar
    try:
        await proceso_masivo_service.recuperar_procesos_al_iniciar()
    except Exception as e:
        logger.warning("Error durante recuperación de inicio: %s", str(e))
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Middleware de cabeceras de seguridad
app.add_middleware(SecurityHeadersMiddleware)

# Configurar middleware CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Manejador global de excepciones no controladas
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Excepción no controlada procesando %s %s: %s",
        request.method, request.url.path, str(exc),
        exc_info=settings.DEBUG
    )
    if settings.DEBUG:
        detail = f"Error interno: {str(exc)}"
    else:
        detail = "Error interno del servidor. Por favor, comuníquese con el administrador si el problema persiste."

    return JSONResponse(
        status_code=500,
        content={"detail": detail}
    )


# Incluir router de API v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "message": "Bienvenido a la API del Sistema de Validación de Comprobantes SUNAT",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health"
    }
