import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.auditoria_evento import AuditoriaEvento
from app.core.rate_limit import login_rate_limiter


async def get_admin_token(client: AsyncClient) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Password123!"})
    assert res.status_code == 200
    return res.json()["access_token"]


async def get_contador_daira_token(client: AsyncClient) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": "contador.daira@test.local", "password": "Password123!"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_crea_contador_con_empresa(client: AsyncClient, db_session: AsyncSession):
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Nuevo Contador",
            "email": "nuevo.contador@daira.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "SecurePassword123!",
            "activo": True
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "nuevo.contador@daira.local"
    assert data["rol"] == "CONTADOR"
    assert data["empresa_id"] == emp.id
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_contador_sin_empresa_es_rechazado(client: AsyncClient):
    token = await get_admin_token(client)
    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Contador Sin Empresa",
            "email": "sinempresa@test.local",
            "rol": "CONTADOR",
            "empresa_id": None,
            "password": "SecurePassword123!"
        }
    )
    assert res.status_code in [400, 422]


@pytest.mark.asyncio
async def test_crear_usuario_email_duplicado_rechazado(client: AsyncClient):
    token = await get_admin_token(client)
    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Duplicado",
            "email": "contador.daira@test.local",
            "rol": "ADMINISTRADOR",
            "password": "Password123!"
        }
    )
    assert res.status_code == 400
    assert "Ya existe un usuario" in res.json()["detail"]


@pytest.mark.asyncio
async def test_contador_bloqueado_en_rutas_admin(client: AsyncClient):
    token = await get_contador_daira_token(client)
    res_users = await client.get("/api/v1/admin/usuarios", headers={"Authorization": f"Bearer {token}"})
    assert res_users.status_code == 403

    res_emp = await client.get("/api/v1/admin/empresas", headers={"Authorization": f"Bearer {token}"})
    assert res_emp.status_code == 403

    res_audit = await client.get("/api/v1/admin/auditoria", headers={"Authorization": f"Bearer {token}"})
    assert res_audit.status_code == 403


@pytest.mark.asyncio
async def test_desactivar_usuario_invalida_jwt_anterior(client: AsyncClient, db_session: AsyncSession):
    # 1. Contador obtiene token válido
    token_contador = await get_contador_daira_token(client)

    # 2. Contador prueba que puede consultar /auth/me
    res_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_contador}"})
    assert res_me.status_code == 200

    # 3. Admin desactiva al contador
    token_admin = await get_admin_token(client)
    res_user = await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))
    user = res_user.scalar_one()

    res_patch = await client.patch(
        f"/api/v1/admin/usuarios/{user.id}/estado",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"activo": False}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["activo"] is False

    # 4. Token anterior del contador debe fallar de inmediato con 401
    res_me_invalido = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_contador}"})
    assert res_me_invalido.status_code == 401
    assert "inactivo" in res_me_invalido.json()["detail"]


@pytest.mark.asyncio
async def test_admin_no_puede_desactivarse_a_si_mismo(client: AsyncClient, db_session: AsyncSession):
    token = await get_admin_token(client)
    res_user = await db_session.execute(select(Usuario).where(Usuario.email == "admin@test.local"))
    admin = res_user.scalar_one()

    res = await client.patch(
        f"/api/v1/admin/usuarios/{admin.id}/estado",
        headers={"Authorization": f"Bearer {token}"},
        json={"activo": False}
    )
    assert res.status_code == 400
    assert "No puede desactivar su propia cuenta" in res.json()["detail"]


@pytest.mark.asyncio
async def test_admin_reset_password_y_cambio_por_usuario(client: AsyncClient, db_session: AsyncSession):
    token_admin = await get_admin_token(client)
    res_user = await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))
    user = res_user.scalar_one()

    # 1. Admin resetea la contraseña
    res_reset = await client.post(
        f"/api/v1/admin/usuarios/{user.id}/reset-password",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"temporary_password": "TempPassword2026!"}
    )
    assert res_reset.status_code == 200
    reset_data = res_reset.json()
    assert reset_data["must_change_password"] is True
    assert reset_data["temporary_password"] == "TempPassword2026!"

    # 2. Contador inicia sesión con la clave temporal
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "TempPassword2026!"}
    )
    assert res_login.status_code == 200
    token_contador = res_login.json()["access_token"]
    assert res_login.json()["user"]["must_change_password"] is True

    # 3. Contador intenta cambiar clave con actual errónea -> falla
    res_fail = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_contador}"},
        json={
            "current_password": "WrongPassword",
            "new_password": "NewPermanentPass2026!",
            "confirm_password": "NewPermanentPass2026!"
        }
    )
    assert res_fail.status_code == 400

    # 4. Contador cambia su clave exitosamente
    res_change = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_contador}"},
        json={
            "current_password": "TempPassword2026!",
            "new_password": "NewPermanentPass2026!",
            "confirm_password": "NewPermanentPass2026!"
        }
    )
    assert res_change.status_code == 200

    # 5. /auth/me refleja must_change_password = False
    res_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_contador}"})
    assert res_me.status_code == 200
    assert res_me.json()["must_change_password"] is False


