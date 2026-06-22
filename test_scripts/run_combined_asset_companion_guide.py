"""Private runner for Slice 177B combined table + figure companion guide.

Reuses the accepted private 176X table companion output dir and the accepted
private 177A figure companion output dir and composes one private rendered HTML
guide. Prints only the closed committed-safe summary; writes the rendered guide
into a gitignored private artifact directory.

Environment:
* ``PRIVATE_TABLE_COMPANION_DIR``  — accepted 176X output dir.
* ``PRIVATE_FIGURE_COMPANION_DIR`` — accepted 177A output dir.
* ``PRIVATE_COMBINED_DIR``         — output dir for the combined private guide.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.combined_asset_companion_guide import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
