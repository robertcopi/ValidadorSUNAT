import io
from decimal import Decimal
import pytest
import openpyxl
from unittest.mock import AsyncMock, patch

from app.schemas.sunat import ComprobanteValidarRequest
from app.services.excel_parser_service import ExcelParserService


def generar_excel_multinivel_prueba(rows):
    """
    Crea un libro Excel en memoria simulando las cabeceras multinivel
    del Formato 8.1 Registro de Compras de SUNAT con celdas combinadas.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hoja1"

    # Fila 7
    ws["B7"] = "FECHA DE"
    ws["D7"] = "COMPROBANTE DE PAGO"
    ws["H7"] = "INFORMACION DEL"
    ws["K7"] = "ADQUISICIONES GRAVADAS"
    ws["M7"] = "ADQUISICIONES GRAVADAS"
    ws["O7"] = "ADQUISICIONES GRAVADAS"
    ws.merge_cells("D7:G7")
    ws.merge_cells("H7:J7")
    ws.merge_cells("K7:L7")
    ws.merge_cells("M7:N7")
    ws.merge_cells("O7:P7")

    # Fila 8
    ws["B8"] = "EMISION DEL"
    ws["D8"] = "O DOCUMENTO"
    ws["H8"] = "PROVEEDOR"
    ws["K8"] = "DESTINADAS A OPERACIONES"
    ws["M8"] = "DESTINADAS A OPERACIONES"
    ws["O8"] = "DESTINADAS A OPERACIONES"
    ws.merge_cells("D8:G8")
    ws.merge_cells("H8:J8")
    ws.merge_cells("K8:L8")
    ws.merge_cells("M8:N8")
    ws.merge_cells("O8:P8")

    # Fila 9
    ws["B9"] = "COMPROBANTE"
    ws["K9"] = "GRAVADAS Y/O DE EXPORTACIÓN"
    ws["L9"] = "GRAVADAS Y/O DE EXPORTACIÓN"
    ws["M9"] = "GRAVADAS Y/O DE EXPORTACIÓN Y A OPERACIONES NO GRAVADAS"
    ws["N9"] = "GRAVADAS Y/O DE EXPORTACIÓN Y A OPERACIONES NO GRAVADAS"
    ws["O9"] = "NO GRAVADAS"
    ws["P9"] = "NO GRAVADAS"
    ws["Z9"] = "TIPO"
    ws.merge_cells("K9:L9")
    ws.merge_cells("M9:N9")
    ws.merge_cells("O9:P9")

    # Fila 10
    ws["B10"] = "DE PAGO"
    ws["D10"] = "TIPO"
    ws["E10"] = "SERIE"
    ws["G10"] = "NUMERO"
    ws["H10"] = "TIPO"
    ws["I10"] = "NUMERO"
    ws["J10"] = "RAZON SOCIAL"
    ws["U10"] = "OTROS"
    ws["V10"] = "IMPORTE"
    ws["Z10"] = "DE"

    # Fila 11
    ws["K11"] = "BASE"
    ws["M11"] = "BASE"
    ws["O11"] = "BASE"
    ws["U11"] = "TRIBUTOS Y"
    ws["V11"] = "TOTAL"
    ws["Z11"] = "CAMBIO"

    # Fila 12
    ws["K12"] = "IMPONIBLE"
    ws["L12"] = "IGV"
    ws["M12"] = "IMPONIBLE"
    ws["N12"] = "IGV"
    ws["O12"] = "IMPONIBLE"
    ws["P12"] = "IGV"
    ws["Q8"] = "VALOR"
    ws["Q9"] = "DE LAS"
    ws["Q10"] = "ADQUISICIONES"
    ws["Q11"] = "NO"
    ws["Q12"] = "GRAVADAS"
    ws["U12"] = "CARGOS"

    # Filas de datos a partir de fila 14
    for idx, row_data in enumerate(rows, start=14):
        for col_idx, val in row_data.items():
            ws.cell(row=idx, column=col_idx, value=val)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ==============================================================================
# 7. EJEMPLO OBLIGATORIO:
# Base imponible = 100.00
# IGV = 18.00
# Otros tributos/cargos = 5.00
# Importe total = 123.00
# Esperado: importe_total_excel = 123.00, monto_base_igv = 118.00, monto SUNAT = 118.00
# El test debe FALLAR si se envía: 123.00
# ==============================================================================
def test_ejemplo_obligatorio_monto_base_mas_igv_no_incluye_otros_tributos():
    row_1 = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001001",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR EJEMPLO 1 SAC",
        11: 100.00,    # Base imponible (Col K)
        12: 18.00,     # IGV (Col L)
        13: 0.00,      # Grupo 2 Base
        14: 0.00,      # Grupo 2 IGV
        15: 0.00,      # Grupo 3 Base
        16: 0.00,      # Grupo 3 IGV
        21: 5.00,      # Otros tributos y cargos (Col U)
        22: 123.00,    # Importe total (Col V)
    }

    excel_bytes = generar_excel_multinivel_prueba([row_1])
    res = ExcelParserService.parse_excel(excel_bytes, "test_ejemplo_1.xlsx")

    assert res.total_filas_detectadas == 1
    assert res.total_listos == 1
    fila = res.filas[0]

    # Validaciones conceptuales exigidas
    assert fila.base_imponible == Decimal("100.00"), "La base imponible debe ser exactamente 100.00"
    assert fila.igv == Decimal("18.00"), "El IGV debe ser exactamente 18.00"
    assert fila.otros_tributos == Decimal("5.00"), "Otros tributos/cargos debe registrarse pero aislarse"
    assert fila.importe_total_excel == Decimal("123.00"), "El importe total del Excel debe conservarse como 123.00"
    assert fila.monto_base_igv == Decimal("118.00"), "monto_base_igv debe ser 100.00 + 18.00 = 118.00"
    assert fila.monto_original == Decimal("118.00"), "monto_original debe ser el valor calculado contable 118.00"
    assert fila.monto == Decimal("118.00"), "monto debe ser 118.00"
    assert fila.monto_sunat == Decimal("118.00"), "monto_sunat debe ser 118.00"

    # Conversión al request que se enviará a SUNAT
    req = ExcelParserService.to_comprobante_validar_request(fila)

    # REGLA ESTRICTA: El valor enviado a SUNAT debe ser 118.00 y NO 123.00
    assert req.monto == Decimal("118.00"), "El monto en ComprobanteValidarRequest debe ser 118.00"
    assert req.monto_sunat == "118.00", "El string formateado para el body de SUNAT debe ser '118.00'"

    # Test debe FALLAR si se enviara 123.00
    assert req.monto != Decimal("123.00"), "¡Error! Se está enviando el importe total (123.00) en vez de base+igv (118.00)"


# ==============================================================================
# 8. SEGUNDO TEST:
# Caso normal:
# Base imponible = 200.00
# IGV = 36.00
# Otros tributos/cargos = 0.00
# Importe total = 236.00
# Esperado: monto SUNAT = 236.00
# ==============================================================================
def test_segundo_caso_normal_sin_otros_tributos():
    row_2 = {
        2: "16/09/2026",
        4: "01",
        5: "F001",
        7: "00001002",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR CASO NORMAL SAC",
        11: 200.00,    # Base imponible
        12: 36.00,     # IGV
        21: 0.00,      # Otros tributos/cargos
        22: 236.00,    # Importe total
    }

    excel_bytes = generar_excel_multinivel_prueba([row_2])
    res = ExcelParserService.parse_excel(excel_bytes, "test_caso_normal.xlsx")

    assert res.total_filas_detectadas == 1
    assert res.total_listos == 1
    fila = res.filas[0]

    assert fila.base_imponible == Decimal("200.00")
    assert fila.igv == Decimal("36.00")
    assert fila.importe_total_excel == Decimal("236.00")
    assert fila.monto_base_igv == Decimal("236.00")
    assert fila.monto == Decimal("236.00")
    assert fila.monto_sunat == Decimal("236.00")

    req = ExcelParserService.to_comprobante_validar_request(fila)
    assert req.monto == Decimal("236.00")
    assert req.monto_sunat == "236.00"


# ==============================================================================
# 9. TERCER TEST — NOTA DE CRÉDITO:
# Base imponible = -100.00
# IGV = -18.00
# Otros tributos/cargos = -5.00
# Importe total = -123.00
# Esperado:
# valor calculado original = -118.00
# monto enviado SUNAT = 118.00
# ==============================================================================
def test_tercer_caso_nota_de_credito_signo_negativo():
    row_3 = {
        2: "17/09/2026",
        4: "07",       # Nota de crédito
        5: "FC01",
        7: "00001003",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR NOTA CREDITO SAC",
        11: -100.00,   # Base imponible negativa
        12: -18.00,    # IGV negativo
        21: -5.00,     # Otros tributos negativos
        22: -123.00,   # Importe total negativo
    }

    excel_bytes = generar_excel_multinivel_prueba([row_3])
    res = ExcelParserService.parse_excel(excel_bytes, "test_nota_credito.xlsx")

    assert res.total_filas_detectadas == 1
    assert res.total_listos == 1
    fila = res.filas[0]

    # Valor calculado original con signo conservado
    assert fila.base_imponible == Decimal("-100.00")
    assert fila.igv == Decimal("-18.00")
    assert fila.monto_base_igv == Decimal("-118.00")
    assert fila.monto_original == Decimal("-118.00"), "El valor calculado original debe conservar el signo negativo -118.00"
    assert fila.importe_total_excel == Decimal("-123.00")

    # Monto positivo enviado a SUNAT
    assert fila.monto == Decimal("118.00"), "El monto para SUNAT debe ser abs(monto_calculado_original) = 118.00"
    assert fila.monto_sunat == Decimal("118.00")

    req = ExcelParserService.to_comprobante_validar_request(fila)
    assert req.monto == Decimal("118.00")
    assert req.monto_sunat == "118.00"
    assert req.monto != Decimal("123.00")
    assert req.monto != Decimal("-118.00"), "SUNAT requiere el monto positivo"


# ==============================================================================
# TEST 4: AISLAMIENTO ESTRICTO DE CABECERAS MULTINIVEL (NO CONFUNDIR GRUPOS)
# ==============================================================================
def test_cabeceras_multinivel_no_confunde_grupos_no_gravadas():
    """
    Verifica que el parser elija específicamente las columnas de:
    'Adquisiciones gravadas destinadas a operaciones gravadas y/o de exportación'
    (Columna 11 y 12) y NO las columnas de operaciones no gravadas (Columnas 13, 14, 15, 16).
    """
    row = {
        2: "18/09/2026",
        4: "01",
        5: "F001",
        7: "00001004",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR GRUPOS MIXTOS SAC",
        11: 500.00,    # Grupo 1 Base (Gravadas y/o exportación)
        12: 90.00,     # Grupo 1 IGV
        13: 999.00,    # Grupo 2 Base (No debe tomarse)
        14: 999.00,    # Grupo 2 IGV (No debe tomarse)
        15: 888.00,    # Grupo 3 Base (No debe tomarse)
        16: 888.00,    # Grupo 3 IGV (No debe tomarse)
        21: 15.00,     # Otros tributos (No debe tomarse)
        22: 3480.00,   # Importe total acumulado
    }

    excel_bytes = generar_excel_multinivel_prueba([row])
    res = ExcelParserService.parse_excel(excel_bytes, "test_grupos.xlsx")

    fila = res.filas[0]
    assert fila.base_imponible == Decimal("500.00"), "Debe seleccionar Columna 11 (Grupo 1) y no Col 13 u 15"
    assert fila.igv == Decimal("90.00"), "Debe seleccionar Columna 12 (Grupo 1) y no Col 14 o 16"
    assert fila.monto_base_igv == Decimal("590.00")
    assert fila.monto == Decimal("590.00")
    assert fila.importe_total_excel == Decimal("3480.00")


# ==============================================================================
# TEST 5: SIMULACIÓN DE FLUJO COMPLETO SIN LLAMADAS REALES A SUNAT
# ==============================================================================
def test_sin_llamadas_reales_a_sunat():
    """
    Confirma que ComprobanteValidarRequest genera exactamente el payload
    esperado para SUNAT con monto=118.00 sin realizar llamadas HTTP externas.
    """
    req = ComprobanteValidarRequest(
        num_ruc="20100070970",
        cod_comp="01",
        numero_serie="F001",
        numero="00001001",
        fecha_emision="15/09/2026",
        monto=Decimal("118.00")
    )
    assert req.monto_sunat == "118.00"
    assert req.monto == Decimal("118.00")
    assert req.fecha_emision_sunat == "15/09/2026"


# ==============================================================================
# TEST 6: PREVIEW END-TO-END VIA API REST (HTTP POST /api/v1/importaciones/preview)
# ==============================================================================
@pytest.mark.asyncio
async def test_api_preview_ejemplo_obligatorio(client, db_session):
    """
    Verifica a través del endpoint HTTP /api/v1/importaciones/preview que el JSON devuelto
    exponga conceptualmente separados:
    - importe_total_excel = 123.00
    - monto_base_igv = 118.00
    - monto (para SUNAT) = 118.00
    - base_imponible = 100.00
    - igv = 18.00
    - otros_tributos = 5.00
    """
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "contador.daira@test.local", "password": "Password123!"}
    )
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]

    row_1 = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001001",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR EJEMPLO 1 SAC",
        11: 100.00,    # Base imponible
        12: 18.00,     # IGV
        21: 5.00,      # Otros tributos/cargos
        22: 123.00,    # Importe total
    }

    excel_bytes = generar_excel_multinivel_prueba([row_1])
    files = {"archivo": ("ejemplo_sunat.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    res = await client.post(
        "/api/v1/importaciones/preview",
        headers={"Authorization": f"Bearer {token}"},
        files=files
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_listos"] == 1
    fila = data["filas"][0]

    assert Decimal(str(fila["base_imponible"])) == Decimal("100.00")
    assert Decimal(str(fila["igv"])) == Decimal("18.00")
    assert Decimal(str(fila["otros_tributos"])) == Decimal("5.00")
    assert Decimal(str(fila["importe_total_excel"])) == Decimal("123.00")
    assert Decimal(str(fila["monto_base_igv"])) == Decimal("118.00")
    assert Decimal(str(fila["monto"])) == Decimal("118.00")
    assert Decimal(str(fila["monto_original"])) == Decimal("118.00")
    assert Decimal(str(fila["monto"])) != Decimal("123.00")


# ==============================================================================
# TESTS OBLIGATORIOS TIPO DE CAMBIO (CASOS 1 A 5 + VALIDACIÓN SEGURA)
# ==============================================================================

@pytest.mark.asyncio
async def test_caso_1_con_tipo_cambio():
    """
    CASO 1 — CON TIPO DE CAMBIO
    Base = 100.00
    IGV = 18.00
    Tipo cambio = 3.750
    Base + IGV = 118.00
    118.00 / 3.750 = 31.4666...
    Esperado:
    monto_sunat = 31.47
    monto_convertido = 31.47
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001001",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR CASO 1 SAC",
        11: 100.00,
        12: 18.00,
        22: 118.00,
        26: 3.750,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.tipo_cambio == Decimal("3.750")
    assert fila.monto_convertido == Decimal("31.47")
    assert fila.monto == Decimal("31.47")
    assert fila.monto_original == Decimal("31.47")


