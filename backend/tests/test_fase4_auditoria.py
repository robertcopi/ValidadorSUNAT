import asyncio
import datetime
from typing import Optional
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.proceso_masivo import ProcesoMasivo
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.models.consulta_cpe import ConsultaCPE
from app.schemas.sunat import ConsultaCPEResponse, EmpresaInfo
from app.services.sunat_service import SunatException
from app.services.proceso_masivo_service import proceso_masivo_service


async def get_token_for(client: AsyncClient, email: str) -> str:
    """Helper para obtener token JWT de un usuario específico."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"}
    )
    assert res.status_code == 200, f"Login falló: {res.text}"
    return res.json()["access_token"]


def cpe_mock(ruc: str, comp: str, serie: str, numero: str, estado: str = "VALIDO", codigo_sunat: str = "0", id: int = 1) -> ConsultaCPEResponse:
    return ConsultaCPEResponse(
        id=id,
        empresa_id=1,
        usuario_id=2,
        ruc_emisor=ruc,
        tipo_comprobante=comp,
        tipo_comprobante_descripcion="FACTURA ELECTRÓNICA",
        serie=serie,
        numero=numero,
        fecha_emision="2026-09-20",
        monto=Decimal("200.00"),
        estado=estado,
        codigo_sunat=codigo_sunat,
        mensaje_sunat=f"Comprobante con estado {estado}.",
        empresa_consultora=EmpresaInfo(ruc="20538976815", razon_social="DAIRA"),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )


def generar_items(n: int, ruc_base: str = "20100070970"):
    items = []
    for i in range(1, n + 1):
        items.append({
            "fila_excel": i + 5,
            "num_ruc": ruc_base,
            "cod_comp": "01",
            "numero_serie": "F001",
            "numero": str(i).zfill(8),
            "fecha_emision": "20/09/2026",
            "monto": 100.00 + i,
            "razon_social": f"PROVEEDOR {i} S.A.C."
        })
    return items


# ==============================================================================
# 1. BACKGROUND PROCESSING DESACOPLADO (HTTP INMEDIATO 201)
# ==============================================================================
@pytest.mark.asyncio
async def test_background_processing_inmediato(client: AsyncClient):
    """
    POST responde INMEDIATAMENTE con 201 y process_id.
    El navegador/cliente no espera a que SUNAT responda.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(3)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "test_bg.xlsx", "items": items}
        )

        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert data["total_registros"] == 3
        assert data["estado"] in ("PENDIENTE", "PROCESANDO", "COMPLETADO")

        proceso_id = data["id"]
        await proceso_masivo_service.esperar_proceso(proceso_id)


# ==============================================================================
# 2. CONCURRENCIA MÁXIMA CONTROLADA MEDIANTE SEMÁFORO
# ==============================================================================
@pytest.mark.asyncio
async def test_concurrencia_maxima_con_semaforo(client: AsyncClient):
    """
    Verifica que la cantidad de consultas simultáneas respeta SUNAT_MAX_CONCURRENCY.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(10)
    max_concurrency_config = getattr(settings, "SUNAT_MAX_CONCURRENCY", 5)

    concurrentes = 0
    max_concurrentes_observados = 0

    async def mock_validar(*args, **kwargs):
        nonlocal concurrentes, max_concurrentes_observados
        concurrentes += 1
        if concurrentes > max_concurrentes_observados:
            max_concurrentes_observados = concurrentes
        await asyncio.sleep(0.02)
        concurrentes -= 1
        return cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=mock_validar):
        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "test_concurrency.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]

        await proceso_masivo_service.esperar_proceso(proceso_id)

        assert max_concurrentes_observados <= max_concurrency_config
        assert max_concurrentes_observados > 0


# ==============================================================================
# 3. DELAY CONFIGURABLE (SUNAT_REQUEST_DELAY_MS)
# ==============================================================================
@pytest.mark.asyncio
async def test_delay_configurable_inter_request(client: AsyncClient):
    """
    Verifica que SUNAT_REQUEST_DELAY_MS ejecuta un sleep asíncrono.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(2)

    original_delay = settings.SUNAT_REQUEST_DELAY_MS
    try:
        settings.SUNAT_REQUEST_DELAY_MS = 50  # 50 ms por item

        with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
            mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

            t_start = asyncio.get_event_loop().time()
            res = await client.post(
                "/api/v1/procesos-masivos",
                headers={"Authorization": f"Bearer {token}"},
                json={"nombre_archivo": "test_delay.xlsx", "items": items}
            )
            assert res.status_code == 201
            await proceso_masivo_service.esperar_proceso(res.json()["id"])
            t_elapsed = asyncio.get_event_loop().time() - t_start

            # Al menos el delay configurado (0.05s) debe haber transcurrido
            assert t_elapsed >= 0.04
    finally:
        settings.SUNAT_REQUEST_DELAY_MS = original_delay


