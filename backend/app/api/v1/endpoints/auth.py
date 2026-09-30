from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.core.rate_limit import login_rate_limiter
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.usuario import Usuario
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse
from app.schemas.usuario import UsuarioResponse
from app.services.audit_service import audit_service

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """Extrae la IP del cliente considerando cabeceras de proxy si existen."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Inicia sesión validando credenciales por nombre de usuario (método principal)
    o por correo electrónico (compatibilidad).
    Implementa limitación de tasa (rate limiting) para prevenir fuerza bruta.
    Registra eventos de auditoría para intentos exitosos y fallidos.
    """
    raw_identifier = credentials.username or credentials.email or ""
    identifier_clean = raw_identifier.strip()
    identifier_lower = identifier_clean.lower()
    client_ip = _get_client_ip(request)
    rate_limit_key = f"{client_ip}:{identifier_lower}"

    # 1. Verificar si la IP/cuenta está temporalmente bloqueada por exceso de intentos
    if login_rate_limiter.is_rate_limited(rate_limit_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intente nuevamente más tarde."
        )

    # 2. Buscar usuario por username normalizado (principal), email o nombre completo (compatibilidad)
    query = select(Usuario).where(
        or_(
            func.lower(Usuario.username) == identifier_lower,
            func.lower(Usuario.email) == identifier_lower,
            func.lower(Usuario.nombre_completo) == identifier_lower,
        )
    )

    result = await db.execute(query)
    users = result.scalars().all()

    user = None
    if users:
        # Priorizar coincidencia exacta por username, luego por correo, luego por nombre completo
        user = next((u for u in users if u.username.lower() == identifier_lower), None)
        if not user:
            user = next((u for u in users if u.email.lower() == identifier_lower), None)
        if not user:
            user = next((u for u in users if u.nombre_completo.lower() == identifier_lower), users[0])

    # 3. Validar credenciales de forma genérica sin revelar si el usuario existe
    if not user or not verify_password(credentials.password, user.password_hash):
        login_rate_limiter.record_failure(rate_limit_key)
        await audit_service.registrar_evento(
            db=db,
            accion="LOGIN_FALLIDO",
            entidad="usuario",
            entidad_id=str(user.id) if user else None,
            usuario_id=user.id if user else None,
            empresa_id=user.empresa_id if user else None,
            detalle={"identificador": identifier_clean, "motivo": "credenciales_invalidas"},
            ip=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Validar si el usuario está activo
    if not user.activo:
        await audit_service.registrar_evento(
            db=db,
            accion="LOGIN_FALLIDO",
            entidad="usuario",
            entidad_id=str(user.id),
            usuario_id=user.id,
            empresa_id=user.empresa_id,
            detalle={"identificador": identifier_clean, "username": user.username, "motivo": "cuenta_desactivada"},
            ip=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra desactivada."
        )

    # 5. Restablecer contador de fallos y registrar éxito
    login_rate_limiter.reset(rate_limit_key)

    await audit_service.registrar_evento(
        db=db,
        accion="LOGIN_EXITOSO",
        entidad="usuario",
        entidad_id=str(user.id),
        usuario_id=user.id,
        empresa_id=user.empresa_id,
        detalle={"username": user.username, "email": user.email, "rol": user.rol},
        ip=client_ip
    )

    access_token = create_access_token(
        subject=user.id,
        empresa_id=user.empresa_id,
        rol=user.rol
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UsuarioResponse.model_validate(user)
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permite al usuario autenticado cambiar su propia contraseña.
    Valida la contraseña actual, que la nueva coincida con la confirmación,
    y que sea distinta a la actual.
    Actualiza must_change_password a False.
    """
    client_ip = _get_client_ip(request)

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual ingresada es incorrecta."
        )

    # Generar nuevo hash seguro mediante bcrypt
    current_user.password_hash = get_password_hash(payload.new_password)
    current_user.must_change_password = False

    await db.commit()
    await db.refresh(current_user)

    await audit_service.registrar_evento(
        db=db,
        accion="CAMBIO_PASSWORD",
        entidad="usuario",
        entidad_id=str(current_user.id),
        usuario_id=current_user.id,
        empresa_id=current_user.empresa_id,
        detalle={"email": current_user.email},
        ip=client_ip
    )

    return {"message": "Contraseña actualizada exitosamente."}


@router.get("/me", response_model=UsuarioResponse)
async def get_current_user_profile(current_user: Usuario = Depends(get_current_user)):
    """Retorna los datos del usuario autenticado y la empresa a la que pertenece."""
    return UsuarioResponse.model_validate(current_user)
