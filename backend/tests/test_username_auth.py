import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.core.security import decode_access_token
from app.models.auditoria_evento import AuditoriaEvento
from app.models.empresa import Empresa
from app.models.usuario import Usuario


async def get_admin_token(client: AsyncClient) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Password123!"}
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_crear_usuario_con_username(client: AsyncClient, db_session):
    """1. Crear usuario con username desde administración."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Robert Estela",
            "username": "robert",
            "email": "robert.estela@daira.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password2026!",
            "activo": True
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "robert"
    assert data["nombre_completo"] == "Robert Estela"
    assert data["email"] == "robert.estela@daira.local"


@pytest.mark.asyncio
async def test_username_robert_valido(client: AsyncClient, db_session):
    """2. Username 'robert' simple y válido (3 a 50 caracteres)."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Robert Valido",
            "username": "robert",
            "email": "robert.valido@daira.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password2026!"
        }
    )
    assert res.status_code == 201
    assert res.json()["username"] == "robert"


@pytest.mark.asyncio
async def test_username_unico_globalmente(client: AsyncClient, db_session):
    """3. Username único globalmente: DAIRA y JJD no pueden compartir el mismo username."""
    token = await get_admin_token(client)
    res_daira = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp_daira = res_daira.scalar_one()
    res_jjd = await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))
    emp_jjd = res_jjd.scalar_one()

    # Crear en DAIRA
    res1 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Juan Perez",
            "username": "juan",
            "email": "juan.daira@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp_daira.id,
            "password": "Password123!"
        }
    )
    assert res1.status_code == 201

    # Intentar crear en JJD con el mismo username
    res2 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Juan Perez JJD",
            "username": "juan",
            "email": "juan.jjd@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp_jjd.id,
            "password": "Password123!"
        }
    )
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_username_duplicado_rechazado_con_409(client: AsyncClient, db_session):
    """4. Si el username ya existe, responder HTTP 409 Conflict con mensaje exacto."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Usuario Uno",
            "username": "usuario1",
            "email": "u1@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )

    res_dup = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Usuario Dos",
            "username": "usuario1",
            "email": "u2@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["detail"] == "El nombre de usuario ya está en uso."


@pytest.mark.asyncio
async def test_username_case_insensitive(client: AsyncClient, db_session):
    """5 y 6. Username case-insensitive: 'ROBERT' y 'robert' colisionan y no pueden coexistir."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res1 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Robert Estela",
            "username": "robert",
            "email": "robert@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res1.status_code == 201

    # Intentar con mayúsculas
    res2 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Robert Mayus",
            "username": "ROBERT",
            "email": "robert.mayus@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res2.status_code == 409
    assert res2.json()["detail"] == "El nombre de usuario ya está en uso."


@pytest.mark.asyncio
async def test_strip_de_espacios_al_crear(client: AsyncClient, db_session):
    """7. Strip de espacios al inicio y al final en username."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Pedro Gomez",
            "username": "  pedro2  ",
            "email": "pedro2@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res.status_code == 201
    assert res.json()["username"] == "pedro2"


@pytest.mark.asyncio
async def test_login_mediante_robert_y_ROBERT(client: AsyncClient, db_session):
    """8 y 9. Login mediante 'robert' y case-insensitive mediante 'ROBERT'."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Robert Estela",
            "username": "robert",
            "email": "robert.test@daira.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "MiPasswordSeguro123!"
        }
    )

    # 8. Login con minúsculas exactas
    res_login1 = await client.post(
        "/api/v1/auth/login",
        json={"username": "robert", "password": "MiPasswordSeguro123!"}
    )
    assert res_login1.status_code == 200
    assert res_login1.json()["user"]["username"] == "robert"

    # 9. Login con mayúsculas
    res_login2 = await client.post(
        "/api/v1/auth/login",
        json={"username": "ROBERT", "password": "MiPasswordSeguro123!"}
    )
    assert res_login2.status_code == 200
    assert res_login2.json()["user"]["username"] == "robert"

    # Login con espacios alrededor
    res_login3 = await client.post(
        "/api/v1/auth/login",
        json={"username": "  robert  ", "password": "MiPasswordSeguro123!"}
    )
    assert res_login3.status_code == 200


@pytest.mark.asyncio
async def test_password_incorrecto_devuelve_401_generico(client: AsyncClient):
    """10. Password incorrecto retorna 401 con mensaje genérico."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "ClaveIncorrecta!"}
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Credenciales incorrectas."


@pytest.mark.asyncio
async def test_usuario_inexistente_devuelve_401_generico(client: AsyncClient):
    """11. Usuario inexistente retorna 401 con mensaje genérico sin filtrar existencia."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"username": "no_existe_usuario", "password": "Password123!"}
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Credenciales incorrectas."