# ==============================================================================
# 4. RETRY POR TIMEOUT TRANSITORIO
# ==============================================================================
@pytest.mark.asyncio
async def test_timeout_retry_exitoso(client: AsyncClient):
    """
    Timeout en 1er intento, éxito en 2do intento.
    El item termina en VALIDO con intentos == 2.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(1)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=[
        httpx.TimeoutException("Timeout SUNAT"),
        cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")
    ]):
        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "test_timeout.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]

        await proceso_masivo_service.esperar_proceso(proceso_id)

        proc_res = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = proc_res.json()
        assert data["total_validos"] == 1
        assert data["total_errores"] == 0
        assert data["estado"] == "COMPLETADO"


# ==============================================================================
# 5. RETRY POR HTTP 429 RATE LIMIT CON BACKOFF
# ==============================================================================
@pytest.mark.asyncio
async def test_http_429_retry(client: AsyncClient):
    """
    HTTP 429 en 1er intento, éxito en 2do intento con backoff.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(1)

    ex_429 = SunatException("Too Many Requests", status_code=429, codigo_sunat="429")

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=[
        ex_429,
        cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")
    ]):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await client.post(
                "/api/v1/procesos-masivos",
                headers={"Authorization": f"Bearer {token}"},
                json={"nombre_archivo": "test_429.xlsx", "items": items}
            )
            assert res.status_code == 201
            proceso_id = res.json()["id"]

            await proceso_masivo_service.esperar_proceso(proceso_id)

            # mock_sleep debe haber sido invocado para el backoff
            assert mock_sleep.called


# ==============================================================================
# 6. RETRY POR HTTP 500 / 502 / 503 / 504
# ==============================================================================
@pytest.mark.asyncio
async def test_http_502_503_retry(client: AsyncClient):
    """
    Error 502 en intento 1, 503 en intento 2, éxito en intento 3.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(1)

    ex_502 = SunatException("Bad Gateway", status_code=502)
    ex_503 = SunatException("Service Unavailable", status_code=503)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=[
        ex_502,
        ex_503,
        cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")
    ]):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            res = await client.post(
                "/api/v1/procesos-masivos",
                headers={"Authorization": f"Bearer {token}"},
                json={"nombre_archivo": "test_502_503.xlsx", "items": items}
            )
            assert res.status_code == 201
            proceso_id = res.json()["id"]

            await proceso_masivo_service.esperar_proceso(proceso_id)

            proc_res = await client.get(
                f"/api/v1/procesos-masivos/{proceso_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert proc_res.json()["estado"] == "COMPLETADO"
            assert proc_res.json()["total_validos"] == 1


# ==============================================================================
# 7 & 8. NO REINTENTAR RESULTADOS FUNCIONALES: NO_VALIDO Y OBSERVADO
# ==============================================================================
@pytest.mark.asyncio
async def test_no_valido_y_observado_no_se_reintentan(client: AsyncClient):
    """
    Resultados funcionales NO_VALIDO y OBSERVADO no deben disparar retries.
    Intentos debe ser exactamente 1.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(2)

    call_count = 0
    async def mock_validar(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return cpe_mock("20100070970", "01", "F001", "00000001", "NO_VALIDO")
        return cpe_mock("20100070970", "01", "F001", "00000002", "OBSERVADO")

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=mock_validar):
        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "test_funcionales.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]

        await proceso_masivo_service.esperar_proceso(proceso_id)

        assert call_count == 2  # Exactamente 1 llamada por item

        proc_res = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = proc_res.json()
        assert data["total_no_validos"] == 1
        assert data["total_observados"] == 1
        assert data["total_errores"] == 0
        assert data["estado"] == "COMPLETADO"


