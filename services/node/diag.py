#!/usr/bin/env python3
"""Diagnosis script: print device detection + actual model device + benchmark latency.

Usage:
  python diag.py           # diagnose both ASR and embedding
  python diag.py --asr     # ASR only
  python diag.py --embed   # embedding only
"""

import argparse
import shutil
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASR_DIR = REPO_ROOT / "services" / "asr"
EMBEDDING_DIR = REPO_ROOT / "services" / "embedding"


def detect_best_device() -> str:
    """Detect the best available torch device: cuda > mps > cpu."""
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def diag_embedding() -> None:
    """Diagnose embedding model: device + latency."""
    print("=== Embedding Diagnosis ===")
    device = detect_best_device()
    print(f"Detected device: {device}")

    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        mps_ok = torch.backends.mps.is_available()
        print(f"  torch.cuda.is_available(): {cuda_ok}")
        print(f"  torch.backends.mps.is_available(): {mps_ok}")
    except ImportError:
        print("  torch not installed")

    try:
        from sentence_transformers import SentenceTransformer
        print(f"  Loading model all-MiniLM-L6-v2 on device={device}...")
        t0 = time.time()
        model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        load_time = time.time() - t0
        print(f"  Model loaded in {load_time:.1f}s")

        # Check actual device
        try:
            device_str = str(next(model.parameters()).device)
        except Exception:
            device_str = "unknown"
        print(f"  Model actual device: {device_str}")

        # Benchmark
        text = "memento embedding dimension probe"
        t0 = time.time()
        vec = model.encode([text], normalize_embeddings=True)
        encode_time = time.time() - t0
        print(f"  Encode latency: {encode_time:.3f}s")
        print(f"  Vector dim: {len(vec[0])}")
    except Exception as e:
        print(f"  ERROR: {e}")


def diag_asr() -> None:
    """Diagnose ASR model: device + latency."""
    print("=== ASR Diagnosis ===")
    device = detect_best_device()
    print(f"Detected device: {device}")

    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        mps_ok = torch.backends.mps.is_available()
        print(f"  torch.cuda.is_available(): {cuda_ok}")
        print(f"  torch.backends.mps.is_available(): {mps_ok}")
    except ImportError:
        print("  torch not installed")

    try:
        from funasr import AutoModel
        print(f"  Loading model iic/SenseVoiceSmall on device={device}...")
        t0 = time.time()
        model = AutoModel(
            model="iic/SenseVoiceSmall",
            device=device,
            disable_update=True,
        )
        load_time = time.time() - t0
        print(f"  Model loaded in {load_time:.1f}s")

        # Check actual device
        try:
            param = next(model.model.parameters())
            print(f"  Model actual device: {param.device}")
        except Exception:
            print("  Model actual device: (unable to determine)")

        # Generate a short silence audio for benchmark
        import numpy as np
        import soundfile as sf
        import tempfile
        sample_rate = 16000
        silence = np.zeros(sample_rate * 3, dtype=np.float32)  # 3 seconds of silence
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, silence, sample_rate)
            tmp_path = f.name

        try:
            t0 = time.time()
            _ = model.generate(input=tmp_path, fs=sample_rate, use_itn=True)
            encode_time = time.time() - t0
            print(f"  Transcribe latency (3s silence): {encode_time:.3f}s")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        print(f"  ERROR: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memento Remote Node Diagnostics")
    parser.add_argument("--asr", action="store_true", help="ASR only")
    parser.add_argument("--embed", action="store_true", help="Embedding only")
    args = parser.parse_args()

    run_asr = args.asr or not args.embed
    run_embed = args.embed or not args.asr

    if run_embed:
        diag_embedding()
        print()
    if run_asr:
        diag_asr()


if __name__ == "__main__":
    main()
