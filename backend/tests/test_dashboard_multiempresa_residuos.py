import pytest
import datetime
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.proceso_masivo import ProcesoMasivo
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.models.consulta_cpe import ConsultaCPE
from app.core.security import get_password_hash


async def create_user_and_token(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    username: str,
    nombre: str,
    rol: str,
    empresa_id: int | None
) -> str:
    pwd_hash = get_password_hash("Password123!")
    user = Usuario(
        username=username,
        email=email,
        nombre_completo=nombre,
        rol=rol,
        empresa_id=empresa_id,
        password_hash=pwd_hash,
        activo=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    res = await client.post("/api/v1/auth/login", json={"email": username, "password": "Password123!"})
    assert res.status_code == 200, f"Error login {username}: {res.text}"
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_dashboard_multiempresa_compartido_y_aislamiento(client: AsyncClient, db_session: AsyncSession):
    """
    Pruebas 1-7:
    1. Robert DAIRA ve datos DAIRA.
    2. Henry DAIRA ve los mismos datos DAIRA.
    3. Daniel DAIRA ve los mismos datos DAIRA.
    4. Ninguno de ellos ve datos JJD.
    5. Contador 1 JJD ve datos JJD.
    6. Contador 2 JJD ve los mismos datos JJD.
    7. Ninguno de ellos ve datos DAIRA.
    """
    res_daira = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp_daira = res_daira.scalar_one()

    res_jjd = await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))
    emp_jjd = res_jjd.scalar_one()

    # Tokens para usuarios DAIRA
    token_robert = await create_user_and_token(client, db_session, "robert@daira.local", "robert", "Robert Estela", "CONTADOR", emp_daira.id)
    token_henry = await create_user_and_token(client, db_session, "henry@daira.local", "henry", "Henry Delgado", "CONTADOR", emp_daira.id)
    token_daniel = await create_user_and_token(client, db_session, "daniel@daira.local", "daniel", "Daniel Bernal", "CONTADOR", emp_daira.id)

    # Tokens para usuarios JJD MAR
    token_jjd1 = await create_user_and_token(client, db_session, "cont1@jjd.local", "cont1_jjd", "Contador 1 - JJD", "CONTADOR", emp_jjd.id)
    token_jjd2 = await create_user_and_token(client, db_session, "cont2@jjd.local", "cont2_jjd", "Contador 2 - JJD", "CONTADOR", emp_jjd.id)

    # Insertar consultas en DAIRA (3 válidas, 1 no válida)
    for i, estado in enumerate(["VALIDO", "VALIDO", "VALIDO", "NO_VALIDO"]):
        db_session.add(ConsultaCPE(
            empresa_id=emp_daira.id,
            usuario_id=2,  # creado
            ruc_emisor="20123456789",
            tipo_comprobante="01",
            serie="F001",
            numero=str(100 + i),
            fecha_emision=datetime.date(2026, 9, 1),
            monto=Decimal("150.00"),
            estado=estado
        ))

    # Insertar consultas en JJD MAR (2 válidas)
    for i in range(2):
        db_session.add(ConsultaCPE(
            empresa_id=emp_jjd.id,
            usuario_id=4,
            ruc_emisor="20987654321",
            tipo_comprobante="01",
            serie="F002",
            numero=str(200 + i),
            fecha_emision=datetime.date(2026, 9, 2),
            monto=Decimal("250.00"),
            estado="VALIDO"
        ))
    await db_session.commit()

    # 1. Robert DAIRA
    res_r = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_robert}"})
    assert res_r.status_code == 200
    data_r = res_r.json()
    assert data_r["total"] == 4
    assert data_r["validos"] == 3
    assert data_r["no_validos"] == 1

    # 2. Henry DAIRA ve exactamente los mismos datos
    res_h = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_henry}"})
    assert res_h.status_code == 200
    data_h = res_h.json()
    assert data_h["total"] == 4
    assert data_h["validos"] == 3

    # 3. Daniel DAIRA ve exactamente los mismos datos
    res_d = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_daniel}"})
    assert res_d.status_code == 200
    data_d = res_d.json()
    assert data_d["total"] == 4

    # 5. Contador 1 JJD ve sólo datos JJD (total 2)
    res_j1 = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_jjd1}"})
    assert res_j1.status_code == 200
    data_j1 = res_j1.json()
    assert data_j1["total"] == 2
    assert data_j1["validos"] == 2

    # 6. Contador 2 JJD ve los mismos datos JJD (total 2)
    res_j2 = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_jjd2}"})
    assert res_j2.status_code == 200
    data_j2 = res_j2.json()
    assert data_j2["total"] == 2

    # 4 y 7: Comprobación de que no se mezclan los datos (4 != 2)


