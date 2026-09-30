import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.models.consulta_cpe import ConsultaCPE
from app.schemas.sunat import ComprobanteValidarRequest, ConsultaCPEResponse, EmpresaInfo, TIPO_COMPROBANTE_MAP

logger = logging.getLogger(__name__)


class SunatException(Exception):
    """Excepción general para errores al interactuar con los servicios de SUNAT."""
    def __init__(self, message: str, status_code: int = 400, codigo_sunat: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.codigo_sunat = codigo_sunat


class SunatCredentialsError(SunatException):
    """Excepción para credenciales faltantes o no configuradas para una empresa."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500, codigo_sunat="CRED_CONFIG_ERROR")


@dataclass
class SunatCredentials:
    client_id: str
    client_secret: str
    ruc_empresa: str


@dataclass
class CachedToken:
    access_token: str
    expires_at: float  # Unix timestamp


# ==============================================================================
# TABLAS DE CÓDIGOS OFICIALES DE SUNAT
# Fuente: "Manual de Consulta Integrada de Validez de Comprobante de Pago por
#          Servicio WEB SUNAT" (SUNAT - Superintendencia Nacional de Aduanas
#          y de Administración Tributaria).
# ==============================================================================

# 1. Estado del comprobante de pago (estadoCp)
ESTADO_CP_MAP = {
    "0": "NO EXISTE: El comprobante no figura registrado en los sistemas de SUNAT.",
    "1": "ACEPTADO: El comprobante de pago es informado y se encuentra Aceptado ante SUNAT.",
    "2": "ANULADO: El comprobante de pago figura formalmente Anulado o comunicado de baja ante SUNAT.",
    "3": "AUTORIZADO: Comprobante de pago físico emitido con autorización de imprenta.",
    "4": "NO AUTORIZADO: Comprobante de pago físico no cuenta con autorización de imprenta.",
}

# 2. Estado del contribuyente emisor (estadoRuc)
ESTADO_RUC_MAP = {
    "00": "ACTIVO",
    "01": "BAJA PROVISIONAL",
    "02": "BAJA PROV. POR OFICIO",
    "03": "SUSPENSION TEMPORAL",
    "10": "BAJA DEFINITIVA",
    "11": "BAJA DE OFICIO",
    "22": "INHABILITADO-VENT.UNICA",
}

# 3. Condición de domicilio fiscal del contribuyente emisor (condDomiRuc)
COND_DOMI_MAP = {
    "00": "HABIDO",
    "09": "PENDIENTE",
    "11": "POR VERIFICAR",
    "12": "NO HABIDO",
    "20": "NO HALLADO",
}


class SunatService:
    """
    Servicio de integración con SUNAT para autenticación OAuth2 y consulta de comprobantes.
    Implementa aislamiento estricto de credenciales y caché de tokens en memoria por empresa.
    """

    def __init__(self):
        # Caché en memoria por RUC de empresa: { "20538976815": CachedToken(...) }
        self._token_cache: Dict[str, CachedToken] = {}
        # Candados por RUC para prevenir solicitudes de token concurrentes duplicadas
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_lock_for_ruc(self, ruc: str) -> asyncio.Lock:
        """Obtiene o crea un Lock específico para la empresa garantizando concurrencia segura."""
        async with self._global_lock:
            if ruc not in self._locks:
                self._locks[ruc] = asyncio.Lock()
            return self._locks[ruc]

    def resolve_raw_credentials(self, empresa_ruc: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resuelve client_id y client_secret para un RUC utilizando:
        1. Alias directos configurados en settings (DAIRA / JJD)
        2. Variables dinámicas de entorno por convención:
           SUNAT_{RUC}_CLIENT_ID y SUNAT_{RUC}_CLIENT_SECRET
        """
        client_id: Optional[str] = None
        client_secret: Optional[str] = None

        if empresa_ruc == "20538976815":
            client_id = settings.SUNAT_DAIRA_CLIENT_ID
            client_secret = settings.SUNAT_DAIRA_CLIENT_SECRET
        elif empresa_ruc == "20612689831":
            client_id = settings.SUNAT_JJD_CLIENT_ID
            client_secret = settings.SUNAT_JJD_CLIENT_SECRET
        else:
            clean_ruc = empresa_ruc.strip()
            client_id = os.getenv(f"SUNAT_{clean_ruc}_CLIENT_ID")
            client_secret = os.getenv(f"SUNAT_{clean_ruc}_CLIENT_SECRET")

        return (
            client_id.strip() if client_id else None,
            client_secret.strip() if client_secret else None
        )

    def get_sunat_config_status(self, empresa_ruc: str) -> Dict[str, bool]:
        """
        Devuelve el estado de configuración de credenciales SUNAT para una empresa.
        NUNCA expone secretos ni tokens.
        """
        cid, csec = self.resolve_raw_credentials(empresa_ruc)
        has_cid = bool(cid)
        has_sec = bool(csec)
        return {
            "configurado": bool(has_cid and has_sec),
            "client_id_configurado": has_cid,
            "client_secret_configurado": has_sec
        }

    def get_credentials_for_empresa(self, empresa_ruc: str) -> SunatCredentials:
        """
        Resuelve estrictamente las credenciales SUNAT configuradas para la empresa por su RUC.
        DAIRA: 20538976815
        GRUPO JJD MAR: 20612689831
        Otras empresas: SUNAT_{RUC}_CLIENT_ID y SUNAT_{RUC}_CLIENT_SECRET
        Utiliza exclusivamente client_id y client_secret (OAuth2 client_credentials).
        """
        client_id, client_secret = self.resolve_raw_credentials(empresa_ruc)

        if not client_id and not client_secret:
            raise SunatCredentialsError(
                f"La empresa con RUC {empresa_ruc} no cuenta con proveedor de credenciales configurado en el sistema."
            )

        if not client_id or not client_secret:
            raise SunatCredentialsError(
                f"Credenciales SUNAT incompletas para la empresa RUC {empresa_ruc}. "
                "Verifique las variables de entorno en el servidor."
            )

        return SunatCredentials(
            client_id=client_id,
            client_secret=client_secret,
            ruc_empresa=empresa_ruc,
        )

    def invalidate_token(self, empresa_ruc: str) -> None:
        """Invalida inmediatamente el token en caché para la empresa especificada."""
        if empresa_ruc in self._token_cache:
            del self._token_cache[empresa_ruc]
            logger.info("Token SUNAT invalidado para empresa RUC %s", empresa_ruc)

    async def get_access_token(self, empresa_ruc: str, client: Optional[httpx.AsyncClient] = None) -> str:
        """
        Obtiene un token OAuth2 válido para la empresa mediante client_credentials.
        Endpoint: POST https://api-seguridad.sunat.gob.pe/v1/clientesextranet/{CLIENT_ID}/oauth2/token/
        Body (application/x-www-form-urlencoded):
          grant_type=client_credentials
          scope=https://api.sunat.gob.pe/v1/contribuyente/contribuyentes
          client_id={CLIENT_ID}
          client_secret={CLIENT_SECRET}
        Reutiliza el token en caché mientras no haya expirado (con buffer de 60 segundos).
        """
        lock = await self._get_lock_for_ruc(empresa_ruc)
        async with lock:
            # 1. Verificar si hay un token válido en caché
            cached = self._token_cache.get(empresa_ruc)
            now = time.time()
            if cached and cached.expires_at > (now + 60):
                return cached.access_token

            # 2. Obtener credenciales seguras (client_id y client_secret)
            creds = self.get_credentials_for_empresa(empresa_ruc)

            auth_url = f"{settings.SUNAT_AUTH_BASE_URL}/{creds.client_id}/oauth2/token/"
            data = {
                "grant_type": "client_credentials",
                "scope": settings.SUNAT_AUTH_SCOPE,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
            }

            timeout = httpx.Timeout(settings.SUNAT_TIMEOUT_SECONDS, connect=10.0)

            should_close_client = False
            if client is None:
                client = httpx.AsyncClient(timeout=timeout)
                should_close_client = True

            try:
                response = await client.post(
                    auth_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )

                if response.status_code != 200:
                    logger.error(
                        "Error al solicitar token SUNAT para RUC %s. Código HTTP: %d",
                        empresa_ruc,
                        response.status_code
                    )
                    try:
                        err_json = response.json()
                        err_desc = err_json.get("error_description") or err_json.get("error") or response.text
                    except Exception:
                        err_desc = response.text
                    raise SunatException(
                        f"Error de autenticación con SUNAT (HTTP {response.status_code}): {err_desc}",
                        status_code=502,
                        codigo_sunat="AUTH_FAILED"
                    )

                token_data = response.json()
                access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)

                if not access_token:
                    raise SunatException(
                        "Respuesta de autenticación SUNAT no contiene access_token válido.",
                        status_code=502,
                        codigo_sunat="INVALID_AUTH_RESPONSE"
                    )

                # Almacenar en caché con expiración
                self._token_cache[empresa_ruc] = CachedToken(
                    access_token=access_token,
                    expires_at=now + float(expires_in)
                )

                logger.info("Nuevo token SUNAT obtenido exitosamente para RUC %s", empresa_ruc)
                return access_token

            except httpx.TimeoutException:
                logger.error("Timeout al solicitar token SUNAT para RUC %s", empresa_ruc)
                raise SunatException(
                    "Tiempo de espera agotado al conectar con el servidor de autenticación SUNAT.",
                    status_code=504,
                    codigo_sunat="TIMEOUT"
                )
            except (httpx.ConnectError, httpx.NetworkError) as e:
                logger.error("Error de red conectando con autenticación SUNAT: %s", str(e))
                raise SunatException(
                    "Error de red o conexión rechazada al contactar a SUNAT.",
                    status_code=502,
                    codigo_sunat="NETWORK_ERROR"
                )
            finally:
                if should_close_client:
                    await client.aclose()

    def interpretar_respuesta_sunat(
        self,
        http_status: int,
        response_json: Optional[Dict[str, Any]],
        response_text: str
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Interpreta la respuesta funcional del servicio de validación de SUNAT conforme a:
        - "Manual de Consulta Integrada de Validez de Comprobante de Pago por Servicio WEB SUNAT"
        
        Devuelve tupla: (estado_interno, codigo_sunat, mensaje_sunat)
        Estados internos seguros: VALIDO | NO_VALIDO | OBSERVADO | ERROR
        """
        # 1. Validación de código de estado HTTP
        if http_status != 200:
            if response_json:
                cod = str(response_json.get("errorCode") or response_json.get("cod") or response_json.get("error") or http_status)
                msg = response_json.get("message") or response_json.get("msg") or response_json.get("error_description") or response_text
                return "ERROR", cod, f"Error devuelto por SUNAT (HTTP {http_status}): {msg}"
            return "ERROR", str(http_status), f"Error devuelto por SUNAT (HTTP {http_status}): {response_text}"

        # 2. Verificación de cuerpo JSON existente
        if not response_json or not isinstance(response_json, dict):
            return "ERROR", "NO_JSON", "SUNAT devolvió una respuesta vacía o con formato no interpretable."

        # 3. Verificación de campos de control de error: 'success' y 'errorCode'
        success = response_json.get("success")
        error_code = response_json.get("errorCode") or response_json.get("cod")
        general_msg = response_json.get("message") or response_json.get("msg")

        if success is False or (error_code and not response_json.get("data")):
            cod_err = str(error_code or "ERROR_CONSULTA")
            msg_err = general_msg or "La consulta no pudo ser completada por SUNAT."
            return "ERROR", cod_err, f"SUNAT reportó error en la consulta: {msg_err}"

        # 4. Extracción del objeto 'data'
        data = response_json.get("data")
        if data is None and "estadoCp" in response_json:
            # Compatibilidad si viniera plano
            data = response_json

        if not data or not isinstance(data, dict):
            cod = str(error_code or "0000")
            msg = general_msg or "Respuesta de SUNAT sin datos de comprobante para evaluar."
            return "ERROR", cod, msg

        # 5. Extracción y normalización de campos oficiales de SUNAT
        # estadoCp: 0 (No Existe), 1 (Aceptado), 2 (Anulado), 3 (Autorizado), 4 (No Autorizado)
        estado_cp_raw = data.get("estadoCp")
        estado_cp = str(estado_cp_raw).strip() if estado_cp_raw is not None else ""

        # estadoRuc: 00 (Activo), 01 (Baja Prov.), 02 (Baja Prov. Oficio), 03 (Susp. Temporal), 10 (Baja Def.), etc.
        estado_ruc_raw = data.get("estadoRuc")
        estado_ruc = str(estado_ruc_raw).strip() if estado_ruc_raw is not None else ""

        # condDomiRuc: 00 (Habido), 09 (Pendiente), 11 (Por Verificar), 12 (No Habido), 20 (No Hallado)
        cond_domi_raw = data.get("condDomiRuc")
        cond_domi = str(cond_domi_raw).strip() if cond_domi_raw is not None else ""

        # Observaciones: array de cadenas devueltas por SUNAT
        obs_raw = data.get("observaciones") or data.get("Observaciones") or []
        if isinstance(obs_raw, list):
            observaciones = [str(o).strip() for o in obs_raw if o]
        elif isinstance(obs_raw, str) and obs_raw.strip():
            observaciones = [obs_raw.strip()]
        else:
            observaciones = []

        # 6. Formulación del detalle descriptivo basado estrictamente en el manual
        desc_cp = ESTADO_CP_MAP.get(estado_cp, f"Estado CPE '{estado_cp}' no catalogado oficialmente")
        desc_ruc = ESTADO_RUC_MAP.get(estado_ruc, f"Estado RUC '{estado_ruc}'") if estado_ruc else ""
        desc_domi = COND_DOMI_MAP.get(cond_domi, f"Condición Domicilio '{cond_domi}'") if cond_domi else ""

        detalles = [desc_cp]
        if desc_ruc:
            detalles.append(f"RUC Emisor: {desc_ruc}")
        if desc_domi:
            detalles.append(f"Domicilio: {desc_domi}")
        if observaciones:
            detalles.append("Observaciones: " + "; ".join(observaciones))
        if general_msg and general_msg not in detalles and general_msg != "OK":
            detalles.append(f"Info: {general_msg}")

        mensaje_completo = " | ".join(detalles)

        # 7. Clasificación funcional sin suposiciones ni invenciones
        if estado_cp == "1":
            # estadoCp = 1 es ACEPTADO formalmente en SUNAT.
            # Verificamos si concurre alguna observación tributaria de validez sustancial:
            tiene_obs_domicilio = (cond_domi != "00" and cond_domi != "")  # No es HABIDO (ej. 12 No Habido, 20 No Hallado)
            tiene_obs_ruc = (estado_ruc != "00" and estado_ruc != "")      # No es ACTIVO (ej. Baja o Suspensión)
            tiene_observaciones = len(observaciones) > 0                   # Existen observaciones explícitas de SUNAT

            if tiene_obs_domicilio or tiene_obs_ruc or tiene_observaciones:
                # Comprobante informado pero con advertencias contables/tributarias críticas
                return "OBSERVADO", estado_cp, mensaje_completo

            # Cumple plenamente con ACEPTADO, RUC ACTIVO y HABIDO sin observaciones
            return "VALIDO", estado_cp, mensaje_completo

        elif estado_cp in ["0", "2", "4"]:
            # 0: NO EXISTE / No informado ante SUNAT
            # 2: ANULADO / Comunicado de baja
            # 4: NO AUTORIZADO por imprenta
            return "NO_VALIDO", estado_cp, mensaje_completo

        elif estado_cp == "3":
            # 3: AUTORIZADO (Comprobante físico autorizado por imprenta, requiere cotejo)
            return "OBSERVADO", estado_cp, mensaje_completo

        else:
            # Código no contemplado en el catálogo oficial de SUNAT (0, 1, 2, 3, 4).
            # Por seguridad NO se inventa ni asume validez o invalidez; se cataloga como OBSERVADO
            # preservando el código original y el texto de SUNAT para auditoría contable.
            return "OBSERVADO", estado_cp or "UNKNOWN", f"Estado no catalogado por SUNAT: {mensaje_completo}"

    def _sanitize_for_audit(self, data: Any) -> Any:
        """Elimina posibles datos sensibles antes de almacenar en BD."""
        if not isinstance(data, dict):
            return data
        sensitive_keys = {
            "password", "password_hash", "client_secret", "sol_password",
            "access_token", "token", "authorization"
        }
        cleaned = {}
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                continue
            if isinstance(v, dict):
                cleaned[k] = self._sanitize_for_audit(v)
            elif isinstance(v, list):
                cleaned[k] = [self._sanitize_for_audit(item) for item in v]
            else:
                cleaned[k] = v
        return cleaned

    async def validar_comprobante(
        self,
        empresa: Empresa,
        usuario: Usuario,
        request_data: ComprobanteValidarRequest,
        db: AsyncSession,
        http_client: Optional[httpx.AsyncClient] = None
    ) -> ConsultaCPEResponse:
        """
        Orquesta la validación de un comprobante ante SUNAT con reintento único ante HTTP 401.
        Garantiza el aislamiento multiempresa y la persistencia de la auditoría.
        """
        empresa_ruc = empresa.ruc

        # 1. Construcción del endpoint de validación
        # URL usa el RUC de la empresa autenticada
        validar_url = f"{settings.SUNAT_API_BASE_URL}/{empresa_ruc}/validarcomprobante"

        # Body enviado a SUNAT usa numRuc como RUC del emisor del comprobante
        sunat_body = {
            "numRuc": request_data.num_ruc,
            "codComp": request_data.cod_comp,
            "numeroSerie": request_data.numero_serie,
            "numero": request_data.numero,
            "fechaEmision": request_data.fecha_emision_sunat,
            "monto": request_data.monto_sunat
        }

        timeout = httpx.Timeout(settings.SUNAT_TIMEOUT_SECONDS, connect=10.0)
        should_close_client = False
        client = http_client
        if client is None:
            client = httpx.AsyncClient(timeout=timeout)
            should_close_client = True

        token = await self.get_access_token(empresa_ruc, client=client)

        try:
            # Intentar consulta
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            try:
                response = await client.post(validar_url, json=sunat_body, headers=headers)
            except httpx.TimeoutException:
                logger.error("Timeout al validar comprobante en SUNAT para empresa %s", empresa_ruc)
                # Registrar error en BD para auditoría
                consulta_error = ConsultaCPE(
                    empresa_id=empresa.id,
                    usuario_id=usuario.id,
                    ruc_emisor=request_data.num_ruc,
                    tipo_comprobante=request_data.cod_comp,
                    serie=request_data.numero_serie,
                    numero=request_data.numero,
                    fecha_emision=request_data.fecha_emision,
                    monto=request_data.monto,
                    estado="ERROR",
                    codigo_sunat="TIMEOUT",
                    mensaje_sunat="Tiempo de espera agotado al consultar SUNAT (Timeout).",
                    respuesta_sunat={"error": "Timeout", "url": validar_url}
                )
                db.add(consulta_error)
                await db.commit()
                await db.refresh(consulta_error)
                raise SunatException("Tiempo de espera agotado al consultar SUNAT.", status_code=504, codigo_sunat="TIMEOUT")
            except (httpx.ConnectError, httpx.NetworkError) as ne:
                logger.error("Error de red conectando con SUNAT: %s", str(ne))
                consulta_error = ConsultaCPE(
                    empresa_id=empresa.id,
                    usuario_id=usuario.id,
                    ruc_emisor=request_data.num_ruc,
                    tipo_comprobante=request_data.cod_comp,
                    serie=request_data.numero_serie,
                    numero=request_data.numero,
                    fecha_emision=request_data.fecha_emision,
                    monto=request_data.monto,
                    estado="ERROR",
                    codigo_sunat="NETWORK_ERROR",
                    mensaje_sunat="No fue posible conectar con los servicios de SUNAT.",
                    respuesta_sunat={"error": "NetworkError", "url": validar_url}
                )
                db.add(consulta_error)
                await db.commit()
                await db.refresh(consulta_error)
                raise SunatException("No fue posible conectar con los servicios de SUNAT.", status_code=502, codigo_sunat="NETWORK_ERROR")

            # Paso 3: Si SUNAT responde 401, invalidar token y reintentar UNA sola vez
            if response.status_code == 401:
                logger.warning("SUNAT devolvió 401 para empresa %s. Invalidando token y reintentando una vez...", empresa_ruc)
                self.invalidate_token(empresa_ruc)
                token = await self.get_access_token(empresa_ruc, client=client)
                headers["Authorization"] = f"Bearer {token}"
                
                try:
                    response = await client.post(validar_url, json=sunat_body, headers=headers)
                except httpx.TimeoutException:
                    raise SunatException("Tiempo de espera agotado en reintento SUNAT.", status_code=504, codigo_sunat="TIMEOUT")
                except (httpx.ConnectError, httpx.NetworkError):
                    raise SunatException("Error de red al reintentar contra SUNAT.", status_code=502, codigo_sunat="NETWORK_ERROR")

            # Paso 11: Interpretar respuesta funcional
            response_json = None
            try:
                response_json = response.json()
            except Exception:
                pass

            estado, cod_sunat, msg_sunat = self.interpretar_respuesta_sunat(
                http_status=response.status_code,
                response_json=response_json,
                response_text=response.text
            )

            # Sanitizar respuesta para auditoría
            sanitized_respuesta = self._sanitize_for_audit(response_json) if response_json else {"raw_text": response.text[:500]}

            # Paso 9 y 10: Registrar consulta en BD
            consulta_db = ConsultaCPE(
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                ruc_emisor=request_data.num_ruc,
                tipo_comprobante=request_data.cod_comp,
                serie=request_data.numero_serie,
                numero=request_data.numero,
                fecha_emision=request_data.fecha_emision,
                monto=request_data.monto,
                estado=estado,
                codigo_sunat=cod_sunat,
                mensaje_sunat=msg_sunat[:500] if msg_sunat else None,
                respuesta_sunat=sanitized_respuesta
            )
            db.add(consulta_db)
            await db.commit()
            await db.refresh(consulta_db)

            tipo_desc = TIPO_COMPROBANTE_MAP.get(consulta_db.tipo_comprobante, consulta_db.tipo_comprobante)

            return ConsultaCPEResponse(
                id=consulta_db.id,
                empresa_id=consulta_db.empresa_id,
                usuario_id=consulta_db.usuario_id,
                ruc_emisor=consulta_db.ruc_emisor,
                tipo_comprobante=consulta_db.tipo_comprobante,
                tipo_comprobante_descripcion=tipo_desc,
                serie=consulta_db.serie,
                numero=consulta_db.numero,
                fecha_emision=consulta_db.fecha_emision,
                monto=consulta_db.monto,
                estado=consulta_db.estado,
                codigo_sunat=consulta_db.codigo_sunat,
                mensaje_sunat=consulta_db.mensaje_sunat,
                empresa_consultora=EmpresaInfo(
                    ruc=empresa.ruc,
                    razon_social=empresa.razon_social
                ),
                created_at=consulta_db.created_at
            )

        finally:
            if should_close_client:
                await client.aclose()


# Instancia singleton del servicio SUNAT
sunat_service = SunatService()
