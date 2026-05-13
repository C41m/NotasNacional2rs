# ---- Stage 1: Dependencies ----
FROM python:3.11-slim AS deps

WORKDIR /app

# Build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

WORKDIR /app

# Runtime dependencies for headless Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk-bridge2.0-0 \
    libgbm1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxkbcommon0 \
    libxshmfence1 \
    libasound2 \
    libatspi2.0-0 \
    libdrm2 \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libx11-xcb1 \
    libxtst6 \
    libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Install Playwright browsers (with bundled deps)
RUN python -m playwright install --with-deps chromium

# Copy application
COPY . .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]