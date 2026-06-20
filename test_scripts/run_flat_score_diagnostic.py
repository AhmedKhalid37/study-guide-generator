"""Slice 176O runner: closed flat-score diagnostic over existing private artifacts.

Reads existing private guide/scoring artifacts only. It never runs generation, never
calls a provider, and prints only the closed diagnostic summary.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.flat_score_diagnostic import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
