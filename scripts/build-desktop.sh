#!/usr/bin/env bash
# Build installers for the current platform.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$ROOT/desktop/node_modules" ] || { echo "ERROR: Run 'npm install' in desktop/ first"; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || { echo "ERROR: Run 'npm install' in frontend/ first"; exit 1; }

echo "==> Backend (PyInstaller)"
"$ROOT/scripts/build-backend.sh"

echo "==> Frontend (Next standalone)"
cd "$ROOT/frontend"
npm run build
rm -rf .next/standalone/.next/static .next/standalone/public
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public

echo "==> Staging resources"
cd "$ROOT/desktop"
rm -rf resources
mkdir -p resources
cp -r "$ROOT/backend/dist/memento-backend" resources/backend
cp -r "$ROOT/frontend/.next/standalone" resources/frontend
# electron-builder strips node_modules from extraResources; ship deps as node_deps
# and resolve them at runtime via NODE_PATH (see desktop/main.js startFrontend).
mv resources/frontend/node_modules resources/frontend/node_deps

echo "==> electron-builder"
npm run dist

echo "Installers in desktop/dist/"