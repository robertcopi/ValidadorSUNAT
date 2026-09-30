import asyncio
import sys
from pathlib import Path

# Agregar directorio app al path para ejecución directa
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.empresa import Empresa
from app.models.usuario import Usuario


async def seed_data():
    """Puebla la base de datos con las empresas y usuarios de desarrollo de forma idempotente."""
    print("Iniciando semillero de datos (Seed)...")
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. EMPRESAS INICIALES
            empresas_data = [
                {"ruc": "20538976815", "razon_social": "DAIRA", "activo": True},
                {"ruc": "20612689831", "razon_social": "GRUPO JJD MAR", "activo": True},
            ]
            
            empresas_db = {}
            for emp_info in empresas_data:
                stmt = select(Empresa).where(Empresa.ruc == emp_info["ruc"])
                result = await session.execute(stmt)
                empresa = result.scalar_one_or_none()
                if not empresa:
                    empresa = Empresa(
                        ruc=emp_info["ruc"],
                        razon_social=emp_info["razon_social"],
                        activo=emp_info["activo"]
                    )
                    session.add(empresa)
                    await session.flush()
                    print(f" [+] Empresa creada: {empresa.razon_social} (RUC: {empresa.ruc})")
                else:
                    print(f" [=] Empresa ya existe: {empresa.razon_social} (RUC: {empresa.ruc})")
                empresas_db[emp_info["razon_social"]] = empresa

            # 2. USUARIOS INICIALES (ADMINISTRADOR Y CONTADORES)
            admin_pwd_hash = get_password_hash(settings.SEED_ADMIN_PASSWORD)
            contador_pwd_hash = get_password_hash(settings.SEED_CONTADOR_PASSWORD)

            usuarios_data = [
                # Administrador Global (sin empresa_id para alcance omnisciente)
                {
                    "username": "admin",
                    "email": settings.SEED_ADMIN_EMAIL,
                    "nombre_completo": "Administrador General",
                    "rol": "ADMINISTRADOR",
                    "empresa_id": None,
                    "password_hash": admin_pwd_hash,
                },
                # Contadores DAIRA
                {
                    "username": "contador1.daira",
                    "email": "contador1.daira@sistema.local",
                    "nombre_completo": "Contador 1 - DAIRA",
                    "rol": "CONTADOR",
                    "empresa_id": empresas_db["DAIRA"].id,
                    "password_hash": contador_pwd_hash,
                },
                {
                    "username": "contador2.daira",
                    "email": "contador2.daira@sistema.local",
                    "nombre_completo": "Contador 2 - DAIRA",
                    "rol": "CONTADOR",
                    "empresa_id": empresas_db["DAIRA"].id,
                    "password_hash": contador_pwd_hash,
                },
                # Contadores GRUPO JJD MAR
                {
                    "username": "contador1.jjdmar",
                    "email": "contador1.jjdmar@sistema.local",
                    "nombre_completo": "Contador 1 - GRUPO JJD MAR",
                    "rol": "CONTADOR",
                    "empresa_id": empresas_db["GRUPO JJD MAR"].id,
                    "password_hash": contador_pwd_hash,
                },
                {
                    "username": "contador2.jjdmar",
                    "email": "contador2.jjdmar@sistema.local",
                    "nombre_completo": "Contador 2 - GRUPO JJD MAR",
                    "rol": "CONTADOR",
                    "empresa_id": empresas_db["GRUPO JJD MAR"].id,
                    "password_hash": contador_pwd_hash,
                },
            ]

            for user_info in usuarios_data:
                stmt = select(Usuario).where(Usuario.email == user_info["email"])
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if not user:
                    user = Usuario(
                        username=user_info["username"],
                        email=user_info["email"],
                        nombre_completo=user_info["nombre_completo"],
                        rol=user_info["rol"],
                        empresa_id=user_info["empresa_id"],
                        password_hash=user_info["password_hash"],
                        activo=True
                    )
                    session.add(user)
                    print(f" [+] Usuario creado: {user.nombre_completo} (@{user.username} - {user.email}) - Rol: {user.rol}")
                else:
                    # Sincronizar clave de desarrollo para que coincida con las credenciales documentadas
                    user.password_hash = user_info["password_hash"]
                    user.activo = True
                    if not user.username:
                        user.username = user_info["username"]
                    print(f" [=] Usuario actualizado: {user.nombre_completo} (@{user.username} - {user.email})")

            await session.commit()
            print("Semillero completado exitosamente sin duplicados.")
        except Exception as e:
            await session.rollback()
            print(f"[!] Error durante la ejecución del semillero: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_data())
