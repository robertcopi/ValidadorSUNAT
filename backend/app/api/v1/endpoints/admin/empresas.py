from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_role, get_db
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.schemas.empresa import (
    EmpresaCreate,
    EmpresaEstadoUpdate,
    EmpresaResponse,
    EmpresaSunatStatusResponse,
    EmpresaUpdate,
)
from app.services.audit_service import audit_service
from app.services.sunat_service import sunat_service

router = APIRouter(dependencies=[Depends(require_role(["ADMINISTRADOR"]))])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("", response_model=List[EmpresaResponse])
async def list_empresas(
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
    q: Optional[str] = Query(None, description="Buscar por RUC o Razón Social"),
    db: AsyncSession = Depends(get_db)
):
    """Lista todas las empresas registradas junto con el total de usuarios asignados."""
    query = select(Empresa).order_by(Empresa.id.asc())

    if activo is not None:
        query = query.where(Empresa.activo == activo)
    if q:
        query = query.where((Empresa.ruc.ilike(f"%{q}%")) | (Empresa.razon_social.ilike(f"%{q}%")))

    result = await db.execute(query)
    empresas = result.scalars().all()

    # Contar usuarios por empresa
    responses = []
    for emp in empresas:
        count_res = await db.execute(select(func.count(Usuario.id)).where(Usuario.empresa_id == emp.id))
        total_u = count_res.scalar() or 0
        resp = EmpresaResponse.model_validate(emp)
        resp.total_usuarios = total_u
        responses.append(resp)

    return responses


@router.post("", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
async def create_empresa(
    payload: EmpresaCreate,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Crea una nueva empresa en el sistema.
    Valida que el RUC tenga exactamente 11 dígitos y sea único.
    """
    client_ip = _get_client_ip(request)
    ruc_clean = payload.ruc.strip()

    # Validar unicidad de RUC
    existing = await db.execute(select(Empresa).where(Empresa.ruc == ruc_clean))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una empresa registrada con el RUC {ruc_clean}."
        )

    nueva_empresa = Empresa(
        ruc=ruc_clean,
        razon_social=payload.razon_social.strip(),
        activo=payload.activo
    )
    db.add(nueva_empresa)
    await db.commit()
    await db.refresh(nueva_empresa)

    await audit_service.registrar_evento(
        db=db,
        accion="EMPRESA_CREADA",
        entidad="empresa",
        entidad_id=str(nueva_empresa.id),
        usuario_id=current_admin.id,
        empresa_id=nueva_empresa.id,
        detalle={
            "ruc": nueva_empresa.ruc,
            "razon_social": nueva_empresa.razon_social
        },
        ip=client_ip
    )

    resp = EmpresaResponse.model_validate(nueva_empresa)
    resp.total_usuarios = 0
    return resp


@router.get("/{empresa_id}", response_model=EmpresaResponse)
async def get_empresa(
    empresa_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene los datos de una empresa por ID."""
    res = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    emp = res.scalar_one_or_none()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada."
        )
    count_res = await db.execute(select(func.count(Usuario.id)).where(Usuario.empresa_id == emp.id))
    total_u = count_res.scalar() or 0
    resp = EmpresaResponse.model_validate(emp)
    resp.total_usuarios = total_u
    return resp


@router.put("/{empresa_id}", response_model=EmpresaResponse)
async def update_empresa(
    empresa_id: int,
    payload: EmpresaUpdate,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """Actualiza la razón social de una empresa."""
    client_ip = _get_client_ip(request)
    res = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    emp = res.scalar_one_or_none()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada."
        )

    if payload.razon_social is not None:
        emp.razon_social = payload.razon_social.strip()

    await db.commit()
    await db.refresh(emp)

    await audit_service.registrar_evento(
        db=db,
        accion="EMPRESA_EDITADA",
        entidad="empresa",
        entidad_id=str(emp.id),
        usuario_id=current_admin.id,
        empresa_id=emp.id,
        detalle={
            "ruc": emp.ruc,
            "razon_social": emp.razon_social
        },
        ip=client_ip
    )

    count_res = await db.execute(select(func.count(Usuario.id)).where(Usuario.empresa_id == emp.id))
    total_u = count_res.scalar() or 0
    resp = EmpresaResponse.model_validate(emp)
    resp.total_usuarios = total_u
    return resp


@router.patch("/{empresa_id}/estado", response_model=EmpresaResponse)
async def update_empresa_estado(
    empresa_id: int,
    payload: EmpresaEstadoUpdate,
    request: Request,
    current_admin: Usuario = Depends(require_role(["ADMINISTRADOR"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Baja lógica o reactivación de una empresa.
    No se elimina físicamente para preservar historial y auditoría.
    """
    client_ip = _get_client_ip(request)
    res = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    emp = res.scalar_one_or_none()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada."
        )

    emp.activo = payload.activo
    await db.commit()
    await db.refresh(emp)

    await audit_service.registrar_evento(
        db=db,
        accion="EMPRESA_EDITADA",
        entidad="empresa",
        entidad_id=str(emp.id),
        usuario_id=current_admin.id,
        empresa_id=emp.id,
        detalle={"ruc": emp.ruc, "activo": emp.activo},
        ip=client_ip
    )

    count_res = await db.execute(select(func.count(Usuario.id)).where(Usuario.empresa_id == emp.id))
    total_u = count_res.scalar() or 0
    resp = EmpresaResponse.model_validate(emp)
    resp.total_usuarios = total_u
    return resp


@router.get("/{empresa_id}/sunat-status", response_model=EmpresaSunatStatusResponse)
async def get_empresa_sunat_status(
    empresa_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Informa al administrador si las credenciales SUNAT están configuradas para la empresa.
    NUNCA devuelve secretos, client_id completo ni tokens.
    """
    res = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    emp = res.scalar_one_or_none()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada."
        )

    status_data = sunat_service.get_sunat_config_status(emp.ruc)
    return EmpresaSunatStatusResponse(**status_data)