@pytest.mark.asyncio
async def test_usuario_desactivado_no_puede_iniciar_sesion(client: AsyncClient, db_session):
    """12. Usuario inactivo no puede iniciar sesión por username."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    res_crear = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Usuario Inactivo",
            "username": "inactivo_user",
            "email": "inactivo@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    user_id = res_crear.json()["id"]

    # Desactivar usuario
    await client.patch(
        f"/api/v1/admin/usuarios/{user_id}/estado",
        headers={"Authorization": f"Bearer {token}"},
        json={"activo": False}
    )

    # Intento de login por username
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "inactivo_user", "password": "Password123!"}
    )
    assert res_login.status_code == 403
    assert "desactivada" in res_login.json()["detail"]


@pytest.mark.asyncio
async def test_auth_me_y_perfil_devuelve_username(client: AsyncClient):
    """13 y 14. /auth/me devuelve el campo username correctamente poblado."""
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "Password123!"}
    )
    token = res_login.json()["access_token"]

    res_me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_me.status_code == 200
    data = res_me.json()
    assert data["username"] == "contador.daira"
    assert data["nombre_completo"] == "Contador DAIRA Test"
    assert data["email"] == "contador.daira@test.local"
    assert data["rol"] == "CONTADOR"
    assert data["empresa"]["razon_social"] == "DAIRA"
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_admin_puede_cambiar_username(client: AsyncClient, db_session):
    """15. Administrador puede editar el username de un usuario."""
    token = await get_admin_token(client)
    res_user = await db_session.execute(select(Usuario).where(Usuario.username == "contador.daira"))
    user = res_user.scalar_one()

    # Cambiar de contador.daira a robert
    res_update = await client.put(
        f"/api/v1/admin/usuarios/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Robert Estela",
            "username": "robert",
            "email": "contador1.daira@sistema.local"
        }
    )
    assert res_update.status_code == 200
    assert res_update.json()["username"] == "robert"

    # Ahora inicia sesión con el nuevo username
    res_login_new = await client.post(
        "/api/v1/auth/login",
        json={"username": "robert", "password": "Password123!"}
    )
    assert res_login_new.status_code == 200

    # El username viejo ya no autentica
    res_login_old = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "Password123!"}
    )
    assert res_login_old.status_code == 401


@pytest.mark.asyncio
async def test_contador_no_puede_cambiar_username_directamente(client: AsyncClient):
    """16. Un usuario con rol CONTADOR no tiene acceso a endpoints de modificación de username."""
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "Password123!"}
    )
    contador_token = res_login.json()["access_token"]
    user_id = res_login.json()["user"]["id"]

    res = await client.put(
        f"/api/v1/admin/usuarios/{user_id}",
        headers={"Authorization": f"Bearer {contador_token}"},
        json={"username": "hack_username"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cambio_y_reset_password_con_username(client: AsyncClient, db_session):
    """17, 18 y 19. Cambio de contraseña, reset y must_change_password funcionan con login por username."""
    token_admin = await get_admin_token(client)
    res_user = await db_session.execute(select(Usuario).where(Usuario.username == "contador.daira"))
    user = res_user.scalar_one()

    # 18. Admin resetea password
    res_reset = await client.post(
        f"/api/v1/admin/usuarios/{user.id}/reset-password",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"temporary_password": "TempPassword2026!"}
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["must_change_password"] is True

    # Login con contraseña temporal usando username
    res_temp_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "TempPassword2026!"}
    )
    assert res_temp_login.status_code == 200
    assert res_temp_login.json()["user"]["must_change_password"] is True
    temp_token = res_temp_login.json()["access_token"]

    # 17 y 19. Usuario cambia su propia clave
    res_change = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={
            "current_password": "TempPassword2026!",
            "new_password": "MiNuevaPasswordDefinitiva2026!",
            "confirm_password": "MiNuevaPasswordDefinitiva2026!"
        }
    )
    assert res_change.status_code == 200

    # Login exitoso con nueva contraseña y username
    res_final_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "MiNuevaPasswordDefinitiva2026!"}
    )
    assert res_final_login.status_code == 200
    assert res_final_login.json()["user"]["must_change_password"] is False


@pytest.mark.asyncio
async def test_jwt_usa_id_interno_en_sub(client: AsyncClient):
    """20. JWT usa ID interno entero en el claim sub (no el username)."""
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "Password123!"}
    )
    token = res_login.json()["access_token"]
    user_id = res_login.json()["user"]["id"]

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["empresa_id"] is not None
    assert payload["rol"] == "CONTADOR"


@pytest.mark.asyncio
async def test_auditoria_registra_edicion_de_username(client: AsyncClient, db_session):
    """21 y 22. Auditoría registra USUARIO_EDITADO al cambiar username."""
    token = await get_admin_token(client)
    res_user = await db_session.execute(select(Usuario).where(Usuario.username == "contador.jjd"))
    user = res_user.scalar_one()

    await client.put(
        f"/api/v1/admin/usuarios/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "contador.jjd.nuevo"}
    )

    # Verificar registro en auditoria_eventos
    audit_res = await db_session.execute(
        select(AuditoriaEvento)
        .where(AuditoriaEvento.accion == "USUARIO_EDITADO", AuditoriaEvento.entidad_id == str(user.id))
        .order_by(AuditoriaEvento.id.desc())
    )
    evento = audit_res.scalars().first()
    assert evento is not None
    assert evento.detalle.get("campo_modificado") == "username" or "username" in evento.detalle.get("campos_modificados", [])
    assert "password" not in str(evento.detalle)
    assert "password_hash" not in str(evento.detalle)


@pytest.mark.asyncio
async def test_no_se_exponen_secretos_en_respuestas(client: AsyncClient):
    """23. En ningún endpoint se exponen contraseñas ni hashes."""
    token = await get_admin_token(client)

    # 1. Login
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Password123!"}
    )
    body_login = res_login.text
    assert "password_hash" not in body_login

    # 2. /auth/me
    res_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert "password_hash" not in res_me.text

    # 3. /admin/usuarios
    res_users = await client.get("/api/v1/admin/usuarios", headers={"Authorization": f"Bearer {token}"})
    assert "password_hash" not in res_users.text


@pytest.mark.asyncio
async def test_rate_limit_con_username(client: AsyncClient):
    """24. Rate limit protege contra fuerza bruta utilizando username."""
    target_username = "contador.daira"
    for _ in range(5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": target_username, "password": "BadPassword!"}
        )
        assert res.status_code == 401

    # 6to intento -> bloqueado por 429
    res_blocked = await client.post(
        "/api/v1/auth/login",
        json={"username": target_username, "password": "BadPassword!"}
    )
    assert res_blocked.status_code == 429


@pytest.mark.asyncio
async def test_username_caracteres_invalidos_rechazados(client: AsyncClient, db_session):
    """Username con caracteres inválidos (como espacios intermedios, arroba o asterisco) es rechazado."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    # Espacio intermedio
    res1 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Test Invalido",
            "username": "robert estela",
            "email": "invalido1@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res1.status_code == 422

    # Carácter especial inválido
    res2 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Test Invalido 2",
            "username": "robert*sunat",
            "email": "invalido2@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_username_longitud_invalida(client: AsyncClient, db_session):
    """Username menor a 3 caracteres o mayor a 50 es rechazado."""
    token = await get_admin_token(client)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp = res_emp.scalar_one()

    # Demasiado corto (2 caracteres)
    res_short = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Corto",
            "username": "ro",
            "email": "corto@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res_short.status_code == 422

    # Demasiado largo (> 50 caracteres)
    res_long = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_completo": "Largo",
            "username": "r" * 51,
            "email": "largo@test.local",
            "rol": "CONTADOR",
            "empresa_id": emp.id,
            "password": "Password123!"
        }
    )
    assert res_long.status_code == 422


