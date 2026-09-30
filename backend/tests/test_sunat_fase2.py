import time
import pytest
import httpx
from httpx import AsyncClient, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.consulta_cpe import ConsultaCPE
from app.models.empresa import Empresa
from app.services.sunat_service import sunat_service, CachedToken, SunatCredentialsError


# Guardar referencia al post original de httpx.AsyncClient
ORIGINAL_ASYNC_CLIENT_POST = AsyncClient.post


def patch_sunat_calls(monkeypatch, sunat_handler):
    """
    Parchea únicamente las llamadas salientes a los dominios de SUNAT,
    permitiendo que las llamadas del cliente de test de FastAPI (/api/v1/...) funcionen normalmente.
    """
    async def mock_post(self, url, *args, **kwargs):
        url_str = str(url)
        if "api-seguridad.sunat.gob.pe" in url_str or "api.sunat.gob.pe" in url_str:
            res = sunat_handler(url_str, kwargs)
            if isinstance(res, Exception):
                raise res
            return res
        return await ORIGINAL_ASYNC_CLIENT_POST(self, url, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "post", mock_post)


# Configuración de credenciales de prueba antes de los tests
@pytest.fixture(autouse=True)
def setup_test_sunat_credentials():
    sunat_service._token_cache.clear()
    settings.SUNAT_DAIRA_CLIENT_ID = "daira-client-id-test"
    settings.SUNAT_DAIRA_CLIENT_SECRET = "daira-client-secret-test"
    settings.SUNAT_DAIRA_SOL_USER = None
    settings.SUNAT_DAIRA_SOL_PASSWORD = None

    settings.SUNAT_JJD_CLIENT_ID = "jjd-client-id-test"
    settings.SUNAT_JJD_CLIENT_SECRET = "jjd-client-secret-test"
    settings.SUNAT_JJD_SOL_USER = None
    settings.SUNAT_JJD_SOL_PASSWORD = None

    yield

    sunat_service._token_cache.clear()


async def get_auth_token(client: AsyncClient, email: str) -> str:
    """Helper para autenticar un usuario y obtener su JWT."""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert res.status_code == 200, f"Login falló: {res.text}"
    return res.json()["access_token"]


SAMPLE_CPE_DATA = {
    "num_ruc": "20103134065",
    "cod_comp": "01",
    "numero_serie": "F006",
    "numero": "0053117",
    "fecha_emision": "01/09/2026",
    "monto": "387.23"
}


# ==============================================================================
# TEST 1: Validar sin JWT -> Rechazado con 401
# ==============================================================================
@pytest.mark.asyncio
async def test_validar_sin_jwt_rechazado(client: AsyncClient):
    response = await client.post("/api/v1/sunat/validar", json=SAMPLE_CPE_DATA)
    assert response.status_code == 401
    assert "No se proporcionaron credenciales" in response.json()["detail"]


