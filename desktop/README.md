# Memento Desktop Shell

## Dev Mode Quick Start

1. Build backend: `./scripts/build-backend.sh`
   Or use venv uvicorn: `export MEMENTO_BACKEND_CMD="../backend/venv/bin/uvicorn main:app --port 8000"`
2. Start frontend: `cd frontend && npm run dev`
3. Start desktop: `cd desktop && npm start`

## Building Installers

Build a desktop installer for the current platform:

```bash
./scripts/build-desktop.sh
```

Installers are written to `desktop/dist/`.

### Prerequisites

- Python 3.10+
- Node 18+
- ffmpeg (available on PATH)
- Run `npm install` in both `desktop/` and `frontend/` before building

### Platform Notes

**No cross-compilation.** PyInstaller and electron-builder produce binaries only for the build platform:
- macOS → `Memento-*.dmg`
- Windows → `Memento-*.exe` (NSIS installer)
- Linux → `Memento-*.AppImage`

Build on each target platform to produce its installer.

### Code Signing

Code signing is **not configured** by default. For production distribution:

- **macOS:** Set `build.mac.identity` in `desktop/package.json` to your Apple Developer ID certificate, then notarize the DMG with `xcrun notarytool`.
- **Windows:** Set `build.win.certificateFile` and `build.win.certificatePassword` (or use `CSC_LINK` / `CSC_KEY_PASSWORD` environment variables).
- **Linux:** AppImage does not require signing for distribution.

Without signing, users must bypass platform security warnings (right-click → Open on macOS, "More info" → "Run anyway" on Windows).
