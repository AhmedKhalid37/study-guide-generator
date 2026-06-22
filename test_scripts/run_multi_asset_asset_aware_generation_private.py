"""Slice 177G private runner: real multi-asset asset-aware generation.

Off-by-default, private only. This drives ONE real provider/model generation over
the existing private ensemble descriptor set (recovered tables + the accepted
non-table figure descriptor) and writes the rendered guide under the gitignored
private OCR tree for operator inspection. It prints only the closed committed-safe
summary; the rendered guide path is shown for the operator on stderr and must not be
copied into committed docs.

Environment (all optional — sensible private-tree defaults are discovered):
* ``PRIVATE_OCR_DIR`` — gitignored private OCR dir holding the recovered
  ``visible_table_figure_pilot.json`` and a ``non_table_figure_descriptor/`` subdir.
* ``PRIVATE_VISIBLE_ARTIFACT`` — explicit visible-asset payload path.
* ``PRIVATE_DESCRIPTOR_DIR`` — explicit non-table figure descriptor dir.
* ``PRIVATE_OUTPUT_DIR`` — explicit output dir.
* ``WRITER_PROVIDER`` — provider id (defaults to the 176W provider, deepseek).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.multi_asset_asset_aware_generation import (  # noqa: E402
    GUIDE_HTML,
    run_multi_asset_asset_aware_generation,
)
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
_VISIBLE_NAME = "visible_table_figure_pilot.json"
_DESCRIPTOR_SUBDIR = "non_table_figure_descriptor"


def _discover_private_ocr_dir() -> str | None:
    """Find the gitignored private OCR dir that holds the recovered payload."""
    for path in _REPO.rglob(_VISIBLE_NAME):
        parent = path.parent
        if is_private_artifact_dir(parent):
            return str(parent)
    return None


def main() -> int:
    private_ocr_dir = os.environ.get("PRIVATE_OCR_DIR") or _discover_private_ocr_dir()
    descriptor_dir = os.environ.get("PRIVATE_DESCRIPTOR_DIR")
    if not descriptor_dir and private_ocr_dir:
        descriptor_dir = str(Path(private_ocr_dir) / _DESCRIPTOR_SUBDIR)

    summary = run_multi_asset_asset_aware_generation(
        visible_artifact_path=os.environ.get("PRIVATE_VISIBLE_ARTIFACT") or None,
        private_ocr_dir=private_ocr_dir,
        private_figure_descriptor_dir=descriptor_dir,
        private_output_dir=os.environ.get("PRIVATE_OUTPUT_DIR") or None,
        provider=os.environ.get("WRITER_PROVIDER") or "deepseek",
        model_choice=os.environ.get("WRITER_MODEL_CHOICE", "Use environment default"),
        custom_model=os.environ.get("WRITER_CUSTOM_MODEL") or None,
        source_label="ensemble",
    )
    print(json.dumps(summary, indent=2))
    if private_ocr_dir and not os.environ.get("PRIVATE_OUTPUT_DIR"):
        guide = Path(private_ocr_dir) / "multi_asset_asset_aware_generation_177g" / GUIDE_HTML
        if guide.is_file():
            # Operator-only path; never copy into committed docs.
            print(f"\n[operator] private rendered guide: {guide}", file=sys.stderr)
    return 0 if summary["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
