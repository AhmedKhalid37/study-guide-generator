"""Slice 176L runner — build the private OCR-context guide preview and score it.

Thin env-driven wrapper over ``pipeline.ocr_context_private_guide.main``. It reads
the private 176I manifest (+ optional 176K visible-asset payload) from a confirmed
private (gitignored / temp) directory, assembles a **private** student guide-preview
markdown from the OCR-extracted content, scores it against an optional **private**
baseline guide markdown using the committed deterministic guide-quality contract lint
(no LLM, no new judge), and prints a **committed-safe closed** score/comparison
summary. No raw guide / OCR / table / caption text, paths, prompts, or responses are
printed. Carries no private paths in code.

Env:
  PRIVATE_OCR_DIR        gitignored/temp dir with 176I's manifest (+176K payload)
  SOURCE_LABEL           closed source label (default "ensemble")
  BASELINE_GUIDE_MD      optional path to the private baseline guide markdown
                         (must live in a gitignored/temp dir)
  INCLUDE_VISIBLE_ASSETS "1" (default) to embed 176K visible assets if present

No cloud OCR. No provider/model generation. No guide-generation wiring into normal
app behavior. No frontend/API. judge_ready=false; repair_ready=false.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.ocr_context_private_guide import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
