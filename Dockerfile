# MOCA backend image — Flask + APScheduler + Playwright scrapers.
#
# Multi-stage:
#   - builder:  install Python deps + Playwright Chromium browser
#   - runtime:  copy app, expose 5000, run gunicorn
#
# Build:
#   docker build -t moca-backend .
#
# Run (without docker-compose):
#   docker run --rm -p 5000:5000 \
#     -v "$(pwd)/data:/app/data" \
#     -v "$(pwd)/config.json:/app/config.json:ro" \
#     -v "$(pwd)/logs:/app/logs" \
#     moca-backend

# ─── builder stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# System packages required to build psycopg2 and to run Playwright Chromium.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        # Playwright Chromium runtime deps (subset Playwright installs):
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (best layer cache hit) + Chromium for Playwright.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

# ─── runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Non-root user — defense in depth. UID 1000 typical on Linux desktops.
RUN groupadd --gid 1000 moca && useradd --uid 1000 --gid moca --shell /bin/bash --create-home moca

# Same runtime libs as builder needs (Playwright still uses them).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages + Playwright browser bundle from builder.
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/ms-playwright /home/moca/.cache/ms-playwright

WORKDIR /app

# Application code. .dockerignore excludes node_modules, dist, debug_archive,
# logs, .git, etc. — keeps the image lean.
COPY --chown=moca:moca . /app

# Persistent volumes — mount these from the host so data survives image rebuilds.
RUN mkdir -p /app/data /app/logs && chown -R moca:moca /app/data /app/logs /home/moca/.cache
VOLUME ["/app/data", "/app/logs"]

USER moca

EXPOSE 5000

# Healthcheck hits the public root (which doesn't require auth) every 30s.
# A failed healthcheck after 3 retries triggers docker-compose restart.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/healthz || exit 1

# Run via gunicorn for production: 2 workers, gthread for APScheduler-friendly
# concurrency, 60s graceful shutdown so scrapes don't get interrupted mid-flight.
# NOTE: APScheduler is in-process — multi-worker would run jobs N times.
# We ship 1 worker until we add an external job store.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", \
     "--worker-class", "gthread", "--graceful-timeout", "60", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
