"""Slice 176R runner: uncommon-deck local OCR extraction artifact.

Env-driven and committed-safe. It runs local-only OCR/text extraction for
candidate_1, writes raw output only to a private artifact directory, and prints only
closed labels.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.uncommon_deck_local_ocr_extraction import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
