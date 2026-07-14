# REHAVID Operaciones · Despliegue en Azure (app Django)

Adaptación de `../rehavid/docs/instrucciones_azure_ingeniero.md` a la arquitectura
Django + PostgreSQL (sin Cosmos DB ni Static Web App: **un solo servicio Django**
sirve HTML y API, más contenedores de Celery).

## Topología

| Recurso | Nombre sugerido | Para qué |
|---|---|---|
| Resource Group | `rehavid-rg` | agrupa todo (region `eastus2`) |
| Azure Container Registry | `rehavidacr` | imágenes de producción |
| App Service Plan (Linux) | `rehavid-plan` | B1/B2 para arrancar |
| App Service (container) | `rehavid-operaciones` | django (gunicorn :5000) |
| App Service (container) | `rehavid-celery-worker` | celery worker (`/start-celeryworker`, sin puerto público) |
| App Service (container) | `rehavid-celery-beat` | celery beat (`/start-celerybeat`, 1 instancia SIEMPRE) |
| PostgreSQL Flexible Server | `rehavid-pg` | BD (B1ms para arrancar, backups automáticos) |
| Azure Cache for Redis | `rehavid-redis` | broker Celery + cache |
| Key Vault | `rehavid-kv` | SECRET_KEY, DB url, credenciales Entra/ML/Mailgun |
| Storage Account (Blob) | `rehavidstorage` | contenedor `rehavid` con `static/` y `media/` |
| Application Insights | `rehavid-appinsights` | telemetría (opcional, ver abajo) |
| App registration Entra ID | `rehavid-sso` | SSO empleados `@rehavid.com.co` |
| Dominio + SSL | `operaciones.rehavid.com.co` | CNAME al App Service + managed certificate |

## Pasos (az CLI)

```bash
az login && az account set --subscription "<subscription-id>"
RG=rehavid-rg; LOC=eastus2

az group create --name $RG --location $LOC

# 1 · Registry
az acr create -g $RG -n rehavidacr --sku Basic --admin-enabled true

# 2 · PostgreSQL Flexible Server (la app usa DATABASE_URL)
az postgres flexible-server create -g $RG -n rehavid-pg \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 \
  --version 16 --database-name rehavid_app \
  --admin-user rehavid --admin-password "<password-fuerte>"
# Permitir acceso desde servicios de Azure:
az postgres flexible-server firewall-rule create -g $RG -n rehavid-pg \
  -r allow-azure --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# 3 · Redis
az redis create -g $RG -n rehavid-redis --location $LOC --sku Basic --vm-size c0

# 4 · Blob (estáticos + media). El container debe llamarse igual que
#     DJANGO_AZURE_CONTAINER_NAME (default: rehavid)
az storage account create -g $RG -n rehavidstorage --sku Standard_LRS
az storage container create --account-name rehavidstorage -n rehavid --public-access blob

# 5 · Key Vault · TODOS los secretos viven aquí
az keyvault create -g $RG -n rehavid-kv
az keyvault secret set --vault-name rehavid-kv --name django-secret-key \
  --value "$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
az keyvault secret set --vault-name rehavid-kv --name database-url \
  --value "postgres://rehavid:<password>@rehavid-pg.postgres.database.azure.com:5432/rehavid_app?sslmode=require"
# + azure-account-key, mailgun-api-key, entra-client-secret, azure-ml-key…

# 6 · App Service Plan + Web Apps de contenedor
az appservice plan create -g $RG -n rehavid-plan --is-linux --sku B2
for APP in rehavid-operaciones rehavid-celery-worker rehavid-celery-beat; do
  az webapp create -g $RG -p rehavid-plan -n $APP \
    --deployment-container-image-name rehavidacr.azurecr.io/rehavid-operaciones:latest
done
az webapp config set -g $RG -n rehavid-celery-worker --startup-file /start-celeryworker
az webapp config set -g $RG -n rehavid-celery-beat  --startup-file /start-celerybeat
az webapp config appsettings set -g $RG -n rehavid-operaciones --settings \
  WEBSITES_PORT=5000 \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  DJANGO_ALLOWED_HOSTS=operaciones.rehavid.com.co \
  DJANGO_SECRET_KEY="@Microsoft.KeyVault(VaultName=rehavid-kv;SecretName=django-secret-key)" \
  DATABASE_URL="@Microsoft.KeyVault(VaultName=rehavid-kv;SecretName=database-url)" \
  REDIS_URL="rediss://:<redis-key>@rehavid-redis.redis.cache.windows.net:6380/0" \
  DJANGO_AZURE_ACCOUNT_NAME=rehavidstorage \
  DJANGO_AZURE_CONTAINER_NAME=rehavid \
  DJANGO_AZURE_ACCOUNT_KEY="@Microsoft.KeyVault(VaultName=rehavid-kv;SecretName=azure-account-key)" \
  DJANGO_ADMIN_URL="admin-rehavid/"
# (repetir appsettings en worker y beat · no necesitan WEBSITES_PORT)
# Para que los App Service lean Key Vault: habilitar identidad administrada y
# darle 'get' sobre secretos:
az webapp identity assign -g $RG -n rehavid-operaciones
az keyvault set-policy -n rehavid-kv --object-id <principalId> --secret-permissions get

# 7 · Health probe
az webapp config set -g $RG -n rehavid-operaciones --generic-configurations '{"healthCheckPath": "/health/"}'

# 8 · Dominio + SSL
az webapp config hostname add -g $RG --webapp-name rehavid-operaciones \
  --hostname operaciones.rehavid.com.co
az webapp config ssl create -g $RG -n rehavid-operaciones --hostname operaciones.rehavid.com.co
```

