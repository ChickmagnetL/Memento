#!/usr/bin/env bash
# Build installers for the current platform.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$(uname -s)" in
  Darwin) TARGET="--mac" ;;
  MINGW*|MSYS*|CYGWIN*) TARGET="--win" ;;
  *) echo "ERROR: Desktop installers are supported only on macOS and Windows"; exit 1 ;;
esac

[ -d "$ROOT/desktop/node_modules" ] || { echo "ERROR: Run 'npm install' in desktop/ first"; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || { echo "ERROR: Run 'npm install' in frontend/ first"; exit 1; }

echo "==> Backend (PyInstaller)"
"$ROOT/scripts/build-backend.sh"

echo "==> Douyin fetcher (PyInstaller)"
"$ROOT/scripts/build-douyin-fetcher.sh"

echo "==> Frontend (Next standalone)"
cd "$ROOT/frontend"
npm run build
rm -rf .next/standalone/.next/static .next/standalone/public
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public

echo "==> Staging resources"
cd "$ROOT"
node scripts/stage-desktop-resources.mjs
node scripts/verify-desktop-resources.mjs

echo "==> electron-builder"
cd "$ROOT/desktop"
npm run dist -- "$TARGET"

echo "Installers in desktop/dist/"