# ==============================================================================
# TEST 2 & 7: Contador DAIRA resuelve DAIRA (RUC 20538976815 en URL)
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_daira_resuelve_daira(client: AsyncClient, monkeypatch):
    captured_urls = []

    def handler(url: str, kwargs: dict):
        captured_urls.append(url)
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "token-daira-test", "expires_in": 3600}, request=Request("POST", url))
        if "validarcomprobante" in url:
            return Response(200, json={
                "success": True,
                "data": {"estadoCp": "1", "estadoRuc": "00", "condDomiRuc": "00", "observaciones": []}
            }, request=Request("POST", url))
        return Response(404, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "VALIDO"
    assert data["empresa_consultora"]["ruc"] == "20538976815"
    assert data["empresa_consultora"]["razon_social"] == "DAIRA"

    # Verificar que la URL de consulta usó el RUC de DAIRA
    validation_call = [u for u in captured_urls if "validarcomprobante" in u][0]
    assert "20538976815/validarcomprobante" in validation_call
    assert "20612689831" not in validation_call


# ==============================================================================
# TEST 3 & 7: Contador JJD resuelve JJD (RUC 20612689831 en URL)
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_jjd_resuelve_jjd(client: AsyncClient, monkeypatch):
    captured_urls = []

    def handler(url: str, kwargs: dict):
        captured_urls.append(url)
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "token-jjd-test", "expires_in": 3600}, request=Request("POST", url))
        if "validarcomprobante" in url:
            return Response(200, json={
                "success": True,
                "data": {"estadoCp": "1", "estadoRuc": "00", "condDomiRuc": "00", "observaciones": []}
            }, request=Request("POST", url))
        return Response(404, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_jjd = await get_auth_token(client, "contador.jjd@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_jjd}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "VALIDO"
    assert data["empresa_consultora"]["ruc"] == "20612689831"
    assert data["empresa_consultora"]["razon_social"] == "GRUPO JJD MAR"

    # Verificar que la URL de consulta usó el RUC de JJD
    validation_call = [u for u in captured_urls if "validarcomprobante" in u][0]
    assert "20612689831/validarcomprobante" in validation_call
    assert "20538976815" not in validation_call


# ==============================================================================
# TEST 4, 5 & 20: Aislamiento estricto de credenciales DAIRA y JJD
# ==============================================================================
@pytest.mark.asyncio
async def test_daira_cannot_use_jjd_credentials_even_with_manipulation(client: AsyncClient, monkeypatch):
    """Un contador DAIRA que intente inyectar cabeceras o parámetros para usar JJD es forzado a DAIRA."""
    captured_auth_data = []

    def handler(url: str, kwargs: dict):
        if "oauth2/token" in url:
            captured_auth_data.append(kwargs.get("data", {}))
            return Response(200, json={"access_token": "token-daira", "expires_in": 3600}, request=Request("POST", url))
        return Response(200, json={"data": {"estadoCp": "1", "estadoRuc": "00", "condDomiRuc": "00"}}, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")

    # Intento de manipulación con X-Empresa-Id apuntando a otra empresa
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={
            "Authorization": f"Bearer {token_daira}",
            "X-Empresa-Id": "2"  # ID de JJD
        },
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 200
    # Las credenciales usadas deben haber sido estrictamente las de DAIRA
    assert captured_auth_data[0]["client_id"] == "daira-client-id-test"
    assert captured_auth_data[0]["client_secret"] == "daira-client-secret-test"
    assert captured_auth_data[0]["grant_type"] == "client_credentials"
    assert captured_auth_data[0]["scope"] == settings.SUNAT_AUTH_SCOPE
    assert "username" not in captured_auth_data[0]
    assert "password" not in captured_auth_data[0]


# ==============================================================================
# TEST 6 & 8: Body enviado a SUNAT correcto y numRuc corresponde al emisor
# ==============================================================================
@pytest.mark.asyncio
async def test_body_enviado_a_sunat_correcto(client: AsyncClient, monkeypatch):
    captured_body = {}

    def handler(url: str, kwargs: dict):
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "token-xyz", "expires_in": 3600}, request=Request("POST", url))
        if "validarcomprobante" in url:
            captured_body.update(kwargs.get("json", {}))
            return Response(200, json={"data": {"estadoCp": "1", "estadoRuc": "00", "condDomiRuc": "00"}}, request=Request("POST", url))
        return Response(404, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json={
            "num_ruc": "20501234567",
            "cod_comp": "01",
            "numero_serie": "f001",  # Debe normalizarse a F001
            "numero": "1234",
            "fecha_emision": "2026-10-15",
            "monto": "1500.5"
        }
    )

    assert captured_body["numRuc"] == "20501234567"
    assert captured_body["codComp"] == "01"
    assert captured_body["numeroSerie"] == "F001"
    assert captured_body["numero"] == "1234"
    assert captured_body["fechaEmision"] == "15/10/2026"
    assert captured_body["monto"] == "1500.50"


# ==============================================================================
# TEST 9, 10 & 11: Token obtención, reutilización en caché y renovación al expirar
# ==============================================================================
@pytest.mark.asyncio
async def test_token_lifecycle_cache_and_expiration():
    auth_requests = 0

    class MockClient:
        async def post(self, url, *args, **kwargs):
            nonlocal auth_requests
            auth_requests += 1
            return Response(200, json={"access_token": f"token-{auth_requests}", "expires_in": 3600}, request=Request("POST", str(url)))

    mock_c = MockClient()

    # 1. Obtener token por primera vez
    t1 = await sunat_service.get_access_token("20538976815", client=mock_c)
    assert t1 == "token-1"
    assert auth_requests == 1

    # 2. Reutilización: la segunda llamada debe devolver de caché sin nueva petición
    t2 = await sunat_service.get_access_token("20538976815", client=mock_c)
    assert t2 == "token-1"
    assert auth_requests == 1

    # 3. Forzar expiración del token en caché
    sunat_service._token_cache["20538976815"] = CachedToken(access_token="token-old", expires_at=time.time() - 10)

    # 4. Debe solicitar uno nuevo
    t3 = await sunat_service.get_access_token("20538976815", client=mock_c)
    assert t3 == "token-2"
    assert auth_requests == 2


# ==============================================================================
# TEST 12 & 13: HTTP 401 invalida token y reintenta exactamente una vez
# ==============================================================================
@pytest.mark.asyncio
async def test_sunat_401_invalida_token_y_reintenta_una_vez(client: AsyncClient, monkeypatch):
    token_requests = 0
    validation_requests = 0

    def handler(url: str, kwargs: dict):
        nonlocal token_requests, validation_requests
        if "oauth2/token" in url:
            token_requests += 1
            return Response(200, json={"access_token": f"token-v{token_requests}", "expires_in": 3600}, request=Request("POST", url))
        if "validarcomprobante" in url:
            validation_requests += 1
            if validation_requests == 1:
                # El primer intento responde 401 (token revocado en SUNAT)
                return Response(401, json={"error": "invalid_token"}, request=Request("POST", url))
            else:
                # El reintento tiene éxito
                return Response(200, json={"data": {"estadoCp": "1", "estadoRuc": "00", "condDomiRuc": "00"}}, request=Request("POST", url))
        return Response(404, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 200
    assert response.json()["estado"] == "VALIDO"
    assert token_requests == 2  # Token inicial + nuevo token tras 401
    assert validation_requests == 2  # Exactamente 1 intento + 1 reintento


# ==============================================================================
# TEST 14: Timeout controlado
# ==============================================================================
@pytest.mark.asyncio
async def test_sunat_timeout_controlado(client: AsyncClient, monkeypatch):
    def handler(url: str, kwargs: dict):
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "token-test", "expires_in": 3600}, request=Request("POST", url))
        return httpx.TimeoutException("Connection timed out", request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 504
    assert "Tiempo de espera agotado" in response.json()["detail"]


# ==============================================================================
# TEST 15: HTTP 500 de SUNAT controlado
# ==============================================================================
@pytest.mark.asyncio
async def test_sunat_http_500_controlado(client: AsyncClient, monkeypatch):
    def handler(url: str, kwargs: dict):
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "token-test", "expires_in": 3600}, request=Request("POST", url))
        if "validarcomprobante" in url:
            return Response(500, json={"cod": "0100", "msg": "Error interno del servidor SUNAT"}, request=Request("POST", url))
        return Response(404, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "ERROR"
    assert "Error devuelto por SUNAT" in data["mensaje_sunat"]


# ==============================================================================
# TEST 16: Credenciales faltantes controladas
# ==============================================================================
@pytest.mark.asyncio
async def test_credenciales_faltantes_controladas(client: AsyncClient):
    settings.SUNAT_DAIRA_CLIENT_ID = None  # Desconfigurar DAIRA

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 500
    assert "Credenciales SUNAT incompletas" in response.json()["detail"]


# ==============================================================================
# TEST 17 & 18: Comprobante válido vs no válido (Interpretación funcional)
# ==============================================================================
@pytest.mark.asyncio
async def test_interpretacion_comprobante_valido_y_no_valido(client: AsyncClient, monkeypatch):
    estado_mock = "1"
    cond_domi_mock = "00"

    def handler(url: str, kwargs: dict):
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "tok", "expires_in": 3600}, request=Request("POST", url))
        return Response(200, json={
            "data": {
                "estadoCp": estado_mock,
                "estadoRuc": "00",
                "condDomiRuc": cond_domi_mock,
                "observaciones": []
            }
        }, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")

    # 1. Comprobante Válido (estadoCp = 1, estadoRuc = 00, condDomiRuc = 00)
    estado_mock = "1"
    cond_domi_mock = "00"
    res1 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res1.json()["estado"] == "VALIDO"
    assert "ACEPTADO" in res1.json()["mensaje_sunat"]

    # 2. Comprobante No Válido - No existe en registros (estadoCp = 0)
    estado_mock = "0"
    res2 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res2.json()["estado"] == "NO_VALIDO"
    assert "NO EXISTE" in res2.json()["mensaje_sunat"]

    # 3. Comprobante No Válido - Anulado (estadoCp = 2)
    estado_mock = "2"
    res3 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res3.json()["estado"] == "NO_VALIDO"
    assert "ANULADO" in res3.json()["mensaje_sunat"]

    # 4. Comprobante No Válido - No autorizado por imprenta (estadoCp = 4)
    estado_mock = "4"
    res4 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res4.json()["estado"] == "NO_VALIDO"
    assert "NO AUTORIZADO" in res4.json()["mensaje_sunat"]

    # 5. Comprobante Observado - Físico Autorizado por imprenta (estadoCp = 3)
    estado_mock = "3"
    res5 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res5.json()["estado"] == "OBSERVADO"
    assert "AUTORIZADO" in res5.json()["mensaje_sunat"]

    # 6. Comprobante Observado - Aceptado pero contribuyente NO HABIDO (condDomiRuc = 12 código oficial)
    estado_mock = "1"
    cond_domi_mock = "12"  # Código oficial SUNAT para NO HABIDO
    res6 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res6.json()["estado"] == "OBSERVADO"
    assert "NO HABIDO" in res6.json()["mensaje_sunat"]

    # 7. Comprobante Observado - Código no catalogado por SUNAT (ej. estadoCp = 99)
    # Por seguridad el backend no inventa ni asume que es válido ni no válido: se clasifica OBSERVADO conservando el código
    estado_mock = "99"
    cond_domi_mock = "00"
    res7 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res7.json()["estado"] == "OBSERVADO"
    assert "no catalogado oficialmente" in res7.json()["mensaje_sunat"]
    assert res7.json()["codigo_sunat"] == "99"

    # 8. Error funcional retornado por SUNAT (success = False con errorCode)
    def handler_err(url: str, kwargs: dict):
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "tok", "expires_in": 3600}, request=Request("POST", url))
        return Response(200, json={
            "success": False,
            "message": "El RUC consultado no coincide con el emisor",
            "errorCode": "ERR_RUC_MISMATCH"
        }, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler_err)
    res8 = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    assert res8.json()["estado"] == "ERROR"
    assert res8.json()["codigo_sunat"] == "ERR_RUC_MISMATCH"
    assert "SUNAT reportó error en la consulta" in res8.json()["mensaje_sunat"]


