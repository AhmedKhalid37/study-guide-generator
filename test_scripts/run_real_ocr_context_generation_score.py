"""Slice 176N runner: real private OCR-context guide generation + closed score.

Thin env-driven wrapper over ``pipeline.real_ocr_context_generation.main``. It reads
the private 176I manifest (+ optional 176K visible-asset payload) from a confirmed
private directory, feeds the OCR-extracted content through the existing guide
generation path with an existing configured provider, writes the generated guide only
to the private directory, scores it with the existing deterministic contract lint,
and prints only a committed-safe closed summary.

Env:
  PRIVATE_OCR_DIR        gitignored/temp dir with 176I's manifest (+176K payload)
  SOURCE_LABEL           closed source label (default "ensemble")
  BASELINE_GUIDE_MD      optional private baseline guide markdown
  INCLUDE_VISIBLE_ASSETS "1" (default) to include 176K visible assets if present
  GENERATION_PROVIDER    optional existing provider id
  GENERATION_PRESET      generator preset id (default "claude_review")

No cloud OCR. No new provider integration. No Layer-2 judge. No repair. No
frontend/API wiring. judge_ready=false; repair_ready=false.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.real_ocr_context_generation import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
