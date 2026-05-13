#!/bin/bash
set -e

# Install Playwright browsers at runtime (avoids build-time timeout/memory limits)
echo "🔧 Installing Playwright Chromium (runtime)..."
python -m playwright install --with-deps chromium 2>&1 || {
    echo "⚠️ Playwright install failed, but continuing anyway..."
}

# Run the CMD from Dockerfile
echo "🚀 Starting uvicorn..."
exec "$@"