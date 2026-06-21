"""Slice 176Q runner: closed uncommon-deck OCR value diagnostic.

Reads existing private/gitignored inventory only. It does not run OCR, generation,
providers, judges, repair, or normal app behavior.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.uncommon_deck_ocr_value_diagnostic import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
