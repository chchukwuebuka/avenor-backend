# Multi-stage production Dockerfile for AVENOR Django 5.1 + Daphne ASGI + Celery
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /build/requirements/
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements/base.txt

# --- Final Production Stage ---
FROM python:3.13-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-traditional \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 1000 avenor && \
    useradd -u 1000 -g avenor -s /bin/bash -m avenor

COPY --from=builder /build/wheels /wheels
COPY requirements/base.txt /app/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /app/requirements.txt && \
    rm -rf /wheels /app/requirements.txt

# Copy backend codebase
COPY --chown=avenor:avenor . /app

# Ensure entrypoint is executable
RUN chmod +x /app/docker-entrypoint.sh && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R avenor:avenor /app/staticfiles /app/media

USER avenor

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/healthz/ || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
