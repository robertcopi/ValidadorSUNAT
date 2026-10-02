"""
Tests de Verificación de Seguridad y Hardening
===============================================
Cubre:
1. Acceso a endpoints protegidos sin token (401)
2. Token JWT manipulado, firma falsa o expirado (401)
3. Usuario desactivado bloqueado inmediatamente (401)
4. Escalación de privilegios: CONTADOR intentando endpoints de ADMINISTRADOR (403)
5. Aislamiento multiempresa (Anti-IDOR): DAIRA vs JJD en procesos masivos y exportaciones (404)
6. Rechazo de archivos no Excel o inválidos (400)
7. Detección y rechazo de zip bombs o ejecutables/macros internos (400)
8. Mitigación de Formula Injection (CSV/Excel Formula Injection) en exportaciones
9. Rate limiting de login y registro de auditoría LOGIN_BLOQUEADO
10. Presencia de cabeceras de seguridad HTTP (CSP, nosniff, frame-options, etc.)
11. Respuestas de error sin trazas internas ni consultas SQL
"""

import io
import time
import uuid
import zipfile
from decimal import Decimal
import pytest
import jwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.proceso_masivo import ProcesoMasivo
from app.models.auditoria_evento import AuditoriaEvento
from app.services.excel_parser_service import ExcelParserService, ExcelParserException
from app.services.proceso_masivo_service import proceso_masivo_service


@pytest.mark.asyncio
async def test_acceso_sin_token_rechazado_401(client: AsyncClient):
    """Endpoints protegidos deben retornar 401 si no se envía cabecera Authorization."""
    rutas_get = [
        "/api/v1/auth/me",
        "/api/v1/admin/empresas",
        "/api/v1/procesos-masivos",
        "/api/v1/admin/usuarios",
    ]
    for ruta in rutas_get:
        res = await client.get(ruta)
        assert res.status_code == 401, f"Ruta GET {ruta} permitió acceso sin token"

    res_post = await client.post("/api/v1/importaciones/preview")
    assert res_post.status_code == 401, "POST /api/v1/importaciones/preview permitió acceso sin token"


@pytest.mark.asyncio
async def test_token_jwt_manipulado_o_firma_falsa_401(client: AsyncClient):
    """Tokens con firma inválida, secreto alterado o formato corrupto deben ser rechazados con 401."""
    token_falso = jwt.encode(
        {"sub": "1", "role": "ADMINISTRADOR", "empresa_id": None},
        "clave-secreta-totalmente-falsa-que-supera-32-bytes-para-evitar-advertencias",
        algorithm=settings.ALGORITHM
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_falso}"})
    assert res.status_code == 401

    res_corrupto = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token.invalido.corrupto"})
    assert res_corrupto.status_code == 401


@pytest.mark.asyncio
async def test_token_jwt_expirado_401(client: AsyncClient):
    """Tokens expirados deben ser rechazados de inmediato con 401."""
    token_expirado = jwt.encode(
        {"sub": "1", "exp": int(time.time()) - 3600},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_expirado}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_usuario_desactivado_bloqueado(client: AsyncClient, db_session: AsyncSession):
    """Un usuario que ha sido desactivado en la BD es rechazado aunque su JWT no haya expirado."""
    stmt = select(Usuario).where(Usuario.email == "contador.daira@test.local")
    user = (await db_session.execute(stmt)).scalar_one()

    token = create_access_token(
        subject=user.id,
        empresa_id=user.empresa_id,
        rol=user.rol
    )

    user.activo = False
    await db_session.commit()

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "inactivo" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_escalacion_roles_contador_bloqueado_en_admin_403(client: AsyncClient):
    """Un usuario con rol CONTADOR no puede acceder a endpoints administrativos."""
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    token_contador = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token_contador}"}

    rutas_admin = [
        ("GET", "/api/v1/admin/usuarios"),
        ("POST", "/api/v1/admin/usuarios"),
        ("POST", "/api/v1/admin/empresas"),
        ("GET", "/api/v1/admin/auditoria"),
    ]

    for metodo, ruta in rutas_admin:
        if metodo == "GET":
            res = await client.get(ruta, headers=headers)
        else:
            res = await client.post(ruta, json={}, headers=headers)
        assert res.status_code == 403, f"CONTADOR pudo acceder a {ruta} con status {res.status_code}"