## SSO Microsoft Entra ID

1. App registration `rehavid-sso` (single tenant).
2. Redirect URI: `https://operaciones.rehavid.com.co/accounts/microsoft/login/callback/`.
3. Crear client secret → Key Vault → app settings `AZURE_SSO_CLIENT_ID`,
   `AZURE_SSO_CLIENT_SECRET`, `AZURE_SSO_TENANT_ID` (la app ya trae el provider
   configurado con auto-vinculación por email verificado).

## Application Insights (opcional)

```bash
az monitor app-insights component create -g $RG --app rehavid-appinsights --location $LOC
```
Setear `APPLICATIONINSIGHTS_CONNECTION_STRING` como app setting **y** agregar
`azure-monitor-opentelemetry` a las dependencias de la imagen. Si la variable
está y el paquete no, la app arranca igual (solo deja un warning).

## Azure ML (predictivo)

Los scripts de entrenamiento viven en el repo original (`../rehavid/ml/`) y son
offline. Cuando el endpoint esté desplegado: setear `AZURE_ML_ENABLED=True`,
`AZURE_ML_ENDPOINT`, `AZURE_ML_KEY`, `AZURE_ML_DEPLOYMENT`. El servicio Django
cae automáticamente al mock si el endpoint falla.

## CI/CD

`.github/workflows/deploy.yml`: al taggear `v*` (o correr manualmente) →
tests contra Postgres 16 → build de `compose/production/django/Dockerfile` →
push a ACR (`:sha` y `:latest`) → deploy a los App Service → espera el 200 de
`/health/`. Migraciones y `collectstatic` (a Blob, con collectfasta) corren en
el arranque del contenedor (`/start`).

Secrets de GitHub requeridos: `AZURE_CREDENTIALS`, `ACR_LOGIN_SERVER`,
`ACR_USERNAME`, `ACR_PASSWORD`, `AZURE_WEBAPP_NAME` (+ `_WORKER`/`_BEAT`).

## Staging local de la imagen

```bash
cp .envs/.production_example/.django .envs/.production/.django   # y completar
cp .envs/.production_example/.postgres .envs/.production/.postgres
docker compose -f docker-compose.production.yml up --build
curl http://localhost:5000/health/   # → {"status": "ok"}
```
