import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from app.core.config import settings

USERNAME_REGEX = re.compile(r"^[a-z0-9._-]+$")


def normalize_username(username: Optional[str]) -> str:
    """
    Normaliza el nombre de usuario eliminando espacios al inicio y final
    y convirtiendo todo a minúsculas.
    """
    if not username:
        return ""
    return username.strip().lower()


def validate_username(username: str) -> str:
    """
    Valida y retorna el nombre de usuario normalizado.
    Reglas:
    - Longitud entre 3 y 50 caracteres.
    - Caracteres permitidos: a-z, 0-9, punto (.), guion bajo (_) y guion medio (-).
    """
    normalized = normalize_username(username)
    if len(normalized) < 3 or len(normalized) > 50:
        raise ValueError("El nombre de usuario debe tener entre 3 y 50 caracteres.")
    if not USERNAME_REGEX.match(normalized):
        raise ValueError("El nombre de usuario solo puede contener letras, números y los caracteres '.', '_', '-'.")
    return normalized



def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con el hash bcrypt almacenado."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Genera un hash seguro mediante bcrypt nativo."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    subject: Union[str, Any],
    empresa_id: Optional[int],
    rol: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Genera un token JWT firmado.
    Incluye:
    - sub: ID del usuario
    - empresa_id: ID de la empresa (o None si es Admin global)
    - rol: Rol del usuario (ADMINISTRADOR | CONTADOR)
    - exp: Timestamp de expiración
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "empresa_id": empresa_id,
        "rol": rol,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
