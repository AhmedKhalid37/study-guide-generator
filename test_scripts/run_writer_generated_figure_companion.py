"""Private runner for the writer-generated figure/diagram companion.

Two modes, both print only the closed summary:

* default (Slice 176Y) — reads existing private visible-asset descriptors.
* ``WRITER_COMPANION_MODE=descriptor_177a`` (Slice 177A) — consumes the accepted
  176Z private non-table figure descriptor (``PRIVATE_DESCRIPTOR_DIR`` /
  ``PRIVATE_DESCRIPTOR_PATH``) and renders the recovered crop as a safe
  private-relative image asset with a writer-generated explanation beneath it.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.writer_generated_figure_companion import main, main_177a  # noqa: E402


if __name__ == "__main__":
    if os.environ.get("WRITER_COMPANION_MODE") == "descriptor_177a":
        raise SystemExit(main_177a())
    raise SystemExit(main())
