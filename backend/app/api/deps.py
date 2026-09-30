from typing import List, Optional
import jwt
from fastapi import Depends, HTTPException, Security, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.empresa import Empresa
from app.models.usuario import Usuario

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> Usuario:
    """
    Valida el token JWT en el encabezado Authorization: Bearer <token>.
    Recupera el usuario completo desde la base de datos garantizando que esté activo.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionaron credenciales de autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: identificador de usuario ausente.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = select(Usuario).where(Usuario.id == user_id, Usuario.activo == True)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario no existe o se encuentra inactivo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_empresa(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_empresa_id: Optional[int] = Header(None, alias="X-Empresa-Id")
) -> Optional[Empresa]:
    """
    Resuelve la empresa activa para la operación:
    - CONTADOR: Obtiene de forma estricta la empresa asignada (ignora cualquier cabecera externa).
    - ADMINISTRADOR: Puede operar en el contexto de una empresa específica mediante la cabecera X-Empresa-Id
      o su empresa_id por defecto, permitiendo alcance global cuando sea None.
    """
    if current_user.rol == "CONTADOR":
        if not current_user.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El contador no tiene una empresa asignada."
            )
        if current_user.empresa:
            return current_user.empresa

        query = select(Empresa).where(Empresa.id == current_user.empresa_id, Empresa.activo == True)
        result = await db.execute(query)
        empresa = result.scalar_one_or_none()
        if not empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa asignada al contador no existe o está inactiva."
            )
        return empresa

    if current_user.rol == "ADMINISTRADOR":
        target_empresa_id = x_empresa_id or current_user.empresa_id
        if target_empresa_id:
            query = select(Empresa).where(Empresa.id == target_empresa_id, Empresa.activo == True)
            result = await db.execute(query)
            empresa = result.scalar_one_or_none()
            if not empresa:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"La empresa con ID {target_empresa_id} no existe o está inactiva."
                )
            return empresa
        return None

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Rol no autorizado para resolver contexto de empresa."
    )


def require_role(allowed_roles: List[str]):
    """Dependencia que restringe el acceso según el rol del usuario autenticado."""
    async def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene los permisos necesarios para realizar esta acción."
            )
        return current_user
    return role_checker
