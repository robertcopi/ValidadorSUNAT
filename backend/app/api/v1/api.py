from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, sunat, importaciones, procesos_masivos, dashboard, admin

api_router = APIRouter()

api_router.include_router(health.router, tags=["Salud"])
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(sunat.router, prefix="/sunat", tags=["SUNAT"])
api_router.include_router(importaciones.router, prefix="/importaciones", tags=["Importaciones"])
api_router.include_router(procesos_masivos.router, prefix="/procesos-masivos", tags=["Procesos Masivos"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(admin.admin_router, prefix="/admin")

