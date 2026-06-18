"""Test-local import setup for the ASR service modules."""

import sys
from pathlib import Path


ASR_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(ASR_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(ASR_SERVICE_DIR))