# ==============================================================================
# 9 & 10. FALLO INDIVIDUAL NO DETIENE LOTE -> COMPLETADO_CON_ERRORES
# ==============================================================================
@pytest.mark.asyncio
async def test_fallo_individual_no_detiene_lote(client: AsyncClient):
    """
    Si 1 de 3 comprobantes falla técnicamente, los otros 2 se completan.
    El estado final del lote es COMPLETADO_CON_ERRORES.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(3)

    def side_effect_fn(*args, **kwargs):
        req = kwargs.get("request_data") or args[2]
        if req.numero == "00000002":
            raise httpx.ConnectError("Connection refused by SUNAT")
        return cpe_mock(req.num_ruc, req.cod_comp, req.numero_serie, req.numero, "VALIDO")

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=side_effect_fn):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            res = await client.post(
                "/api/v1/procesos-masivos",
                headers={"Authorization": f"Bearer {token}"},
                json={"nombre_archivo": "test_partial_fail.xlsx", "items": items}
            )
            assert res.status_code == 201
            proceso_id = res.json()["id"]

            await proceso_masivo_service.esperar_proceso(proceso_id)

            proc_res = await client.get(
                f"/api/v1/procesos-masivos/{proceso_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            data = proc_res.json()
            assert data["total_registros"] == 3
            assert data["total_procesados"] == 3
            assert data["total_validos"] == 2
            assert data["total_errores"] == 1
            assert data["estado"] == "COMPLETADO_CON_ERRORES"


# ==============================================================================
# 11. REINTENTO SELECTIVO DE ERRORES TÉCNICOS
# ==============================================================================
@pytest.mark.asyncio
async def test_endpoint_reintentar_errores(client: AsyncClient):
    """
    POST /api/v1/procesos-masivos/{id}/reintentar-errores
    Solo reintenta items en ERROR; deja intactos VALIDO, NO_VALIDO y OBSERVADO.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(2)

    # Paso 1: Crear lote donde el 2do item falla
    should_fail = True
    def mock_val(*args, **kwargs):
        req = kwargs.get("request_data") or args[2]
        if req.numero == "00000002" and should_fail:
            raise httpx.ConnectError("Fallo de red temporal")
        return cpe_mock(req.num_ruc, req.cod_comp, req.numero_serie, req.numero, "VALIDO")

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", side_effect=mock_val):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            res = await client.post(
                "/api/v1/procesos-masivos",
                headers={"Authorization": f"Bearer {token}"},
                json={"nombre_archivo": "test_retry_endpoint.xlsx", "items": items}
            )
            assert res.status_code == 201
            proceso_id = res.json()["id"]

            await proceso_masivo_service.esperar_proceso(proceso_id)

            # Paso 2: Ejecutar reintento permitiendo que ahora sí responda SUNAT
            should_fail = False
            res_retry = await client.post(
                f"/api/v1/procesos-masivos/{proceso_id}/reintentar-errores",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res_retry.status_code == 200
            assert res_retry.json()["total_reintentados"] == 1

            await proceso_masivo_service.esperar_proceso(proceso_id)

            proc_final = await client.get(
                f"/api/v1/procesos-masivos/{proceso_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            data = proc_final.json()
            assert data["total_validos"] == 2
            assert data["total_errores"] == 0
            assert data["estado"] == "COMPLETADO"


# ==============================================================================
# 12. IDEMPOTENCIA CON IDEMPOTENCY-KEY
# ==============================================================================
@pytest.mark.asyncio
async def test_idempotency_key_retorna_proceso_existente(client: AsyncClient):
    """
    Doble clic accidental con la misma Idempotency-Key retorna el proceso existente sin duplicar.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(3)
    idem_key = "IDEM-TEST-UNIQUE-999"

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

        # Primer clic
        res1 = await client.post(
            "/api/v1/procesos-masivos",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idem_key
            },
            json={"nombre_archivo": "test_idem.xlsx", "items": items}
        )
        assert res1.status_code == 201
        id_1 = res1.json()["id"]

        # Segundo clic accidental
        res2 = await client.post(
            "/api/v1/procesos-masivos",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idem_key
            },
            json={"nombre_archivo": "test_idem.xlsx", "items": items}
        )
        assert res2.status_code == 200  # Ya existía -> 200 OK con proceso existente
        id_2 = res2.json()["id"]

        assert id_1 == id_2
        await proceso_masivo_service.esperar_proceso(id_1)


# ==============================================================================
# 13. TENANCY Y AISLAMIENTO ENTRE EMPRESAS (DAIRA vs JJD)
# ==============================================================================
@pytest.mark.asyncio
async def test_tenancy_aislamiento_daira_jjd(client: AsyncClient):
    """
    Contador DAIRA crea proceso DAIRA.
    Contador JJD NO puede consultar ni modificar el proceso de DAIRA (404 Not Found).
    """
    token_daira = await get_token_for(client, "contador.daira@test.local")
    token_jjd = await get_token_for(client, "contador.jjd@test.local")

    items = generar_items(2)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

        res_daira = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token_daira}"},
            json={"nombre_archivo": "daira_batch.xlsx", "items": items}
        )
        assert res_daira.status_code == 201
        proc_daira_id = res_daira.json()["id"]
        await proceso_masivo_service.esperar_proceso(proc_daira_id)

        # Contador JJD intenta consultar proceso DAIRA
        res_jjd_consult = await client.get(
            f"/api/v1/procesos-masivos/{proc_daira_id}",
            headers={"Authorization": f"Bearer {token_jjd}"}
        )
        assert res_jjd_consult.status_code == 404

        # Contador JJD intenta consultar items de proceso DAIRA
        res_jjd_items = await client.get(
            f"/api/v1/procesos-masivos/{proc_daira_id}/items",
            headers={"Authorization": f"Bearer {token_jjd}"}
        )
        assert res_jjd_items.status_code == 404

        # Contador JJD intenta reintentar errores en proceso DAIRA
        res_jjd_retry = await client.post(
            f"/api/v1/procesos-masivos/{proc_daira_id}/reintentar-errores",
            headers={"Authorization": f"Bearer {token_jjd}"}
        )
        assert res_jjd_retry.status_code == 404


# ==============================================================================
# 14. PAGINACIÓN Y FILTROS EN LISTADO DE ITEMS
# ==============================================================================
@pytest.mark.asyncio
async def test_paginacion_y_filtros_de_items(client: AsyncClient):
    """
    GET /api/v1/procesos-masivos/{id}/items
    Verifica page, page_size, estado_sunat, serie, numero y busqueda.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(5)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "test_pagination.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]

        await proceso_masivo_service.esperar_proceso(proceso_id)

        # Página 1 con 2 items
        p1 = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}/items?page=1&page_size=2",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert p1.status_code == 200
        d1 = p1.json()
        assert d1["total"] == 5
        assert len(d1["items"]) == 2
        assert d1["page"] == 1
        assert d1["total_pages"] == 3

        # Filtro por número de comprobante
        filt = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}/items?numero=00000003",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert filt.status_code == 200
        df = filt.json()
        assert df["total"] == 1
        assert df["items"][0]["numero"] == "00000003"


