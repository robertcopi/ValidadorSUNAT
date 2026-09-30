import pytest
from httpx import AsyncClient
from fastapi import APIRouter, Depends
from app.api.deps import get_current_empresa, require_role
from app.main import app
from app.models.empresa import Empresa
from app.models.usuario import Usuario

# Router auxiliar para verificar aislamiento y roles en tests
mock_tenancy_router = APIRouter(prefix="/api/v1/test-tenancy", tags=["TestTenancy"])


@mock_tenancy_router.get("/empresa-info")
async def get_my_company_info(empresa: Empresa = Depends(get_current_empresa)):
    if not empresa:
        return {"scope": "global", "empresa": None}
    return {
        "scope": "empresa",
        "empresa_id": empresa.id,
        "ruc": empresa.ruc,
        "razon_social": empresa.razon_social
    }


@mock_tenancy_router.get("/solo-admin")
async def admin_only_route(current_user: Usuario = Depends(require_role(["ADMINISTRADOR"]))):
    return {"message": "Acceso permitido solo para administradores", "user": current_user.email}


app.include_router(mock_tenancy_router)


@pytest.mark.asyncio
async def test_contador_daira_cannot_access_jjd_data(client: AsyncClient):
    """Verifica que el token del contador de DAIRA resuelve única y exclusivamente a DAIRA (20538976815)."""
    login_daira = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    token_daira = login_daira.json()["access_token"]

    response = await client.get(
        "/api/v1/test-tenancy/empresa-info",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ruc"] == "20538976815"
    assert data["razon_social"] == "DAIRA"
    assert data["ruc"] != "20612689831"


@pytest.mark.asyncio
async def test_contador_jjd_resolves_only_jjd(client: AsyncClient):
    """Verifica que el contador de GRUPO JJD MAR resuelve a 20612689831 y no a DAIRA."""
    login_jjd = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.jjd@test.local", "password": "Password123!"}
    )
    token_jjd = login_jjd.json()["access_token"]

    response = await client.get(
        "/api/v1/test-tenancy/empresa-info",
        headers={"Authorization": f"Bearer {token_jjd}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ruc"] == "20612689831"
    assert data["razon_social"] == "GRUPO JJD MAR"
    assert data["ruc"] != "20538976815"


@pytest.mark.asyncio
async def test_contador_cannot_access_admin_route(client: AsyncClient):
    """Verifica que un contador sea rechazado con HTTP 403 al intentar acceder a rutas de ADMINISTRADOR."""
    login_daira = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    token_daira = login_daira.json()["access_token"]

    response = await client.get(
        "/api/v1/test-tenancy/solo-admin",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert response.status_code == 403
    assert "No tiene los permisos necesarios" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_can_access_admin_route(client: AsyncClient):
    """Verifica que el administrador sí tiene acceso permitido a las rutas protegidas por rol."""
    login_admin = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "Password123!"}
    )
    token_admin = login_admin.json()["access_token"]

    response = await client.get(
        "/api/v1/test-tenancy/solo-admin",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert response.status_code == 200
    assert response.json()["user"] == "admin@test.local"
