"""Start Memento backend for benchmarks on 127.0.0.1:8010."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "backend"))

import bench_env  # noqa: F401  # sets env before other memento imports
import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8010, reload=False)
