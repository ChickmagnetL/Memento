#!/usr/bin/env bash
# Package the FastAPI backend with PyInstaller (onedir).
set -euo pipefail

cd "$(dirname "$0")/../backend"

./venv/bin/pip show pyinstaller > /dev/null 2>&1 || ./venv/bin/pip install pyinstaller

./venv/bin/pyinstaller --noconfirm --onedir --name memento-backend \
  --paths . \
  --add-data "storage/schema.sql:storage" \
  --add-data "config/default.yaml:config" \
  --collect-data jieba \
  --collect-submodules qdrant_client \
  --collect-submodules pydantic_ai \
  --collect-submodules yt_dlp \
  --hidden-import aiosqlite \
  --copy-metadata genai-prices \
  --copy-metadata pydantic-ai-slim \
  --copy-metadata openai \
  --copy-metadata pydantic \
  --copy-metadata pydantic-settings \
  --copy-metadata fastapi \
  --copy-metadata uvicorn \
  --copy-metadata starlette \
  desktop_entry.py

echo "Built: backend/dist/memento-backend/"
"$(dirname "$0")/fix-pyi-symlinks.sh" dist/memento-backend