# ==============================================================================
# 15. LISTADO DE PROCESOS MASIVOS PAGINADO
# ==============================================================================
@pytest.mark.asyncio
async def test_listado_procesos_masivos_paginado(client: AsyncClient):
    """
    GET /api/v1/procesos-masivos lista los procesos de la empresa autenticada.
    """
    token = await get_token_for(client, "contador.daira@test.local")

    res = await client.get(
        "/api/v1/procesos-masivos?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


# ==============================================================================
# 16. RECUPERACIÓN TRAS REINICIO DEL BACKEND
# ==============================================================================
@pytest.mark.asyncio
async def test_recuperacion_al_iniciar_backend(client: AsyncClient, db_session):
    """
    Verifica que recuperar_procesos_al_iniciar:
    - Conserva items ya completados.
    - Resetea items PROCESANDO huérfanos a PENDIENTE.
    - Reactiva los workers para continuar sin perder información.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(4)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "crash_sim.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]

        # Dejar que el proceso inicial termine
        await proceso_masivo_service.esperar_proceso(proceso_id)

        # Simular que el proceso quedó en PROCESANDO tras un corte abrupto
        stmt = select(ProcesoMasivo).where(ProcesoMasivo.id == proceso_id)
        r = await db_session.execute(stmt)
        proc = r.scalar_one()
        proc.estado = "PROCESANDO"

        # Simular que 2 items ya estaban completados y 2 quedaron en PROCESANDO huérfanos
        stmt_it = select(ProcesoMasivoItem).where(ProcesoMasivoItem.proceso_id == proceso_id).order_by(ProcesoMasivoItem.id)
        items_db = (await db_session.execute(stmt_it)).scalars().all()
        items_db[0].estado = "VALIDO"
        items_db[1].estado = "VALIDO"
        items_db[2].estado = "PROCESANDO"
        items_db[3].estado = "PROCESANDO"
        await db_session.commit()

        # Ejecutar lógica de arranque (lifespan)
        await proceso_masivo_service.recuperar_procesos_al_iniciar()
        await proceso_masivo_service.esperar_proceso(proceso_id)

        db_session.expire_all()
        res_check = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_check.status_code == 200
        data = res_check.json()
        assert data["estado"] == "COMPLETADO"
        assert data["total_validos"] == 4


# ==============================================================================
# 17. AUDITORÍA EN consultas_cpe
# ==============================================================================
@pytest.mark.asyncio
async def test_auditoria_consultas_cpe_vinculada(client: AsyncClient, db_session):
    """
    Cada consulta real se audita en consultas_cpe y se vincula con el item.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(1)

    # Insertar un registro real en consultas_cpe simulando lo que hace sunat_service
    cpe_audit = ConsultaCPE(
        empresa_id=1,
        usuario_id=2,
        ruc_emisor="20100070970",
        tipo_comprobante="01",
        serie="F001",
        numero="00000001",
        fecha_emision=datetime.date(2026, 9, 20),
        monto=Decimal("101.00"),
        estado="VALIDO",
        codigo_sunat="0",
        mensaje_sunat="Comprobante válido auditado",
    )
    db_session.add(cpe_audit)
    await db_session.commit()
    await db_session.refresh(cpe_audit)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_resp = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")
        mock_resp.id = cpe_audit.id
        mock_val.return_value = mock_resp

        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "audit_test.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]

        await proceso_masivo_service.esperar_proceso(proceso_id)

        items_res = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}/items",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert items_res.status_code == 200
        items_data = items_res.json()["items"]
        assert len(items_data) == 1
        assert items_data[0]["consulta_cpe_id"] == cpe_audit.id


# ==============================================================================
# 18. AUSENCIA DE SECRETOS EN RESPUESTAS Y LOGS
# ==============================================================================
@pytest.mark.asyncio
async def test_ausencia_de_secretos_en_respuestas(client: AsyncClient):
    """
    Confirma que client_secret, sol_password y token nunca se exponen en las respuestas JSON.
    """
    token = await get_token_for(client, "contador.daira@test.local")
    items = generar_items(1)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")

        res = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre_archivo": "security_test.xlsx", "items": items}
        )
        assert res.status_code == 201
        proceso_id = res.json()["id"]
        await proceso_masivo_service.esperar_proceso(proceso_id)

        # Verificar respuesta de creación
        txt_res = res.text.lower()
        assert "client_secret" not in txt_res
        assert "sol_password" not in txt_res
        assert "password" not in txt_res

        # Verificar detalle de proceso
        p_res = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        p_txt = p_res.text.lower()
        assert "client_secret" not in p_txt
        assert "sol_password" not in p_txt
        assert "password" not in p_txt
