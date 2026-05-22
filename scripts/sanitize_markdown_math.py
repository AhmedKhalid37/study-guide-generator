#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.markdown_sanitizer import sanitize, sanitize_markdown_math


def validate_with_node(path: Path, show_math: bool = False) -> int:
    validator = Path(__file__).with_name("validate_math.js")
    if not shutil.which("node"):
        print("node is not installed; skipping KaTeX validation.", file=sys.stderr)
        return 0
    if not validator.exists():
        print("validate_math.js not found; skipping KaTeX validation.", file=sys.stderr)
        return 0

    cmd = ["node", str(validator), str(path)]
    if show_math:
        cmd.append("--show-math")
    proc = subprocess.run(cmd, text=True)
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair broken Claude/ChatGPT Markdown math.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--validate", action="store_true", help="Validate math with KaTeX via Node.")
    parser.add_argument("--show-math", action="store_true", help="Print math expressions during validation.")
    args = parser.parse_args()

    raw = args.input.read_text(encoding="utf-8", errors="replace")
    clean = sanitize(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(clean, encoding="utf-8")
    print(f"Saved {args.output}")

    if args.validate:
        raise SystemExit(validate_with_node(args.output, args.show_math))


if __name__ == "__main__":
    main()
