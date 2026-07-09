"""Test fixtures for embedding service tests."""
import sys
from pathlib import Path

EMBEDDING_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(EMBEDDING_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(EMBEDDING_SERVICE_DIR))