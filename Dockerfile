# ---- Stage 1: Dependencies + Playwright ----
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Definir path fixo para browsers do Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Instalar Chromium no path fixo (sem --with-deps, pois deps já estão instaladas)
RUN python -m playwright install chromium

# ---- Stage 2: Runtime ----
FROM python:3.11-slim

WORKDIR /app

# System deps for Chromium at runtime
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

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# ✅ Copiar browsers do path fixo
COPY --from=builder /opt/playwright-browsers /opt/playwright-browsers

# ✅ Definir a mesma variável de ambiente no runtime
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Create non-root user
RUN useradd -m appuser \
    && chown -R appuser:appuser /app /opt/playwright-browsers

# Copy application
COPY --chown=appuser:appuser . .

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]