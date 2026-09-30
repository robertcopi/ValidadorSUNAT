import io
import re
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
import openpyxl
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proceso_masivo import ProcesoMasivo
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.models.consulta_cpe import ConsultaCPE
from app.schemas.sunat import ConsultaCPEResponse, EmpresaInfo
from app.services.proceso_masivo_service import proceso_masivo_service


async def get_token_for(client: AsyncClient, email: str) -> str:
    """Helper para autenticar un usuario y obtener su JWT."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"}
    )
    assert res.status_code == 200, f"Login falló: {res.text}"
    return res.json()["access_token"]


def cpe_mock(ruc: str, comp: str, serie: str, numero: str, estado: str = "VALIDO") -> ConsultaCPEResponse:
    return ConsultaCPEResponse(
        id=999,
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
        codigo_sunat="0" if estado == "VALIDO" else "1",
        mensaje_sunat=f"Comprobante estado {estado}.",
        empresa_consultora=EmpresaInfo(ruc="20538976815", razon_social="DAIRA"),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )


# ==============================================================================
# 1. DASHBOARD VACÍO
# ==============================================================================
@pytest.mark.asyncio
async def test_dashboard_vacio(client: AsyncClient):
    token = await get_token_for(client, "contador.daira@test.local")
    # Filtro por un proceso inexistente para simular resultado vacío
    res = await client.get(
        "/api/v1/dashboard/resumen?proceso_id=nonexistent-uuid-9999",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["validos"] == 0
    assert data["no_validos"] == 0
    assert data["observados"] == 0
    assert data["errores"] == 0
    assert data["porcentaje_validos"] == 0.0


# ==============================================================================
# 2. DASHBOARD CON RESULTADOS
# ==============================================================================
@pytest.mark.asyncio
async def test_dashboard_con_resultados(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-dash-test-1"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        nombre_archivo="compras_test.xlsx",
        estado="COMPLETADO",
        total_registros=10,
        total_procesados=10,
        total_validos=7,
        total_no_validos=1,
        total_observados=1,
        total_errores=1,
        porcentaje=Decimal("100.00"),
    )
    db_session.add(proc)

    # Crear items
    items_estados = ["VALIDO"] * 7 + ["NO_VALIDO"] * 1 + ["OBSERVADO"] * 1 + ["ERROR"] * 1
    for idx, est in enumerate(items_estados, start=1):
        it = ProcesoMasivoItem(
            proceso_id=proc_id,
            fila_excel=idx + 5,
            num_ruc="20100070970",
            cod_comp="01",
            numero_serie="F001",
            numero=str(idx).zfill(8),
            fecha_emision=datetime.date(2026, 9, 15),
            monto_original=Decimal("150.00"),
            monto=Decimal("150.00"),
            razon_social="PROVEEDOR TEST",
            estado=est,
            codigo_sunat="0" if est == "VALIDO" else "1",
        )
        db_session.add(it)

    await db_session.commit()

    res = await client.get(
        f"/api/v1/dashboard/resumen?proceso_id={proc_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 10
    assert data["validos"] == 7
    assert data["no_validos"] == 1
    assert data["observados"] == 1
    assert data["errores"] == 1
    assert data["porcentaje_validos"] == 70.0
    assert data["porcentaje_no_validos"] == 10.0


# ==============================================================================
# 3. DASHBOARD AISLADO POR EMPRESA
# ==============================================================================
@pytest.mark.asyncio
async def test_dashboard_aislado_por_empresa(client: AsyncClient, db_session: AsyncSession):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    token_jjd = await get_token_for(client, "contador.jjd@test.local")

    proc_jjd_id = "proc-jjd-dash-1"
    proc_jjd = ProcesoMasivo(
        id=proc_jjd_id,
        empresa_id=2,  # JJD
        usuario_id=3,
        nombre_archivo="compras_jjd.xlsx",
        estado="COMPLETADO",
        total_registros=5,
        total_procesados=5,
        total_validos=5,
        porcentaje=Decimal("100.00"),
    )
    db_session.add(proc_jjd)

    for i in range(1, 6):
        it = ProcesoMasivoItem(
            proceso_id=proc_jjd_id,
            fila_excel=i + 5,
            num_ruc="20100070970",
            cod_comp="01",
            numero_serie="F001",
            numero=str(i).zfill(8),
            fecha_emision=datetime.date(2026, 9, 15),
            monto=Decimal("100.00"),
            estado="VALIDO",
        )
        db_session.add(it)
    await db_session.commit()

    # Si DAIRA consulta con el proceso_id de JJD, no ve ningún registro de JJD (total 0)
    res_daira = await client.get(
        f"/api/v1/dashboard/resumen?proceso_id={proc_jjd_id}",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res_daira.status_code == 200
    assert res_daira.json()["total"] == 0

    # JJD sí ve sus registros
    res_jjd = await client.get(
        f"/api/v1/dashboard/resumen?proceso_id={proc_jjd_id}",
        headers={"Authorization": f"Bearer {token_jjd}"}
    )
    assert res_jjd.status_code == 200
    assert res_jjd.json()["total"] == 5
    assert res_jjd.json()["validos"] == 5


# ==============================================================================
# 4. HISTORIAL PAGINADO
# ==============================================================================
@pytest.mark.asyncio
async def test_historial_paginado(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")

    res = await client.get(
        "/api/v1/procesos-masivos?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "total_pages" in data
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2


# ==============================================================================
# 5. DETALLE PROCESO
# ==============================================================================
@pytest.mark.asyncio
async def test_detalle_proceso(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-detalle-test-1"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        nombre_archivo="detalle_test.xlsx",
        estado="COMPLETADO",
        total_registros=2,
        total_procesados=2,
        total_validos=2,
        porcentaje=Decimal("100.00"),
    )
    db_session.add(proc)
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=6,
        num_ruc="20100070970",
        cod_comp="01",
        numero_serie="F001",
        numero="00000001",
        fecha_emision=datetime.date(2026, 9, 15),
        monto_original=Decimal("200.00"),
        monto=Decimal("200.00"),
        razon_social="EMPRESA PROVEEDORA S.A.",
        estado="VALIDO",
        codigo_sunat="0",
        mensaje_sunat="ACEPTADO",
    ))
    await db_session.commit()

    # GET proceso cabecera
    res_proc = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_proc.status_code == 200
    assert res_proc.json()["id"] == proc_id
    assert res_proc.json()["total_registros"] == 2

    # GET proceso items
    res_items = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}/items",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_items.status_code == 200
    items_data = res_items.json()["items"]
    assert len(items_data) == 1
    assert items_data[0]["num_ruc"] == "20100070970"
    assert items_data[0]["estado"] == "VALIDO"
    assert items_data[0]["codigo_sunat"] == "0"


# ==============================================================================
# 6. FILTROS (HISTORIAL Y ITEMS)
# ==============================================================================
@pytest.mark.asyncio
async def test_filtros(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-filtros-1"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        nombre_archivo="archivo_filtro_especial.xlsx",
        estado="COMPLETADO",
        total_registros=2,
    )
    db_session.add(proc)
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=6,
        num_ruc="20555555555",
        cod_comp="01",
        numero_serie="F100",
        numero="00000050",
        fecha_emision=datetime.date(2026, 9, 15),
        monto=Decimal("500.00"),
        razon_social="DISTRIBUIDORA NORTE SAC",
        estado="VALIDO",
    ))
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=7,
        num_ruc="20666666666",
        cod_comp="03",
        numero_serie="B200",
        numero="00000060",
        fecha_emision=datetime.date(2026, 9, 16),
        monto=Decimal("150.00"),
        razon_social="SERVICIOS SUR EIRL",
        estado="ERROR",
    ))
    await db_session.commit()

    # Filtro en historial por nombre_archivo
    res_h = await client.get(
        "/api/v1/procesos-masivos?nombre_archivo=filtro_especial",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_h.status_code == 200
    assert any(p["id"] == proc_id for p in res_h.json()["items"])

    # Filtro en items por ruc
    res_i1 = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}/items?ruc=20555555555",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_i1.status_code == 200
    assert len(res_i1.json()["items"]) == 1
    assert res_i1.json()["items"][0]["num_ruc"] == "20555555555"

    # Filtro en items por estado
    res_i2 = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}/items?estado=ERROR",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_i2.status_code == 200
    assert len(res_i2.json()["items"]) == 1
    assert res_i2.json()["items"][0]["estado"] == "ERROR"


# ==============================================================================
# 7, 8, 9 & 12: EXPORTACIÓN EXCEL, NOTA DE CRÉDITO NEGATIVA, MONTO ORIGINAL
# ==============================================================================
@pytest.mark.asyncio
async def test_exportacion_xlsx_con_nota_credito_negativa(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-export-nc-1"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        nombre_archivo="registro_compras_nc.xlsx",
        estado="COMPLETADO",
        total_registros=2,
        total_procesados=2,
        total_validos=2,
        porcentaje=Decimal("100.00"),
    )
    db_session.add(proc)

    # Item 1: Factura normal
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=6,
        num_ruc="20100070970",
        cod_comp="01",
        numero_serie="F001",
        numero="000100",
        fecha_emision=datetime.date(2026, 9, 10),
        monto_original=Decimal("1500.50"),
        monto=Decimal("1500.50"),
        razon_social="PROVEEDOR NORMAL S.A.",
        estado="VALIDO",
        codigo_sunat="0",
        mensaje_sunat="ACEPTADO",
    ))

    # Item 2: Nota de crédito negativa (ej. -21142.71 original, 21142.71 consultado SUNAT)
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=7,
        num_ruc="20200070970",
        cod_comp="07",
        numero_serie="FC01",
        numero="000200",
        fecha_emision=datetime.date(2026, 9, 11),
        monto_original=Decimal("-21142.71"),
        monto=Decimal("21142.71"),
        razon_social="PROVEEDOR NOTA CREDITO",
        estado="VALIDO",
        codigo_sunat="0",
        mensaje_sunat="ACEPTADO",
    ))
    await db_session.commit()

    # Solicitar exportación
    res = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}/exportar",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert "resultado_sunat_" in res.headers["content-disposition"]

    # 12. Abrir archivo Excel con openpyxl para verificar estructura y datos
    excel_bytes = io.BytesIO(res.content)
    wb = openpyxl.load_workbook(excel_bytes)
    assert "Resultados SUNAT" in wb.sheetnames
    ws = wb["Resultados SUNAT"]

    # Verificar encabezados en fila 8
    headers = [ws.cell(row=8, column=col).value for col in range(1, 15)]
    assert "Fila Excel" in headers
    assert "Importe Original" in headers
    assert "Importe Consultado SUNAT" in headers
    assert "Resultado" in headers

    # Verificar datos preservados (fila 9 y 10)
    # Fila 9: Factura normal
    assert float(ws.cell(row=9, column=8).value) == 1500.50
    assert float(ws.cell(row=9, column=9).value) == 1500.50

    # Fila 10: Nota de Crédito preserva signo contable negativo (-21142.71)
    monto_orig_nc = float(ws.cell(row=10, column=8).value)
    monto_sunat_nc = float(ws.cell(row=10, column=9).value)
    assert monto_orig_nc == -21142.71
    assert monto_sunat_nc == 21142.71


# ==============================================================================
# 10. EXPORTACIÓN PROCESO OTRA EMPRESA -> 404
# ==============================================================================
@pytest.mark.asyncio
async def test_exportacion_proceso_otra_empresa_404(client: AsyncClient, db_session: AsyncSession):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    token_jjd = await get_token_for(client, "contador.jjd@test.local")

    # Proceso de JJD (empresa_id = 2)
    proc_jjd = ProcesoMasivo(
        id="proc-jjd-privado",
        empresa_id=2,
        usuario_id=3,
        nombre_archivo="jjd_privado.xlsx",
        total_registros=1,
    )
    db_session.add(proc_jjd)
    await db_session.commit()

    # DAIRA intenta exportar proceso de JJD -> 404
    res1 = await client.get(
        "/api/v1/procesos-masivos/proc-jjd-privado/exportar",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res1.status_code == 404
    assert "No se encontró el proceso masivo" in res1.json()["detail"]

    # JJD intenta exportar proceso inexistente o de DAIRA -> 404
    res2 = await client.get(
        "/api/v1/procesos-masivos/proc-inexistente-123/exportar",
        headers={"Authorization": f"Bearer {token_jjd}"}
    )
    assert res2.status_code == 404


# ==============================================================================
# 11. EXPORTAR NO LLAMA SUNAT
# ==============================================================================
@pytest.mark.asyncio
async def test_exportar_no_llama_sunat(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-zero-sunat"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        nombre_archivo="zero_sunat.xlsx",
        total_registros=1,
    )
    db_session.add(proc)
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=6,
        num_ruc="20100070970",
        cod_comp="01",
        numero_serie="F001",
        numero="00000001",
        fecha_emision=datetime.date(2026, 9, 15),
        monto=Decimal("100.00"),
        estado="VALIDO",
    ))
    await db_session.commit()

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_val:
        with patch("app.services.sunat_service.sunat_service.get_access_token", new_callable=AsyncMock) as mock_tok:
            res = await client.get(
                f"/api/v1/procesos-masivos/{proc_id}/exportar",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 200
            # Confirmar 0 llamadas a SUNAT durante la exportación
            mock_val.assert_not_called()
            mock_tok.assert_not_called()


# ==============================================================================
# 13. ESTADOS CORRECTOS (ÚNICAMENTE VALIDO, NO_VALIDO, OBSERVADO, ERROR)
# ==============================================================================
@pytest.mark.asyncio
async def test_estados_correctos_fase5(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-estados-fase5"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        total_registros=4,
    )
    db_session.add(proc)

    estados_oficiales = ["VALIDO", "NO_VALIDO", "OBSERVADO", "ERROR"]
    for i, est in enumerate(estados_oficiales, start=1):
        db_session.add(ProcesoMasivoItem(
            proceso_id=proc_id,
            fila_excel=i + 5,
            num_ruc="20100070970",
            cod_comp="01",
            numero_serie="F001",
            numero=str(i).zfill(8),
            fecha_emision=datetime.date(2026, 9, 15),
            monto=Decimal("100.00"),
            estado=est,
        ))
    await db_session.commit()

    res = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}/items",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    items = res.json()["items"]
    estados_devueltos = {it["estado"] for it in items}
    assert estados_devueltos == {"VALIDO", "NO_VALIDO", "OBSERVADO", "ERROR"}
    # No inventar estados adicionales como ANULADO o ACEPTADO en el estado interno
    assert "ANULADO" not in estados_devueltos
    assert "ACEPTADO" not in estados_devueltos


# ==============================================================================
# 14. CANTIDADES DINÁMICAS (1, 3, 25, 100 COMPROBANTES)
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("cantidad", [1, 3, 25, 50])
async def test_cantidades_dinamicas_dashboard(client: AsyncClient, db_session: AsyncSession, cantidad: int):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = f"proc-dinamico-{cantidad}"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        total_registros=cantidad,
    )
    db_session.add(proc)

    for i in range(1, cantidad + 1):
        db_session.add(ProcesoMasivoItem(
            proceso_id=proc_id,
            fila_excel=i + 5,
            num_ruc="20100070970",
            cod_comp="01",
            numero_serie="F001",
            numero=str(i).zfill(8),
            fecha_emision=datetime.date(2026, 9, 15),
            monto=Decimal("100.00"),
            estado="VALIDO",
        ))
    await db_session.commit()

    res = await client.get(
        f"/api/v1/dashboard/resumen?proceso_id={proc_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == cantidad
    assert data["validos"] == cantidad
    assert data["porcentaje_validos"] == 100.0


# ==============================================================================
# 15. SEGURIDAD CONTRA EXCEL FORMULA INJECTION
# ==============================================================================
@pytest.mark.asyncio
async def test_seguridad_contra_formula_injection(client: AsyncClient, db_session: AsyncSession):
    token = await get_token_for(client, "contador.daira@test.local")
    proc_id = "proc-formula-injection-test"

    proc = ProcesoMasivo(
        id=proc_id,
        empresa_id=1,
        usuario_id=2,
        nombre_archivo="injection_test.xlsx",
        total_registros=1,
    )
    db_session.add(proc)

    # Texto malicioso que inicia con '=' y '@'
    db_session.add(ProcesoMasivoItem(
        proceso_id=proc_id,
        fila_excel=6,
        num_ruc="20100070970",
        cod_comp="01",
        numero_serie="=1+1",
        numero="@SUM(1,2)",
        fecha_emision=datetime.date(2026, 9, 15),
        monto_original=Decimal("50.00"),
        monto=Decimal("50.00"),
        razon_social="=cmd|' /C calc'!A0",
        estado="ERROR",
        mensaje_sunat="+MALICIOUS_TAG",
    ))
    await db_session.commit()

    res = await client.get(
        f"/api/v1/procesos-masivos/{proc_id}/exportar",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200

    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    ws = wb["Resultados SUNAT"]

    # Fila 9 contiene los datos
    val_razon = str(ws.cell(row=9, column=3).value)
    val_serie = str(ws.cell(row=9, column=5).value)
    val_numero = str(ws.cell(row=9, column=6).value)
    val_mensaje = str(ws.cell(row=9, column=13).value)

    # Debe neutralizarse anteponiendo comilla simple (') para evitar que Excel lo ejecute como fórmula
    assert val_razon.startswith("'=")
    assert val_serie.startswith("'=")
    assert val_numero.startswith("'@")
    assert val_mensaje.startswith("'+")
