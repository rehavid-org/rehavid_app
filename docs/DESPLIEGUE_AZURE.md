# REHAVID Operaciones - Despliegue en Azure (VM unica)

> **Nota**: este documento reemplaza el plan anterior de App Service. La topologia
> elegida es una unica VM Azure con Docker Compose (Django + Celery + Postgres +
> Redis + Caddy). Mas simple, menor costo, un solo punto de operacion.

## Topologia

| Componente | Contenedor / servicio | Funcion |
|---|---|---|
| Reverse proxy + TLS | `caddy:2.8-alpine` | Auto-TLS Let's Encrypt, puertos 80/443 |
| App Django | `compose/production/django/Dockerfile` | Gunicorn :5000, whitenoise static |
| Celery worker | misma imagen | `/start-celeryworker` |
| Celery beat | misma imagen | `/start-celerybeat` |
| PostgreSQL 16 | `postgres:16-alpine` | BD interna (sin puerto publico) |
| Redis 7 | `redis:7-alpine` | Broker + cache (sin puerto publico) |
| Backups | `backup.sh` (cron host) | Local + Azure Blob (managed identity) |

Todo corre en **una sola VM** (`rehavid-vm`, Ubuntu 24.04, Standard_B2ms).

## Quick path

```bash
# 1. Provisionar recursos Azure (ver seccion abajo)
az group create -n rehavid-rg -l eastus2
# ... (ver "Provision con az CLI")

# 2. En la VM: instalar Docker, clonar repo, configurar .envs
ssh rehavid@<vm-ip>
bash scripts/deploy-vm.sh

# 3. Apuntar DNS y verificar
curl http://<vm-ip>/health/           # pre-DNS (HTTP plano)
# Tras propagar DNS:
curl https://operaciones.rehavid.com.co/health/
```

## Provision con az CLI

```bash
az login
az account set --subscription "<subscription-id>"

RG=rehavid-rg
LOC=eastus2

# Resource Group
az group create --name $RG --location $LOC

# VM (Ubuntu 24.04 LTS, Standard_B2ms)
az vm create \
  --resource-group $RG \
  --name rehavid-vm \
  --image Canonical:ubuntu-24_04-lts:server:latest \
  --size Standard_B2ms \
  --admin-username rehavid \
  --ssh-key-values @~/.ssh/id_rsa.pub \
  --public-ip-sku Standard \
  --assign-identity [system]

# NSG: solo SSH, HTTP, HTTPS
az vm open-port -g $RG -n rehavid-vm --port 22 --priority 100
az vm open-port -g $RG -n rehavid-vm --port 80 --priority 200
az vm open-port -g $RG -n rehavid-vm --port 443 --priority 300

# Storage Account para backups
az storage account create \
  -g $RG -n rehavidstorage --sku Standard_LRS

az storage container create \
  --account-name rehavidstorage \
  -n rehavid-pg-backups \
  --auth-mode login

# Dar permiso a la identidad de la VM sobre el container
VM_PRINCIPAL=$(az vm show -g $RG -n rehavid-vm --query identity.principalId -otsv)
az role assignment create \
  --assignee $VM_PRINCIPAL \
  --role "Storage Blob Data Contributor" \
  --scope $(az storage account show -g $RG -n rehavidstorage --query id -otsv)
```

## Setup de la VM

```bash
ssh rehavid@<vm-ip>

# Docker engine + compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# (re-login para que el grupo docker tome efecto)

# Clonar repo
sudo mkdir -p /opt/rehavid/app
sudo chown $USER:$USER /opt/rehavid/app
git clone https://github.com/rehavid-org/rehavid_app.git /opt/rehavid/app

# Configurar envs de produccion
mkdir -p /opt/rehavid/app/.envs/.production
cp /opt/rehavid/app/.envs/.production_example/.django /opt/rehavid/app/.envs/.production/.django
cp /opt/rehavid/app/.envs/.production_example/.postgres /opt/rehavid/app/.envs/.production/.postgres
# EDITAR ambos archivos con valores reales (secret, passwords, mailgun, etc.)

# Crear directorio de backups
sudo mkdir -p /opt/rehavid/backups
sudo chown $USER:$USER /opt/rehavid/backups

# Desplegar
bash /opt/rehavid/app/scripts/deploy-vm.sh
```

