#!/usr/bin/env bash
# ===========================================================================
# Despliegue idempotente en la VM Azure.
# Ejecutar vía SSH tras instalar Docker y clonar/copiar el repo.
# ===========================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/rehavid/app}"
COMPOSE_FILE="docker-compose.vm.yml"
HEALTH_TIMEOUT=120

log() { echo "[$(date -u +%FT%TZ)] $*"; }

cd "${APP_DIR}"

log "Building and starting services..."
docker compose -f "${COMPOSE_FILE}" up -d --build

log "Waiting for django health (up to ${HEALTH_TIMEOUT}s)..."
ELAPSED=0
while [[ ${ELAPSED} -lt ${HEALTH_TIMEOUT} ]]; do
  if docker compose -f "${COMPOSE_FILE}" exec -T django \
    python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health/', timeout=4).status == 200 else 1)" 2>/dev/null; then
    log "django is healthy."
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

if [[ ${ELAPSED} -ge ${HEALTH_TIMEOUT} ]]; then
  log "WARNING: django did not become healthy within ${HEALTH_TIMEOUT}s."
  docker compose -f "${COMPOSE_FILE}" logs --tail=30 django
  exit 1
fi

log "Running migrations (belt-and-suspenders)..."
docker compose -f "${COMPOSE_FILE}" exec -T django python manage.py migrate --noinput

log "Running collectstatic..."
docker compose -f "${COMPOSE_FILE}" exec -T django python manage.py collectstatic --noinput

# python manage.py seed_demo  # solo si se quiere cargar datos demo iniciales

log "=== Deploy complete ==="
log ""
log "Health check:  curl http://<vm-ip>/health/"
log "DNS:           Apuntar operaciones.rehavid.com.co -> <vm-ip>"
log "               Caddy emitira el certificado Let's Encrypt cuando el DNS resuelva."
log ""
docker compose -f "${COMPOSE_FILE}" ps
