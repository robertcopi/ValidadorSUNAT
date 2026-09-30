import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator

# Agregar el directorio backend al sys.path para importar 'app'
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.empresa import Empresa
from app.models.usuario import Usuario

from sqlalchemy.pool import StaticPool
from app.core.rate_limit import login_rate_limiter
from app.services.proceso_masivo_service import proceso_masivo_service

# Base de datos SQLite en memoria para tests rápidos y aislados
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    login_rate_limiter.clear_all()
    proceso_masivo_service.set_session_factory(TestingSessionLocal)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Seed básico para tests
        empresa_daira = Empresa(ruc="20538976815", razon_social="DAIRA", activo=True)
        empresa_jjd = Empresa(ruc="20612689831", razon_social="GRUPO JJD MAR", activo=True)
        session.add_all([empresa_daira, empresa_jjd])
        await session.flush()

        test_pwd = get_password_hash("Password123!")

        admin = Usuario(
            username="admin",
            email="admin@test.local",
            nombre_completo="Admin Test",
            rol="ADMINISTRADOR",
            empresa_id=None,
            password_hash=test_pwd,
            activo=True
        )
        contador_daira = Usuario(
            username="contador.daira",
            email="contador.daira@test.local",
            nombre_completo="Contador DAIRA Test",
            rol="CONTADOR",
            empresa_id=empresa_daira.id,
            password_hash=test_pwd,
            activo=True
        )
        contador_jjd = Usuario(
            username="contador.jjd",
            email="contador.jjd@test.local",
            nombre_completo="Contador JJD Test",
            rol="CONTADOR",
            empresa_id=empresa_jjd.id,
            password_hash=test_pwd,
            activo=True
        )
        session.add_all([admin, contador_daira, contador_jjd])
        await session.commit()

        yield session

    # Cancelar o esperar tareas activas en segundo plano antes del teardown de la base de datos
    for task in list(proceso_masivo_service._active_tasks.values()):
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    proceso_masivo_service._active_tasks.clear()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
