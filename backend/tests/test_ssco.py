import io
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

import httpx
import openpyxl
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.padron_ssco import PadronSSCO, PadronSSCOSincronizacion, ConsultaSSCO
from app.models.empresa import Empresa
from app.services.sunat_service import sunat_service


def generar_excel_ssco_bytes(
    filas=None,
    encabezados=None
) -> bytes:
    """Genera un archivo Excel .xlsx válido en memoria emulando el padrón oficial de SUNAT."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hoja1"

    if encabezados is None:
        encabezados = [
            "RUC",
            "Razón social",
            "Domicilio fiscal",
            "Resolución de atribución como SSCO",
            "Fecha de emisión de la resolución de atribución",
            "Fecha en la que la resolución de atribución quedó firme",
            "RUC o documento de identidad del representante legal (1)",
            "Apellidos y nombres del representante legal",
            "Fecha de publicación (2)"
        ]
    ws.append(encabezados)

    if filas is None:
        filas = [
            (
                "20601234567",
                "EMPRESA FRAUDULENTA EJEMPLO S.A.C.",
                "AV. LOS HEROES 123 - LIMA",
                "Resolución de Intendencia N.° 024-024-0012345/SUNAT",
                date(2026, 8, 15),
                date(2026, 8, 30),
                "10456789012",
                "PEREZ ALVAREZ JUAN",
                date(2026, 9, 30)
            ),
            (
                "10456789012",
                "PEREZ ALVAREZ JUAN CARLOS",
                "JR. HUANCAYO 456 - HUANCAYO",
                "Resolución de Intendencia N.° 194-024-0005432/SUNAT",
                date(2026, 8, 20),
                date(2026, 9, 5),
                "10456789012",
                "PEREZ ALVAREZ JUAN CARLOS",
                date(2026, 9, 30)
            )
        ]

    for f in filas:
        ws.append(list(f))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def obtener_tokens(client: AsyncClient):
    """Obtiene tokens JWT para ADMIN, CONTADOR DAIRA y CONTADOR JJD."""
    res_admin = await client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Password123!"})
    token_admin = res_admin.json()["access_token"]

    res_daira = await client.post("/api/v1/auth/login", json={"email": "contador.daira@test.local", "password": "Password123!"})
    token_daira = res_daira.json()["access_token"]

    res_jjd = await client.post("/api/v1/auth/login", json={"email": "contador.jjd@test.local", "password": "Password123!"})
    token_jjd = res_jjd.json()["access_token"]

    return token_admin, token_daira, token_jjd


# ==============================================================================
# TESTS 1 - 6: VALIDACIONES DE CONSULTA INDIVIDUAL POR RUC
# ==============================================================================

@pytest.mark.asyncio
async def test_01_ruc_encontrado(client: AsyncClient, db_session: AsyncSession):
    """1. RUC encontrado en el padrón local: devuelve 200, estado ENCONTRADO_SSCO, es_ssco=True y detalle."""
    token_admin, token_daira, _ = await obtener_tokens(client)

    # Cargar padrón con excel válido
    excel_bytes = generar_excel_ssco_bytes()
    upload_res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert upload_res.status_code == 200

    # Consultar RUC registrado
    res = await client.get(
        "/api/v1/ssco/consultar/20601234567",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ruc"] == "20601234567"
    assert data["estado"] == "ENCONTRADO_SSCO"
    assert data["es_ssco"] is True
    assert "RUC encontrado en el padrón de Sujetos Sin Capacidad Operativa" in data["mensaje"]
    assert "Requiere revisión contable" in data["mensaje"]
    assert data["razon_social"] == "EMPRESA FRAUDULENTA EJEMPLO S.A.C."
    assert "Resolución de Intendencia" in data["resolucion_atribucion"]
    assert data["fecha_publicacion"] == "30/09/2026"


@pytest.mark.asyncio
async def test_02_ruc_no_encontrado(client: AsyncClient, db_session: AsyncSession):
    """2. RUC no encontrado: devuelve 200, estado NO_ENCONTRADO, es_ssco=False sin lenguaje de falso positivo."""
    token_admin, token_daira, _ = await obtener_tokens(client)

    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    res = await client.get(
        "/api/v1/ssco/consultar/20999999999",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ruc"] == "20999999999"
    assert data["estado"] == "NO_ENCONTRADO"
    assert data["es_ssco"] is False
    assert data["mensaje"] == "El RUC no figura en el padrón SSCO consultado."
    assert "proveedor válido" not in data["mensaje"].lower()
    assert "sin riesgo" not in data["mensaje"].lower()


@pytest.mark.asyncio
async def test_03_ruc_menos_11_digitos(client: AsyncClient, db_session: AsyncSession):
    """3. RUC con menos de 11 dígitos: devuelve HTTP 400."""
    _, token_daira, _ = await obtener_tokens(client)
    res = await client.get(
        "/api/v1/ssco/consultar/1234567890",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 400
    assert "11 dígitos" in res.json()["detail"]


@pytest.mark.asyncio
async def test_04_ruc_mas_11_digitos(client: AsyncClient, db_session: AsyncSession):
    """4. RUC con más de 11 dígitos: devuelve HTTP 400."""
    _, token_daira, _ = await obtener_tokens(client)
    res = await client.get(
        "/api/v1/ssco/consultar/123456789012",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 400
    assert "11 dígitos" in res.json()["detail"]


@pytest.mark.asyncio
async def test_05_ruc_con_letras(client: AsyncClient, db_session: AsyncSession):
    """5. RUC con letras o caracteres no numéricos: devuelve HTTP 400."""
    _, token_daira, _ = await obtener_tokens(client)
    res = await client.get(
        "/api/v1/ssco/consultar/2053897681A",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 400
    assert "11 dígitos" in res.json()["detail"]


@pytest.mark.asyncio
async def test_06_padron_vacio_no_verificado(client: AsyncClient, db_session: AsyncSession):
    """6. Padrón vacío o sin sincronización previa: responde NO_VERIFICADO (evitando falsos negativos)."""
    _, token_daira, _ = await obtener_tokens(client)
    res = await client.get(
        "/api/v1/ssco/consultar/20601234567",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["estado"] == "NO_VERIFICADO"
    assert data["es_ssco"] is False
    assert "No existe un padrón SSCO disponible" in data["mensaje"]


# ==============================================================================
# TESTS 7 - 10: CONTEXTO MULTIEMPRESA Y AUDITORÍA DE CONSULTAS
# ==============================================================================

@pytest.mark.asyncio
async def test_07_contador_daira_registra_consulta_como_daira(client: AsyncClient, db_session: AsyncSession):
    """7. CONTADOR DAIRA registra la consulta en consultas_ssco asociada a empresa DAIRA."""
    token_admin, token_daira, _ = await obtener_tokens(client)

    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    res = await client.get(
        "/api/v1/ssco/consultar/20601234567",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 200

    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()

    stmt = select(ConsultaSSCO).where(ConsultaSSCO.ruc_consultado == "20601234567")
    reg = (await db_session.execute(stmt)).scalar_one_or_none()
    assert reg is not None
    assert reg.empresa_id == emp_daira.id


@pytest.mark.asyncio
async def test_08_contador_jjd_registra_consulta_como_jjd(client: AsyncClient, db_session: AsyncSession):
    """8. CONTADOR JJD registra la consulta en consultas_ssco asociada a empresa JJD."""
    token_admin, _, token_jjd = await obtener_tokens(client)

    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    res = await client.get(
        "/api/v1/ssco/consultar/10456789012",
        headers={"Authorization": f"Bearer {token_jjd}"}
    )
    assert res.status_code == 200

    emp_jjd = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))).scalar_one()

    stmt = select(ConsultaSSCO).where(ConsultaSSCO.ruc_consultado == "10456789012")
    reg = (await db_session.execute(stmt)).scalar_one_or_none()
    assert reg is not None
    assert reg.empresa_id == emp_jjd.id


@pytest.mark.asyncio
async def test_09_aislamiento_historial_consultas_ssco(client: AsyncClient, db_session: AsyncSession):
    """9. Aislamiento estricto de auditoría: las consultas de DAIRA y JJD no se confunden en consultas_ssco."""
    token_admin, token_daira, token_jjd = await obtener_tokens(client)

    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    await client.get("/api/v1/ssco/consultar/20601234567", headers={"Authorization": f"Bearer {token_daira}"})
    await client.get("/api/v1/ssco/consultar/10456789012", headers={"Authorization": f"Bearer {token_jjd}"})

    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    emp_jjd = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))).scalar_one()

    consultas_daira = (await db_session.execute(select(ConsultaSSCO).where(ConsultaSSCO.empresa_id == emp_daira.id))).scalars().all()
    consultas_jjd = (await db_session.execute(select(ConsultaSSCO).where(ConsultaSSCO.empresa_id == emp_jjd.id))).scalars().all()

    assert len(consultas_daira) == 1
    assert consultas_daira[0].ruc_consultado == "20601234567"

    assert len(consultas_jjd) == 1
    assert consultas_jjd[0].ruc_consultado == "10456789012"


@pytest.mark.asyncio
async def test_10_admin_con_contexto_empresa(client: AsyncClient, db_session: AsyncSession):
    """10. ADMIN con cabecera X-Empresa-Id asigna la consulta a esa empresa; sin cabecera opera como None."""
    token_admin, _, _ = await obtener_tokens(client)

    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()

    # Consulta con contexto X-Empresa-Id
    res1 = await client.get(
        "/api/v1/ssco/consultar/20601234567",
        headers={"Authorization": f"Bearer {token_admin}", "X-Empresa-Id": str(emp_daira.id)}
    )
    assert res1.status_code == 200

    reg1 = (await db_session.execute(
        select(ConsultaSSCO).where(ConsultaSSCO.ruc_consultado == "20601234567", ConsultaSSCO.empresa_id == emp_daira.id)
    )).scalar_one_or_none()
    assert reg1 is not None

    # Consulta sin contexto de empresa
    res2 = await client.get(
        "/api/v1/ssco/consultar/10456789012",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert res2.status_code == 200

    reg2 = (await db_session.execute(
        select(ConsultaSSCO).where(ConsultaSSCO.ruc_consultado == "10456789012", ConsultaSSCO.empresa_id == None)
    )).scalar_one_or_none()
    assert reg2 is not None


# ==============================================================================
# TESTS 11 - 12: SEGURIDAD Y ROLES DE SINCRONIZACIÓN
# ==============================================================================

@pytest.mark.asyncio
async def test_11_sincronizacion_rechazada_para_contador(client: AsyncClient, db_session: AsyncSession):
    """11. Sincronización automática rechazada para CONTADOR (HTTP 403 Forbidden)."""
    _, token_daira, _ = await obtener_tokens(client)
    res = await client.post(
        "/api/v1/ssco/sincronizar",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_12_sincronizacion_permitida_para_admin(client: AsyncClient, db_session: AsyncSession):
    """12. Sincronización permitida para ADMINISTRADOR (descargando y reemplazando con éxito)."""
    token_admin, _, _ = await obtener_tokens(client)
    excel_bytes = generar_excel_ssco_bytes()

    # Simular descarga HTTPX exitosa desde SUNAT
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = excel_bytes
        mock_get.return_value = mock_resp

        res = await client.post(
            "/api/v1/ssco/sincronizar",
            headers={"Authorization": f"Bearer {token_admin}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["estado"] == "EXITOSO"
        assert data["total_registros"] == 2
        assert data["origen"] == "AUTO_DESCARGA"


# ==============================================================================
# TESTS 13 - 18: VALIDACIONES DE ESTRUCTURA DEL ARCHIVO XLSX
# ==============================================================================

@pytest.mark.asyncio
async def test_13_xlsx_valido(client: AsyncClient, db_session: AsyncSession):
    """13. XLSX válido: se carga correctamente mediante endpoint manual."""
    token_admin, _, _ = await obtener_tokens(client)
    excel_bytes = generar_excel_ssco_bytes()

    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 200
    assert res.json()["total_registros"] == 2


@pytest.mark.asyncio
async def test_14_archivo_corrupto(client: AsyncClient, db_session: AsyncSession):
    """14. Archivo corrupto (bytes corruptos que empiezan con PK pero zip roto): HTTP 400."""
    token_admin, _, _ = await obtener_tokens(client)
    corrupted_bytes = b"PK\x03\x04" + b"random_corrupted_data" * 20

    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("corrupted.xlsx", corrupted_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 400
    assert "corrupto" in res.json()["detail"].lower() or "zip" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_15_archivo_que_no_es_xlsx(client: AsyncClient, db_session: AsyncSession):
    """15. Archivo que no es XLSX (por ej. archivo de texto plano o extensión incorrecta): HTTP 400."""
    token_admin, _, _ = await obtener_tokens(client)

    # Extensión no permitida
    res1 = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("archivo.pdf", b"%PDF-1.4...", "application/pdf")}
    )
    assert res1.status_code == 400

    # Extensión .xlsx pero contenido no es ZIP/Excel
    res2 = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("falso.xlsx", b"Esto es texto plano", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res2.status_code == 400
    assert "válido" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_16_encabezados_incorrectos(client: AsyncClient, db_session: AsyncSession):
    """16. Archivo con columnas faltantes o incorrectas: HTTP 400 con detalle explicativo."""
    token_admin, _, _ = await obtener_tokens(client)
    bad_excel = generar_excel_ssco_bytes(encabezados=["COLUMNA_A", "COLUMNA_B"])

    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("bad_headers.xlsx", bad_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 400
    assert "encabezados oficiales" in res.json()["detail"]


@pytest.mark.asyncio
async def test_17_ruc_invalido_dentro_del_archivo(client: AsyncClient, db_session: AsyncSession):
    """17. Fila con RUC de longitud errónea en el archivo: HTTP 400."""
    token_admin, _, _ = await obtener_tokens(client)
    filas_mal_ruc = [
        ("123", "EMPRESA RUC CORTO", "DIR", "RES", date(2026, 1, 1), date(2026, 1, 10), "10123", "REP", date(2026, 1, 15))
    ]
    bad_ruc_excel = generar_excel_ssco_bytes(filas=filas_mal_ruc)

    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("bad_ruc.xlsx", bad_ruc_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 400
    assert "RUC inválido" in res.json()["detail"]


@pytest.mark.asyncio
async def test_18_ruc_duplicado(client: AsyncClient, db_session: AsyncSession):
    """18. Archivo que contiene RUCs duplicados internamente: HTTP 400."""
    token_admin, _, _ = await obtener_tokens(client)
    filas_duplicadas = [
        ("20601234567", "EMPRESA A", "DIR 1", "RES 1", date(2026, 1, 1), date(2026, 1, 10), "10123", "REP 1", date(2026, 1, 15)),
        ("20601234567", "EMPRESA B", "DIR 2", "RES 2", date(2026, 1, 1), date(2026, 1, 10), "10123", "REP 2", date(2026, 1, 15)),
    ]
    dupe_excel = generar_excel_ssco_bytes(filas=filas_duplicadas)

    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("dupe.xlsx", dupe_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 400
    assert "duplicado" in res.json()["detail"].lower()


# ==============================================================================
# TESTS 19 - 21: ROLLBACK Y REEMPLAZO CONSISTENTE
# ==============================================================================

@pytest.mark.asyncio
async def test_19_error_de_red_conserva_padron_anterior(client: AsyncClient, db_session: AsyncSession):
    """19. Error de red durante descarga de SUNAT conserva el padrón anterior intacto."""
    token_admin, _, _ = await obtener_tokens(client)

    # 1. Cargar padrón inicial
    excel_inicial = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_inicial, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    count_previo = (await db_session.execute(select(func.count()).select_from(PadronSSCO))).scalar()
    assert count_previo == 2

    # 2. Simular fallo de conexión con SUNAT
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection timed out")):
        res = await client.post(
            "/api/v1/ssco/sincronizar",
            headers={"Authorization": f"Bearer {token_admin}"}
        )
        assert res.status_code == 502

    # 3. Verificar que el padrón se conservó intacto
    count_post = (await db_session.execute(select(func.count()).select_from(PadronSSCO))).scalar()
    assert count_post == 2


@pytest.mark.asyncio
async def test_20_archivo_invalido_conserva_padron_anterior(client: AsyncClient, db_session: AsyncSession):
    """20. Archivo inválido o corrupto activa rollback y conserva el padrón previo intacto."""
    token_admin, _, _ = await obtener_tokens(client)

    # 1. Cargar inicial
    excel_inicial = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_inicial, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    # 2. Intentar cargar archivo con RUC inválido
    bad_excel = generar_excel_ssco_bytes(filas=[
        ("999", "INVALID", "DIR", "RES", date(2026, 1, 1), date(2026, 1, 10), "101", "REP", date(2026, 1, 15))
    ])
    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("bad.xlsx", bad_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 400

    # 3. El padrón original sigue conteniendo los 2 registros
    count_post = (await db_session.execute(select(func.count()).select_from(PadronSSCO))).scalar()
    assert count_post == 2


@pytest.mark.asyncio
async def test_21_actualizacion_correcta_reemplaza_de_forma_consistente_la_version(client: AsyncClient, db_session: AsyncSession):
    """21. Actualización atómica reemplaza de forma consistente el conjunto oficial (sin acumular registros obsoletos)."""
    token_admin, _, _ = await obtener_tokens(client)

    # 1. Cargar v1 con 2 registros: 20601234567 y 10456789012
    v1_excel = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("v1.xlsx", v1_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    # 2. Cargar v2 con solo 1 nuevo registro: 20609999999 (SUNAT corrigió/eliminó los anteriores)
    v2_filas = [
        ("20609999999", "NUEVA EMPRESA SSCO", "DIR", "RES", date(2026, 9, 1), date(2026, 9, 15), "102", "REP", date(2026, 9, 30))
    ]
    v2_excel = generar_excel_ssco_bytes(filas=v2_filas)
    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("v2.xlsx", v2_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 200

    # 3. El padrón ahora contiene exactamente 1 registro
    todos_los_rucs = (await db_session.execute(select(PadronSSCO.ruc))).scalars().all()
    assert todos_los_rucs == ["20609999999"]
    assert "20601234567" not in todos_los_rucs


# ==============================================================================
# TESTS 22 - 24: CARGA MANUAL ADMIN, ESTADO Y AISLAMIENTO DE CPE
# ==============================================================================

@pytest.mark.asyncio
async def test_22_carga_manual_solo_admin(client: AsyncClient, db_session: AsyncSession):
    """22. Endpoint de carga manual de Excel restringido a rol ADMINISTRADOR (CONTADOR recibe 403)."""
    _, token_daira, _ = await obtener_tokens(client)
    excel_bytes = generar_excel_ssco_bytes()

    res = await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_daira}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_23_endpoint_estado_devuelve_fecha_y_cantidad_correctas(client: AsyncClient, db_session: AsyncSession):
    """23. Endpoint /ssco/estado devuelve padron_disponible, total_registros y fecha de corte oficial."""
    token_admin, token_daira, _ = await obtener_tokens(client)

    # Estado previo a la carga
    res_vacio = await client.get("/api/v1/ssco/estado", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_vacio.status_code == 200
    assert res_vacio.json()["padron_disponible"] is False
    assert res_vacio.json()["total_registros"] == 0

    # Cargar padrón
    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    # Estado posterior
    res_cargado = await client.get("/api/v1/ssco/estado", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_cargado.status_code == 200
    data = res_cargado.json()
    assert data["padron_disponible"] is True
    assert data["total_registros"] == 2
    assert data["fecha_padron_sunat"] == "30/09/2026"
    assert data["origen"] == "MANUAL_EXCEL"
    assert data["estado"] == "EXITOSO"


@pytest.mark.asyncio
async def test_24_cero_llamadas_a_api_cpe_durante_consultas_ssco(client: AsyncClient, db_session: AsyncSession):
    """24. Garantía de aislamiento: CERO llamadas a la API de CPE ni a sunat_service durante consultas SSCO."""
    token_admin, token_daira, _ = await obtener_tokens(client)

    excel_bytes = generar_excel_ssco_bytes()
    await client.post(
        "/api/v1/ssco/cargar-excel",
        headers={"Authorization": f"Bearer {token_admin}"},
        files={"file": ("padron.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    # Espiar sunat_service.validar_comprobante
    with patch.object(sunat_service, "validar_comprobante", wraps=sunat_service.validar_comprobante) as spy_cpe:
        # Consulta RUC encontrado
        res1 = await client.get("/api/v1/ssco/consultar/20601234567", headers={"Authorization": f"Bearer {token_daira}"})
        assert res1.status_code == 200

        # Consulta RUC no encontrado
        res2 = await client.get("/api/v1/ssco/consultar/20999999999", headers={"Authorization": f"Bearer {token_daira}"})
        assert res2.status_code == 200

        # Verificar que validar_comprobante NUNCA fue llamado
        assert spy_cpe.call_count == 0
