# ============================================================
# REHAVID Operaciones · imagen de producción (multi-stage)
# builder: uv instala deps al venv · runtime: slim, no-root
# ============================================================

# ── Stage 1 · builder ───────────────────────────────────────
FROM ghcr.io/astral-sh/uv:0.11.28-python3.14-trixie-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_COMPILE_BYTECODE=0 \
  UV_PYTHON_DOWNLOADS=never \
  UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app

RUN apt-get update && apt-get install --no-install-recommends -y \
  libpq-dev \
  build-essential \
  && rm -rf /var/lib/apt/lists/*

# Solo dependencias de producción (sin grupo dev), cacheado por lockfile
COPY pyproject.toml uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-install-project --no-dev

# ── Stage 2 · runtime ───────────────────────────────────────
FROM python:3.14-slim-trixie AS runtime

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/venv/bin:$PATH" \
  DJANGO_SETTINGS_MODULE=config.settings.production

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install --no-install-recommends -y \
  # runtime de psycopg (c-extension)
  libpq5 \
  && rm -rf /var/lib/apt/lists/* \
  # usuario sin privilegios
  && addgroup --system django \
  && adduser --system --ingroup django django

COPY --from=builder /venv /venv

COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
COPY --chown=django:django ./compose/production/django/start /start
COPY --chown=django:django ./compose/production/django/celery/worker/start /start-celeryworker
COPY --chown=django:django ./compose/production/django/celery/beat/start /start-celerybeat
RUN sed -i 's/\r$//g' /entrypoint /start /start-celeryworker /start-celerybeat \
  && chmod +x /entrypoint /start /start-celeryworker /start-celerybeat

COPY --chown=django:django . ${APP_HOME}

RUN mkdir -p ${APP_HOME}/staticfiles && chown django:django ${APP_HOME}/staticfiles ${APP_HOME}

USER django

# Probe de contenedor: el endpoint /health/ verifica la BD
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
