"""Slice 176T runner: candidate_1 structured/local OCR attempt.

Env-driven and committed-safe. It attempts existing local OCR routes for
candidate_1, writes raw output only to a private artifact directory, and prints
only closed labels.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.candidate1_structured_ocr_attempt import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
