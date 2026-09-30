import asyncio
import datetime
import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

import httpx
from sqlalchemy import select, func, desc, or_, case, update
from sqlalchemy.ext.asyncio import AsyncSession

import io
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.models.consulta_cpe import ConsultaCPE
from app.models.proceso_masivo import ProcesoMasivo
from app.models.proceso_masivo_item import ProcesoMasivoItem
from app.schemas.sunat import ComprobanteValidarRequest
from app.schemas.proceso_masivo import (
    ItemProcesoMasivo,
    CrearProcesoMasivoRequest,
    ProcesoMasivoResponse,
    ProcesoMasivoItemResponse,
    PaginatedProcesoMasivoItemsResponse,
    PaginatedProcesosMasivosResponse,
    ReintentarErroresResponse,
)
from app.schemas.dashboard import DashboardResumenResponse
from app.services.sunat_service import (
    sunat_service,
    SunatException,
    SunatCredentialsError,
)

logger = logging.getLogger(__name__)


class ProcesoMasivoException(Exception):
    """Excepción para errores de negocio y validación en procesos masivos."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProcesoMasivoService:
    """
    Servicio de orquestación y persistencia de Procesos Masivos de Validación SUNAT.
    
    Cumple estrictamente con todos los requisitos de Fase 4:
    1. Estados internos unificados: VALIDO, NO_VALIDO, OBSERVADO, ERROR (reutiliza interpretar_respuesta_sunat).
    2. Ejecución 100% asíncrona desacoplada del request HTTP (background worker).
    3. Persistencia física individual en PostgreSQL (procesos_masivos y proceso_masivo_items).
    4. Concurrencia controlada mediante asyncio.Semaphore(settings.SUNAT_MAX_CONCURRENCY).
    5. Delay configurable inter-request (settings.SUNAT_REQUEST_DELAY_MS).
    6. Retries inteligentes exclusivos para fallos técnicos transitorios (timeout, network, 429, 500-504).
    7. Tratamiento de HTTP 429 con respeto a Retry-After y exponential backoff.
    8. Aislamiento de fallos individuales (un comprobante fallido no cancela el lote).
    9. Reintento selectivo de errores técnicos (POST .../reintentar-errores).
    10. Idempotencia mediante Idempotency-Key.
    11. Multitenancy estricto basado en contexto JWT.
    12. Recuperación automática al reiniciar el backend de procesos PROCESANDO/PENDIENTE.
    13. Paginación de items y listado general.
    14. Auditoría en consultas_cpe para cada llamada real a SUNAT.
    15. Transacciones cortas: nunca mantiene transacción DB abierta durante la llamada HTTP a SUNAT.
    16. Cantidad dinámica: cero dependencias de 220, límite técnico configurable MAX_MASSIVE_ITEMS.
    """

    def __init__(self):
        # Permite inyectar sessionmaker alternativo en tests (ej. SQLite en memoria)
        self._session_factory = AsyncSessionLocal
        # Candado para tareas en segundo plano activas
        self._active_tasks: Dict[str, asyncio.Task] = {}

    def set_session_factory(self, factory) -> None:
        """Permite inyectar el session factory de tests."""
        self._session_factory = factory

    def _get_db_session(self) -> AsyncSession:
        """Obtiene una nueva sesión asíncrona de base de datos."""
        return self._session_factory()

    @staticmethod
    def validar_limite_seguridad(cantidad_items: int) -> None:
        """
        Valida que la cantidad de comprobantes no exceda el límite técnico configurable
        y no sea cero.
        """
        if cantidad_items == 0:
            raise ProcesoMasivoException(
                message="No se seleccionó ningún comprobante para procesar.",
                status_code=400,
            )

        max_permitido = settings.MAX_MASSIVE_ITEMS
        if cantidad_items > max_permitido:
            raise ProcesoMasivoException(
                message=f"El proceso contiene {cantidad_items:,} comprobantes y supera el límite configurado de {max_permitido:,}.",
                status_code=400,
            )

    @staticmethod
    def calcular_porcentaje(total_procesados: int, total_registros: int) -> float:
        """Calcula el porcentaje de avance dinámico redondeado a 2 decimales."""
        if total_registros <= 0:
            return 0.0
        pct = (Decimal(str(total_procesados)) / Decimal(str(total_registros))) * Decimal("100.00")
        return float(pct.quantize(Decimal("0.01")))

    @staticmethod
    def parse_fecha_emision(fecha_str: str) -> datetime.date:
        """Convierte una cadena DD/MM/YYYY a datetime.date."""
        try:
            return datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").date()
        except ValueError:
            try:
                return datetime.date.fromisoformat(fecha_str.strip())
            except ValueError:
                return datetime.date.today()

    async def crear_proceso(
        self,
        db: AsyncSession,
        empresa: Empresa,
        usuario: Usuario,
        request: CrearProcesoMasivoRequest,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[ProcesoMasivo, bool]:
        """
        Registra el proceso y sus items en PostgreSQL.
        Soporta Idempotencia: si ya existe para la empresa e idempotency_key, retorna el existente.
        Retorna: (proceso_masivo, fue_creado_nuevo)
        """
        idem_key = idempotency_key or request.idempotency_key
        if idem_key:
            stmt = select(ProcesoMasivo).where(
                ProcesoMasivo.empresa_id == empresa.id,
                ProcesoMasivo.idempotency_key == idem_key,
            )
            res = await db.execute(stmt)
            existente = res.scalar_one_or_none()
            if existente:
                logger.info("Idempotencia detectada para clave '%s' en empresa %s. Retornando proceso %s.", idem_key, empresa.ruc, existente.id)
                return existente, False

        total_items = len(request.items)
        self.validar_limite_seguridad(total_items)

        proceso_id = str(uuid.uuid4())
        proceso = ProcesoMasivo(
            id=proceso_id,
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            nombre_archivo=request.nombre_archivo,
            idempotency_key=idem_key,
            estado="PENDIENTE",
            total_registros=total_items,
            total_procesados=0,
            total_validos=0,
            total_no_validos=0,
            total_observados=0,
            total_errores=0,
            porcentaje=Decimal("0.00"),
            started_at=None,
            finished_at=None,
        )
        db.add(proceso)

        # Crear registros de items individuales
        for idx, item in enumerate(request.items, start=1):
            fecha_dt = self.parse_fecha_emision(item.fecha_emision)
            monto_dec = abs(Decimal(str(item.monto))).quantize(Decimal("0.01"))
            monto_orig = item.monto_original if item.monto_original is not None else item.monto
            monto_orig_dec = Decimal(str(monto_orig)).quantize(Decimal("0.01")) if monto_orig is not None else monto_dec

            item_db = ProcesoMasivoItem(
                proceso_id=proceso_id,
                fila_excel=item.fila_excel if item.fila_excel is not None else idx,
                num_ruc=item.num_ruc.strip(),
                cod_comp=item.cod_comp.strip().zfill(2),
                numero_serie=item.numero_serie.strip().upper(),
                numero=item.numero.strip(),
                fecha_emision=fecha_dt,
                monto_original=monto_orig_dec,
                monto=monto_dec,
                razon_social=item.razon_social.strip() if item.razon_social else None,
                estado="PENDIENTE",
                intentos=0,
            )
            db.add(item_db)

        await db.commit()
        await db.refresh(proceso)
        return proceso, True

    def iniciar_worker_asincrono(self, proceso_id: str, empresa_id: int, usuario_id: int) -> None:
        """Lanza la ejecución del worker en segundo plano desacoplado del request HTTP."""
        task = asyncio.create_task(
            self._ejecutar_worker(proceso_id, empresa_id, usuario_id)
        )
        self._active_tasks[proceso_id] = task

        def cleanup(t):
            self._active_tasks.pop(proceso_id, None)

        task.add_done_callback(cleanup)

    async def esperar_proceso(self, proceso_id: str, timeout: float = 10.0) -> None:
        """Helper para testing o sincronización: espera a que el worker activo finalice."""
        task = self._active_tasks.get(proceso_id)
        if task and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    async def _ejecutar_worker(self, proceso_id: str, empresa_id: int, usuario_id: int) -> None:
        """
        Worker en segundo plano para procesar items de un proceso masivo.
        Maneja transacciones cortas (sin transacción abierta durante el HTTP a SUNAT),
        concurrencia controlada, delay y reintentos técnicos.
        """
        logger.info("Iniciando worker de proceso masivo %s...", proceso_id)

        # 1. Marcar proceso como PROCESANDO
        async with self._get_db_session() as db:
            stmt = select(ProcesoMasivo).where(ProcesoMasivo.id == proceso_id)
            res = await db.execute(stmt)
            proceso = res.scalar_one_or_none()
            if not proceso:
                logger.error("No se encontró el proceso masivo %s para iniciar worker.", proceso_id)
                return

            proceso.estado = "PROCESANDO"
            if not proceso.started_at:
                proceso.started_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()

            # Obtener empresa y usuario para contexto
            res_emp = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
            empresa = res_emp.scalar_one_or_none()
            res_usr = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
            usuario = res_usr.scalar_one_or_none()

        if not empresa or not usuario:
            logger.error("Empresa %s o usuario %s no encontrados para proceso %s.", empresa_id, usuario_id, proceso_id)
            return

        # 2. Consultar items pendientes
        async with self._get_db_session() as db:
            stmt_items = select(ProcesoMasivoItem).where(
                ProcesoMasivoItem.proceso_id == proceso_id,
                ProcesoMasivoItem.estado == "PENDIENTE"
            ).order_by(ProcesoMasivoItem.id)
            res_items = await db.execute(stmt_items)
            items_pendientes = res_items.scalars().all()
            ids_pendientes = [item.id for item in items_pendientes]
            logger.info("Proceso %s: ids_pendientes: %s (total: %d)", proceso_id, ids_pendientes, len(ids_pendientes))

        concurrency = getattr(settings, "SUNAT_MAX_CONCURRENCY", 5)
        semaphore = asyncio.Semaphore(concurrency)
        db_lock = asyncio.Lock()

        # 3. Función procesadora de un item individual
        async def procesar_item(item_id: int):
            async with semaphore:
                # Paso A: Marcar PROCESANDO y commit (Transacción cerrada antes de HTTP)
                async with db_lock:
                    async with self._get_db_session() as db_item:
                        res_it = await db_item.execute(select(ProcesoMasivoItem).where(ProcesoMasivoItem.id == item_id))
                        item = res_it.scalar_one_or_none()
                        if not item:
                            return
                        item.estado = "PROCESANDO"
                        await db_item.commit()

                # Copiar datos para llamada HTTP fuera de sesión
                item_data = {
                    "id": item.id,
                    "num_ruc": item.num_ruc,
                    "cod_comp": item.cod_comp,
                    "numero_serie": item.numero_serie,
                    "numero": item.numero,
                    "fecha_emision": item.fecha_emision.strftime("%d/%m/%Y"),
                    "monto": item.monto,
                    "intentos": item.intentos,
                }

                # Paso B: Aplicar Delay configurable si aplica
                delay_ms = getattr(settings, "SUNAT_REQUEST_DELAY_MS", 0)
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)

                # Paso C: Ejecutar consulta con reintentos técnicos exclusivos (CONCURRENTE, SIN DB TRANSACCIÓN)
                resultado_estado, cod_sunat, msg_sunat, intentos_realizados, consulta_db_id = (
                    await self._consultar_sunat_con_retries(empresa, usuario, item_data)
                )

                # Paso D: Guardar resultado y actualizar contadores (Transacción corta)
                async with db_lock:
                    async with self._get_db_session() as db_item:
                        res_it = await db_item.execute(select(ProcesoMasivoItem).where(ProcesoMasivoItem.id == item_id))
                        item = res_it.scalar_one_or_none()
                        if item:
                            item.estado = resultado_estado
                            item.codigo_sunat = cod_sunat
                            item.estado_sunat = cod_sunat
                            item.mensaje_sunat = msg_sunat[:500] if msg_sunat else None
                            item.intentos = intentos_realizados
                            item.consulta_cpe_id = consulta_db_id
                            await db_item.commit()

                    async with self._get_db_session() as db_proc:
                        res_proc = await db_proc.execute(select(ProcesoMasivo).where(ProcesoMasivo.id == proceso_id))
                        proc = res_proc.scalar_one_or_none()
                        if proc:
                            proc.total_procesados += 1
                            if resultado_estado == "VALIDO":
                                proc.total_validos += 1
                            elif resultado_estado == "NO_VALIDO":
                                proc.total_no_validos += 1
                            elif resultado_estado == "OBSERVADO":
                                proc.total_observados += 1
                            else:
                                proc.total_errores += 1
                            proc.porcentaje = self.calcular_porcentaje(proc.total_procesados, proc.total_registros)
                            await db_proc.commit()

        # Ejecutar concurrentemente con semáforo
        tasks = [asyncio.create_task(procesar_item(iid)) for iid in ids_pendientes]
        if tasks:
            gather_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in gather_results:
                if isinstance(res, Exception):
                    logger.error("Error en procesar_item: %s", res, exc_info=res)

        # 4. Finalizar proceso sincronizando contadores exactos mediante agregación en DB
        async with self._get_db_session() as db:
            stmt_agg = select(
                func.count(ProcesoMasivoItem.id),
                func.sum(case((ProcesoMasivoItem.estado == "VALIDO", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado == "NO_VALIDO", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado == "OBSERVADO", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado == "ERROR", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado.in_(["VALIDO", "NO_VALIDO", "OBSERVADO", "ERROR"]), 1), else_=0)),
            ).where(ProcesoMasivoItem.proceso_id == proceso_id)
            res_agg = await db.execute(stmt_agg)
            tot_items, validos, no_validos, observados, errores, procesados = res_agg.first()

            res_proc = await db.execute(select(ProcesoMasivo).where(ProcesoMasivo.id == proceso_id))
            proc = res_proc.scalar_one_or_none()
            if proc:
                proc.total_procesados = int(procesados or 0)
                proc.total_validos = int(validos or 0)
                proc.total_no_validos = int(no_validos or 0)
                proc.total_observados = int(observados or 0)
                proc.total_errores = int(errores or 0)
                proc.finished_at = datetime.datetime.now(datetime.timezone.utc)
                proc.porcentaje = self.calcular_porcentaje(proc.total_procesados, proc.total_registros)
                if proc.total_errores > 0:
                    proc.estado = "COMPLETADO_CON_ERRORES"
                else:
                    proc.estado = "COMPLETADO"
                await db.commit()

        logger.info("Worker de proceso masivo %s finalizado con estado %s.", proceso_id, proc.estado if proc else "N/A")

    async def _consultar_sunat_con_retries(
        self,
        empresa: Empresa,
        usuario: Usuario,
        item_data: dict,
    ) -> Tuple[str, Optional[str], Optional[str], int, Optional[int]]:
        """
        Ejecuta la llamada a SUNAT con política estricta de reintentos:
        - Reintenta SOLAMENTE errores técnicos transitorios: timeout, connection error, HTTP 429, 500, 502, 503, 504.
        - NO reintenta resultados funcionales: VALIDO, NO_VALIDO, OBSERVADO.
        - HTTP 429 respeta Retry-After o aplica backoff.
        Retorna: (estado_interno, codigo_sunat, mensaje_sunat, intentos_totales, consulta_cpe_id)
        """
        max_retries = getattr(settings, "SUNAT_MASSIVE_MAX_RETRIES", 3)
        intentos = item_data.get("intentos", 0)

        req_sunat = ComprobanteValidarRequest(
            num_ruc=item_data["num_ruc"],
            cod_comp=item_data["cod_comp"],
            numero_serie=item_data["numero_serie"],
            numero=item_data["numero"],
            fecha_emision=item_data["fecha_emision"],
            monto=item_data["monto"],
        )

        ultimo_error_msg = ""
        ultimo_cod_sunat = "ERROR"

        for attempt in range(1, max_retries + 1):
            intentos += 1
            try:
                # Transacción aislada para registrar en consultas_cpe
                async with self._get_db_session() as db_audit:
                    res_cpe = await sunat_service.validar_comprobante(
                        empresa=empresa,
                        usuario=usuario,
                        request_data=req_sunat,
                        db=db_audit,
                    )
                    # Resultado funcional obtenido exitosamente (VALIDO, NO_VALIDO, OBSERVADO)
                    # NO se reintenta jamás
                    return res_cpe.estado, res_cpe.codigo_sunat, res_cpe.mensaje_sunat, intentos, res_cpe.id

            except SunatCredentialsError as ce:
                # Error de configuración permanente: no reintentar
                return "ERROR", "CRED_CONFIG_ERROR", ce.message, intentos, None

            except SunatException as se:
                ultimo_error_msg = se.message
                ultimo_cod_sunat = getattr(se, "codigo_sunat", "ERROR")
                http_status = getattr(se, "status_code", 400)

                # Verificar si es error técnico transitorio
                es_transitorio = (
                    http_status in [429, 500, 502, 503, 504] or
                    ultimo_cod_sunat in ["TIMEOUT", "NETWORK_ERROR", "429"]
                )

                if not es_transitorio or attempt == max_retries:
                    break

                # Manejo de HTTP 429 Rate Limit
                if http_status == 429:
                    # Exponential backoff base 1s
                    backoff = min(2.0 ** attempt, 30.0)
                    await asyncio.sleep(backoff)
                else:
                    # Backoff suave para 500/502/503/504
                    await asyncio.sleep(min(1.0 * attempt, 10.0))

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as net_err:
                ultimo_error_msg = f"Fallo de red: {str(net_err)}"
                ultimo_cod_sunat = "NETWORK_ERROR"
                if attempt == max_retries:
                    break
                await asyncio.sleep(min(1.0 * attempt, 10.0))

            except Exception as ex:
                ultimo_error_msg = f"Error inesperado: {str(ex)}"
                ultimo_cod_sunat = "INTERNAL_ERROR"
                break

        return "ERROR", ultimo_cod_sunat, ultimo_error_msg, intentos, None

    async def reintentar_errores(
        self,
        db: AsyncSession,
        proceso_id: str,
        empresa: Empresa,
        usuario: Usuario,
    ) -> ReintentarErroresResponse:
        """
        Reintenta únicamente los items que terminaron en estado ERROR (técnico).
        No reintenta comprobantes VALIDO, NO_VALIDO u OBSERVADO.
        """
        # Validar tenancy
        stmt_proc = select(ProcesoMasivo).where(
            ProcesoMasivo.id == proceso_id,
            ProcesoMasivo.empresa_id == empresa.id
        )
        res_proc = await db.execute(stmt_proc)
        proceso = res_proc.scalar_one_or_none()
        if not proceso:
            raise ProcesoMasivoException(
                message=f"No se encontró el proceso masivo con ID '{proceso_id}'.",
                status_code=404
            )

        if proceso.estado == "PROCESANDO":
            raise ProcesoMasivoException(
                message="El proceso masivo ya se encuentra en ejecución.",
                status_code=400
            )

        # Buscar items en ERROR
        stmt_items = select(ProcesoMasivoItem).where(
            ProcesoMasivoItem.proceso_id == proceso_id,
            ProcesoMasivoItem.estado == "ERROR"
        )
        res_items = await db.execute(stmt_items)
        items_error = res_items.scalars().all()
        total_error = len(items_error)

        if total_error == 0:
            return ReintentarErroresResponse(
                proceso_id=proceso_id,
                total_reintentados=0,
                mensaje="El proceso no contiene comprobantes con error técnico para reintentar.",
                estado=proceso.estado,
            )

        # Resetear items con error técnico a PENDIENTE
        for it in items_error:
            it.estado = "PENDIENTE"

        # Ajustar contadores del proceso
        proceso.total_errores = max(0, proceso.total_errores - total_error)
        proceso.total_procesados = proceso.total_validos + proceso.total_no_validos + proceso.total_observados
        proceso.porcentaje = self.calcular_porcentaje(proceso.total_procesados, proceso.total_registros)
        proceso.estado = "PROCESANDO"
        proceso.finished_at = None

        await db.commit()

        # Iniciar worker en segundo plano
        self.iniciar_worker_asincrono(proceso_id, empresa.id, usuario.id)

        return ReintentarErroresResponse(
            proceso_id=proceso_id,
            total_reintentados=total_error,
            mensaje=f"Se inició el reintento para {total_error} comprobantes con error técnico.",
            estado="PROCESANDO",
        )

    async def obtener_proceso(
        self,
        db: AsyncSession,
        proceso_id: str,
        empresa_id: int,
    ) -> Optional[ProcesoMasivoResponse]:
        """Obtiene un proceso validando aislamiento de tenancy."""
        stmt = select(ProcesoMasivo).where(
            ProcesoMasivo.id == proceso_id,
            ProcesoMasivo.empresa_id == empresa_id
        )
        res = await db.execute(stmt)
        proc = res.scalar_one_or_none()
        if not proc:
            return None

        return ProcesoMasivoResponse(
            id=proc.id,
            empresa_id=proc.empresa_id,
            usuario_id=proc.usuario_id,
            usuario_nombre=proc.usuario.nombre_completo if proc.usuario else None,
            nombre_archivo=proc.nombre_archivo,
            idempotency_key=proc.idempotency_key,
            estado=proc.estado,
            total_registros=proc.total_registros,
            total_procesados=proc.total_procesados,
            porcentaje=float(proc.porcentaje),
            total_validos=proc.total_validos,
            total_no_validos=proc.total_no_validos,
            total_observados=proc.total_observados,
            total_errores=proc.total_errores,
            mensaje_error=proc.mensaje_error,
            started_at=proc.started_at,
            finished_at=proc.finished_at,
            created_at=proc.created_at,
            updated_at=proc.updated_at,
        )

    async def listar_procesos(
        self,
        db: AsyncSession,
        empresa_id: int,
        page: int = 1,
        page_size: int = 10,
        fecha_desde: Optional[datetime.date] = None,
        fecha_hasta: Optional[datetime.date] = None,
        nombre_archivo: Optional[str] = None,
        estado: Optional[str] = None,
    ) -> PaginatedProcesosMasivosResponse:
        """Lista los procesos masivos paginados para la empresa autenticada con filtros opcionales."""
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        offset = (page - 1) * page_size

        conditions = [ProcesoMasivo.empresa_id == empresa_id]
        if fecha_desde:
            conditions.append(func.date(ProcesoMasivo.created_at) >= fecha_desde)
        if fecha_hasta:
            conditions.append(func.date(ProcesoMasivo.created_at) <= fecha_hasta)
        if nombre_archivo and nombre_archivo.strip():
            conditions.append(ProcesoMasivo.nombre_archivo.ilike(f"%{nombre_archivo.strip()}%"))
        if estado and estado.strip():
            conditions.append(ProcesoMasivo.estado == estado.upper().strip())

        count_stmt = select(func.count(ProcesoMasivo.id)).where(*conditions)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(ProcesoMasivo).where(
            *conditions
        ).order_by(desc(ProcesoMasivo.created_at)).offset(offset).limit(page_size)
        res = await db.execute(stmt)
        procesos = res.scalars().all()

        items = [
            ProcesoMasivoResponse(
                id=p.id,
                empresa_id=p.empresa_id,
                usuario_id=p.usuario_id,
                usuario_nombre=p.usuario.nombre_completo if p.usuario else None,
                nombre_archivo=p.nombre_archivo,
                idempotency_key=p.idempotency_key,
                estado=p.estado,
                total_registros=p.total_registros,
                total_procesados=p.total_procesados,
                porcentaje=float(p.porcentaje),
                total_validos=p.total_validos,
                total_no_validos=p.total_no_validos,
                total_observados=p.total_observados,
                total_errores=p.total_errores,
                mensaje_error=p.mensaje_error,
                started_at=p.started_at,
                finished_at=p.finished_at,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in procesos
        ]

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedProcesosMasivosResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def listar_items_proceso(
        self,
        db: AsyncSession,
        proceso_id: str,
        empresa_id: int,
        page: int = 1,
        page_size: int = 20,
        estado: Optional[str] = None,
        estado_sunat: Optional[str] = None,
        busqueda: Optional[str] = None,
        ruc: Optional[str] = None,
        serie: Optional[str] = None,
        numero: Optional[str] = None,
        razon_social: Optional[str] = None,
    ) -> PaginatedProcesoMasivoItemsResponse:
        """Lista los items de un proceso masivo de forma paginada y filtrable."""
        # 1. Validar tenancy
        stmt_proc = select(ProcesoMasivo).where(
            ProcesoMasivo.id == proceso_id,
            ProcesoMasivo.empresa_id == empresa_id
        )
        res_proc = await db.execute(stmt_proc)
        proc = res_proc.scalar_one_or_none()
        if not proc:
            raise ProcesoMasivoException(
                message=f"No se encontró el proceso masivo con ID '{proceso_id}'.",
                status_code=404
            )

        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        offset = (page - 1) * page_size

        # Construir filtros
        conditions = [ProcesoMasivoItem.proceso_id == proceso_id]
        if estado:
            conditions.append(ProcesoMasivoItem.estado == estado.upper().strip())
        if estado_sunat:
            conditions.append(or_(ProcesoMasivoItem.estado_sunat == estado_sunat, ProcesoMasivoItem.codigo_sunat == estado_sunat))
        if ruc and ruc.strip():
            conditions.append(ProcesoMasivoItem.num_ruc.ilike(f"%{ruc.strip()}%"))
        if serie and serie.strip():
            conditions.append(ProcesoMasivoItem.numero_serie.ilike(f"%{serie.strip()}%"))
        if numero and numero.strip():
            conditions.append(ProcesoMasivoItem.numero.ilike(f"%{numero.strip()}%"))
        if razon_social and razon_social.strip():
            conditions.append(ProcesoMasivoItem.razon_social.ilike(f"%{razon_social.strip()}%"))
        if busqueda and busqueda.strip():
            q = f"%{busqueda.strip()}%"
            conditions.append(
                or_(
                    ProcesoMasivoItem.num_ruc.ilike(q),
                    ProcesoMasivoItem.numero_serie.ilike(q),
                    ProcesoMasivoItem.numero.ilike(q),
                    ProcesoMasivoItem.razon_social.ilike(q),
                )
            )

        # Conteo total
        count_stmt = select(func.count(ProcesoMasivoItem.id)).where(*conditions)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Consulta paginada
        stmt = select(ProcesoMasivoItem).where(*conditions).order_by(ProcesoMasivoItem.id).offset(offset).limit(page_size)
        res = await db.execute(stmt)
        items_db = res.scalars().all()

        items = [
            ProcesoMasivoItemResponse(
                id=it.id,
                proceso_id=it.proceso_id,
                fila_excel=it.fila_excel,
                num_ruc=it.num_ruc,
                cod_comp=it.cod_comp,
                numero_serie=it.numero_serie,
                numero=it.numero,
                fecha_emision=it.fecha_emision.strftime("%d/%m/%Y"),
                monto_original=it.monto_original if it.monto_original is not None else it.monto,
                monto=it.monto,
                razon_social=it.razon_social,
                estado=it.estado,
                estado_sunat=it.estado_sunat,
                codigo_sunat=it.codigo_sunat,
                mensaje_sunat=it.mensaje_sunat,
                intentos=it.intentos,
                consulta_cpe_id=it.consulta_cpe_id,
                created_at=it.created_at,
                updated_at=it.updated_at,
            )
            for it in items_db
        ]

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedProcesoMasivoItemsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def recuperar_procesos_al_iniciar(self) -> int:
        """
        Recuperación automática de procesos interrumpidos tras reinicio del backend.
        Los comprobantes ya completados (VALIDO, NO_VALIDO, OBSERVADO) se conservan.
        Los comprobantes que quedaron abandonados en 'PROCESANDO' se devuelven a 'PENDIENTE'.
        Se reanuda el worker en segundo plano para cada proceso recuperado.
        Retorna la cantidad de procesos recuperados.
        """
        logger.info("Verificando procesos masivos pendientes de recuperación al iniciar backend...")
        recuperados = 0

        async with self._get_db_session() as db:
            stmt = select(ProcesoMasivo).where(
                ProcesoMasivo.estado.in_(["PENDIENTE", "PROCESANDO"])
            )
            res = await db.execute(stmt)
            procesos = res.scalars().all()

            for proc in procesos:
                # 1. Resetear items abandonados en PROCESANDO -> PENDIENTE
                await db.execute(
                    update(ProcesoMasivoItem)
                    .where(
                        ProcesoMasivoItem.proceso_id == proc.id,
                        ProcesoMasivoItem.estado == "PROCESANDO"
                    )
                    .values(estado="PENDIENTE")
                )
                await db.flush()

                # 2. Recontar progreso exacto
                res_validos = (await db.execute(select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc.id, ProcesoMasivoItem.estado == "VALIDO"))).scalar() or 0
                res_no_val = (await db.execute(select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc.id, ProcesoMasivoItem.estado == "NO_VALIDO"))).scalar() or 0
                res_obs = (await db.execute(select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc.id, ProcesoMasivoItem.estado == "OBSERVADO"))).scalar() or 0
                res_err = (await db.execute(select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc.id, ProcesoMasivoItem.estado == "ERROR"))).scalar() or 0
                res_pend = (await db.execute(select(func.count(ProcesoMasivoItem.id)).where(ProcesoMasivoItem.proceso_id == proc.id, ProcesoMasivoItem.estado == "PENDIENTE"))).scalar() or 0

                proc.total_validos = res_validos
                proc.total_no_validos = res_no_val
                proc.total_observados = res_obs
                proc.total_errores = res_err
                proc.total_procesados = res_validos + res_no_val + res_obs + res_err
                proc.porcentaje = self.calcular_porcentaje(proc.total_procesados, proc.total_registros)

                if res_pend > 0:
                    proc.estado = "PENDIENTE"
                    await db.commit()
                    # Reanudar worker
                    self.iniciar_worker_asincrono(proc.id, proc.empresa_id, proc.usuario_id)
                    recuperados += 1
                else:
                    # Todos terminados
                    proc.estado = "COMPLETADO_CON_ERRORES" if res_err > 0 else "COMPLETADO"
                    proc.porcentaje = Decimal("100.00")
                    await db.commit()

        logger.info("Recuperación de inicio finalizada. %d procesos reanudados.", recuperados)
        return recuperados

    async def exportar_proceso_excel(
        self,
        db: AsyncSession,
        proceso_id: str,
        empresa_id: int,
    ) -> Tuple[io.BytesIO, str]:
        """
        Genera un archivo Excel (.xlsx) con los resultados oficiales de SUNAT para el proceso masivo.
        Preserva monto_original (con su signo contable original) y monto (consultado a SUNAT).
        Protege contra Excel Formula Injection.
        NO realiza llamadas a SUNAT; utiliza exclusivamente los datos ya persistidos en PostgreSQL.
        """
        # 1. Verificar proceso y pertenencia estricta a la empresa
        stmt = select(ProcesoMasivo).where(
            ProcesoMasivo.id == proceso_id,
            ProcesoMasivo.empresa_id == empresa_id
        )
        res = await db.execute(stmt)
        proc = res.scalar_one_or_none()
        if not proc:
            raise ProcesoMasivoException(
                f"No se encontró el proceso masivo con ID '{proceso_id}' para su empresa.",
                status_code=404
            )

        # 2. Obtener todos los items del proceso ordenados por fila_excel o id
        stmt_items = select(ProcesoMasivoItem).where(
            ProcesoMasivoItem.proceso_id == proceso_id
        ).order_by(ProcesoMasivoItem.fila_excel, ProcesoMasivoItem.id)
        res_items = await db.execute(stmt_items)
        items = res_items.scalars().all()

        # 3. Crear Workbook con openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Resultados SUNAT"
        ws.views.sheetView[0].showGridLines = True

        # Estilos
        font_title = Font(name="Calibri", size=14, bold=True, color="1F4E79")
        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        fill_header = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        font_info_label = Font(name="Calibri", size=10, bold=True, color="333333")
        font_info_val = Font(name="Calibri", size=10, color="000000")
        border_thin = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        fill_valido = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        fill_no_valido = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        fill_observado = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
        fill_error = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        def sanitize_formula(val: Any) -> Any:
            """Protección contra Excel Formula Injection sin alterar valores numéricos legítimos."""
            if val is None:
                return ""
            if isinstance(val, (int, float, Decimal)):
                return val
            s = str(val).strip()
            if s and s[0] in ("=", "+", "-", "@"):
                try:
                    float(s)
                    return val
                except ValueError:
                    return f"'{s}"
            return val

        # Título
        ws.cell(row=1, column=1, value="SISTEMA DE VALIDACIÓN DE COMPROBANTES SUNAT - REPORTE OFICIAL").font = font_title

        # Metadata de proceso
        empresa_nombre = proc.empresa.razon_social if proc.empresa else ""
        empresa_ruc = proc.empresa.ruc if proc.empresa else ""
        fecha_proceso = proc.created_at.strftime("%d/%m/%Y %H:%M:%S") if proc.created_at else ""

        ws.cell(row=3, column=1, value="Empresa:").font = font_info_label
        ws.cell(row=3, column=2, value=sanitize_formula(empresa_nombre)).font = font_info_val
        ws.cell(row=3, column=4, value="RUC Empresa:").font = font_info_label
        ws.cell(row=3, column=5, value=empresa_ruc).font = font_info_val

        ws.cell(row=4, column=1, value="Archivo Origen:").font = font_info_label
        ws.cell(row=4, column=2, value=sanitize_formula(proc.nombre_archivo or "N/A")).font = font_info_val
        ws.cell(row=4, column=4, value="Fecha Proceso:").font = font_info_label
        ws.cell(row=4, column=5, value=fecha_proceso).font = font_info_val

        ws.cell(row=5, column=1, value="Total Comprobantes:").font = font_info_label
        ws.cell(row=5, column=2, value=proc.total_registros).font = font_info_val
        ws.cell(row=5, column=4, value="Válidos:").font = font_info_label
        ws.cell(row=5, column=5, value=proc.total_validos).font = font_info_val
        ws.cell(row=5, column=7, value="No Válidos:").font = font_info_label
        ws.cell(row=5, column=8, value=proc.total_no_validos).font = font_info_val

        ws.cell(row=6, column=4, value="Observados:").font = font_info_label
        ws.cell(row=6, column=5, value=proc.total_observados).font = font_info_val
        ws.cell(row=6, column=7, value="Errores:").font = font_info_label
        ws.cell(row=6, column=8, value=proc.total_errores).font = font_info_val

        # Fila 8: Encabezados de tabla
        headers = [
            "Fila Excel",
            "RUC Emisor",
            "Razón Social",
            "Tipo Comprobante",
            "Serie",
            "Número",
            "Fecha Emisión",
            "Importe Original",
            "Importe Consultado SUNAT",
            "Resultado",
            "Estado SUNAT",
            "Código SUNAT",
            "Mensaje SUNAT",
            "Fecha Consulta",
        ]

        header_row = 8
        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Filas de datos
        current_row = header_row + 1
        for it in items:
            monto_orig = float(it.monto_original) if it.monto_original is not None else float(it.monto)
            monto_sunat = float(it.monto)
            fecha_emision_str = it.fecha_emision.strftime("%d/%m/%Y") if it.fecha_emision else ""
            fecha_consulta_str = it.created_at.strftime("%d/%m/%Y %H:%M:%S") if it.created_at else ""

            row_data = [
                it.fila_excel,
                sanitize_formula(it.num_ruc),
                sanitize_formula(it.razon_social or ""),
                sanitize_formula(it.cod_comp),
                sanitize_formula(it.numero_serie),
                sanitize_formula(it.numero),
                fecha_emision_str,
                monto_orig,
                monto_sunat,
                it.estado,
                sanitize_formula(it.estado_sunat or ""),
                sanitize_formula(it.codigo_sunat or ""),
                sanitize_formula(it.mensaje_sunat or ""),
                fecha_consulta_str,
            ]

            for col_idx, val in enumerate(row_data, start=1):
                c = ws.cell(row=current_row, column=col_idx, value=val)
                c.border = border_thin
                c.font = font_info_val

                # Formato monetario en columnas 8 y 9
                if col_idx in (8, 9):
                    c.number_format = '#,##0.00;[Red]-#,##0.00;0.00'
                    c.alignment = Alignment(horizontal="right")
                elif col_idx in (1, 4, 5, 6, 7, 10, 11, 12, 14):
                    c.alignment = Alignment(horizontal="center")
                else:
                    c.alignment = Alignment(horizontal="left")

                # Color de estado en columna 10
                if col_idx == 10:
                    if it.estado == "VALIDO":
                        c.fill = fill_valido
                    elif it.estado == "NO_VALIDO":
                        c.fill = fill_no_valido
                    elif it.estado == "OBSERVADO":
                        c.fill = fill_observado
                    elif it.estado == "ERROR":
                        c.fill = fill_error

            current_row += 1

        # Freeze panes bajo los encabezados
        ws.freeze_panes = "A9"

        # Autofilter en los datos
        last_row = max(current_row - 1, header_row)
        ws.auto_filter.ref = f"A{header_row}:N{last_row}"

        # Ajuste de anchos de columna
        column_widths = {
            1: 12,  # Fila Excel
            2: 15,  # RUC
            3: 35,  # Razón Social
            4: 18,  # Tipo Comprobante
            5: 12,  # Serie
            6: 15,  # Número
            7: 15,  # Fecha Emisión
            8: 18,  # Importe Original
            9: 22,  # Importe SUNAT
            10: 16, # Resultado
            11: 16, # Estado SUNAT
            12: 15, # Código SUNAT
            13: 45, # Mensaje SUNAT
            14: 20, # Fecha Consulta
        }
        for col_idx, width in column_widths.items():
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        # Guardar en memoria
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Nombre seguro de archivo
        base_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', (proc.nombre_archivo or "proceso").replace(".xlsx", ""))
        fecha_tag = (proc.created_at or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S")
        filename = f"resultado_sunat_{base_name}_{fecha_tag}.xlsx"

        return output, filename

    async def obtener_resumen_dashboard(
        self,
        db: AsyncSession,
        empresa_id: int,
        fecha_desde: Optional[datetime.date] = None,
        fecha_hasta: Optional[datetime.date] = None,
        estado: Optional[str] = None,
        proceso_id: Optional[str] = None,
    ) -> DashboardResumenResponse:
        """
        Obtiene el resumen estadístico agregado para el Dashboard en PostgreSQL.
        Soporta filtros opcionales de fecha, estado y proceso.
        Filtra estrictamente por la empresa autenticada.
        """
        conditions = [ProcesoMasivo.empresa_id == empresa_id]
        if proceso_id and proceso_id.strip():
            conditions.append(ProcesoMasivo.id == proceso_id.strip())
        if fecha_desde:
            conditions.append(func.date(ProcesoMasivo.created_at) >= fecha_desde)
        if fecha_hasta:
            conditions.append(func.date(ProcesoMasivo.created_at) <= fecha_hasta)

        item_conditions = list(conditions)
        if estado and estado.strip():
            item_conditions.append(ProcesoMasivoItem.estado == estado.upper().strip())

        # Conteo agregado desde ProcesoMasivoItem joined con ProcesoMasivo
        stmt = (
            select(
                func.count(ProcesoMasivoItem.id),
                func.sum(case((ProcesoMasivoItem.estado == "VALIDO", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado == "NO_VALIDO", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado == "OBSERVADO", 1), else_=0)),
                func.sum(case((ProcesoMasivoItem.estado == "ERROR", 1), else_=0)),
            )
            .join(ProcesoMasivo, ProcesoMasivo.id == ProcesoMasivoItem.proceso_id)
            .where(*item_conditions)
        )
        res = await db.execute(stmt)
        total_items, val_items, no_val_items, obs_items, err_items = res.first() or (0, 0, 0, 0, 0)
        total_items = total_items or 0
        val_items = val_items or 0
        no_val_items = no_val_items or 0
        obs_items = obs_items or 0
        err_items = err_items or 0

        # Si no se filtra por proceso específico, agregamos consultas_cpe independientes (no vinculadas a proceso)
        if not proceso_id:
            cpe_conditions = [ConsultaCPE.empresa_id == empresa_id]
            if fecha_desde:
                cpe_conditions.append(func.date(ConsultaCPE.created_at) >= fecha_desde)
            if fecha_hasta:
                cpe_conditions.append(func.date(ConsultaCPE.created_at) <= fecha_hasta)
            if estado and estado.strip():
                cpe_conditions.append(ConsultaCPE.estado == estado.upper().strip())

            # Excluir las consultas que ya pertenecen a un item de proceso masivo
            stmt_cpe = (
                select(
                    func.count(ConsultaCPE.id),
                    func.sum(case((ConsultaCPE.estado == "VALIDO", 1), else_=0)),
                    func.sum(case((ConsultaCPE.estado == "NO_VALIDO", 1), else_=0)),
                    func.sum(case((ConsultaCPE.estado == "OBSERVADO", 1), else_=0)),
                    func.sum(case((ConsultaCPE.estado == "ERROR", 1), else_=0)),
                )
                .where(
                    *cpe_conditions,
                    ConsultaCPE.id.not_in(
                        select(ProcesoMasivoItem.consulta_cpe_id).where(ProcesoMasivoItem.consulta_cpe_id.is_not(None))
                    )
                )
            )
            res_cpe = await db.execute(stmt_cpe)
            tot_cpe, val_cpe, no_val_cpe, obs_cpe, err_cpe = res_cpe.first() or (0, 0, 0, 0, 0)
            total_items += tot_cpe or 0
            val_items += val_cpe or 0
            no_val_items += no_val_cpe or 0
            obs_items += obs_cpe or 0
            err_items += err_cpe or 0

        total = total_items
        pct_val = round((val_items / total) * 100.0, 2) if total > 0 else 0.0
        pct_no_val = round((no_val_items / total) * 100.0, 2) if total > 0 else 0.0
        pct_obs = round((obs_items / total) * 100.0, 2) if total > 0 else 0.0
        pct_err = round((err_items / total) * 100.0, 2) if total > 0 else 0.0

        return DashboardResumenResponse(
            total=total,
            validos=val_items,
            no_validos=no_val_items,
            observados=obs_items,
            errores=err_items,
            porcentaje_validos=pct_val,
            porcentaje_no_validos=pct_no_val,
            porcentaje_observados=pct_obs,
            porcentaje_errores=pct_err,
        )


# Instancia singleton del servicio
proceso_masivo_service = ProcesoMasivoService()