# ==============================================================================
# TEST 19 & 20: Consulta guardada en BD y aislamiento en consultas_cpe
# ==============================================================================
@pytest.mark.asyncio
async def test_consulta_guardada_en_bd_con_tenancy(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    def handler(url: str, kwargs: dict):
        if "oauth2/token" in url:
            return Response(200, json={"access_token": "tok", "expires_in": 3600}, request=Request("POST", url))
        return Response(200, json={"data": {"estadoCp": "1", "estadoRuc": "00", "condDomiRuc": "00"}}, request=Request("POST", url))

    patch_sunat_calls(monkeypatch, handler)

    token_daira = await get_auth_token(client, "contador.daira@test.local")
    res = await client.post("/api/v1/sunat/validar", headers={"Authorization": f"Bearer {token_daira}"}, json=SAMPLE_CPE_DATA)
    consulta_id = res.json()["id"]

    # Verificar directamente en la base de datos
    stmt = select(ConsultaCPE).where(ConsultaCPE.id == consulta_id)
    result = await db_session.execute(stmt)
    consulta_db = result.scalar_one_or_none()

    assert consulta_db is not None
    assert consulta_db.ruc_emisor == "20103134065"
    assert consulta_db.serie == "F006"
    assert consulta_db.numero == "0053117"
    assert consulta_db.estado == "VALIDO"

    # Verificar pertenencia a DAIRA (empresa_id = 1)
    stmt_empresa = select(Empresa).where(Empresa.ruc == "20538976815")
    empresa_daira = (await db_session.execute(stmt_empresa)).scalar_one()
    assert consulta_db.empresa_id == empresa_daira.id


# ==============================================================================
# TEST 21: Administrador sin empresa rechaza la consulta controladamente
# ==============================================================================
@pytest.mark.asyncio
async def test_administrador_sin_empresa_rechaza_consulta(client: AsyncClient):
    token_admin = await get_auth_token(client, "admin@test.local")
    response = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=SAMPLE_CPE_DATA
    )

    assert response.status_code == 400
    assert "Debe tener una empresa asociada o seleccionada" in response.json()["detail"]


