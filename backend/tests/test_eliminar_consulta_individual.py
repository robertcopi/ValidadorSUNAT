import datetime
from decimal import Decimal
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.consulta_cpe import ConsultaCPE
from app.models.proceso_masivo import ProcesoMasivo
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.models.auditoria_evento import AuditoriaEvento


async def get_token_for(client: AsyncClient, email: str) -> str:
    """Helper para autenticar un usuario y obtener su JWT."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"}
    )
    assert res.status_code == 200, f"Login falló: {res.text}"
    return res.json()["access_token"]


async def crear_consulta_cpe(
    db_session,
    empresa_id: int,
    usuario_id: int,
    tipo: str = "01",
    serie: str = "F001",
    numero: str = "00000410",
    ruc: str = "20612689831",
    monto: Decimal = Decimal("9023.60"),
    estado: str = "VALIDO",
) -> ConsultaCPE:
    consulta = ConsultaCPE(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        ruc_emisor=ruc,
        tipo_comprobante=tipo,
        serie=serie,
        numero=numero,
        fecha_emision=datetime.date(2026, 9, 20),
        monto=monto,
        estado=estado,
        codigo_sunat="0",
        mensaje_sunat="El comprobante número F001-00000410 ha sido informado.",
        respuesta_sunat={"estadoCp": "1"},
    )
    db_session.add(consulta)
    await db_session.commit()
    await db_session.refresh(consulta)
    return consulta


# ==============================================================================
# TEST 1: CONTADOR DAIRA elimina consulta individual DAIRA -> 200 y desaparece
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_daira_elimina_consulta_propia_exito(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    user_daira = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))).scalar_one()

    # 1. Crear consulta para DAIRA
    consulta = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="F001", numero="00000410")
    consulta_id = consulta.id

    # 2. Eliminar consulta
    res = await client.delete(
        f"/api/v1/sunat/consultas/{consulta_id}",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 200
    assert res.json() == {"message": "Consulta eliminada correctamente"}

    # 3. Verificar que desapareció de consultas_cpe
    stmt = select(ConsultaCPE).where(ConsultaCPE.id == consulta_id)
    cpe_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert cpe_db is None


# ==============================================================================
# TEST 2: CONTADOR DAIRA intenta eliminar consulta JJD -> no permitido (404)
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_daira_intenta_eliminar_consulta_jjd_rechazado(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    emp_jjd = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))).scalar_one()
    user_jjd = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.jjd@test.local"))).scalar_one()

    # Consulta perteneciente a JJD
    consulta_jjd = await crear_consulta_cpe(db_session, emp_jjd.id, user_jjd.id, serie="F002", numero="00000100")

    # Contador DAIRA intenta eliminarla
    res = await client.delete(
        f"/api/v1/sunat/consultas/{consulta_jjd.id}",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 404

    # Verificar que el registro de JJD sigue intacto
    stmt = select(ConsultaCPE).where(ConsultaCPE.id == consulta_jjd.id)
    cpe_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert cpe_db is not None


# ==============================================================================
# TEST 3: CONTADOR JJD intenta eliminar consulta DAIRA -> no permitido (404)
# ==============================================================================
@pytest.mark.asyncio
async def test_contador_jjd_intenta_eliminar_consulta_daira_rechazado(client: AsyncClient, db_session):
    token_jjd = await get_token_for(client, "contador.jjd@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    user_daira = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))).scalar_one()

    # Consulta perteneciente a DAIRA
    consulta_daira = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="E001", numero="14991")

    # Contador JJD intenta eliminarla
    res = await client.delete(
        f"/api/v1/sunat/consultas/{consulta_daira.id}",
        headers={"Authorization": f"Bearer {token_jjd}"}
    )
    assert res.status_code == 404

    # Verificar que el registro de DAIRA sigue intacto
    stmt = select(ConsultaCPE).where(ConsultaCPE.id == consulta_daira.id)
    cpe_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert cpe_db is not None


# ==============================================================================
# TEST 4: ID inexistente -> 404
# ==============================================================================
@pytest.mark.asyncio
async def test_eliminar_consulta_id_inexistente_retorna_404(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")

    res = await client.delete(
        "/api/v1/sunat/consultas/999999",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 404


# ==============================================================================
# TEST 5: Consulta vinculada a proceso_masivo_items -> 409 y no se elimina
# ==============================================================================
@pytest.mark.asyncio
async def test_consulta_vinculada_a_proceso_masivo_retorna_409(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    user_daira = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))).scalar_one()

    # 1. Crear consulta
    consulta = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="F001", numero="00000412")

    # 2. Crear proceso masivo e item vinculado a esta consulta
    proc = ProcesoMasivo(
        id="proc-test-vinculado-123",
        empresa_id=emp_daira.id,
        usuario_id=user_daira.id,
        nombre_archivo="Lote_Prueba.xlsx",
        estado="COMPLETADO",
        total_registros=1,
        total_procesados=1,
        total_validos=1,
    )
    db_session.add(proc)
    await db_session.flush()

    item = ProcesoMasivoItem(
        proceso_id=proc.id,
        fila_excel=2,
        num_ruc="20612689831",
        cod_comp="01",
        numero_serie="F001",
        numero="00000412",
        fecha_emision=datetime.date(2026, 9, 20),
        monto=Decimal("9023.60"),
        estado="VALIDO",
        consulta_cpe_id=consulta.id,
    )
    db_session.add(item)
    await db_session.commit()

    # 3. Intentar eliminar individualmente la consulta vinculada al lote
    res = await client.delete(
        f"/api/v1/sunat/consultas/{consulta.id}",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 409
    assert "pertenece a un lote masivo" in res.json()["detail"]

    # 4. Verificar que la consulta sigue existiendo
    stmt = select(ConsultaCPE).where(ConsultaCPE.id == consulta.id)
    cpe_db = (await db_session.execute(stmt)).scalar_one_or_none()
    assert cpe_db is not None


# ==============================================================================
# TEST 6: Eliminación reduce correctamente el resumen/dashboard
# ==============================================================================
@pytest.mark.asyncio
async def test_eliminacion_reduce_correctamente_dashboard(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    user_daira = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))).scalar_one()

    # 1. Crear dos consultas individuales válidas
    c1 = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="F001", numero="00000413", estado="VALIDO")
    c2 = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="F001", numero="00000414", estado="VALIDO")

    # 2. Verificar dashboard antes de eliminar
    res_dash_antes = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_dash_antes.status_code == 200
    data_antes = res_dash_antes.json()
    assert data_antes["total"] == 2
    assert data_antes["validos"] == 2

    # 3. Eliminar una consulta
    res_del = await client.delete(
        f"/api/v1/sunat/consultas/{c1.id}",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res_del.status_code == 200

    # 4. Verificar dashboard después de eliminar
    res_dash_despues = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_dash_despues.status_code == 200
    data_despues = res_dash_despues.json()
    assert data_despues["total"] == 1
    assert data_despues["validos"] == 1


# ==============================================================================
# TEST 7: Se crea evento de auditoría
# ==============================================================================
@pytest.mark.asyncio
async def test_se_crea_evento_de_auditoria(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    user_daira = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))).scalar_one()

    consulta = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="F001", numero="00000415")
    consulta_id = consulta.id

    res = await client.delete(
        f"/api/v1/sunat/consultas/{consulta_id}",
        headers={"Authorization": f"Bearer {token_daira}"}
    )
    assert res.status_code == 200

    # Verificar registro en auditoria_eventos
    stmt = select(AuditoriaEvento).where(
        AuditoriaEvento.accion == "ELIMINAR_CONSULTA_INDIVIDUAL",
        AuditoriaEvento.entidad == "consultas_cpe",
        AuditoriaEvento.entidad_id == str(consulta_id),
    )
    evento = (await db_session.execute(stmt)).scalar_one_or_none()
    assert evento is not None
    assert evento.usuario_id == user_daira.id
    assert evento.empresa_id == emp_daira.id
    assert evento.detalle["serie"] == "F001"
    assert evento.detalle["numero"] == "00000415"
    assert evento.detalle["ruc_emisor"] == "20612689831"

    # Verificar que no contenga credenciales ni secretos
    for key in ["token", "client_secret", "password", "password_hash"]:
        assert key not in evento.detalle


# ==============================================================================
# TEST 8: ADMIN respeta el contexto multiempresa existente
# ==============================================================================
@pytest.mark.asyncio
async def test_admin_respeta_contexto_multiempresa(client: AsyncClient, db_session):
    token_admin = await get_token_for(client, "admin@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    emp_jjd = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))).scalar_one()
    user_admin = (await db_session.execute(select(Usuario).where(Usuario.email == "admin@test.local"))).scalar_one()

    # Consulta perteneciente a DAIRA
    c_daira = await crear_consulta_cpe(db_session, emp_daira.id, user_admin.id, serie="F001", numero="00000416")

    # 1. Admin con contexto DAIRA (X-Empresa-Id: 1) elimina consulta DAIRA -> 200
    res1 = await client.delete(
        f"/api/v1/sunat/consultas/{c_daira.id}",
        headers={
            "Authorization": f"Bearer {token_admin}",
            "X-Empresa-Id": str(emp_daira.id)
        }
    )
    assert res1.status_code == 200

    # 2. Nueva consulta para DAIRA
    c_daira_2 = await crear_consulta_cpe(db_session, emp_daira.id, user_admin.id, serie="F001", numero="00000417")

    # Admin con contexto JJD (X-Empresa-Id: 2) intenta eliminar consulta DAIRA -> 404 (aislamiento por contexto)
    res2 = await client.delete(
        f"/api/v1/sunat/consultas/{c_daira_2.id}",
        headers={
            "Authorization": f"Bearer {token_admin}",
            "X-Empresa-Id": str(emp_jjd.id)
        }
    )
    assert res2.status_code == 404

    # 3. Admin sin contexto específico (global) puede eliminar
    res3 = await client.delete(
        f"/api/v1/sunat/consultas/{c_daira_2.id}",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert res3.status_code == 200


# ==============================================================================
# TEST 9: CERO llamadas HTTP externas a SUNAT durante la eliminación
# ==============================================================================
@pytest.mark.asyncio
async def test_cero_llamadas_http_a_sunat_al_eliminar(client: AsyncClient, db_session):
    token_daira = await get_token_for(client, "contador.daira@test.local")
    emp_daira = (await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))).scalar_one()
    user_daira = (await db_session.execute(select(Usuario).where(Usuario.email == "contador.daira@test.local"))).scalar_one()

    consulta = await crear_consulta_cpe(db_session, emp_daira.id, user_daira.id, serie="F001", numero="00000418")

    # Mock que fallaría si se llama a sunat
    with patch("httpx.AsyncClient.post") as mock_post:
        res = await client.delete(
            f"/api/v1/sunat/consultas/{consulta.id}",
            headers={"Authorization": f"Bearer {token_daira}"}
        )
        assert res.status_code == 200
        mock_post.assert_not_called()
