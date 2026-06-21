"""Slice 176W runner: writer-generated table companion (real provider call).

Makes ONE real provider/model generation call: the writer receives the existing
private recovered table as a closed descriptor and must insert the
``{{table:patient_dataset}}`` token, write an explanation beneath it, and emit a
simplified study table. The single token is resolved to the faithful recovered table
and the companion is rendered to private (gitignored) HTML for the operator to read.

It prints ONLY closed status labels — never the prompt, response, table text,
explanation text, or any private path. It runs no OCR, no coverage eval, no judge, no
repair, and no Docker.

Env:
  PRIVATE_VISIBLE_ARTIFACT   gitignored path to the 176I/176U visible payload
  PRIVATE_OCR_DIR            gitignored dir holding the visible payload
  PRIVATE_COMPANION_DIR      gitignored dir to write the private companion output
  WRITER_PROVIDER            closed provider id (default: stored default, else deepseek)
  WRITER_MODEL_CHOICE        model selector (default: "Use environment default")
  WRITER_CUSTOM_MODEL        custom model id when WRITER_MODEL_CHOICE is custom
  SOURCE_LABEL               closed source label (default "ensemble")
  RENDER_HTML                "0" to skip rendering
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.writer_generated_table_companion import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
