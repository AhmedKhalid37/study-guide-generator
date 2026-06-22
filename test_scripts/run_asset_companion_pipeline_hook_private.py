"""Private runner for Slice 177E default-off asset-companion pipeline hook.

Reads an existing private full guide Markdown file and the accepted private 177B
combined companion output directory, then explicitly enables the hook for one private
dry-run. Prints only the closed committed-safe summary and writes rendered output into
gitignored private storage.

Environment:
* ``PRIVATE_FULL_GUIDE_PATH`` — existing accepted full guide Markdown file.
* ``PRIVATE_COMBINED_DIR`` — accepted 177B combined companion output dir.
* ``PRIVATE_PIPELINE_HOOK_DIR`` — output dir for this private hook artifact.
* ``ENABLE_ASSET_COMPANION_PIPELINE_HOOK`` — set to ``1`` by this runner.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.asset_companion_pipeline_hook import main  # noqa: E402


if __name__ == "__main__":
    os.environ.setdefault("ENABLE_ASSET_COMPANION_PIPELINE_HOOK", "1")
    raise SystemExit(main())