@pytest.mark.asyncio
async def test_crud_empresas_y_ruc_duplicado(client: AsyncClient):
    token = await get_admin_token(client)

    # 1. Crear empresa válida
    res_create = await client.post(
        "/api/v1/admin/empresas",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ruc": "20123456789",
            "razon_social": "NUEVA EMPRESA TEST S.A.C.",
            "activo": True
        }
    )
    assert res_create.status_code == 201
    emp_id = res_create.json()["id"]

    # 2. Intentar duplicar RUC -> rechazado
    res_dup = await client.post(
        "/api/v1/admin/empresas",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ruc": "20123456789",
            "razon_social": "OTRA EMPRESA CON MISMO RUC",
            "activo": True
        }
    )
    assert res_dup.status_code == 400
    assert "Ya existe una empresa" in res_dup.json()["detail"]

    # 3. Editar razón social
    res_edit = await client.put(
        f"/api/v1/admin/empresas/{emp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"razon_social": "RAZON SOCIAL EDITADA"}
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["razon_social"] == "RAZON SOCIAL EDITADA"

    # 4. Baja lógica
    res_patch = await client.patch(
        f"/api/v1/admin/empresas/{emp_id}/estado",
        headers={"Authorization": f"Bearer {token}"},
        json={"activo": False}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["activo"] is False


@pytest.mark.asyncio
async def test_sunat_status_endpoint_no_revela_secretos(client: AsyncClient, db_session: AsyncSession):
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res = await client.get(
        f"/api/v1/admin/empresas/{emp.id}/sunat-status",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "configurado" in data
    assert "client_id_configurado" in data
    assert "client_secret_configurado" in data
    assert "client_secret" not in data
    assert "access_token" not in data
    assert "client_id" not in data


@pytest.mark.asyncio
async def test_auditoria_registro_y_visor(client: AsyncClient):
    token = await get_admin_token(client)

    # El login de admin generó un evento LOGIN_EXITOSO
    res = await client.get("/api/v1/admin/auditoria", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0

    # Verificar que el evento más reciente es LOGIN_EXITOSO y no contiene secretos
    primer_evento = data["items"][0]
    assert primer_evento["accion"] in ["LOGIN_EXITOSO", "USUARIO_CREADO", "EMPRESA_CREADA"]
    if primer_evento.get("detalle"):
        detalle_str = str(primer_evento["detalle"]).lower()
        assert "password" not in detalle_str or "[redacted]" in detalle_str
        assert "client_secret" not in detalle_str


@pytest.mark.asyncio
async def test_login_rate_limiting(client: AsyncClient):
    login_rate_limiter.clear_all()

    # Realizar 5 intentos fallidos
    for _ in range(5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "usuario.test@test.local", "password": "WrongPassword!"}
        )
        assert res.status_code == 401

    # El 6to intento debe responder 429 Too Many Requests
    res_bloqueado = await client.post(
        "/api/v1/auth/login",
        json={"email": "usuario.test@test.local", "password": "WrongPassword!"}
    )
    assert res_bloqueado.status_code == 429
    assert "Demasiados intentos fallidos" in res_bloqueado.json()["detail"]


@pytest.mark.asyncio
async def test_health_check_and_ready(client: AsyncClient):
    # /health
    res_health = await client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # /health/ready
    res_ready = await client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ok"
    assert res_ready.json()["database"] == "ok"


@pytest.mark.asyncio
async def test_security_headers_presentes(client: AsyncClient):
    res = await client.get("/api/v1/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "no-referrer"
    assert "Permissions-Policy" in res.headers
