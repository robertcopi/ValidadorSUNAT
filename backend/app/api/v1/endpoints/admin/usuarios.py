import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_role, get_db
from app.core.security import get_password_hash
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.schemas.auth import ResetPasswordResponse
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioEstadoUpdate,
    UsuarioResetPasswordRequest,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.services.audit_service import audit_service

router = APIRouter(dependencies=[Depends(require_role(["ADMINISTRADOR"]))])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("", response_model=List[UsuarioResponse])
async def list_usuarios(
    rol: Optional[str] = Query(None, description="Filtrar por rol (ADMINISTRADOR o CONTADOR)"),
    empresa_id: Optional[int] = Query(None, description="Filtrar por empresa asignada"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
    db: AsyncSession = Depends(get_db)
):
    """Lista todos los usuarios con filtros opcionales. Solo administradores."""
    query = select(Usuario).order_by(Usuario.id.asc())

    if rol:
        query = query.where(Usuario.rol == rol.upper())
    if empresa_id:
        query = query.where(Usuario.empresa_id == empresa_id)
    if activo is not None:
        query = query.where(Usuario.activo == activo)

    result = await db.execute(query)
    usuarios = result.scalars().all()
    return [UsuarioResponse.model_validate(u) for u in usuarios]


@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    payload: UsuarioCreate,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Crea un nuevo usuario en el sistema.
    Regla: CONTADOR debe pertenecer a exactamente una empresa válida.
    ADMINISTRADOR puede tener empresa_id = None.
    """
    client_ip = _get_client_ip(request)

    # 1. Validar unicidad de email
    email_clean = payload.email.strip().lower()
    existing_res = await db.execute(select(Usuario).where(Usuario.email == email_clean))
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )

    # 2. Validar empresa si es requerida
    if payload.rol == "CONTADOR":
        if not payload.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un usuario con rol CONTADOR debe pertenecer obligatoriamente a una empresa."
            )
        emp_res = await db.execute(select(Empresa).where(Empresa.id == payload.empresa_id))
        empresa = emp_res.scalar_one_or_none()
        if not empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa seleccionada no existe."
            )
        if not empresa.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede asignar un contador a una empresa inactiva."
            )
    elif payload.empresa_id is not None:
        # Administrador con empresa asignada opcional
        emp_res = await db.execute(select(Empresa).where(Empresa.id == payload.empresa_id))
        if not emp_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa seleccionada no existe."
            )

    # 3. Hashear contraseña con bcrypt
    hashed = get_password_hash(payload.password)

    nuevo_usuario = Usuario(
        nombre_completo=payload.nombre_completo.strip(),
        email=email_clean,
        password_hash=hashed,
        rol=payload.rol,
        empresa_id=payload.empresa_id,
        activo=payload.activo,
        must_change_password=False,
    )
    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)

    await audit_service.registrar_evento(
        db=db,
        accion="USUARIO_CREADO",
        entidad="usuario",
        entidad_id=str(nuevo_usuario.id),
        usuario_id=current_admin.id,
        empresa_id=nuevo_usuario.empresa_id,
        detalle={
            "email": nuevo_usuario.email,
            "nombre_completo": nuevo_usuario.nombre_completo,
            "rol": nuevo_usuario.rol,
            "empresa_id": nuevo_usuario.empresa_id
        },
        ip=client_ip
    )

    return UsuarioResponse.model_validate(nuevo_usuario)


@router.get("/{usuario_id}", response_model=UsuarioResponse)
async def get_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene los datos de un usuario por su ID."""
    res = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )
    return UsuarioResponse.model_validate(user)


