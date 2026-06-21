"""Slice 176U runner: private rendered visible-asset insertion proof.

Uses existing private recovered table artifacts only. It does not run provider
generation, guide generation, OCR, coverage evaluation, Docker, judges, or repair.
It prints only closed status labels.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.rendered_visible_asset_insertion_proof import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