@pytest.mark.asyncio
async def test_caso_2_sin_tipo_cambio():
    """
    CASO 2 — SIN TIPO DE CAMBIO
    Base = 100.00
    IGV = 18.00
    Tipo cambio = vacío / None
    Esperado:
    monto_sunat = 118.00
    monto_convertido = None
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001002",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR CASO 2 SAC",
        11: 100.00,
        12: 18.00,
        22: 118.00,
        # 26: sin tipo de cambio
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.tipo_cambio is None
    assert fila.monto_convertido is None
    assert fila.monto == Decimal("118.00")
    assert fila.monto_original == Decimal("118.00")


@pytest.mark.asyncio
async def test_caso_3_tipo_cambio_cero():
    """
    CASO 3 — TIPO DE CAMBIO CERO
    Base = 100.00
    IGV = 18.00
    Tipo cambio = 0
    Esperado:
    NO dividir entre cero.
    monto_sunat = 118.00
    monto_convertido = None
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001003",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR CASO 3 SAC",
        11: 100.00,
        12: 18.00,
        22: 118.00,
        26: 0.0,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.tipo_cambio == Decimal("0.0")
    assert fila.monto_convertido is None
    assert fila.monto == Decimal("118.00")
    assert fila.monto_original == Decimal("118.00")