@router.put("/{usuario_id}", response_model=UsuarioResponse)
async def update_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza datos de un usuario (nombre, email, empresa, rol).
    Valida restricciones de rol y empresa.
    """
    client_ip = _get_client_ip(request)
    res = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    # Validar email si cambia
    if payload.email is not None:
        clean_email = payload.email.strip().lower()
        if clean_email != user.email:
            dup = await db.execute(select(Usuario).where(Usuario.email == clean_email, Usuario.id != usuario_id))
            if dup.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El correo electrónico ya se encuentra en uso por otro usuario."
                )
            user.email = clean_email

    if payload.nombre_completo is not None:
        user.nombre_completo = payload.nombre_completo.strip()

    target_rol = payload.rol or user.rol
    user.rol = target_rol

    # Validar empresa según rol
    if target_rol == "CONTADOR":
        target_empresa_id = payload.empresa_id if payload.empresa_id is not None else user.empresa_id
        if not target_empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un usuario con rol CONTADOR no puede quedar sin empresa asignada."
            )
        emp_res = await db.execute(select(Empresa).where(Empresa.id == target_empresa_id))
        empresa = emp_res.scalar_one_or_none()
        if not empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa seleccionada no existe."
            )
        user.empresa_id = target_empresa_id
    elif payload.empresa_id is not None:
        if payload.empresa_id == 0:
            user.empresa_id = None
        else:
            emp_res = await db.execute(select(Empresa).where(Empresa.id == payload.empresa_id))
            if not emp_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La empresa seleccionada no existe."
                )
            user.empresa_id = payload.empresa_id

    await db.commit()
    await db.refresh(user)

    await audit_service.registrar_evento(
        db=db,
        accion="USUARIO_EDITADO",
        entidad="usuario",
        entidad_id=str(user.id),
        usuario_id=current_admin.id,
        empresa_id=user.empresa_id,
        detalle={
            "email": user.email,
            "nombre_completo": user.nombre_completo,
            "rol": user.rol,
            "empresa_id": user.empresa_id
        },
        ip=client_ip
    )

    return UsuarioResponse.model_validate(user)


@router.patch("/{usuario_id}/estado", response_model=UsuarioResponse)
async def update_usuario_estado(
    usuario_id: int,
    payload: UsuarioEstadoUpdate,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Baja lógica o reactivación de un usuario.
    No se permite desactivar a uno mismo si es el administrador logueado.
    """
    client_ip = _get_client_ip(request)
    if usuario_id == current_admin.id and not payload.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puede desactivar su propia cuenta de administrador."
        )

    res = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    user.activo = payload.activo
    await db.commit()
    await db.refresh(user)

    accion_auditoria = "USUARIO_ACTIVADO" if payload.activo else "USUARIO_DESACTIVADO"
    await audit_service.registrar_evento(
        db=db,
        accion=accion_auditoria,
        entidad="usuario",
        entidad_id=str(user.id),
        usuario_id=current_admin.id,
        empresa_id=user.empresa_id,
        detalle={"email": user.email, "activo": user.activo},
        ip=client_ip
    )

    return UsuarioResponse.model_validate(user)


@router.post("/{usuario_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password_admin(
    usuario_id: int,
    payload: UsuarioResetPasswordRequest,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Establece una contraseña temporal para el usuario y activa must_change_password=True.
    No expone hashes.
    """
    client_ip = _get_client_ip(request)
    res = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    # Generar contraseña temporal segura si no se especificó
    temp_pass = payload.temporary_password or f"Tmp#{secrets.token_urlsafe(8)}!"

    user.password_hash = get_password_hash(temp_pass)
    user.must_change_password = True

    await db.commit()
    await db.refresh(user)

    await audit_service.registrar_evento(
        db=db,
        accion="RESET_PASSWORD",
        entidad="usuario",
        entidad_id=str(user.id),
        usuario_id=current_admin.id,
        empresa_id=user.empresa_id,
        detalle={"email": user.email, "must_change_password": True},
        ip=client_ip
    )

    return ResetPasswordResponse(
        message="Contraseña temporal asignada correctamente. El usuario deberá cambiarla al iniciar sesión.",
        temporary_password=temp_pass,
        must_change_password=True
    )
