# Procedimiento Operacional: Respaldo y Restauración de Base de Datos (PostgreSQL)

Este documento detalla el procedimiento técnico para realizar respaldos (`backup`) y restauraciones (`restore`) de la base de datos PostgreSQL del **Sistema de Validación de Comprobantes SUNAT**.

---

## 1. Consideraciones Previas y Seguridad

- **Integridad:** Las copias de seguridad se realizan a nivel lógico mediante la utilidad nativa de PostgreSQL (`pg_dump`).
- **Aislamiento:** **NUNCA** ejecute pruebas de restauración sobre la base de datos de producción o la base activa del contenedor (`sunat_consultas_db`). Pruebe siempre sobre una base de datos de prueba separada (por ejemplo, `sunat_db_test_restore`).
- **Preservación de Volúmenes:** **NUNCA** ejecute `docker compose down -v` en operaciones de mantenimiento o actualización rutinaria, ya que destruye irreversiblemente el volumen persistente `postgres_data`.

---

## 2. Generación de Respaldo (`pg_dump`)

### 2.1 Respaldo en Entorno Dockerizado

Para generar un backup sin detener los contenedores:

```bash
# Definir timestamp para versionado
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Crear directorio local de backups si no existe
mkdir -p ./backups

# Ejecutar pg_dump dentro del contenedor de PostgreSQL en formato custom comprimido (.dump)
docker compose exec -T postgres pg_dump -U sunat_user -Fc sunat_consultas_db > ./backups/sunat_backup_${TIMESTAMP}.dump
```

*En Windows PowerShell:*
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force -Path ".\backups"
docker compose exec -T postgres pg_dump -U sunat_user -Fc sunat_consultas_db | Set-Content -Encoding Byte -Path ".\backups\sunat_backup_$timestamp.dump"
```

### 2.2 Respaldo en Texto Plano SQL (Alternativa)

```bash
docker compose exec -T postgres pg_dump -U sunat_user --clean --if-exists sunat_consultas_db > ./backups/sunat_backup_${TIMESTAMP}.sql
```

---

## 3. Listado y Verificación del Archivo de Respaldo

Para verificar la integridad y contenido de un archivo `.dump` sin restaurarlo:

```bash
# Listar archivos generados con tamaño y fecha
ls -lh ./backups/

# Inspeccionar el contenido del backup binario mediante pg_restore
docker compose exec -T postgres pg_restore --list < ./backups/sunat_backup_${TIMESTAMP}.dump
```

---

## 4. Procedimiento Seguro de Restauración (`Restore`)

> **ATENCIÓN CRÍTICA:** Cree siempre una base de datos de prueba para validar que el respaldo es funcional.

### Paso 1: Crear base de datos de prueba en PostgreSQL

```bash
docker compose exec -T postgres psql -U sunat_user -c "CREATE DATABASE sunat_db_test_restore;"
```

### Paso 2: Restaurar el archivo en la base de datos de prueba

Para archivos en formato binario custom (`.dump`):
```bash
docker compose exec -T postgres pg_restore -U sunat_user -d sunat_db_test_restore --clean --if-exists < ./backups/sunat_backup_${TIMESTAMP}.dump
```

Para archivos en formato SQL plano (`.sql`):
```bash
docker compose exec -T postgres psql -U sunat_user -d sunat_db_test_restore < ./backups/sunat_backup_${TIMESTAMP}.sql
```

### Paso 3: Validar la integridad de los datos restaurados

Verifique el conteo de tablas y registros en la base de prueba:

```bash
# Verificar conteo de tablas críticas
docker compose exec -T postgres psql -U sunat_user -d sunat_db_test_restore -c "SELECT count(*) FROM empresas;"
docker compose exec -T postgres psql -U sunat_user -d sunat_db_test_restore -c "SELECT count(*) FROM usuarios;"
docker compose exec -T postgres psql -U sunat_user -d sunat_db_test_restore -c "SELECT count(*) FROM procesos_masivos;"
docker compose exec -T postgres psql -U sunat_user -d sunat_db_test_restore -c "SELECT count(*) FROM auditoria_eventos;"
```

### Paso 4: Eliminar la base de datos de prueba tras la validación

Una vez validado el respaldo:
```bash
docker compose exec -T postgres psql -U sunat_user -c "DROP DATABASE sunat_db_test_restore;"
```

---

## 5. Restauración en Caso de Desastre Real (Disaster Recovery)

Solo si la base de datos principal se encuentra corrupta o en un nuevo servidor:

1. Levantar contenedor de base de datos vacío:
   ```bash
   docker compose up -d postgres
   ```
2. Esperar a que el servicio esté `healthy`:
   ```bash
   docker compose ps
   ```
3. Restaurar sobre la base de producción:
   ```bash
   docker compose exec -T postgres pg_restore -U sunat_user -d sunat_consultas_db --clean --if-exists < ./backups/sunat_backup_VALIDADO.dump
   ```
4. Ejecutar migraciones Alembic para asegurar sincronización de head:
   ```bash
   docker compose exec backend alembic upgrade head
   ```
