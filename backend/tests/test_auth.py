import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Verifica que el login con credenciales válidas retorne 200, JWT y datos del usuario y empresa."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "contador.daira@test.local"
    assert data["user"]["rol"] == "CONTADOR"
    assert data["user"]["empresa"]["ruc"] == "20538976815"
    assert data["user"]["empresa"]["razon_social"] == "DAIRA"
    assert "password_hash" not in data["user"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Verifica que una contraseña incorrecta retorne 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "WrongPassword"}
    )
    assert response.status_code == 401
    assert "Credenciales incorrectas" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Verifica que un usuario no registrado retorne 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "noexiste@test.local", "password": "Password123!"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_unauthorized(client: AsyncClient):
    """Verifica que /auth/me sin encabezado Authorization devuelva 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_authorized(client: AsyncClient):
    """Verifica que /auth/me con token válido devuelva los datos del usuario logueado."""
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "admin@test.local"
    assert user_data["rol"] == "ADMINISTRADOR"
    assert user_data["empresa_id"] is None


@pytest.mark.asyncio
async def test_login_by_username_or_name(client: AsyncClient):
    """Verifica que el login funcione con correo, con nombre de usuario o con el nombre completo."""
    # 1. Login con prefijo de usuario ('admin')
    res_username = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin", "password": "Password123!"}
    )
    assert res_username.status_code == 200
    assert res_username.json()["user"]["email"] == "admin@test.local"

    # 2. Login con nombre completo ('Admin Test')
    res_name = await client.post(
        "/api/v1/auth/login",
        json={"email": "Admin Test", "password": "Password123!"}
    )
    assert res_name.status_code == 200
    assert res_name.json()["user"]["email"] == "admin@test.local"

    # 3. Login con prefijo contador ('contador.daira')
    res_contador = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira", "password": "Password123!"}
    )
    assert res_contador.status_code == 200
    assert res_contador.json()["user"]["email"] == "contador.daira@test.local"