@pytest.mark.asyncio
async def test_administrador_vision_consolidada(client: AsyncClient, db_session: AsyncSession):
    """
    Pruebas 8, 9 y 10:
    8. Administrador ve DAIRA + JJD en Visión Consolidada.
    9. Si DAIRA tiene 19 y JJD 0 -> ADMIN muestra 19.
    10. Si DAIRA tiene 300 y JJD 200 -> ADMIN muestra 500.
    """
    res_daira = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp_daira = res_daira.scalar_one()

    res_jjd = await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))
    emp_jjd = res_jjd.scalar_one()

    token_admin = await create_user_and_token(client, db_session, "admin2@test.local", "superadmin", "Admin Sup", "ADMINISTRADOR", None)

    # Caso 9: DAIRA = 19 (5 válidos, 1 no válido, 0 observados, 13 errores), JJD = 0
    for i in range(5):
        db_session.add(ConsultaCPE(
            empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20111111111", tipo_comprobante="01",
            serie="F001", numero=f"V{i}", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("100"), estado="VALIDO"
        ))
    db_session.add(ConsultaCPE(
        empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20111111111", tipo_comprobante="01",
        serie="F001", numero="NV1", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("100"), estado="NO_VALIDO"
    ))
    for i in range(13):
        db_session.add(ConsultaCPE(
            empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20111111111", tipo_comprobante="01",
            serie="F001", numero=f"E{i}", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("100"), estado="ERROR"
        ))
    await db_session.commit()

    # Admin consulta dashboard sin cabecera X-Empresa-Id (Visión Consolidada)
    res_admin = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin.status_code == 200
    data_adm = res_admin.json()
    assert data_adm["total"] == 19
    assert data_adm["validos"] == 5
    assert data_adm["no_validos"] == 1
    assert data_adm["observados"] == 0
    assert data_adm["errores"] == 13

    # Caso 10: Agregar 200 comprobantes a JJD y 281 más a DAIRA (DAIRA=300, JJD=200 -> Total=500)
    for i in range(281):
        db_session.add(ConsultaCPE(
            empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20111111111", tipo_comprobante="01",
            serie="F001", numero=f"DV{i}", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("100"), estado="VALIDO"
        ))
    for i in range(200):
        db_session.add(ConsultaCPE(
            empresa_id=emp_jjd.id, usuario_id=1, ruc_emisor="20222222222", tipo_comprobante="01",
            serie="F002", numero=f"JV{i}", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("100"), estado="VALIDO"
        ))
    await db_session.commit()

    res_admin_500 = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin_500.status_code == 200
    data_500 = res_admin_500.json()
    assert data_500["total"] == 500


