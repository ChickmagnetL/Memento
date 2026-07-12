import importlib.util
import sys
from pathlib import Path

NODE_APP = Path(__file__).resolve().parents[2] / "services" / "node" / "node_app"


def _load(name: str, file: str):
    path = NODE_APP / file
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_ports_are_16888_and_16889():
    ports = _load("node_app_ports", "ports.py")
    assert ports.ASR_PORT == 16888
    assert ports.EMBEDDING_PORT == 16889
