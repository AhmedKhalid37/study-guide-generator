"""Slice 176P runner: closed deck-specific coverage eval over private artifacts.

Reads existing private artifacts only. It never runs generation, never calls a
provider, and prints only the closed coverage summary.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.deck_specific_coverage_eval import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
