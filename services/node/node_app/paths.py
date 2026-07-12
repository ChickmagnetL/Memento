from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
SERVICES_DIR = NODE_DIR.parent
REPO_ROOT = SERVICES_DIR.parent
ASR_DIR = SERVICES_DIR / "asr"
EMBEDDING_DIR = SERVICES_DIR / "embedding"
BIN_DIR = SERVICES_DIR / ".bin"
PYTHON_DIR = SERVICES_DIR / ".python"
