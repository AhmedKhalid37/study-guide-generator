"""Private runner for Slice 177C full-guide asset companion preview.

Reuses an existing accepted private full generated guide (ensemble lineage) and the
accepted private 177B combined asset companion output dir, then inserts the companion
into the full guide and renders one private HTML preview. Prints only the closed
committed-safe summary; writes the rendered preview into a gitignored private
artifact directory.

Environment:
* ``PRIVATE_FULL_GUIDE_PATH``  — existing accepted full guide Markdown file.
* ``PRIVATE_COMBINED_DIR``     — accepted 177B combined companion output dir.
* ``PRIVATE_FULL_PREVIEW_DIR`` — output dir for the private full-guide preview.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.full_guide_asset_companion_preview import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