@pytest.mark.asyncio
async def test_caso_4_nota_credito():
    """
    CASO 4 — NOTA DE CRÉDITO
    Base = -100.00
    IGV = -18.00
    Tipo cambio = 3.750
    monto_base_igv = -118.00
    monto_convertido = -31.47
    monto_original = -31.47 (trazabilidad con signo)
    monto_sunat = 31.47 (positivo para consulta SUNAT)
    """
    row = {
        2: "15/09/2026",
        4: "07",
        5: "FC01",
        7: "00001004",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR CASO 4 SAC",
        11: -100.00,
        12: -18.00,
        22: -118.00,
        26: 3.750,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("-100.00")
    assert fila.igv == Decimal("-18.00")
    assert fila.monto_base_igv == Decimal("-118.00")
    assert fila.tipo_cambio == Decimal("3.750")
    assert fila.monto_convertido == Decimal("-31.47")
    assert fila.monto_original == Decimal("-31.47")
    assert fila.monto == Decimal("31.47")


@pytest.mark.asyncio
async def test_caso_5_otros_tributos():
    """
    CASO 5 — OTROS TRIBUTOS
    Base = 100.00
    IGV = 18.00
    Otros tributos = 5.00
    Importe total Excel = 123.00
    Tipo cambio = 3.750
    El cálculo debe continuar utilizando solamente:
    (100 + 18) / 3.750 = 31.47
    NO:
    123 / 3.750 = 32.80
    Esperado:
    monto_sunat = 31.47
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001005",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR CASO 5 SAC",
        11: 100.00,
        12: 18.00,
        21: 5.00,
        22: 123.00,
        26: 3.750,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.otros_tributos == Decimal("5.00")
    assert fila.importe_total_excel == Decimal("123.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.tipo_cambio == Decimal("3.750")
    assert fila.monto_convertido == Decimal("31.47")
    assert fila.monto == Decimal("31.47")
    # Asegurar que NO se usó el importe total (123 / 3.750 = 32.80)
    assert fila.monto != Decimal("32.80")


@pytest.mark.asyncio
async def test_caso_tc_invalido_seguro():
    """
    CASO TC INVÁLIDO / NO NUMÉRICO
    Verifica que un valor no numérico en tipo de cambio no produzca error 500,
    no divida, registre la observación y mantenga monto_sunat = abs(monto_base_igv).
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00001006",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR TC INVALIDO SAC",
        11: 100.00,
        12: 18.00,
        22: 118.00,
        26: "INVALIDO",
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.monto_convertido is None
    assert fila.monto == Decimal("118.00")
    assert any("Tipo de cambio inválido" in err for err in fila.errores)


# ==============================================================================
# TESTS EXIGIDOS: REQUERIMIENTOS 21 A 27 - VALOR DE LAS ADQUISICIONES NO GRAVADAS
# ==============================================================================

@pytest.mark.asyncio
async def test_req_test_1_sin_no_gravadas():
    """
    TEST 1 — SIN NO GRAVADAS
    Base = 100
    IGV = 18
    No gravadas = vacío
    TC = vacío
    Esperado:
    monto_base_igv = 118.00
    monto_calculado_original = 118.00
    monto_sunat = 118.00
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00002001",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR REQ1 SAC",
        11: 100.00,
        12: 18.00,
        17: None,  # No gravadas vacío
        22: 118.00,
        26: None,  # TC vacío
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.valor_adquisiciones_no_gravadas is None
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.monto_calculado_original == Decimal("118.00")
    assert fila.monto_convertido is None
    assert fila.monto == Decimal("118.00")
    assert fila.monto_sunat == Decimal("118.00")


@pytest.mark.asyncio
async def test_req_test_2_con_no_gravadas():
    """
    TEST 2 — CON NO GRAVADAS
    Base = 100
    IGV = 18
    No gravadas = 25
    TC = vacío
    Esperado:
    monto_base_igv = 118.00
    monto_calculado_original = 143.00
    monto_sunat = 143.00
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00002002",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR REQ2 SAC",
        11: 100.00,
        12: 18.00,
        17: 25.00,  # No gravadas = 25.00
        22: 143.00,
        26: None,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.valor_adquisiciones_no_gravadas == Decimal("25.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.monto_calculado_original == Decimal("143.00")
    assert fila.monto_convertido is None
    assert fila.monto == Decimal("143.00")
    assert fila.monto_sunat == Decimal("143.00")


@pytest.mark.asyncio
async def test_req_test_3_otros_tributos():
    """
    TEST 3 — OTROS TRIBUTOS
    Base = 100
    IGV = 18
    No gravadas = 25
    Otros tributos = 5
    Importe Total Excel = 148
    Esperado:
    monto_calculado_original = 143.00
    monto_sunat = 143.00
    Comprobar explícitamente:
    monto_sunat != 148.00
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00002003",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR REQ3 SAC",
        11: 100.00,
        12: 18.00,
        17: 25.00,  # No gravadas = 25.00
        21: 5.00,   # Otros tributos = 5.00
        22: 148.00, # Total Excel = 148.00
        26: None,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.valor_adquisiciones_no_gravadas == Decimal("25.00")
    assert fila.otros_tributos == Decimal("5.00")
    assert fila.importe_total_excel == Decimal("148.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.monto_calculado_original == Decimal("143.00")
    assert fila.monto == Decimal("143.00")
    assert fila.monto_sunat == Decimal("143.00")
    # Comprobar explícitamente que NO incluye otros tributos
    assert fila.monto != Decimal("148.00")


@pytest.mark.asyncio
async def test_req_test_4_tipo_de_cambio():
    """
    TEST 4 — TIPO DE CAMBIO
    Base = 100
    IGV = 18
    No gravadas = 25
    TC = 3.7500
    Esperado:
    monto_calculado_original = 143.00
    143 / 3.7500 = 38.133...
    monto_convertido = 38.13
    monto_sunat = 38.13
    """
    row = {
        2: "15/09/2026",
        4: "01",
        5: "F001",
        7: "00002004",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR REQ4 SAC",
        11: 100.00,
        12: 18.00,
        17: 25.00,
        22: 143.00,
        26: 3.7500,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("100.00")
    assert fila.igv == Decimal("18.00")
    assert fila.valor_adquisiciones_no_gravadas == Decimal("25.00")
    assert fila.monto_base_igv == Decimal("118.00")
    assert fila.monto_calculado_original == Decimal("143.00")
    assert fila.tipo_cambio == Decimal("3.7500")
    assert fila.monto_convertido == Decimal("38.13")
    assert fila.monto == Decimal("38.13")
    assert fila.monto_sunat == Decimal("38.13")


@pytest.mark.asyncio
async def test_req_test_5_nota_de_credito():
    """
    TEST 5 — NOTA DE CRÉDITO
    Base = -100
    IGV = -18
    No gravadas = -25
    TC = 3.7500
    Esperado:
    monto_base_igv = -118.00
    monto_calculado_original = -143.00
    monto_convertido = -38.13
    monto_sunat = 38.13
    """
    row = {
        2: "15/09/2026",
        4: "07",
        5: "FC01",
        7: "00002005",
        8: "6",
        9: "20100070970",
        10: "PROVEEDOR REQ5 SAC",
        11: -100.00,
        12: -18.00,
        17: -25.00,
        22: -143.00,
        26: 3.7500,
    }
    excel_bytes = generar_excel_multinivel_prueba([row])
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 1
    fila = res.filas[0]
    assert fila.estado_archivo == "LISTO"
    assert fila.base_imponible == Decimal("-100.00")
    assert fila.igv == Decimal("-18.00")
    assert fila.valor_adquisiciones_no_gravadas == Decimal("-25.00")
    assert fila.monto_base_igv == Decimal("-118.00")
    assert fila.monto_calculado_original == Decimal("-143.00")
    assert fila.tipo_cambio == Decimal("3.7500")
    assert fila.monto_convertido == Decimal("-38.13")
    assert fila.monto_original == Decimal("-38.13")
    assert fila.monto == Decimal("38.13")
    assert fila.monto_sunat == Decimal("38.13")


@pytest.mark.asyncio
async def test_req_test_6_varias_filas_aislamiento():
    """
    TEST 6 — VARIAS FILAS
    FILA 1: Base = 100, IGV = 18, No gravadas = vacío, TC = vacío -> SUNAT = 118.00
    FILA 2: Base = 100, IGV = 18, No gravadas = 25, TC = vacío -> SUNAT = 143.00
    FILA 3: Base = 100, IGV = 18, No gravadas = vacío, TC = 3.7500 -> 118 / 3.7500 = 31.47 -> SUNAT = 31.47
    FILA 4: Base = 100, IGV = 18, No gravadas = 25, TC = 3.7500 -> 143 / 3.7500 = 38.13 -> SUNAT = 38.13

    Comprobar que cada fila utiliza únicamente SUS PROPIOS valores sin forward-fill ni contaminación.
    """
    rows = [
        # Fila 1
        {
            2: "15/09/2026", 4: "01", 5: "F001", 7: "00003001", 8: "6", 9: "20100070970",
            10: "PROV FILA 1", 11: 100.00, 12: 18.00, 17: None, 22: 118.00, 26: None,
        },
        # Fila 2
        {
            2: "15/09/2026", 4: "01", 5: "F001", 7: "00003002", 8: "6", 9: "20100070970",
            10: "PROV FILA 2", 11: 100.00, 12: 18.00, 17: 25.00, 22: 143.00, 26: None,
        },
        # Fila 3
        {
            2: "15/09/2026", 4: "01", 5: "F001", 7: "00003003", 8: "6", 9: "20100070970",
            10: "PROV FILA 3", 11: 100.00, 12: 18.00, 17: None, 22: 118.00, 26: 3.7500,
        },
        # Fila 4
        {
            2: "15/09/2026", 4: "01", 5: "F001", 7: "00003004", 8: "6", 9: "20100070970",
            10: "PROV FILA 4", 11: 100.00, 12: 18.00, 17: 25.00, 22: 143.00, 26: 3.7500,
        },
    ]
    excel_bytes = generar_excel_multinivel_prueba(rows)
    parser = ExcelParserService()
    res = parser.parse_excel(excel_bytes, "test.xlsx")

    assert len(res.filas) == 4

    # Fila 1:
    f1 = res.filas[0]
    assert f1.base_imponible == Decimal("100.00")
    assert f1.igv == Decimal("18.00")
    assert f1.valor_adquisiciones_no_gravadas is None
    assert f1.monto_base_igv == Decimal("118.00")
    assert f1.monto_calculado_original == Decimal("118.00")
    assert f1.tipo_cambio is None
    assert f1.monto_convertido is None
    assert f1.monto == Decimal("118.00")

    # Fila 2:
    f2 = res.filas[1]
    assert f2.base_imponible == Decimal("100.00")
    assert f2.igv == Decimal("18.00")
    assert f2.valor_adquisiciones_no_gravadas == Decimal("25.00")
    assert f2.monto_base_igv == Decimal("118.00")
    assert f2.monto_calculado_original == Decimal("143.00")
    assert f2.tipo_cambio is None
    assert f2.monto_convertido is None
    assert f2.monto == Decimal("143.00")

    # Fila 3:
    f3 = res.filas[2]
    assert f3.base_imponible == Decimal("100.00")
    assert f3.igv == Decimal("18.00")
    assert f3.valor_adquisiciones_no_gravadas is None  # NO se heredó el 25.00 de la fila 2
    assert f3.monto_base_igv == Decimal("118.00")
    assert f3.monto_calculado_original == Decimal("118.00")
    assert f3.tipo_cambio == Decimal("3.7500")
    assert f3.monto_convertido == Decimal("31.47")
    assert f3.monto == Decimal("31.47")

    # Fila 4:
    f4 = res.filas[3]
    assert f4.base_imponible == Decimal("100.00")
    assert f4.igv == Decimal("18.00")
    assert f4.valor_adquisiciones_no_gravadas == Decimal("25.00")
    assert f4.monto_base_igv == Decimal("118.00")
    assert f4.monto_calculado_original == Decimal("143.00")
    assert f4.tipo_cambio == Decimal("3.7500")
    assert f4.monto_convertido == Decimal("38.13")
    assert f4.monto == Decimal("38.13")


@pytest.mark.asyncio
async def test_req_test_7_archivo_real_filas_con_no_gravadas():
    """
    TEST 7 — CON ARCHIVO REAL
    Utilizar el Registro de Compras real disponible en el proyecto únicamente para parseo local.
    NO realizar consultas reales a SUNAT.
    Verificar filas 77 y 195 donde VALOR DE LAS ADQUISICIONES NO GRAVADAS tiene valores.
    """
    with open("tests/fixtures/reg_compras_real.xlsx", "rb") as f:
        file_bytes = f.read()

    parser = ExcelParserService()
    res = parser.parse_excel(file_bytes, "reg_compras_real.xlsx")

    # Diagnóstico debe haber detectado columna de adquisiciones no gravadas
    assert "Columna 17" in res.diagnostico.columnas_mapeadas.get("adquisiciones_no_gravadas", "")

    filas_map = {f.fila_excel: f for f in res.filas}

    # Fila 77:
    # Base = 10588.89, IGV = 1906.00, No gravadas = 5.11, Total = 12500.00, TC = None
    assert 77 in filas_map
    f77 = filas_map[77]
    assert f77.base_imponible == Decimal("10588.89")
    assert f77.igv == Decimal("1906.00")
    assert f77.valor_adquisiciones_no_gravadas == Decimal("5.11")
    assert f77.monto_base_igv == Decimal("12494.89")
    assert f77.monto_calculado_original == Decimal("12500.00")
    assert f77.tipo_cambio is None
    assert f77.monto_convertido is None
    assert f77.monto == Decimal("12500.00")
    assert f77.monto_sunat == Decimal("12500.00")

    # Fila 195 (Nota de crédito con Tipo de Cambio):
    # Base = -17917.50, IGV = -3225.15, No gravadas = -0.06, Total = -21142.71, TC = 3.3720
    assert 195 in filas_map
    f195 = filas_map[195]
    assert f195.base_imponible == Decimal("-17917.50")
    assert f195.igv == Decimal("-3225.15")
    assert f195.valor_adquisiciones_no_gravadas == Decimal("-0.06")
    assert f195.monto_base_igv == Decimal("-21142.65")
    assert f195.monto_calculado_original == Decimal("-21142.71")
    assert f195.tipo_cambio == Decimal("3.3720")
    # -21142.71 / 3.3720 = -6270.08007... -> -6270.08
    assert f195.monto_convertido == Decimal("-6270.08")
    assert f195.monto_original == Decimal("-6270.08")
    assert f195.monto == Decimal("6270.08")
    assert f195.monto_sunat == Decimal("6270.08")



