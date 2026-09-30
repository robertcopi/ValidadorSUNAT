# Manual y Directrices de Seguridad del Sistema

Este documento describe la arquitectura de seguridad, controles técnicos y buenas prácticas implementadas en el **Sistema de Validación de Comprobantes SUNAT**.

---

## 1. Autenticación y Seguridad JWT

- **Tokens Firmados:** La autenticación utiliza JSON Web Tokens (JWT) firmados con el algoritmo `HS256` utilizando la clave `SECRET_KEY` configurada en el servidor.
- **Validación Activa en Base de Datos:** Cada solicitud validada por `get_current_user` consulta activamente la base de datos para corroborar que el usuario exista y que `usuario.activo == True`.
- **Inhabilitación Inmediata:** Si un usuario es desactivado lógicamente por un administrador, cualquier JWT previamente emitido queda inmediatamente revocado e inutilizado, respondiendo `HTTP 401 Unauthorized`.
- **Expiración de Sesión:** Los tokens cuentan con un tiempo de vida configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## 2. Control de Acceso Basado en Roles (RBAC)

El sistema implementa dos roles estrictamente delimitados:

| Rol | Alcance | Módulos Permitidos |
|---|---|---|
| **ADMINISTRADOR** | Global / Multiempresa (`empresa_id = NULL` o asignada) | Panel de administración de usuarios, empresas, visor de auditoría, dashboards de todas las empresas. |
| **CONTADOR** | Tenancy estricto (`empresa_id` obligatorio) | Validación individual, carga masiva, historial, reportes y dashboards **exclusivamente de su empresa**. Acceso denegado (`HTTP 403`) a rutas `/admin/*`. |

---

## 3. Arquitectura Multiempresa y Aislamiento de Datos (Multi-Tenancy)

- **Aislamiento en Base de Datos:** Toda consulta, proceso masivo o registro persistido contiene una clave foránea `empresa_id`.
- **Filtro Forzoso en Backend:** Todas las consultas SQL generadas para usuarios con rol `CONTADOR` aplican una cláusula WHERE fija con `empresa_id = current_user.empresa_id`.
- **Validación Cruzada Imposible:** Un contador de la empresa DAIRA no puede consultar, visualizar ni descargar procesos de la empresa GRUPO JJD MAR, aún manipulando parámetros en la URL o cabeceras HTTP.

---

## 4. Gestión de Credenciales y Secretos SUNAT

- **OAuth2 Client Credentials:** La API de Consulta Integrada de SUNAT requiere exclusivamente `CLIENT_ID` y `CLIENT_SECRET`. No requiere ni utiliza `SOL_USER` ni `SOL_PASSWORD`.
- **Almacenamiento Fuera de Base de Datos:** Los secretos de SUNAT **NUNCA** se almacenan en texto plano en PostgreSQL. Se gestionan exclusivamente en variables de entorno seguras del servidor (`.env`).
- **Exposición Cero:**
  - El frontend nunca recibe el `client_secret` ni el `access_token` de SUNAT.
  - Los endpoints de consulta devuelven únicamente el estado booleano de configuración (`configurado: true/false`).
  - Los logs y tablas de auditoría censuran cualquier intento de registro de credenciales.
- **Evolución Futura para Almacenamiento en BD:** Si en el futuro se requiriese almacenar credenciales en base de datos, deberá implementarse cifrado asimétrico o de sobre cerrado mediante un gestor de claves (KMS, HashiCorp Vault o AWS Secrets Manager), nunca en texto claro.

---

## 5. Gestión Segura de Contraseñas

- **Hashing Criptográfico:** Las contraseñas se procesan con `bcrypt` (12 rondas de sal).
- **Prohibición de Texto Plano:** Bajo ninguna circunstancia se almacena ni devuelve la contraseña en texto plano ni el hash bcrypt en las respuestas JSON de la API.
- **Cambio de Contraseña:** Los usuarios pueden cambiar su clave en `/api/v1/auth/change-password` validando previamente su clave actual, coincidencia con confirmación y longitud mínima.
- **Contraseñas Temporales y `must_change_password`:** Cuando un administrador restablece la contraseña de un usuario, se genera una contraseña temporal y se activa la bandera `must_change_password = True`, obligando al usuario a cambiarla.

---

## 6. Auditoría Inmutable de Acciones

El sistema cuenta con una tabla de auditoría (`auditoria_eventos`) que registra de forma inalterable las acciones críticas:

- `LOGIN_EXITOSO` y `LOGIN_FALLIDO`
- `CAMBIO_PASSWORD` y `RESET_PASSWORD`
- `USUARIO_CREADO`, `USUARIO_EDITADO`, `USUARIO_ACTIVADO`, `USUARIO_DESACTIVADO`
- `EMPRESA_CREADA`, `EMPRESA_EDITADA`
- `PROCESO_MASIVO_CREADO`, `REINTENTO_PROCESO`, `EXPORTACION_EXCEL`

**Sanitización Automática:** El servicio `audit_service` analiza recursivamente los objetos JSON y reemplaza cualquier campo sensible (`password`, `token`, `secret`, `client_secret`) por `[REDACTED]`.

---

## 7. Limitación de Tasa (Rate Limiting) en Login

- Para mitigar ataques de fuerza bruta o adivinación de contraseñas, el endpoint `/api/v1/auth/login` restringe el número de intentos fallidos por IP y correo (máximo 5 intentos en una ventana de 5 minutos).
- Al superarse el límite, responde con `HTTP 429 Too Many Requests`.
- Ante credenciales inválidas, responde con un mensaje genérico unificado ("*Credenciales incorrectas. Verifique su correo y contraseña*"), impidiendo la enumeración de usuarios.

---

## 8. Cabeceras de Seguridad y CORS

- **CORS Estricto:** En producción se restringen los orígenes mediante `BACKEND_CORS_ORIGINS`. El uso del comodín `*` está prohibido.
- **Cabeceras HTTP Inyectadas en Todo Response:**
  - `X-Content-Type-Options: nosniff` (previene MIME-type sniffing).
  - `X-Frame-Options: DENY` (protege contra ataques de clickjacking).
  - `Referrer-Policy: no-referrer` (evita fugas de URLs sensibles en cabeceras).
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`.
  - `Strict-Transport-Security` (HSTS) habilitado en entornos HTTPS/producción.

---

## 9. Registro y Centralización de Logs

- Todos los eventos del backend son procesados por un formateador centralizado.
- Se implementa `SensitiveDataFilter`, el cual filtra y redacta automáticamente tokens de tipo `Bearer <token>` y campos sensibles antes de emitirlos a consola o disco.

---

## 10. Respaldo y Continuidad Operativa

- Las copias de seguridad de la base de datos se generan mediante `pg_dump` con formato comprimido custom.
- Los respaldos deben almacenarse en almacenamiento cifrado externo o en almacenamiento inmutable de la nube (ej. AWS S3 con Object Lock).
- La restauración periódica en bases de prueba aisladas garantiza la recuperación ante desastres sin interrumpir el servicio operativo.