# ==============================================================================
# TEST 22: Validación de esquemas Pydantic (RUC inválido, montos negativos, etc.)
# ==============================================================================
@pytest.mark.asyncio
async def test_validaciones_pydantic_en_backend(client: AsyncClient):
    token_daira = await get_auth_token(client, "contador.daira@test.local")

    # RUC de longitud errónea
    res1 = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json={**SAMPLE_CPE_DATA, "num_ruc": "12345"}
    )
    assert res1.status_code == 422

    # Tipo de comprobante no soportado
    res2 = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json={**SAMPLE_CPE_DATA, "cod_comp": "99"}
    )
    assert res2.status_code == 422

    # Monto negativo
    res3 = await client.post(
        "/api/v1/sunat/validar",
        headers={"Authorization": f"Bearer {token_daira}"},
        json={**SAMPLE_CPE_DATA, "monto": "-50.00"}
    )
    assert res3.status_code == 422


# ==============================================================================
# TEST 23: OAuth2 client_credentials token request format, url, body & headers
# ==============================================================================
@pytest.mark.asyncio
async def test_oauth2_token_request_format_and_params():
    """
    Verifica que la solicitud de token OAuth2 cumpla exactamente con la especificación de SUNAT:
    POST https://api-seguridad.sunat.gob.pe/v1/clientesextranet/{CLIENT_ID}/oauth2/token/
    Content-Type: application/x-www-form-urlencoded
    grant_type=client_credentials
    scope=https://api.sunat.gob.pe/v1/contribuyente/contribuyentes
    client_id={CLIENT_ID}
    client_secret={CLIENT_SECRET}
    Sin requerir ni enviar SOL_USER ni SOL_PASSWORD.
    """
    captured = {}

    class MockClient:
        async def post(self, url, *args, **kwargs):
            captured["url"] = str(url)
            captured["headers"] = kwargs.get("headers", {})
            captured["data"] = kwargs.get("data", {})
            return Response(
                200,
                json={"access_token": "token-oauth2-valido", "expires_in": 3600},
                request=Request("POST", str(url))
            )

    sunat_service.invalidate_token("20538976815")
    mock_c = MockClient()

    token = await sunat_service.get_access_token("20538976815", client=mock_c)

    assert token == "token-oauth2-valido"
    # URL esperada con CLIENT_ID interpolado en el path
    assert captured["url"] == "https://api-seguridad.sunat.gob.pe/v1/clientesextranet/daira-client-id-test/oauth2/token/"
    # Header application/x-www-form-urlencoded
    assert captured["headers"].get("Content-Type") == "application/x-www-form-urlencoded"
    # Campos obligatorios del body
    assert captured["data"]["grant_type"] == "client_credentials"
    assert captured["data"]["scope"] == "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes"
    assert captured["data"]["client_id"] == "daira-client-id-test"
    assert captured["data"]["client_secret"] == "daira-client-secret-test"
    # Asegurar que NO se exige ni envía SOL_USER ni SOL_PASSWORD
    assert "username" not in captured["data"]
    assert "password" not in captured["data"]
    assert "sol_user" not in captured["data"]
    assert "sol_password" not in captured["data"]