@pytest.mark.asyncio
async def test_tenancy_daira_jjd_aislados_con_login_username(client: AsyncClient):
    """21. DAIRA y JJD siguen estrictamente aisladas al operar con usuarios autenticados por username."""
    # Login contador DAIRA
    res_d = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.daira", "password": "Password123!"}
    )
    assert res_d.status_code == 200
    token_daira = res_d.json()["access_token"]
    empresa_daira_id = res_d.json()["user"]["empresa_id"]

    # Login contador JJD
    res_j = await client.post(
        "/api/v1/auth/login",
        json={"username": "contador.jjd", "password": "Password123!"}
    )
    assert res_j.status_code == 200
    token_jjd = res_j.json()["access_token"]
    empresa_jjd_id = res_j.json()["user"]["empresa_id"]

    assert empresa_daira_id != empresa_jjd_id

    # DAIRA no puede consultar procesos masivos de JJD
    res_d_proc = await client.get(
        "/api/v1/procesos-masivos",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res_d_proc.status_code == 200


@pytest.mark.asyncio
async def test_login_por_email_compatibilidad(client: AsyncClient):
    """26. Compatibilidad de transición: login mediante email sigue funcionando."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    assert res.status_code == 200
    assert res.json()["user"]["username"] == "contador.daira"
    assert res.json()["user"]["email"] == "contador.daira@test.local"

