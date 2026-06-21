"""Slice 176S runner: uncommon-deck coverage eval over existing artifacts.

Reads existing private/gitignored baseline/generated guides and the candidate_1
local extraction artifact. It does not run generation, OCR, providers, judges,
repair, Docker, or normal app behavior.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.deck_specific_coverage_eval import uncommon_deck_coverage_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(uncommon_deck_coverage_main())
