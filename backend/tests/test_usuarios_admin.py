import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.core.security import verify_password


async def get_admin_token(client: AsyncClient) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Password123!"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_crear_contador_con_daira_exitoso(client: AsyncClient, db_session: AsyncSession):
    """Prueba 1 y 2: Crear CONTADOR con DAIRA correctamente."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp_daira = res_emp.scalar_one()

    payload = {
        "nombre_completo": "Daniel Bernal",
        "username": "daniel",
        "email": "Danielbernal@daira.pe",
        "rol": "CONTADOR",
        "empresa_id": emp_daira.id,
        "password": "PasswordSegura123!",
        "activo": True
    }

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert res.status_code == 201, f"Error: {res.text}"
    data = res.json()
    assert data["nombre_completo"] == "Daniel Bernal"
    assert data["username"] == "daniel"
    assert data["email"] == "danielbernal@daira.pe"
    assert data["rol"] == "CONTADOR"
    assert data["empresa_id"] == emp_daira.id
    # No exponer secretos
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_crear_contador_con_jjd_exitoso(client: AsyncClient, db_session: AsyncSession):
    """Prueba 3: Crear CONTADOR con JJD MAR correctamente."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))
    emp_jjd = res_emp.scalar_one()

    payload = {
        "nombre_completo": "Contador JJD",
        "username": "contador.jjd2",
        "email": "contador2@jjdmar.pe",
        "rol": "CONTADOR",
        "empresa_id": emp_jjd.id,
        "password": "PasswordSegura123!",
        "activo": True
    }

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "contador.jjd2"
    assert data["empresa_id"] == emp_jjd.id


@pytest.mark.asyncio
async def test_contador_sin_empresa_rechazado(client: AsyncClient):
    """Prueba 4: CONTADOR sin empresa asignada es rechazado."""
    token = await get_admin_token(client)
    payload = {
        "nombre_completo": "Contador Huérfano",
        "username": "huerfano",
        "email": "huerfano@daira.pe",
        "rol": "CONTADOR",
        "empresa_id": None,
        "password": "PasswordSegura123!"
    }

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert res.status_code in [400, 422]
    detail = res.json()["detail"]
    detail_str = str(detail).lower()
    assert "empresa" in detail_str


@pytest.mark.asyncio
async def test_username_duplicado_error_controlado(client: AsyncClient, db_session: AsyncSession):
    """Prueba 5: Username duplicado devuelve error controlado 400/409."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    # Primer usuario
    res1 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Usuario Uno",
            "username": "mismo_user",
            "email": "user1@daira.pe",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "PasswordSegura123!"
        }
    )
    assert res1.status_code == 201

    # Segundo usuario con el mismo username pero en mayúsculas/espacios
    res2 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Usuario Dos",
            "username": "  MISMO_USER  ",
            "email": "user2@daira.pe",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "PasswordSegura123!"
        }
    )
    assert res2.status_code in [400, 409]
    detail = res2.json()["detail"]
    assert "nombre de usuario ya está registrado" in detail.lower() or "en uso" in detail.lower()


@pytest.mark.asyncio
async def test_email_duplicado_error_controlado(client: AsyncClient, db_session: AsyncSession):
    """Prueba 6: Email duplicado devuelve error controlado 400/409."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    # Usuario con mismo email
    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Otro Usuario",
            "username": "otro_user",
            "email": "contador.daira@test.local",  # Ya existe en conftest
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "PasswordSegura123!"
        }
    )
    assert res.status_code in [400, 409]
    detail = res.json()["detail"]
    assert "correo electrónico ya está registrado" in detail.lower() or "en uso" in detail.lower()


@pytest.mark.asyncio
async def test_normalizacion_username_y_email(client: AsyncClient, db_session: AsyncSession):
    """Prueba 7 y 8: Username y email se normalizan (minúsculas y strip)."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "  Normalizar Test  ",
            "username": "  UserNorm  ",
            "email": "  TestNorm@Daira.PE  ",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "PasswordSegura123!"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "usernorm"
    assert data["email"] == "testnorm@daira.pe"
    assert data["nombre_completo"] == "Normalizar Test"


@pytest.mark.asyncio
async def test_password_hasheado_en_bd(client: AsyncClient, db_session: AsyncSession):
    """Prueba 9: El password queda hasheado y nunca en texto plano en la BD."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    plain_pass = "SuperClaveSecreta123!"
    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Hash Check",
            "username": "hashcheck",
            "email": "hashcheck@daira.pe",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": plain_pass
        }
    )
    assert res.status_code == 201
    uid = res.json()["id"]

    stmt = select(Usuario).where(Usuario.id == uid)
    db_user = (await db_session.execute(stmt)).scalar_one()
    assert db_user.password_hash != plain_pass
    assert verify_password(plain_pass, db_user.password_hash) is True


@pytest.mark.asyncio
async def test_login_con_username_nuevo(client: AsyncClient, db_session: AsyncSession):
    """Prueba extra: Login con username corto (ej. 'daniel')."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Daniel Login",
            "username": "danielshort",
            "email": "danielshort@daira.pe",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )

    # Iniciar sesión usando sólo el username
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "danielshort", "password": "Password123!"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["user"]["username"] == "danielshort"
