import asyncio
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.core.config import settings
from app.models.proceso_masivo import ProcesoMasivo
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.models.consulta_cpe import ConsultaCPE
from app.models.auditoria_evento import AuditoriaEvento
from app.services.proceso_masivo_service import proceso_masivo_service


async def get_token_for(client: AsyncClient, email: str) -> str:
    """Helper para obtener token JWT de un usuario específico."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"}
    )
    assert res.status_code == 200, f"Login falló: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(autouse=True)
def mock_worker():
    """Evita lanzar workers asíncronos reales contra SUNAT durante tests de eliminación."""
    with patch.object(proceso_masivo_service, "iniciar_worker_asincrono") as m:
        yield m



def generar_items(n: int, ruc_base: str = "20100070970"):
    """Genera lista de items válidos para validación masiva."""
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
            "monto_original": 100.00 + i,
            "razon_social": f"PROVEEDOR PRUEBA {i}",
        })
    return items


# ==============================================================================
# TEST 1: Eliminar proceso con 220 items elimina únicamente ese proceso y sus items
# ==============================================================================
@pytest.mark.asyncio
async def test_eliminar_proceso_220_items_elimina_solo_ese_proceso_y_sus_items(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    items_220 = generar_items(220)

    # 1. Crear proceso con 220 comprobantes
    res_crear = await client.post(
        "/api/v1/procesos-masivos",
        json={
            "nombre_archivo": "Reg. Compras 09-2026.xlsx",
            "items": items_220,
        },
        headers=headers,
    )
    assert res_crear.status_code == 201
    proc_id = res_crear.json()["id"]

    # Verificar creación en BD
    stmt_proc = select(ProcesoMasivo).where(ProcesoMasivo.id == proc_id)
    proc_db = (await db_session.execute(stmt_proc)).scalar_one_or_none()
    assert proc_db is not None
    assert proc_db.total_registros == 220

    stmt_items = select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc_id)
    count_items = (await db_session.execute(stmt_items)).scalar()
    assert count_items == 220

    # 2. Eliminar el proceso masivo
    res_del = await client.delete(
        f"/api/v1/procesos-masivos/{proc_id}",
        headers=headers,
    )
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["success"] is True
    assert del_data["proceso_id"] == proc_id
    assert del_data["items_eliminados"] == 220
    assert del_data["mensaje"] == "Lote eliminado correctamente."

    # 3. Verificar que ya no existe en BD
    proc_after = (await db_session.execute(stmt_proc)).scalar_one_or_none()
    assert proc_after is None

    count_after = (await db_session.execute(stmt_items)).scalar()
    assert count_after == 0


# ==============================================================================
# TEST 2: Otro proceso del mismo archivo permanece intacto
# ==============================================================================
@pytest.mark.asyncio
async def test_otro_proceso_mismo_archivo_permanece_intacto(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    # Proceso 1 del mismo archivo
    res1 = await client.post(
        "/api/v1/procesos-masivos",
        json={
            "nombre_archivo": "Reg. Compras 09-2026.xlsx",
            "items": generar_items(5),
        },
        headers=headers,
    )
    assert res1.status_code == 201
    proc1_id = res1.json()["id"]

    # Proceso 2 del mismo archivo
    res2 = await client.post(
        "/api/v1/procesos-masivos",
        json={
            "nombre_archivo": "Reg. Compras 09-2026.xlsx",
            "items": generar_items(10),
        },
        headers=headers,
    )
    assert res2.status_code == 201
    proc2_id = res2.json()["id"]

    # Eliminar Proceso 1
    res_del = await client.delete(f"/api/v1/procesos-masivos/{proc1_id}", headers=headers)
    assert res_del.status_code == 200

    # Proceso 2 debe permanecer intacto
    stmt_proc2 = select(ProcesoMasivo).where(ProcesoMasivo.id == proc2_id)
    p2_db = (await db_session.execute(stmt_proc2)).scalar_one_or_none()
    assert p2_db is not None
    assert p2_db.total_registros == 10
    assert p2_db.nombre_archivo == "Reg. Compras 09-2026.xlsx"

    stmt_items2 = select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc2_id)
    assert (await db_session.execute(stmt_items2)).scalar() == 10


# ==============================================================================
# TEST 3: Eliminar un proceso no elimina otros procesos de la empresa
# ==============================================================================
@pytest.mark.asyncio
async def test_eliminar_un_proceso_no_elimina_otros_procesos(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    res_a = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Archivo_A.xlsx", "items": generar_items(3)},
        headers=headers,
    )
    res_b = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Archivo_B.xlsx", "items": generar_items(7)},
        headers=headers,
    )
    id_a = res_a.json()["id"]
    id_b = res_b.json()["id"]

    # Eliminar A
    await client.delete(f"/api/v1/procesos-masivos/{id_a}", headers=headers)

    # Listar procesos: B debe aparecer
    res_list = await client.get("/api/v1/procesos-masivos", headers=headers)
    assert res_list.status_code == 200
    ids_en_lista = [p["id"] for p in res_list.json()["items"]]
    assert id_a not in ids_en_lista
    assert id_b in ids_en_lista


# ==============================================================================
# TEST 4: CONTADOR DAIRA no puede eliminar proceso JJD
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_daira_no_puede_eliminar_proceso_jjd(client: AsyncClient, db_session):
    token_jjd = await get_token_for(client, "contador.jjd@test.local")
    res_jjd = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Lote_JJD.xlsx", "items": generar_items(4)},
        headers={"Authorization": f"Bearer {token_jjd}"},
    )
    id_jjd = res_jjd.json()["id"]

    # Contador DAIRA intenta eliminar lote de JJD
    token_daira = await get_token_for(client, "contador.daira@test.local")
    res_del = await client.delete(
        f"/api/v1/procesos-masivos/{id_jjd}",
        headers={"Authorization": f"Bearer {token_daira}"},
    )
    assert res_del.status_code == 404
    assert "No se encontró el proceso masivo" in res_del.json()["detail"]

    # Verificar que el lote de JJD sigue existiendo
    stmt_jjd = select(ProcesoMasivo).where(ProcesoMasivo.id == id_jjd)
    proc_jjd = (await db_session.execute(stmt_jjd)).scalar_one_or_none()
    assert proc_jjd is not None


# ==============================================================================
# TEST 5: CONTADOR JJD no puede eliminar proceso DAIRA
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_jjd_no_puede_eliminar_proceso_daira(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    res_daira = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Lote_DAIRA.xlsx", "items": generar_items(4)},
        headers={"Authorization": f"Bearer {token_daira}"},
    )
    id_daira = res_daira.json()["id"]

    # Contador JJD intenta eliminar lote de DAIRA
    token_jjd = await get_token_for(client, "contador.jjd@test.local")
    res_del = await client.delete(
        f"/api/v1/procesos-masivos/{id_daira}",
        headers={"Authorization": f"Bearer {token_jjd}"},
    )
    assert res_del.status_code == 404
    assert "No se encontró el proceso masivo" in res_del.json()["detail"]

    # Verificar que el lote de DAIRA sigue existiendo
    stmt_daira = select(ProcesoMasivo).where(ProcesoMasivo.id == id_daira)
    proc_daira = (await db_session.execute(stmt_daira)).scalar_one_or_none()
    assert proc_daira is not None


# ==============================================================================
# TEST 6: ID inexistente devuelve respuesta controlada 404
# ==============================================================================
@pytest.mark.asyncio
async def test_id_inexistente_devuelve_respuesta_controlada(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    fake_id = "00000000-0000-0000-0000-000000000000"
    res = await client.delete(
        f"/api/v1/procesos-masivos/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "No se encontró el proceso masivo con ID '00000000-0000-0000-0000-000000000000' para su empresa." in res.json()["detail"]


# ==============================================================================
# TEST 7: No quedan items huérfanos y limpia consultas_cpe exclusivas
# ==============================================================================
@pytest.mark.asyncio
async def test_no_quedan_items_huerfanos_ni_consultas_cpe_huerfanas(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Crear un proceso con 3 items
    res_proc = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Prueba_Huerfanos.xlsx", "items": generar_items(3)},
        headers=headers,
    )
    proc_id = res_proc.json()["id"]

    # 2. Insertar registros en consultas_cpe y vincularlos a los items simulando ejecución SUNAT
    stmt_items = select(ProcesoMasivoItem).where(ProcesoMasivoItem.proceso_id == proc_id)
    items = (await db_session.execute(stmt_items)).scalars().all()
    cpe_ids_creados = []
    for it in items:
        cpe = ConsultaCPE(
            empresa_id=1,
            usuario_id=2,
            ruc_emisor=it.num_ruc,
            tipo_comprobante=it.cod_comp,
            serie=it.numero_serie,
            numero=it.numero,
            fecha_emision=it.fecha_emision,
            monto=it.monto,
            estado="VALIDO",
            codigo_sunat="0",
            mensaje_sunat="Comprobante válido",
        )
        db_session.add(cpe)
        await db_session.flush()
        it.consulta_cpe_id = cpe.id
        cpe_ids_creados.append(cpe.id)

    # También crear una consulta_cpe independiente legítima que NO pertenece a este lote
    cpe_independiente = ConsultaCPE(
        empresa_id=1,
        usuario_id=2,
        ruc_emisor="20100070970",
        tipo_comprobante="01",
        serie="F001",
        numero="99999999",
        fecha_emision=datetime.date(2026, 9, 20),
        monto=Decimal("500.00"),
        estado="VALIDO",
        codigo_sunat="0",
        mensaje_sunat="Consulta individual independiente",
    )
    db_session.add(cpe_independiente)
    await db_session.commit()
    indep_id = cpe_independiente.id

    # 3. Eliminar el proceso masivo
    res_del = await client.delete(f"/api/v1/procesos-masivos/{proc_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["consultas_cpe_eliminadas"] == 3
    assert res_del.json()["items_eliminados"] == 3

    # 4. Verificar en BD:
    # No existen items con ese proceso_id
    count_items = (await db_session.execute(
        select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc_id)
    )).scalar()
    assert count_items == 0

    # Las consultas_cpe asociadas al lote fueron eliminadas
    stmt_cpe_deleted = select(func.count(ConsultaCPE.id)).where(ConsultaCPE.id.in_(cpe_ids_creados))
    count_cpe_deleted = (await db_session.execute(stmt_cpe_deleted)).scalar()
    assert count_cpe_deleted == 0

    # La consulta_cpe independiente permanece INTACTA
    stmt_indep = select(ConsultaCPE).where(ConsultaCPE.id == indep_id)
    cpe_indep_db = (await db_session.execute(stmt_indep)).scalar_one_or_none()
    assert cpe_indep_db is not None
    assert cpe_indep_db.mensaje_sunat == "Consulta individual independiente"


# ==============================================================================
# TEST 8: La eliminación no realiza llamadas a SUNAT
# ==============================================================================
@pytest.mark.asyncio
async def test_eliminacion_no_realiza_llamadas_a_sunat(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    res_proc = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Prueba_Sin_Sunat.xlsx", "items": generar_items(3)},
        headers=headers,
    )
    proc_id = res_proc.json()["id"]

    # Mockear cualquier llamada HTTP en httpx y en sunat_service
    with patch("httpx.AsyncClient.post") as mock_http_post, \
         patch("app.services.sunat_service.sunat_service.validar_comprobante") as mock_sunat:
        res_del = await client.delete(f"/api/v1/procesos-masivos/{proc_id}", headers=headers)
        assert res_del.status_code == 200
        # Verificar que ni HTTP a SUNAT ni validar_comprobante fueron llamados
        mock_http_post.assert_not_called()
        mock_sunat.assert_not_called()


# ==============================================================================
# TEST 9: Después de eliminar se puede volver a cargar/procesar el mismo archivo
# ==============================================================================
@pytest.mark.asyncio
async def test_despues_de_eliminar_se_puede_volver_a_cargar_mismo_archivo(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-key-repetida-001"}

    payload = {
        "nombre_archivo": "Reg. Compras 09-2026.xlsx",
        "items": generar_items(5),
    }

    # 1. Cargar proceso con la clave de idempotencia
    res1 = await client.post("/api/v1/procesos-masivos", json=payload, headers=headers)
    assert res1.status_code == 201
    proc1_id = res1.json()["id"]

    # Doble clic con la misma Idempotency-Key devuelve el mismo proceso existente (idempotencia activa)
    res_doble = await client.post("/api/v1/procesos-masivos", json=payload, headers=headers)
    assert res_doble.status_code == 200
    assert res_doble.json()["id"] == proc1_id

    # 2. Eliminar el lote de prueba
    res_del = await client.delete(f"/api/v1/procesos-masivos/{proc1_id}", headers=headers)
    assert res_del.status_code == 200

    # 3. Volver a cargar el MISMO archivo con la MISMA (o nueva) Idempotency-Key
    res_recarga = await client.post("/api/v1/procesos-masivos", json=payload, headers=headers)
    assert res_recarga.status_code == 201
    nuevo_id = res_recarga.json()["id"]

    # Debe ser un nuevo proceso válido
    assert nuevo_id != proc1_id
    assert res_recarga.json()["total_registros"] == 5
    assert res_recarga.json()["nombre_archivo"] == "Reg. Compras 09-2026.xlsx"


# ==============================================================================
# TEST 10: En production se respeta la restricción (CONTADOR bloqueado, ADMIN permitido)
# ==============================================================================
@pytest.mark.asyncio
async def test_restriccion_en_production_restringe_a_administrador(client: AsyncClient, db_session):
    token_contador = await get_token_for(client, "contador.daira@test.local")
    token_admin = await get_token_for(client, "admin@test.local")

    # Crear proceso como contador
    res_proc = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Lote_Produccion.xlsx", "items": generar_items(2)},
        headers={"Authorization": f"Bearer {token_contador}"},
    )
    proc_id = res_proc.json()["id"]

    # Simular entorno production sin debug
    with patch.object(settings, "ENVIRONMENT", "production"), \
         patch.object(settings, "DEBUG", False):

        # 1. CONTADOR intenta eliminar en production -> 403 Forbidden
        res_contador_del = await client.delete(
            f"/api/v1/procesos-masivos/{proc_id}",
            headers={"Authorization": f"Bearer {token_contador}"},
        )
        assert res_contador_del.status_code == 403
        assert "exclusivamente a usuarios administradores" in res_contador_del.json()["detail"]

        # Verificar que el proceso sigue intacto
        stmt_check = select(ProcesoMasivo).where(ProcesoMasivo.id == proc_id)
        assert (await db_session.execute(stmt_check)).scalar_one_or_none() is not None

        # 2. ADMINISTRADOR elimina en production -> 200 OK
        res_admin_del = await client.delete(
            f"/api/v1/procesos-masivos/{proc_id}",
            headers={
                "Authorization": f"Bearer {token_admin}",
                "X-Empresa-Id": "1",  # Contexto empresa DAIRA
            },
        )
        assert res_admin_del.status_code == 200
        assert res_admin_del.json()["success"] is True

        # Verificar eliminación efectiva
        assert (await db_session.execute(stmt_check)).scalar_one_or_none() is None


# ==============================================================================
# TEST 11: La auditoría de ELIMINAR_LOTE_PRUEBA permanece registrada
# ==============================================================================
@pytest.mark.asyncio
async def test_auditoria_eliminar_lote_prueba_permanece_registrada(client: AsyncClient, db_session):
    token = await get_token_for(client, "contador.daira@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    res_proc = await client.post(
        "/api/v1/procesos-masivos",
        json={"nombre_archivo": "Reg. Compras 09-2026.xlsx", "items": generar_items(15)},
        headers=headers,
    )
    proc_id = res_proc.json()["id"]

    # Eliminar proceso
    res_del = await client.delete(f"/api/v1/procesos-masivos/{proc_id}", headers=headers)
    assert res_del.status_code == 200

    # Consultar eventos de auditoría
    stmt_audit = select(AuditoriaEvento).where(
        AuditoriaEvento.accion == "ELIMINAR_LOTE_PRUEBA",
        AuditoriaEvento.entidad == "proceso_masivo",
        AuditoriaEvento.entidad_id == proc_id,
    )
    evento = (await db_session.execute(stmt_audit)).scalar_one_or_none()
    assert evento is not None
    assert evento.usuario_id == 2  # Contador DAIRA
    assert evento.empresa_id == 1  # DAIRA
    assert evento.detalle["nombre_archivo"] == "Reg. Compras 09-2026.xlsx"
    assert evento.detalle["total_registros"] == 15
    assert evento.detalle["items_eliminados"] == 15
    assert evento.created_at is not None