@pytest.mark.asyncio
async def test_aislamiento_multiempresa_idor_bloqueado(client: AsyncClient, db_session: AsyncSession):
    """
    Verifica que un CONTADOR de Empresa DAIRA no pueda consultar ni exportar
    un lote o proceso perteneciente a Empresa JJD (Anti-IDOR).
    """
    empresa_jjd = (await db_session.execute(select(Empresa).where(Empresa.razon_social == "GRUPO JJD MAR"))).scalar_one()
    usuario_jjd = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.jjd@test.local"))).scalar_one()

    proceso_jjd = ProcesoMasivo(
        id=str(uuid.uuid4()),
        empresa_id=empresa_jjd.id,
        usuario_id=usuario_jjd.id,
        nombre_archivo="jjd_lote_privado.xlsx",
        total_registros=1,
        total_procesados=1,
        total_validos=1,
        total_no_validos=0,
        total_observados=0,
        total_errores=0,
        estado="COMPLETADO"
    )
    db_session.add(proceso_jjd)
    await db_session.commit()
    await db_session.refresh(proceso_jjd)

    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    token_daira = res_login.json()["access_token"]
    headers_daira = {"Authorization": f"Bearer {token_daira}"}

    res_ver = await client.get(f"/api/v1/procesos-masivos/{proceso_jjd.id}", headers=headers_daira)
    assert res_ver.status_code == 404, "CONTADOR de DAIRA pudo ver proceso privado de JJD"

    res_export = await client.get(f"/api/v1/procesos-masivos/{proceso_jjd.id}/exportar", headers=headers_daira)
    assert res_export.status_code == 404, "CONTADOR de DAIRA pudo exportar proceso privado de JJD"


@pytest.mark.asyncio
async def test_subida_archivo_no_excel_rechazada_400(client: AsyncClient):
    """Archivos con extensiones o contenidos que no sean .xlsx son rechazados."""
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    headers = {"Authorization": f"Bearer {res_login.json()['access_token']}"}

    files_txt = {"archivo": ("malicioso.txt", b"Texto plano simulado", "text/plain")}
    res = await client.post("/api/v1/importaciones/preview", headers=headers, files=files_txt)
    assert res.status_code == 400

    files_fake_xlsx = {"archivo": ("falso.xlsx", b"No es un zip ni un ooxml real", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res2 = await client.post("/api/v1/importaciones/preview", headers=headers, files=files_fake_xlsx)
    assert res2.status_code == 400


def test_subida_zip_bomb_o_archivos_peligrosos_rechazada_400():
    """Protección contra Zip Bombs o archivos comprimidos con ejecutables internos."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/payload.exe", b"MZ\x90\x00malicious binary content")
    zip_bytes = buf.getvalue()

    with pytest.raises(ExcelParserException) as exc_info:
        ExcelParserService.validar_archivo(zip_bytes, "malicioso.xlsx")
    assert "ejecutables" in str(exc_info.value).lower() or "no autorizados" in str(exc_info.value).lower()


def test_proteccion_formula_injection_en_exportacion():
    """
    Verifica que celdas que inicien con carácteres de fórmula (=, +, -, @)
    sean prefijadas con comilla simple para neutralizar Formula Injection,
    mientras que números y decimales legítimos se mantengan numéricos.
    """
    assert proceso_masivo_service.sanitize_formula("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert proceso_masivo_service.sanitize_formula("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert proceso_masivo_service.sanitize_formula("-2+3*cmd") == "'-2+3*cmd"
    assert proceso_masivo_service.sanitize_formula("@SUM(1,2)") == "'@SUM(1,2)"

    assert proceso_masivo_service.sanitize_formula(Decimal("-21142.71")) == Decimal("-21142.71")
    assert proceso_masivo_service.sanitize_formula(-500.25) == -500.25
    assert proceso_masivo_service.sanitize_formula(12345) == 12345
    assert proceso_masivo_service.sanitize_formula("Texto Normal") == "Texto Normal"


@pytest.mark.asyncio
async def test_login_rate_limiting_y_auditoria_bloqueado(client: AsyncClient, db_session: AsyncSession):
    """
    Múltiples intentos fallidos de login provocan bloqueo por Rate Limiting (429)
    y el evento queda registrado en la tabla de auditoría como LOGIN_BLOQUEADO.
    """
    for _ in range(settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.local", "password": "PasswordIncorrecta!"}
        )
        assert res.status_code == 401

    res_bloqueado = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "PasswordIncorrecta!"}
    )
    assert res_bloqueado.status_code == 429

    stmt = select(AuditoriaEvento).where(AuditoriaEvento.accion == "LOGIN_BLOQUEADO")
    evento = (await db_session.execute(stmt)).scalars().first()
    assert evento is not None
    assert evento.accion == "LOGIN_BLOQUEADO"


@pytest.mark.asyncio
async def test_security_headers_presentes_en_todas_las_respuestas(client: AsyncClient):
    """Verifica que las cabeceras HTTP de seguridad estén presentes en las respuestas."""
    res = await client.get("/api/v1/health")
    assert res.status_code == 200

    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "no-referrer"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_errores_500_no_filtran_stacktraces_ni_sql():
    """Excepciones no controladas deben devolver mensaje genérico y nunca el traceback o query SQL."""
    from app.main import app

    @app.get("/api/v1/test-seguridad/error-interno")
    async def endpoint_con_error():
        raise RuntimeError("FATAL_SQL_INTERNAL_ERROR: SELECT secret FROM credentials")

    original_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res_error = await ac.get("/api/v1/test-seguridad/error-interno")
            assert res_error.status_code == 500
            data = res_error.json()

            # El detalle nunca debe filtrar la consulta SQL ni la traza en producción
            assert "SELECT secret" not in data.get("detail", "")
            assert "Traceback" not in data.get("detail", "")
            assert "error interno" in data.get("detail", "").lower()
    finally:
        settings.ENVIRONMENT = original_env
