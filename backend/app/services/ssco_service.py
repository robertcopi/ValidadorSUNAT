import io
import logging
import re
import zipfile
from datetime import date, datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse

import httpx
import openpyxl
from sqlalchemy import select, func, delete, insert, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.padron_ssco import PadronSSCO, PadronSSCOSincronizacion, ConsultaSSCO
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.ssco import SSCOConsultaResponse, SSCOEstadoResponse, SSCOSyncResponse
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

# URL oficial gobernada por backend (no configurable arbitrariamente por el cliente)
SUNAT_SSCO_OFFICIAL_URL = "https://www.sunat.gob.pe/padronesnotificaciones/ssco/sujesincapacidadOperativa.xlsx"
ALLOWED_HOST = "www.sunat.gob.pe"
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class SSCOValidationException(Exception):
    """Excepción específica para errores de validación de formato o integridad del padrón SSCO."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SSCOService:
    """
    Servicio de gestión del Padrón de Sujetos Sin Capacidad Operativa (SSCO).
    Proporciona consultas de RUC aisladas, sincronización oficial y carga de contingencia.
    """

    def validar_formato_ruc(self, ruc: str) -> None:
        """Valida que el RUC sea obligatorio, contenga exactamente 11 caracteres y sean solo dígitos."""
        if not ruc or not isinstance(ruc, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El RUC es obligatorio y debe ser una cadena de texto."
            )
        ruc_limpio = ruc.strip()
        if len(ruc_limpio) != 11 or not ruc_limpio.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El RUC debe tener exactamente 11 dígitos numéricos."
            )

    async def obtener_estado(self, db: AsyncSession) -> SSCOEstadoResponse:
        """Retorna el estado de disponibilidad y métricas del padrón SSCO local."""
        count_stmt = select(func.count()).select_from(PadronSSCO)
        count_res = await db.execute(count_stmt)
        total_registros = count_res.scalar() or 0

        sync_stmt = (
            select(PadronSSCOSincronizacion)
            .where(PadronSSCOSincronizacion.estado == "EXITOSO")
            .order_by(desc(PadronSSCOSincronizacion.created_at))
            .limit(1)
        )
        sync_res = await db.execute(sync_stmt)
        ultima_sync = sync_res.scalar_one_or_none()

        padron_disponible = total_registros > 0 and ultima_sync is not None

        return SSCOEstadoResponse(
            padron_disponible=padron_disponible,
            total_registros=total_registros,
            ultima_sincronizacion_exitosa=ultima_sync.created_at if ultima_sync else None,
            fecha_padron_sunat=ultima_sync.fecha_padron_sunat if ultima_sync else None,
            origen=ultima_sync.origen if ultima_sync else None,
            estado=ultima_sync.estado if ultima_sync else "SIN_PADRON"
        )

    async def consultar_ruc(
        self,
        ruc: str,
        current_user: Usuario,
        empresa: Optional[Empresa],
        db: AsyncSession
    ) -> SSCOConsultaResponse:
        """
        Consulta si un RUC figura en el padrón local de SSCO.
        La consulta es estrictamente local en PostgreSQL (cero llamadas a APIs de SUNAT ni a CPE).
        Registra la trazabilidad en 'consultas_ssco' respetando el contexto multiempresa.
        """
        self.validar_formato_ruc(ruc)
        ruc_norm = ruc.strip()

        # 1. Verificar si el padrón está disponible (no vacío y con al menos 1 sincronización exitosa)
        estado_padron = await self.obtener_estado(db)
        if not estado_padron.padron_disponible:
            return SSCOConsultaResponse(
                ruc=ruc_norm,
                estado="NO_VERIFICADO",
                es_ssco=False,
                mensaje="No existe un padrón SSCO disponible para realizar la verificación.",
                fecha_padron=None
            )

        # 2. Consultar el padrón local por RUC
        stmt = select(PadronSSCO).where(PadronSSCO.ruc == ruc_norm)
        result = await db.execute(stmt)
        registro = result.scalar_one_or_none()

        fecha_corte = estado_padron.fecha_padron_sunat or (
            registro.fecha_publicacion.strftime("%d/%m/%Y") if registro and registro.fecha_publicacion else None
        )

        # 3. Determinar respuesta conceptual
        if registro:
            estado_res = "ENCONTRADO_SSCO"
            es_ssco = True
            mensaje = (
                "RUC encontrado en el padrón de Sujetos Sin Capacidad Operativa (SSCO). "
                "Requiere revisión contable."
            )
            detalle = {
                "razon_social": registro.razon_social,
                "domicilio_fiscal": registro.domicilio_fiscal,
                "resolucion_atribucion": registro.resolucion_atribucion,
                "fecha_emision_resolucion": registro.fecha_emision_resolucion.isoformat() if registro.fecha_emision_resolucion else None,
                "fecha_firmeza": registro.fecha_firmeza.isoformat() if registro.fecha_firmeza else None,
                "doc_representante": registro.doc_representante,
                "nombre_representante": registro.nombre_representante,
                "fecha_publicacion": registro.fecha_publicacion.isoformat() if registro.fecha_publicacion else None,
            }
            resp = SSCOConsultaResponse(
                ruc=ruc_norm,
                estado=estado_res,
                es_ssco=es_ssco,
                mensaje=mensaje,
                razon_social=registro.razon_social,
                domicilio_fiscal=registro.domicilio_fiscal,
                resolucion_atribucion=registro.resolucion_atribucion,
                fecha_emision_resolucion=registro.fecha_emision_resolucion.strftime("%d/%m/%Y") if registro.fecha_emision_resolucion else None,
                fecha_firmeza=registro.fecha_firmeza.strftime("%d/%m/%Y") if registro.fecha_firmeza else None,
                doc_representante=registro.doc_representante,
                nombre_representante=registro.nombre_representante,
                fecha_publicacion=registro.fecha_publicacion.strftime("%d/%m/%Y") if registro.fecha_publicacion else None,
                fecha_padron=fecha_corte
            )
        else:
            estado_res = "NO_ENCONTRADO"
            es_ssco = False
            mensaje = "El RUC no figura en el padrón SSCO consultado."
            detalle = None
            resp = SSCOConsultaResponse(
                ruc=ruc_norm,
                estado=estado_res,
                es_ssco=es_ssco,
                mensaje=mensaje,
                fecha_padron=fecha_corte
            )

        # 4. Registrar trazabilidad multiempresa en consultas_ssco
        # - CONTADOR: utiliza estrictamente su empresa asignada
        # - ADMIN: utiliza la empresa seleccionada si existe contexto, de lo contrario None
        target_empresa_id = empresa.id if empresa else (
            current_user.empresa_id if current_user.rol == "CONTADOR" else None
        )

        registro_consulta = ConsultaSSCO(
            empresa_id=target_empresa_id,
            usuario_id=current_user.id,
            ruc_consultado=ruc_norm,
            es_ssco=es_ssco,
            detalle_ssco=detalle,
            fecha_padron_consultado=fecha_corte,
            created_at=datetime.now(timezone.utc)
        )
        db.add(registro_consulta)
        await db.commit()

        return resp

    def _validar_seguridad_archivo(self, file_bytes: bytes) -> None:
        """Verifica que el payload sea un archivo ZIP/OpenXML XLSX válido y no exceda límites seguros."""
        if not file_bytes:
            raise SSCOValidationException("El archivo recibido está vacío.")

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise SSCOValidationException(
                f"El archivo excede el tamaño máximo permitido de {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        # Verificar cabecera mágica PK de archivos ZIP
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise SSCOValidationException("El archivo no es un documento Excel (.xlsx) válido.")

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                # Comprobar estructura OpenXML de Excel
                namelist = zf.namelist()
                if "[Content_Types].xml" not in namelist:
                    raise SSCOValidationException("La estructura del archivo no corresponde a un libro Excel OpenXML válido.")
                # Proteger contra zip bombs analizando ratio de compresión
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 100 * 1024 * 1024:  # > 100 MB descomprimido
                    raise SSCOValidationException("El archivo contiene un ratio de descompresión sospechoso (potencial zip-bomb).")
        except zipfile.BadZipFile:
            raise SSCOValidationException("El archivo está corrupto o no es un formato ZIP/XLSX válido.")

    def _parsear_fecha(self, valor: Any) -> date:
        """Convierte valores de fecha de Excel (datetime, date, serial num o string) a date de Python."""
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date):
            return valor
        if isinstance(valor, (int, float)):
            # Serial fecha de Excel
            try:
                dt = datetime.fromordinal(datetime(1899, 12, 30).toordinal() + int(valor))
                return dt.date()
            except Exception:
                raise SSCOValidationException(f"Fecha serial de Excel inválida: {valor}")
        if isinstance(valor, str):
            val_limpio = valor.strip()
            formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]
            for fmt in formatos:
                try:
                    return datetime.strptime(val_limpio, fmt).date()
                except ValueError:
                    pass
            raise SSCOValidationException(f"Formato de fecha no reconocido: '{valor}'")
        raise SSCOValidationException(f"Tipo de dato de fecha inválido: {type(valor)}")

    def parsear_y_validar_excel(self, file_bytes: bytes) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Lee y valida exhaustivamente el contenido del archivo XLSX de SSCO.
        Valida encabezados oficiales, RUCs de 11 dígitos, unicidad y fechas.
        Retorna la lista de registros sanitizados y la fecha máxima de publicación oficial.
        """
        self._validar_seguridad_archivo(file_bytes)

        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        except Exception as e:
            raise SSCOValidationException(f"Error al abrir el libro Excel: {str(e)}")

        # Seleccionar hoja (por defecto 'Hoja1' o la primera activa)
        sheet_name = "Hoja1" if "Hoja1" in wb.sheetnames else wb.sheetnames[0]
        sheet = wb[sheet_name]

        rows_iter = sheet.iter_rows(values_only=True)
        try:
            raw_header = next(rows_iter, None)
        except Exception as e:
            raise SSCOValidationException(f"No se pudieron leer los encabezados del archivo: {str(e)}")

        if not raw_header:
            raise SSCOValidationException("El archivo Excel está completamente vacío.")

        # Mapear encabezados esperados
        # Normalizar encabezados (quitar tildes, caracteres especiales, pasar a mayúsculas)
        def normalizar_col(c: Any) -> str:
            if c is None:
                return ""
            s = str(c).strip().upper()
            s = s.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
            return re.sub(r'[^A-Z0-9 ]', '', s)

        norm_headers = [normalizar_col(h) for h in raw_header]

        idx_ruc = None
        idx_razon_social = None
        idx_domicilio = None
        idx_resolucion = None
        idx_fec_emision = None
        idx_fec_firmeza = None
        idx_doc_rep = None
        idx_nom_rep = None
        idx_fec_pub = None

        for idx, h in enumerate(norm_headers):
            if "RUC" in h and idx_ruc is None and "REPRESENTANTE" not in h:
                idx_ruc = idx
            elif "RAZON SOCIAL" in h:
                idx_razon_social = idx
            elif "DOMICILIO" in h:
                idx_domicilio = idx
            elif "RESOLUCION" in h and "EMISION" not in h and "FIRME" not in h:
                idx_resolucion = idx
            elif "EMISION" in h:
                idx_fec_emision = idx
            elif "FIRME" in h:
                idx_fec_firmeza = idx
            elif "DOCUMENTO" in h or ("RUC" in h and "REPRESENTANTE" in h):
                idx_doc_rep = idx
            elif "REPRESENTANTE" in h and ("NOMBRE" in h or "APELLIDO" in h):
                idx_nom_rep = idx
            elif "PUBLICACION" in h:
                idx_fec_pub = idx

        # Si no se detectaron por palabras clave exactas, intentar por posiciones estándar del archivo SUNAT
        if idx_ruc is None and len(norm_headers) >= 1 and "RUC" in norm_headers[0]:
            idx_ruc = 0

        campos_faltantes = []
        if idx_ruc is None: campos_faltantes.append("RUC")
        if idx_razon_social is None: campos_faltantes.append("Razón social")
        if idx_resolucion is None: campos_faltantes.append("Resolución de atribución")
        if idx_fec_emision is None: campos_faltantes.append("Fecha de emisión de resolución")
        if idx_fec_firmeza is None: campos_faltantes.append("Fecha de firmeza")
        if idx_fec_pub is None: campos_faltantes.append("Fecha de publicación")

        if campos_faltantes:
            raise SSCOValidationException(
                f"El archivo no contiene los encabezados oficiales requeridos: {', '.join(campos_faltantes)}."
            )

        # Parsear filas de datos
        registros = []
        rucs_vistos = set()
        max_fecha_pub: Optional[date] = None

        row_num = 1
        for row in rows_iter:
            row_num += 1
            if not row or not any(row):
                continue  # Saltear filas vacías

            raw_ruc = row[idx_ruc] if idx_ruc < len(row) else None
            if raw_ruc is None or str(raw_ruc).strip() == "":
                continue

            # Validar RUC
            # Manejar número entero o texto
            ruc_str = str(int(raw_ruc) if isinstance(raw_ruc, (int, float)) else raw_ruc).strip()
            if len(ruc_str) != 11 or not ruc_str.isdigit():
                raise SSCOValidationException(
                    f"Fila {row_num}: RUC inválido '{raw_ruc}'. Debe contener exactamente 11 dígitos numéricos."
                )

            # Validar unicidad dentro del archivo
            if ruc_str in rucs_vistos:
                raise SSCOValidationException(
                    f"Fila {row_num}: RUC duplicado en el archivo ({ruc_str}). El padrón oficial no debe contener duplicados."
                )
            rucs_vistos.add(ruc_str)

            # Razón social
            raw_rs = row[idx_razon_social] if idx_razon_social < len(row) else None
            razon_social = str(raw_rs).strip() if raw_rs is not None else ""
            if not razon_social:
                raise SSCOValidationException(f"Fila {row_num}: La Razón Social no puede estar vacía.")

            # Domicilio
            raw_dom = row[idx_domicilio] if idx_domicilio is not None and idx_domicilio < len(row) else None
            domicilio = str(raw_dom).strip() if raw_dom is not None else None

            # Resolución
            raw_res = row[idx_resolucion] if idx_resolucion < len(row) else None
            resolucion = str(raw_res).strip() if raw_res is not None else ""
            if not resolucion:
                raise SSCOValidationException(f"Fila {row_num}: La Resolución de atribución no puede estar vacía.")

            # Fechas
            try:
                fec_emision = self._parsear_fecha(row[idx_fec_emision])
                fec_firmeza = self._parsear_fecha(row[idx_fec_firmeza])
                fec_pub = self._parsear_fecha(row[idx_fec_pub])
            except Exception as e:
                raise SSCOValidationException(f"Fila {row_num}: Error en fecha ({str(e)})")

            if max_fecha_pub is None or fec_pub > max_fecha_pub:
                max_fecha_pub = fec_pub

            # Representante legal
            raw_doc_rep = row[idx_doc_rep] if idx_doc_rep is not None and idx_doc_rep < len(row) else None
            doc_rep = str(raw_doc_rep).strip() if raw_doc_rep is not None else None

            raw_nom_rep = row[idx_nom_rep] if idx_nom_rep is not None and idx_nom_rep < len(row) else None
            nom_rep = str(raw_nom_rep).strip() if raw_nom_rep is not None else None

            registros.append({
                "ruc": ruc_str,
                "razon_social": razon_social[:255],
                "domicilio_fiscal": domicilio,
                "resolucion_atribucion": resolucion[:255],
                "fecha_emision_resolucion": fec_emision,
                "fecha_firmeza": fec_firmeza,
                "doc_representante": doc_rep[:20] if doc_rep else None,
                "nombre_representante": nom_rep[:255] if nom_rep else None,
                "fecha_publicacion": fec_pub,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

        if not registros:
            raise SSCOValidationException("El archivo no contiene registros válidos para importar.")

        fecha_oficial_str = max_fecha_pub.strftime("%d/%m/%Y") if max_fecha_pub else None
        return registros, fecha_oficial_str

    async def aplicar_reemplazo_atomico(
        self,
        registros: List[Dict[str, Any]],
        fecha_oficial_str: Optional[str],
        origen: str,
        current_user: Usuario,
        db: AsyncSession
    ) -> SSCOSyncResponse:
        """
        Ejecuta el reemplazo atómico del padrón en PostgreSQL.
        Garantía de Rollback: si falla cualquier paso, el padrón anterior se conserva intacto.
        """
        try:
            # Reemplazo atómico en una única transacción
            # 1. Eliminar datos vigentes
            await db.execute(delete(PadronSSCO))

            # 2. Insertar lote completo
            if registros:
                await db.execute(insert(PadronSSCO), registros)

            # 3. Registrar sincronización exitosa
            sync_log = PadronSSCOSincronizacion(
                origen=origen,
                total_registros=len(registros),
                fecha_padron_sunat=fecha_oficial_str,
                usuario_id=current_user.id,
                estado="EXITOSO",
                mensaje=f"Actualización completada exitosamente. Total registros oficiales: {len(registros)}.",
                created_at=datetime.now(timezone.utc)
            )
            db.add(sync_log)

            # 4. Registrar evento de auditoría
            accion_audit = "ACTUALIZAR_PADRON_SSCO" if origen == "AUTO_DESCARGA" else "CARGAR_PADRON_SSCO_MANUAL"
            await audit_service.registrar_evento(
                db=db,
                accion=accion_audit,
                entidad="padron_ssco",
                usuario_id=current_user.id,
                empresa_id=current_user.empresa_id,
                detalle={
                    "origen": origen,
                    "total_registros": len(registros),
                    "fecha_padron_sunat": fecha_oficial_str,
                },
                commit=False
            )

            await db.commit()

            return SSCOSyncResponse(
                mensaje=f"Padrón SSCO actualizado correctamente con {len(registros)} registros oficiales.",
                total_registros=len(registros),
                fecha_padron_sunat=fecha_oficial_str,
                origen=origen,
                estado="EXITOSO"
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Error al persistir padrón SSCO: {str(e)}", exc_info=True)

            # En una transacción separada, registrar el fallo para auditoría
            try:
                error_log = PadronSSCOSincronizacion(
                    origen=origen,
                    total_registros=0,
                    fecha_padron_sunat=fecha_oficial_str,
                    usuario_id=current_user.id,
                    estado="ERROR",
                    mensaje=f"Fallo durante la persistencia: {str(e)}",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(error_log)
                await db.commit()
            except Exception:
                await db.rollback()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al persistir el padrón en la base de datos: {str(e)}"
            )

    async def sincronizar_desde_sunat(
        self,
        current_user: Usuario,
        db: AsyncSession
    ) -> SSCOSyncResponse:
        """
        Descarga directamente el archivo oficial desde el portal SUNAT y actualiza el padrón atómicamente.
        Solo accesible por rol ADMINISTRADOR.
        """
        parsed_url = urlparse(SUNAT_SSCO_OFFICIAL_URL)
        if parsed_url.scheme != "https" or parsed_url.netloc != ALLOWED_HOST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La URL de descarga no corresponde a la fuente oficial autorizada de SUNAT."
            )

        # Descargar con HTTPX
        # Configurar User-Agent explícito institucional/navegador estándar para evitar bloqueos por WAF
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0, verify=True, follow_redirects=False) as client:
                response = await client.get(SUNAT_SSCO_OFFICIAL_URL, headers=headers)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"SUNAT respondió con código HTTP {response.status_code} al solicitar el padrón SSCO."
                    )
                content = response.content
        except httpx.RequestError as exc:
            # Registrar el error de red conservando el padrón anterior
            try:
                error_log = PadronSSCOSincronizacion(
                    origen="AUTO_DESCARGA",
                    total_registros=0,
                    fecha_padron_sunat=None,
                    usuario_id=current_user.id,
                    estado="ERROR",
                    mensaje=f"Error de red al conectar con SUNAT: {str(exc)}",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(error_log)
                await db.commit()
            except Exception:
                await db.rollback()

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"No se pudo descargar el archivo oficial de SUNAT debido a un error de conexión: {str(exc)}"
            )

        # Parsear y validar
        try:
            registros, fecha_oficial = self.parsear_y_validar_excel(content)
        except SSCOValidationException as ve:
            # Registrar fallo
            try:
                error_log = PadronSSCOSincronizacion(
                    origen="AUTO_DESCARGA",
                    total_registros=0,
                    fecha_padron_sunat=None,
                    usuario_id=current_user.id,
                    estado="ERROR",
                    mensaje=f"Archivo oficial de SUNAT no superó la validación: {ve.message}",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(error_log)
                await db.commit()
            except Exception:
                await db.rollback()
            raise HTTPException(status_code=ve.status_code, detail=ve.message)

        # Aplicar reemplazo atómico
        return await self.aplicar_reemplazo_atomico(
            registros=registros,
            fecha_oficial_str=fecha_oficial,
            origen="AUTO_DESCARGA",
            current_user=current_user,
            db=db
        )

    async def cargar_excel_manual(
        self,
        file_bytes: bytes,
        current_user: Usuario,
        db: AsyncSession
    ) -> SSCOSyncResponse:
        """
        Carga manual del archivo XLSX oficial por parte del ADMINISTRADOR como contingencia.
        Aplica exactamente las mismas validaciones de seguridad, estructura y atomicidad.
        """
        try:
            registros, fecha_oficial = self.parsear_y_validar_excel(file_bytes)
        except SSCOValidationException as ve:
            try:
                error_log = PadronSSCOSincronizacion(
                    origen="MANUAL_EXCEL",
                    total_registros=0,
                    fecha_padron_sunat=None,
                    usuario_id=current_user.id,
                    estado="ERROR",
                    mensaje=f"Carga manual rechazada: {ve.message}",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(error_log)
                await db.commit()
            except Exception:
                await db.rollback()
            raise HTTPException(status_code=ve.status_code, detail=ve.message)

        return await self.aplicar_reemplazo_atomico(
            registros=registros,
            fecha_oficial_str=fecha_oficial,
            origen="MANUAL_EXCEL",
            current_user=current_user,
            db=db
        )


ssco_service = SSCOService()
