# Guía de Despliegue y Puesta en Producción

Esta guía describe el procedimiento estándar para la instalación, despliegue y mantenimiento del **Sistema de Validación de Comprobantes SUNAT**.

---

## 1. Requisitos Previos

- **Servidor:** Linux (Ubuntu 22.04 LTS / Debian 12 recomendado) o Windows Server con Docker Desktop / WSL2.
- **CPU / RAM:** Mínimo 2 vCPU, 4 GB de memoria RAM.
- **Almacenamiento:** Mínimo 20 GB de espacio libre en disco (SSD recomendado).
- **Herramientas de Software:**
  - Docker Engine 24.0+ y Docker Compose v2.20+.
  - Git 2.30+.
  - Conectividad de red saliente hacia `api-seguridad.sunat.gob.pe` y `api.sunat.gob.pe` por HTTPS (puerto 443).

---

## 2. Variables de Entorno

Copie la plantilla de variables de entorno y configure los parámetros reales:

```bash
cp .env.example .env
chmod 600 .env
```

### Configuración obligatoria en `.env`:
- `SECRET_KEY`: Cadena criptográfica aleatoria de al menos 64 caracteres.
  *(Genere una con: `openssl rand -hex 32`)*
- `ENVIRONMENT`: Establecer estrictamente en `production`.
- `DEBUG`: Establecer en `False`.
- `POSTGRES_PASSWORD`: Contraseña segura para PostgreSQL.
- `BACKEND_CORS_ORIGINS`: Dominio o lista de dominios autorizados (por ejemplo, `["https://contabilidad.miempresa.com"]`). **Nunca utilizar `*` en producción**.
- `SUNAT_DAIRA_CLIENT_ID` y `SUNAT_DAIRA_CLIENT_SECRET`: Credenciales OAuth2 provistas por SUNAT para DAIRA.
- `SUNAT_JJD_CLIENT_ID` y `SUNAT_JJD_CLIENT_SECRET`: Credenciales OAuth2 provistas por SUNAT para GRUPO JJD MAR.
- Para empresas adicionales:
  - `SUNAT_{RUC}_CLIENT_ID` y `SUNAT_{RUC}_CLIENT_SECRET`.

---

## 3. Construcción de Contenedores con Docker

Construya las imágenes asegurando que el código y dependencias estén actualizados:

```bash
docker compose build --no-cache
```

---

## 4. Ejecución de Migraciones Alembic

La base de datos PostgreSQL debe inicializarse con el esquema más reciente. Ejecute:

```bash
# Iniciar primero el servicio de base de datos
docker compose up -d postgres

# Aplicar migraciones hasta la última versión
docker compose run --rm backend alembic upgrade head
```

---

## 5. Carga de Semillas Iniciales (Seed)

Para crear las empresas iniciales (DAIRA y JJD) y los usuarios de arranque:

```bash
docker compose run --rm backend python -m scripts.seed_data
```

> **IMPORTANTE:** Cambie inmediatamente las contraseñas de las cuentas creadas al ingresar al sistema desde la sección **Mi Perfil** o mediante el módulo de administración.

---

## 6. Levantar Servicios

Inicie la suite completa en segundo plano:

```bash
docker compose up -d
```

Verifique que todos los contenedores se encuentren en estado `Up` y `healthy`:
```bash
docker compose ps
```

---

## 7. Verificación de Salud del Sistema (Health Check)

Valide los endpoints de diagnóstico:

```bash
# Diagnóstico general
curl -f http://localhost:8000/api/v1/health

# Readiness probe (backend y base de datos conectados)
curl -f http://localhost:8000/api/v1/health/ready
```

Respuesta esperada:
```json
{
  "status": "ok",
  "database": "ok"
}
```

---

## 8. Verificación de Frontend

1. Acceda mediante el navegador web a la URL configurada (ej. `http://localhost:5173` o dominio de producción).
2. Verifique la carga del formulario de login.
3. Inicie sesión con el usuario administrador.
4. Confirme que la barra de navegación muestre el rol y el contexto multiempresa.

---

## 9. Política y Verificación de Backups

Consulte [`docs/BACKUP_RESTORE.md`](file:///c:/Users/ROBERT/Documents/sipan/X/practicas/ConsultasSunat/docs/BACKUP_RESTORE.md) para configurar un cron job de respaldo diario.

Ejemplo de crontab para respaldos a las 02:00 AM:
```cron
0 2 * * * cd /opt/consultas-sunat && docker compose exec -T postgres pg_dump -U sunat_user -Fc sunat_consultas_db > /opt/backups/sunat_$(date +\%Y\%m\%d).dump
```

---

## 10. Flujo de Actualización Segura (Zero Data Loss)

Para aplicar parches o nuevas versiones sin pérdida de información:

> **ADVERTENCIA CRÍTICA:** **NUNCA** utilice `docker compose down -v`. La bandera `-v` elimina los volúmenes persistentes y destruirá los datos históricos de PostgreSQL.

### Procedimiento recomendado de actualización:

```bash
# 1. Obtener los últimos cambios de código
git pull origin main

# 2. Generar backup preventivo antes de actualizar
docker compose exec -T postgres pg_dump -U sunat_user -Fc sunat_consultas_db > ./backups/pre_update_backup.dump

# 3. Reconstruir imágenes con las nuevas versiones
docker compose build

# 4. Levantar servicios recreando únicamente los contenedores actualizados
docker compose up -d

# 5. Aplicar migraciones de base de datos pendientes
docker compose exec backend alembic upgrade head

# 6. Validar estado de salud
curl -f http://localhost:8000/api/v1/health/ready
```
