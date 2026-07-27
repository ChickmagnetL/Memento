"""Benchmark environment bootstrap.

Import this module FIRST (before any memento imports). It sets os.environ for
isolated bench data dir, local embedding, chat credentials, and bilibili cookie
loaded from the user's source memento.db. Never prints secrets.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

# Absolute paths used by Phase 0 benchmarks.
_MEMENTO_PROJECT_ROOT = "/Users/leo/development/memento"
_BENCH_DATA_DIR = (
    "/Users/leo/development/memento/.claude/worktrees/rag-benchmarks/bench_data"
)
_DEFAULT_SOURCE_DB = "/Users/leo/Library/Application Support/memento-desktop/data/memento.db"


def _load_chat_config(db_path: str) -> dict:
    """Load active chat preset config from source memento.db."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT mp.config FROM active_preset ap "
            "JOIN model_presets mp ON ap.preset_id=mp.id "
            "WHERE ap.model_name='chat'"
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return {}
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_bilibili_cookie(db_path: str) -> str:
    """Load bilibili_cookie from app_config.video_processing JSON."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM app_config WHERE key='video_processing'"
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return ""
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    cookie = data.get("bilibili_cookie") or ""
    return cookie if isinstance(cookie, str) else ""


def _apply_env() -> None:
    os.environ["MEMENTO_PROJECT_ROOT"] = _MEMENTO_PROJECT_ROOT
    os.environ["STORAGE__DATA_DIR"] = _BENCH_DATA_DIR
    os.environ["MODELS__EMBEDDING__ENDPOINT"] = "http://localhost:8003/v1"
    os.environ["MODELS__EMBEDDING__MODEL"] = "Qwen/Qwen3-Embedding-0.6B"
    os.environ["MODELS__EMBEDDING__API_KEY"] = "local"
    os.environ["RAG__VECTOR_SIZE"] = "1024"

    source_db = os.environ.get("SOURCE_MEMENTO_DB") or _DEFAULT_SOURCE_DB
    chat = _load_chat_config(source_db)
    if chat.get("endpoint") and "MODELS__CHAT__ENDPOINT" not in os.environ:
        os.environ["MODELS__CHAT__ENDPOINT"] = str(chat["endpoint"])
    if chat.get("model") and "MODELS__CHAT__MODEL" not in os.environ:
        os.environ["MODELS__CHAT__MODEL"] = str(chat["model"])
    if chat.get("api_key") and "MODELS__CHAT__API_KEY" not in os.environ:
        os.environ["MODELS__CHAT__API_KEY"] = str(chat["api_key"])

    cookie = _load_bilibili_cookie(source_db)
    if cookie:
        os.environ["VIDEO_PROCESSING__BILIBILI_COOKIE"] = cookie

    Path(_BENCH_DATA_DIR).mkdir(parents=True, exist_ok=True)

    model = os.environ.get("MODELS__CHAT__MODEL") or "(unset)"
    endpoint = os.environ.get("MODELS__CHAT__ENDPOINT") or "(unset)"
    cookie_set = bool(os.environ.get("VIDEO_PROCESSING__BILIBILI_COOKIE"))
    print(
        f"bench_env loaded: chat model={model}, endpoint={endpoint}, "
        f"cookie_set={cookie_set}"
    )


_apply_env()