## Backups

El script `compose/vm/postgres/backup.sh` corre en el **host** (no en contenedor):

- `pg_dump` via `docker compose exec` + gzip a `/opt/rehavid/backups/`
- Retencion local: 7 dias (configurable via `RETENTION_DAYS`)
- Off-VM: sube a Azure Blob via managed identity (si `AZURE_STORAGE_ACCOUNT` esta set)
- Un fallo de Blob nunca rompe el backup local

### Cron

```bash
crontab -e
# Agregar:
15 3 * * *  /opt/rehavid/app/compose/vm/postgres/backup.sh >> /var/log/rehavid-backup.log 2>&1
```

### Restore

```bash
# Desde un dump local:
docker compose -f docker-compose.vm.yml exec -T postgres \
  pg_restore -U cloudcoder -d rehavid_app --clean --if-exists \
  < /opt/rehavid/backups/rehavid-XXXXXXXXTXXXXXXZ.dump.gz
```

## DNS + SSL

1. Crear registro DNS: `operaciones.rehavid.com.co` → CNAME o A → IP publica de la VM.
2. Caddy detecta el dominio y emite el certificado Let's Encrypt automaticamente.
3. **Antes de que el DNS propague**, se puede verificar via `http://<vm-ip>/health/`.
4. Una vez el DNS resuelve, `https://operaciones.rehavid.com.co` funciona con TLS.

## SSO Microsoft Entra ID

1. App registration `rehavid-sso` (single tenant).
2. Redirect URI: `https://operaciones.rehavid.com.co/accounts/microsoft/login/callback/`.
3. Setear en `.envs/.production/.django`: `AZURE_SSO_CLIENT_ID`, `AZURE_SSO_CLIENT_SECRET`, `AZURE_SSO_TENANT_ID`.
4. Reiniciar: `docker compose -f docker-compose.vm.yml restart django`.

## Azure ML (predictivo)

Cuando el endpoint este desplegado, setear en `.django`:
`AZURE_ML_ENABLED=True`, `AZURE_ML_ENDPOINT`, `AZURE_ML_KEY`, `AZURE_ML_DEPLOYMENT`.
El servicio Django cae automaticamente al mock heuristico si el endpoint falla.

## Rollback / Restore

```bash
# Listar backups disponibles:
ls -lh /opt/rehavid/backups/

# Restore desde backup:
docker compose -f docker-compose.vm.yml exec -T postgres \
  pg_restore -U cloudcoder -d rehavid_app --clean --if-exists \
  < /opt/rehavid/backups/rehavid-20260716T031500Z.dump.gz

# Reiniciar app:
docker compose -f docker-compose.vm.yml restart django celeryworker celerybeat
```

## Costo estimado

| Recurso | SKU | Costo mensual aprox. |
|---|---|---|
| VM Standard_B2ms | 2 vCPU, 8 GB RAM | ~$60 USD |
| Disco OS 64 GB | Premium SSD | ~$8 USD |
| Storage Account | Standard LRS, <10 GB backups | ~$1 USD |
| **Total** | | **~$70 USD/mes** |

Significativamente menor que App Service + PG Flexible + Redis + Blob por separado.

## Staging local de la imagen

```bash
cp .envs/.production_example/.django .envs/.production/.django   # y completar
cp .envs/.production_example/.postgres .envs/.production/.postgres
docker compose -f docker-compose.vm.yml up --build
curl http://localhost/health/   # via Caddy (o http://localhost:5000/health/ sin Caddy)
```
