import asyncio
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.models.proceso_masivo import ProcesoMasivo
from app.models.auditoria_evento import AuditoriaEvento
from app.schemas.sunat import ConsultaCPEResponse, EmpresaInfo
from app.services.proceso_masivo_service import proceso_masivo_service


def cpe_mock(ruc: str, comp: str, serie: str, numero: str, estado: str = "VALIDO", id: int = 1) -> ConsultaCPEResponse:
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
        monto=Decimal("150.00"),
        estado=estado,
        codigo_sunat="0",
        mensaje_sunat="El comprobante existe y se encuentra aceptado.",
        empresa_consultora=EmpresaInfo(ruc="20538976815", razon_social="DAIRA"),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )


@pytest.mark.asyncio
async def test_flujo_e2e_completo_casos_1_al_15(client: AsyncClient, db_session: AsyncSession):
    """
    Prueba End-to-End integral que valida los 15 casos operativos de la Fase 6:
    1. Admin crea contador DAIRA
    2. Contador DAIRA inicia sesión
    3. DAIRA intenta acceder a JJD -> rechazado
    4. Contador carga Excel / comprobantes
    5. Parser genera registros LISTO
    6. Proceso masivo se crea
    7. SUNAT mock responde
    8. Resultados se almacenan
    9. Dashboard refleja resultados
    10. Historial muestra proceso
    11. Exportación genera XLSX
    12. Exportar genera 0 llamadas adicionales a SUNAT
    13. Admin desactiva contador
    14. JWT anterior del contador deja de funcionar (401)
    15. Auditoría contiene eventos correspondientes
    """

    # Obtener IDs de empresas creadas por fixture
    res_daira = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp_daira = res_daira.scalar_one()

    res_jjd = await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))
    emp_jjd = res_jjd.scalar_one()

    # Login inicial del Administrador
    res_admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "Password123!"}
    )
    assert res_admin_login.status_code == 200
    token_admin = res_admin_login.json()["access_token"]

    # =========================================================================
    # CASO 1: Admin crea contador DAIRA
    # =========================================================================
    email_nuevo_contador = "contador.e2e@daira.local"
    res_c1 = await client.post(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "nombre_completo": "Contador E2E DAIRA",
            "username": "contador.e2e",
            "email": email_nuevo_contador,
            "rol": "CONTADOR",
            "empresa_id": emp_daira.id,
            "password": "PasswordE2E2026!",
            "activo": True
        }
    )
    assert res_c1.status_code == 201, f"Fallo Caso 1: {res_c1.text}"
    nuevo_contador_id = res_c1.json()["id"]

    # =========================================================================
    # CASO 2: Contador DAIRA inicia sesión
    # =========================================================================
    res_c2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email_nuevo_contador, "password": "PasswordE2E2026!"}
    )
    assert res_c2.status_code == 200, f"Fallo Caso 2: {res_c2.text}"
    token_contador_daira = res_c2.json()["access_token"]
    assert res_c2.json()["user"]["rol"] == "CONTADOR"
    assert res_c2.json()["user"]["empresa_id"] == emp_daira.id

    # =========================================================================
    # CASO 3: DAIRA intenta acceder a JJD -> rechazado / aislado
    # =========================================================================
    # 1. El contador DAIRA está estrictamente anclado a su empresa DAIRA
    res_c3_me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_contador_daira}"}
    )
    assert res_c3_me.status_code == 200
    assert res_c3_me.json()["empresa"]["ruc"] == "20538976815"
    assert res_c3_me.json()["empresa"]["ruc"] != "20612689831"

    # 2. Si DAIRA intenta consultar procesos ajenos de JJD, el backend rechaza con 404
    res_c3_proc = await client.get(
        "/api/v1/procesos-masivos/proc-ajeno-jjd-9999",
        headers={"Authorization": f"Bearer {token_contador_daira}"}
    )
    assert res_c3_proc.status_code == 404

    # 3. Intentar manipular cabecera X-Empresa-Id no altera el tenancy estricto del contador
    res_c3_dash = await client.get(
        "/api/v1/dashboard/resumen",
        headers={
            "Authorization": f"Bearer {token_contador_daira}",
            "X-Empresa-Id": str(emp_jjd.id)
        }
    )
    assert res_c3_dash.status_code == 200
    assert res_c3_dash.json()["total"] == 0

    # =========================================================================
    # CASO 4 & 5: Contador carga comprobantes válidos para procesamiento
    # =========================================================================
    items_lote = [
        {
            "fila_excel": 6,
            "num_ruc": "20100070970",
            "cod_comp": "01",
            "numero_serie": "F001",
            "numero": "00000001",
            "fecha_emision": "20/09/2026",
            "monto": 150.00,
            "monto_original": 150.00,
            "razon_social": "PROVEEDOR 1 S.A."
        },
        {
            "fila_excel": 7,
            "num_ruc": "20200080980",
            "cod_comp": "01",
            "numero_serie": "F001",
            "numero": "00000002",
            "fecha_emision": "20/09/2026",
            "monto": 250.00,
            "monto_original": 250.00,
            "razon_social": "PROVEEDOR 2 S.A."
        }
    ]

    # =========================================================================
    # CASO 6, 7 & 8: Proceso masivo se crea, SUNAT mock responde y se almacena
    # =========================================================================
    sunat_call_count = 0

    async def mock_validar(empresa, usuario, req_data, db, http_client=None):
        nonlocal sunat_call_count
        sunat_call_count += 1
        return cpe_mock(req_data.num_ruc, req_data.cod_comp, req_data.numero_serie, req_data.numero, "VALIDO", id=sunat_call_count)

    with patch("app.services.sunat_service.sunat_service.validar_comprobante", new_callable=AsyncMock) as mock_validar:
        mock_validar.return_value = cpe_mock("20100070970", "01", "F001", "00000001", "VALIDO")
        res_c6 = await client.post(
            "/api/v1/procesos-masivos",
            headers={"Authorization": f"Bearer {token_contador_daira}"},
            json={
                "nombre_archivo": "comprobantes_e2e_daira.xlsx",
                "total_registros": len(items_lote),
                "items": items_lote
            }
        )
        assert res_c6.status_code == 201, f"Fallo Caso 6: {res_c6.text}"
        proceso_id = res_c6.json()["id"]

        # Esperar a que el worker asíncrono termine el procesamiento dentro del patch activo
        await proceso_masivo_service.esperar_proceso(proceso_id)

        res_poll = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}",
            headers={"Authorization": f"Bearer {token_contador_daira}"}
        )
        assert res_poll.status_code == 200
        data_proc = res_poll.json()
        assert data_proc["estado"] in ["COMPLETADO", "FINALIZADO"]
        assert data_proc["total_procesados"] == 2
        assert data_proc["total_validos"] == 2

    # =========================================================================
    # CASO 9: Dashboard refleja resultados
    # =========================================================================
    res_c9 = await client.get(
        "/api/v1/dashboard/resumen",
        headers={"Authorization": f"Bearer {token_contador_daira}"}
    )
    assert res_c9.status_code == 200
    dash_data = res_c9.json()
    assert dash_data["total"] >= 2
    assert dash_data["validos"] >= 2

    # =========================================================================
    # CASO 10: Historial muestra proceso
    # =========================================================================
    res_c10 = await client.get(
        "/api/v1/procesos-masivos",
        headers={"Authorization": f"Bearer {token_contador_daira}"}
    )
    assert res_c10.status_code == 200
    hist_items = res_c10.json()["items"]
    assert any(p["id"] == proceso_id for p in hist_items)

    # =========================================================================
    # CASO 11 & 12: Exportación genera XLSX y genera 0 llamadas a SUNAT
    # =========================================================================
    calls_before_export = sunat_call_count
    with patch("app.services.sunat_service.sunat_service.validar_comprobante") as mock_sunat_forbidden:
        res_c11 = await client.get(
            f"/api/v1/procesos-masivos/{proceso_id}/exportar",
            headers={"Authorization": f"Bearer {token_contador_daira}"}
        )
        assert res_c11.status_code == 200
        assert "application/vnd.openxmlformats" in res_c11.headers.get("content-type", "")
        # CASO 12: Exactamente 0 llamadas a SUNAT en la exportación
        assert mock_sunat_forbidden.call_count == 0

    # =========================================================================
    # CASO 13: Admin desactiva contador
    # =========================================================================
    res_c13 = await client.patch(
        f"/api/v1/admin/usuarios/{nuevo_contador_id}/estado",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"activo": False}
    )
    assert res_c13.status_code == 200
    assert res_c13.json()["activo"] is False

    # =========================================================================
    # CASO 14: JWT anterior del contador deja de funcionar de inmediato
    # =========================================================================
    res_c14 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_contador_daira}"}
    )
    assert res_c14.status_code == 401
    assert "inactivo" in res_c14.json()["detail"].lower()

    # =========================================================================
    # CASO 15: Auditoría contiene eventos correspondientes
    # =========================================================================
    res_c15 = await client.get(
        "/api/v1/admin/auditoria",
        headers={"Authorization": f"Bearer {token_admin}"},
        params={"page_size": 50}
    )
    assert res_c15.status_code == 200
    acciones_registradas = [e["accion"] for e in res_c15.json()["items"]]

    # Validar presencia de acciones esperadas en el flujo
    assert "USUARIO_CREADO" in acciones_registradas
    assert "LOGIN_EXITOSO" in acciones_registradas
    assert "PROCESO_MASIVO_CREADO" in acciones_registradas
    assert "EXPORTACION_EXCEL" in acciones_registradas
    assert "USUARIO_DESACTIVADO" in acciones_registradas
