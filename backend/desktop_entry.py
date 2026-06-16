"""PyInstaller entrypoint for the packaged desktop backend.

Binds to localhost only (the Electron shell is the sole client) and
disables reload (no source tree in the bundle).
"""

import uvicorn

from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
