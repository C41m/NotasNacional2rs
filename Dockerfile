FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright Chromium
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

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Definir path fixo ANTES de instalar os browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Instalar Chromium no path fixo (sem --with-deps)
RUN playwright install chromium

# Copy application
COPY . .

# ✅ Garantir que appuser tenha acesso ao diretório dos browsers
RUN useradd -m appuser \
    && chown -R appuser:appuser /app /ms-playwright

USER appuser

# ✅ Manter a mesma env var no runtime
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]