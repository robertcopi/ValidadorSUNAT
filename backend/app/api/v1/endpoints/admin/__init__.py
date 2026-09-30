from fastapi import APIRouter
from app.api.v1.endpoints.admin import usuarios, empresas, auditoria

admin_router = APIRouter()

admin_router.include_router(usuarios.router, prefix="/usuarios", tags=["Admin - Usuarios"])
admin_router.include_router(empresas.router, prefix="/empresas", tags=["Admin - Empresas"])
admin_router.include_router(auditoria.router, prefix="/auditoria", tags=["Admin - Auditoría"])
