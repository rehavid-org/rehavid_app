#!/usr/bin/env bash
# ===========================================================================
# Backup diario de PostgreSQL (VM host, no contenedor).
#
# Cron (editar con `crontab -e`):
#   15 3 * * *  /opt/rehavid/app/compose/vm/postgres/backup.sh >> /var/log/rehavid-backup.log 2>&1
# ===========================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/rehavid/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vm.yml}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/rehavid/app}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

AZURE_STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-}"
AZURE_STORAGE_BACKUP_CONTAINER="${AZURE_STORAGE_BACKUP_CONTAINER:-rehavid-pg-backups}"

POSTGRES_USER="${POSTGRES_USER:-cloudcoder}"
POSTGRES_DB="${POSTGRES_DB:-rehavid_app}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILENAME="rehavid-${TIMESTAMP}.dump.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

log "=== Backup start: ${FILENAME} ==="

mkdir -p "${BACKUP_DIR}"

docker compose -f "${COMPOSE_DIR}/${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --format=custom \
  | gzip > "${FILEPATH}"

log "Local backup written: ${FILEPATH} ($(du -h "${FILEPATH}" | cut -f1))"

# Retención local
find "${BACKUP_DIR}" -name 'rehavid-*.dump.gz' -mtime +"${RETENTION_DAYS}" -delete -print \
  | while read -r f; do log "Deleted old backup: ${f}"; done

# Off-VM a Azure Blob (identidad administrada de la VM)
if [[ -n "${AZURE_STORAGE_ACCOUNT}" ]]; then
  log "Uploading to Azure Blob: ${AZURE_STORAGE_ACCOUNT}/${AZURE_STORAGE_BACKUP_CONTAINER}/${FILENAME}"
  if ! az login --identity --output none 2>/dev/null; then
    log "WARNING: az login --identity failed; skipping Blob upload"
  else
    if az storage blob upload \
      --account-name "${AZURE_STORAGE_ACCOUNT}" \
      --container-name "${AZURE_STORAGE_BACKUP_CONTAINER}" \
      --name "${FILENAME}" \
      --file "${FILEPATH}" \
      --auth-mode login \
      --overwrite \
      --output none 2>/dev/null; then
      log "Blob upload complete"
    else
      log "WARNING: Blob upload failed; local backup is still safe at ${FILEPATH}"
    fi
  fi
else
  log "AZURE_STORAGE_ACCOUNT not set; skipping off-VM backup"
fi

log "=== Backup finish ==="