@pytest.mark.asyncio
async def test_eliminacion_lote_residuos_y_aislamiento(client: AsyncClient, db_session: AsyncSession):
    """
    Pruebas 11-15:
    11. Eliminar un lote elimina correctamente sus datos dependientes de prueba.
    12. Eliminar un lote NO elimina consultas individuales legítimas.
    13. Eliminar un lote DAIRA NO afecta JJD.
    14. No quedan registros huérfanos después de eliminar un lote.
    15. Dashboard queda consistente después de eliminar un lote.
    """
    res_daira = await db_session.execute(select(Empresa).where(Empresa.ruc == "20538976815"))
    emp_daira = res_daira.scalar_one()

    res_jjd = await db_session.execute(select(Empresa).where(Empresa.ruc == "20612689831"))
    emp_jjd = res_jjd.scalar_one()

    token_daira = await create_user_and_token(client, db_session, "cont_del@daira.local", "cont_del", "Cont Del", "CONTADOR", emp_daira.id)
    token_jjd = await create_user_and_token(client, db_session, "cont_jjd_del@jjd.local", "cont_jjd_del", "Cont JJD Del", "CONTADOR", emp_jjd.id)

    # 1. Consulta individual legítima previa en DAIRA
    cpe_legitima = ConsultaCPE(
        empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20123456789", tipo_comprobante="01",
        serie="F001", numero="9999", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("80"), estado="VALIDO"
    )
    # Consulta legítima previa en JJD
    cpe_jjd = ConsultaCPE(
        empresa_id=emp_jjd.id, usuario_id=1, ruc_emisor="20999999999", tipo_comprobante="01",
        serie="F002", numero="8888", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("120"), estado="VALIDO"
    )
    db_session.add_all([cpe_legitima, cpe_jjd])
    await db_session.commit()
    await db_session.refresh(cpe_legitima)
    await db_session.refresh(cpe_jjd)

    import uuid
    proceso_daira = ProcesoMasivo(
        id=str(uuid.uuid4()),
        empresa_id=emp_daira.id,
        usuario_id=1,
        nombre_archivo="Lote_Prueba_DAIRA.xlsx",
        idempotency_key="idemp_test_daira_1",
        total_registros=2,
        total_procesados=2,
        total_validos=2,
        total_no_validos=0,
        total_observados=0,
        total_errores=0,
        porcentaje=Decimal("100.00"),
        estado="COMPLETADO"
    )
    db_session.add(proceso_daira)
    await db_session.commit()
    await db_session.refresh(proceso_daira)

    cpe_lote1 = ConsultaCPE(
        empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20555555555", tipo_comprobante="01",
        serie="F005", numero="1", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("50"), estado="VALIDO"
    )
    cpe_lote2 = ConsultaCPE(
        empresa_id=emp_daira.id, usuario_id=1, ruc_emisor="20555555555", tipo_comprobante="01",
        serie="F005", numero="2", fecha_emision=datetime.date(2026, 9, 1), monto=Decimal("50"), estado="VALIDO"
    )
    db_session.add_all([cpe_lote1, cpe_lote2])
    await db_session.commit()
    await db_session.refresh(cpe_lote1)
    await db_session.refresh(cpe_lote2)

    item1 = ProcesoMasivoItem(
        proceso_id=proceso_daira.id, fila_excel=1, num_ruc="20555555555", cod_comp="01",
        numero_serie="F005", numero="1", fecha_emision=datetime.date(2026, 9, 1),
        monto=Decimal("50"), estado="VALIDO", consulta_cpe_id=cpe_lote1.id
    )
    item2 = ProcesoMasivoItem(
        proceso_id=proceso_daira.id, fila_excel=2, num_ruc="20555555555", cod_comp="01",
        numero_serie="F005", numero="2", fecha_emision=datetime.date(2026, 9, 1),
        monto=Decimal("50"), estado="VALIDO", consulta_cpe_id=cpe_lote2.id
    )
    db_session.add_all([item1, item2])
    await db_session.commit()

    # Dashboard antes de eliminar: DAIRA debe mostrar 3 (1 legítima + 2 de lote)
    res_dash_antes = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_dash_antes.json()["total"] == 3

    # 11 y 13: Eliminar el lote de DAIRA
    res_del = await client.delete(f"/api/v1/procesos-masivos/{proceso_daira.id}", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 12: Comprobar que la consulta legítima de DAIRA NO fue eliminada
    cpe_leg_check = (await db_session.execute(select(ConsultaCPE).where(ConsultaCPE.id == cpe_legitima.id))).scalar_one_or_none()
    assert cpe_leg_check is not None

    # 11: Comprobar que las consultas exclusivas del lote SI fueron eliminadas
    cpe1_check = (await db_session.execute(select(ConsultaCPE).where(ConsultaCPE.id == cpe_lote1.id))).scalar_one_or_none()
    cpe2_check = (await db_session.execute(select(ConsultaCPE).where(ConsultaCPE.id == cpe_lote2.id))).scalar_one_or_none()
    assert cpe1_check is None
    assert cpe2_check is None

    # 13: Comprobar que JJD sigue intacto con su consulta legítima
    cpe_jjd_check = (await db_session.execute(select(ConsultaCPE).where(ConsultaCPE.id == cpe_jjd.id))).scalar_one_or_none()
    assert cpe_jjd_check is not None

    # 14: No quedan items huérfanos de ese proceso
    items_count = (await db_session.execute(select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proceso_daira.id))).scalar()
    assert items_count == 0

    # 15: Dashboard de DAIRA ahora muestra exactamente 1 (solo la legítima)
    res_dash_despues = await client.get("/api/v1/dashboard/resumen", headers={"Authorization": f"Bearer {token_daira}"})
    assert res_dash_despues.json()["total"] == 1
    assert res_dash_despues.json()["validos"] == 1
