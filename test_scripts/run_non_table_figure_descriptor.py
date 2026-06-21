"""Slice 176Z private runner for non-table figure descriptor production.

Reads existing private artifacts/source and prints only the closed summary.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.non_table_figure_descriptor import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
