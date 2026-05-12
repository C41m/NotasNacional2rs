# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build-time system dependencies (only what's needed to compile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

WORKDIR /app

# Only runtime dependencies for headless Chromium — NO GUI libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxshmfence1 \
    libx11-xcb1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN python -m playwright install chromium

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy application (uses .dockerignore)
COPY . .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]