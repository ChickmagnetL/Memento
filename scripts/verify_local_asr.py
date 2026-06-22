#!/usr/bin/env python3
"""v0.2-4c 本地 ASR 真实下载/转录验证 runbook 脚本 (manual, NOT in pytest).

对 6 个本地 ASR 模型 (SenseVoice Small + 5 Moonshine variants) 逐个:
  1. 真实下载 (未缓存时; venv 已存在, 直接调 download_model 跳过 pip 循环)
  2. 缓存检测 (manager.get_status 报 installed + cache_path 且路径真实存在)
  3. 运行时分流 + 转录 (POST /v1/audio/transcriptions, 比对关键词)
  4. SenseVoice 额外: 检查 services/asr/model_cache/ 是否在转录后被新建
     (FunAsrTranscriber cache_dir="model_cache" 与 deploy 下载位置不一致的信号)

前置 (由调用方/子代理准备):
  - ASR server 已起:
      cd services/asr && .venv/bin/uvicorn server:app --host 127.0.0.1 --port 8765
  - 本脚本在 backend venv 跑:
      cd backend && venv/bin/python ../scripts/verify_local_asr.py

输出: 每模型 pass/fail + 详情, 打印 + 写 ${ASR_AUDIO_DIR:-/tmp/memento_asr_verify}/results.json
退出码: 0=全过, 1=有失败
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "services" / "asr"))

from config.settings import get_settings  # noqa: E402
from core.asr_model_manager import AsrModelManager  # noqa: E402
from core.asr_model_registry import list_local_asr_models  # noqa: E402
import deploy  # noqa: E402  (services/asr/deploy.py, stdlib-only)

SERVER_URL = os.environ.get("ASR_SERVER_URL", "http://127.0.0.1:8765")
AUDIO_DIR = Path(os.environ.get("ASR_AUDIO_DIR", "/tmp/memento_asr_verify"))
RESULTS_PATH = AUDIO_DIR / "results.json"

EN_TEXT = "The quick brown fox jumps over the lazy dog. Knowledge is power."
EN_KEYWORDS = ["fox", "lazy", "knowledge"]  # case-insensitive substring
ZH_TEXT = "知识就是力量，学习改变命运。"
ZH_KEYWORDS = ["知识", "力量", "学习"]
ZH_VOICE = "Tingting"  # zh_CN, available on macOS


# --- TTS audio -----------------------------------------------------------

def _tts(voice: str, text: str, wav: Path) -> None:
    aiff = wav.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff), "-ar", "16000", "-ac", "1", str(wav)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    aiff.unlink(missing_ok=True)


def ensure_audio() -> tuple[Path, Path]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    en, zh = AUDIO_DIR / "en.wav", AUDIO_DIR / "zh.wav"
    if not en.exists():
        _tts("Samantha", EN_TEXT, en)
    if not zh.exists():
        _tts(ZH_VOICE, ZH_TEXT, zh)
    return en, zh


# --- server --------------------------------------------------------------

def wait_server(timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(SERVER_URL + "/health", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    raise RuntimeError(f"ASR server not healthy at {SERVER_URL}")


def transcribe(model_field: str, audio: Path) -> dict:
    """POST /v1/audio/transcriptions via curl (clean multipart upload)."""
    cmd = [
        "curl", "-s", "-X", "POST",
        f"{SERVER_URL}/v1/audio/transcriptions",
        "-F", f"file=@{audio}",
        "-F", f"model={model_field}",
        "-F", "response_format=verbose_json",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_error": out.stdout or out.stderr}


# --- manager -------------------------------------------------------------

def build_manager() -> AsrModelManager:
    data_dir = Path(get_settings().storage.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return AsrModelManager(service_dir=ROOT / "services" / "asr", data_dir=data_dir)


# --- main ----------------------------------------------------------------

def _text_of(resp: dict) -> str:
    if "_error" in resp:
        return ""
    segs = resp.get("segments") or []
    return " ".join(s.get("text", "") for s in segs) or resp.get("text", "")


def main() -> int:
    print(f"[verify] server={SERVER_URL} audio_dir={AUDIO_DIR}")
    en, zh = ensure_audio()
    wait_server()
    mgr = build_manager()
    python = deploy.python_bin()
    results = []

    # SenseVoice cache_dir-mismatch probe: snapshot before any transcription
    model_cache_dir = ROOT / "services" / "asr" / "model_cache"
    mc_before = model_cache_dir.exists()

    for m in list_local_asr_models():
        slug = m.slug
        entry: dict = {
            "slug": slug, "runtime": m.runtime, "spec": m.spec, "model_id": m.model_id,
        }
        print(f"\n[verify] === {slug} ({m.runtime}) ===")

        # 1. download if not cached (venv already exists -> skip pip cycle)
        pre = mgr.get_status().models.get(slug)
        if pre and pre.installed is True:
            entry["download"] = "skipped (already cached)"
            print("[verify] cached, skip download")
        else:
            print("[verify] downloading (real)...")
            try:
                deploy.download_model(
                    python, model_id=m.model_id, runtime=m.runtime, spec=m.spec,
                    on_progress=lambda s, d, p=None: print(f"    {s}: {d}"),
                )
                entry["download"] = "ok"
            except Exception as exc:  # noqa: BLE001
                entry["download"] = f"FAILED: {exc}"
                entry["pass"] = False
                results.append(entry)
                print(f"[verify] DOWNLOAD FAILED: {exc}")
                continue

        # 2. cache detection
        post = mgr.get_status().models.get(slug)
        cache_path = post.cache_path if post else None
        cache_ok = (
            post is not None
            and post.installed is True
            and bool(cache_path)
            and Path(cache_path).exists()
        )
        entry["cache_detected"] = cache_ok
        entry["cache_path"] = cache_path
        print(f"[verify] cache_detected={cache_ok} path={cache_path}")

        # 3. transcribe (Moonshine <- English, SenseVoice <- Chinese)
        audio = en if m.runtime == "moonshine" else zh
        model_field = m.spec if m.runtime == "moonshine" else m.model_id
        try:
            resp = transcribe(model_field, audio)
        except Exception as exc:  # noqa: BLE001
            resp = {"_error": str(exc)}
        text = _text_of(resp)
        keywords = EN_KEYWORDS if m.runtime == "moonshine" else ZH_KEYWORDS
        hit = [k for k in keywords if k.lower() in text.lower()]
        transcribe_ok = "_error" not in resp and len(hit) >= 1
        entry["transcribe_ok"] = transcribe_ok
        entry["transcribe_error"] = resp.get("_error")
        entry["transcribe_text"] = text[:300]
        entry["keywords_hit"] = hit
        print(f"[verify] transcribe_ok={transcribe_ok} text={text[:120]!r}")

        # 4. SenseVoice: did services/asr/model_cache/ get created during transcribe?
        if m.runtime == "sensevoice":
            mc_after = model_cache_dir.exists()
            entry["model_cache_dir_created"] = (not mc_before) and mc_after
            if entry["model_cache_dir_created"]:
                print("[verify] WARN services/asr/model_cache/ created — cache_dir mismatch bug")

        entry["pass"] = bool(cache_ok and transcribe_ok)
        results.append(entry)

    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.get("pass"))
    print(f"[verify] {passed}/{len(results)} models passed. results -> {RESULTS_PATH}")
    for r in results:
        mark = "PASS" if r.get("pass") else "FAIL"
        print(
            f"  [{mark}] {r['slug']}: "
            f"download={r.get('download', '?')} "
            f"cache={r.get('cache_detected')} "
            f"transcribe={r.get('transcribe_ok')}"
        )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
