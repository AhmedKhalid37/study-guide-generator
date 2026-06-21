"""Slice 176Y private runner for writer-generated figure/diagram companion.

Reads existing private visible-asset descriptors and prints only the closed summary.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.writer_generated_figure_companion import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
