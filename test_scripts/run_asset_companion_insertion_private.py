"""Private runner for Slice 177D off-by-default asset-companion insertion seam.

Reuses an existing accepted private full generated guide (ensemble lineage) and the
accepted private 177B combined asset companion output dir, then runs the gated
insertion seam with ``enabled=True`` and renders one private HTML artifact. Prints only
the closed committed-safe summary; writes the rendered output into a gitignored private
artifact directory.

The seam is off-by-default: this runner is the explicit opt-in. Normal app generation
never sets the enable flag, so default generation behavior is unchanged.

Environment:
* ``PRIVATE_FULL_GUIDE_PATH`` — existing accepted full guide Markdown file.
* ``PRIVATE_COMBINED_DIR``    — accepted 177B combined companion output dir.
* ``PRIVATE_INSERTION_DIR``   — output dir for the private inserted-guide artifact.
* ``ENABLE_INSERTION_SEAM``   — must be ``1`` for the runner to enable the seam.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.asset_companion_insertion import main  # noqa: E402


if __name__ == "__main__":
    # The private runner is the explicit opt-in for the off-by-default seam.
    os.environ.setdefault("ENABLE_INSERTION_SEAM", "1")
    raise SystemExit(main())
