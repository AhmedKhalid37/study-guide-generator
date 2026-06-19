#!/usr/bin/env python3
"""Slice 167 -- Phase 0 closed-summary validator CLI.

A safe, local, offline tooling bridge that lets an operator validate
already-sanitized Phase 0 *closed summary* JSON files later, without this script
ever reading raw/private source materials. It is NOT the real operator run: it
executes no provider/model/judge, performs no repair, and discovers nothing on
its own.

Hard properties (must hold):

* Accepts only JSON files explicitly passed on the command line.
* No default input path; no recursive search; no directory scanning.
* Never reads raw job artifacts, operator baseline directories, source/reference
  PDFs, generated guides, generated guide markdown, OCR output, screenshots, or
  any raw artifact by default -- and even an explicitly-passed file is only
  accepted as a closed JSON summary run through the closed-result ingest layer.
* Rejects directories and non-JSON inputs.
* Prints ONLY a closed validation summary (counts + closed tokens). It never
  echoes the input JSON, a private path, a filename, a hash, a byte count, a
  secret, a provider payload, an evidence quote, or any other private material.
* The frozen production offline judge stays frozen: ``judge_ready`` /
  ``repair_ready`` are always ``False``. Any dev-time reference-anchored judge is
  a separate operator-local activity and is never executed here.
* Numeric correctness remains recompute-first via the golden specs; this is NOT
  manual operator ``known_numbers`` infrastructure.

Exit code is nonzero if any input is invalid (missing/dir/non-JSON/rejected).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline.quality_safety_eval_harness import (  # noqa: E402
    REQUIRED_GOLDEN_PAIR_IDS,
    build_phase0_exit_check_from_operator_results,
    ingest_phase0_operator_closed_result,
)

VALIDATION_KIND = "phase0_closed_summary_validation"

# Closed validator-level vocabulary. The validator surfaces *what kind* of
# rejection occurred using only these closed tokens -- it never re-emits the
# ingest layer's internal blocker tokens (some of which name forbidden material
# categories) and never echoes any input content. Defense in depth.
_FILE_NOT_READABLE = "input_not_a_readable_file"
_FILE_IS_DIRECTORY = "input_is_a_directory"
_FILE_NOT_JSON = "input_not_a_json_file"
_FILE_NOT_VALID_JSON = "input_not_valid_json"
_REJECT_INVALID_SHAPE = "input_rejected_invalid_shape"
_REJECT_FORBIDDEN = "input_rejected_forbidden_material"


def _load_one(path: Path) -> tuple[Any, str | None]:
    """Load one explicit input. Returns (parsed_obj, None) or (None, token)."""
    if path.is_dir():
        return None, _FILE_IS_DIRECTORY
    if not path.is_file():
        return None, _FILE_NOT_READABLE
    if path.suffix.lower() != ".json":
        return None, _FILE_NOT_JSON
    try:
        text = path.read_text(encoding="utf-8")
        obj = json.loads(text)
    except (OSError, ValueError):
        return None, _FILE_NOT_VALID_JSON
    return obj, None


def validate_closed_summaries(paths: list[Any]) -> dict[str, Any]:
    """Validate explicit closed-summary files; return a closed summary dict.

    Pure aside from reading the explicitly-passed files. No scanning, no network,
    no provider/model/judge calls. Output carries closed tokens and counts only.
    """
    input_count = len(paths)
    accepted: list[Any] = []
    accepted_kinds: set[str] = set()
    blockers: set[str] = set()
    warnings: set[str] = set()
    invalid_count = 0

    for raw_path in paths:
        obj, file_err = _load_one(Path(raw_path))
        if file_err is not None:
            invalid_count += 1
            blockers.add(file_err)
            continue
        ingest = ingest_phase0_operator_closed_result(obj)
        status = ingest.get("ingest_status")
        if status == "ok":
            accepted.append(obj)
            kind = ingest.get("accepted_kind")
            if isinstance(kind, str):
                accepted_kinds.add(kind)
            for warning in ingest.get("warnings", []):
                if isinstance(warning, str):
                    warnings.add(warning)
        elif status == "blocked":
            invalid_count += 1
            blockers.add(_REJECT_FORBIDDEN)
        else:  # "invalid" or any unexpected status
            invalid_count += 1
            blockers.add(_REJECT_INVALID_SHAPE)

    # Combine only the accepted closed results; the exit-check re-ingests them and
    # can never invent readiness (the structural fact-sheet wiring blocker holds).
    exit_check = build_phase0_exit_check_from_operator_results(accepted)

    return {
        "kind": VALIDATION_KIND,
        "ok": input_count > 0 and invalid_count == 0,
        "input_count": input_count,
        "accepted_count": len(accepted),
        "invalid_count": invalid_count,
        "accepted_kinds": sorted(accepted_kinds),
        "blockers": sorted(blockers),
        "warnings": sorted(warnings),
        "phase0_exit_status": exit_check.get("phase0_exit_status"),
        "golden_pair_ids": list(REQUIRED_GOLDEN_PAIR_IDS),
        "production_offline_judge_frozen": True,
        "judge_ready": False,
        "repair_ready": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_phase0_closed_summary.py",
        description=(
            "Validate Phase 0 closed operator summary JSON files. Accepts only "
            "explicit JSON files; never scans directories or reads private "
            "materials. Prints a closed validation summary only."
        ),
        epilog=(
            "Examples:\n"
            "  python test_scripts/validate_phase0_closed_summary.py summary.json\n"
            "  python test_scripts/validate_phase0_closed_summary.py run.json judge.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "summaries",
        nargs="+",
        metavar="SUMMARY_JSON",
        help="One or more closed Phase 0 summary JSON files (explicit paths only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = validate_closed_summaries(args.summaries)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
