#!/usr/bin/env python3
"""Memento Remote Node — single entrypoint. Run: python bootstrap.py"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from node_app.cli import main

if __name__ == "__main__":
    main()