# ==============================================================================
# TEST 24: Generación de token funciona sin SOL_USER ni SOL_PASSWORD
# ==============================================================================
@pytest.mark.asyncio
async def test_oauth2_token_generation_without_sol_user_and_sol_password():
    """Verifica explícitamente que con SOL_USER y SOL_PASSWORD nulos o ausentes, el token se genera con éxito."""
    settings.SUNAT_DAIRA_SOL_USER = None
    settings.SUNAT_DAIRA_SOL_PASSWORD = None
    settings.SUNAT_JJD_SOL_USER = None
    settings.SUNAT_JJD_SOL_PASSWORD = None

    class MockClient:
        async def post(self, url, *args, **kwargs):
            return Response(
                200,
                json={"access_token": "token-sin-sol", "expires_in": 1800},
                request=Request("POST", str(url))
            )

    sunat_service.invalidate_token("20538976815")
    token_daira = await sunat_service.get_access_token("20538976815", client=MockClient())
    assert token_daira == "token-sin-sol"

    sunat_service.invalidate_token("20612689831")
    token_jjd = await sunat_service.get_access_token("20612689831", client=MockClient())
    assert token_jjd == "token-sin-sol"


# ==============================================================================
# TEST 25: Falla controlada si faltan client_id o client_secret
# ==============================================================================
def test_credenciales_faltantes_lanza_error():
    """Si falta client_id o client_secret, se lanza SunatCredentialsError."""
    settings.SUNAT_DAIRA_CLIENT_ID = None
    with pytest.raises(SunatCredentialsError) as exc_info:
        sunat_service.get_credentials_for_empresa("20538976815")
    assert "Credenciales SUNAT incompletas" in str(exc_info.value)

    settings.SUNAT_DAIRA_CLIENT_ID = "daira-client-id-test"
    settings.SUNAT_DAIRA_CLIENT_SECRET = ""
    with pytest.raises(SunatCredentialsError) as exc_info2:
        sunat_service.get_credentials_for_empresa("20538976815")
    assert "Credenciales SUNAT incompletas" in str(exc_info2.value)

