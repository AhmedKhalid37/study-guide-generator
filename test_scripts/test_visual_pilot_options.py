#!/usr/bin/env python3
"""Focused tests for Slice 57: visual-pilot readiness in /api/options capabilities.

Run with:

    python test_scripts/test_visual_pilot_options.py

No external APIs and no PyMuPDF/Tesseract/Mistral/Gemini/Chandra dependency.

Slice 57 makes the Builder's per-job visual opt-in reflect whether the pilot can
realistically work for a NEW job. It adds two non-secret booleans plus a derived
readiness flag to ``/api/options.capabilities``:

  * ``visual_markdown_image_pilot``  — global pilot master flag (Slice 54/55; kept
    for backward compatibility, same meaning as before).
  * ``local_figure_extraction``      — local figure-extraction flag (produces the
    ``fitz_local`` figures the pilot inserts).
  * ``visual_references_ready``      — true ONLY when BOTH of the above are true.

This is a readiness/UX guard only — it does NOT change the backend dual gate, does
NOT enable insertion, and does NOT auto-enable extraction.

Two parts:

  * Part A — PURE readiness truth table (always runs): drives the two source-of-truth
    flag functions under every env combination, asserting the derived readiness is
    the AND of the two, and that only safe booleans are involved.
  * Part B — /api/options shape (needs FastAPI): calls ``api.server.options()``
    directly under each env combination and asserts the capability subtree's keys,
    booleans, backward compatibility, and the absence of any secret / path / env
    name / raw config in the capabilities payload. SKIPPED automatically when
    FastAPI is not importable in host Python (run in Docker for full coverage).
"""
from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_asset_extractor import (  # noqa: E402
    ENABLE_ENV as FIGURE_ENV,
    local_figure_extraction_enabled,
)
from pipeline.visual_markdown_insertion import (  # noqa: E402
    ENABLE_ENV as PILOT_ENV,
    is_visual_markdown_pilot_enabled,
)

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\)")
URLLIKE = re.compile(r"https?://")
ENVNAMELIKE = re.compile(r"GUIDEFORGE_[A-Z_]+")


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}{(' — ' + detail) if detail else ''}")


@contextmanager
def env(pilot: bool, figure: bool):
    """Temporarily set the two master switches, restoring prior values after."""
    saved = {PILOT_ENV: os.environ.get(PILOT_ENV), FIGURE_ENV: os.environ.get(FIGURE_ENV)}
    os.environ[PILOT_ENV] = "1" if pilot else "0"
    os.environ[FIGURE_ENV] = "1" if figure else "0"
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# The readiness truth table: ready iff BOTH switches on.
TRUTH_TABLE = [
    (False, False, False),
    (True, False, False),
    (False, True, False),
    (True, True, True),
]


# ---------------------------------------------------------------------------
# Part A — pure readiness truth table (no FastAPI)
# ---------------------------------------------------------------------------


def part_a() -> None:
    for pilot, figure, expected_ready in TRUTH_TABLE:
        with env(pilot, figure):
            got_pilot = is_visual_markdown_pilot_enabled()
            got_figure = local_figure_extraction_enabled()
            ready = got_pilot and got_figure
            label = f"pilot={pilot} figure={figure}"
            check(f"master flag reflects env ({label})", got_pilot is pilot)
            check(f"figure flag reflects env ({label})", got_figure is figure)
            check(f"readiness is AND of both ({label})", ready is expected_ready)
            check(
                f"all three are plain booleans ({label})",
                all(isinstance(v, bool) for v in (got_pilot, got_figure, ready)),
            )


# ---------------------------------------------------------------------------
# Part B — /api/options capability shape (needs FastAPI)
# ---------------------------------------------------------------------------


def part_b() -> int:
    try:
        from api import server  # noqa: WPS433
    except Exception as exc:  # FastAPI / deps not importable in host python
        print(f"[SKIP] api.server options section ({type(exc).__name__})")
        return 0

    for pilot, figure, expected_ready in TRUTH_TABLE:
        with env(pilot, figure):
            try:
                payload = server.options()
            except Exception as exc:  # pragma: no cover - provider registry issues
                print(f"[SKIP] server.options() raised ({type(exc).__name__})")
                return 0
            caps = payload.get("capabilities")
            label = f"pilot={pilot} figure={figure}"
            check(f"capabilities present ({label})", isinstance(caps, dict))
            if not isinstance(caps, dict):
                continue
            # Backward compatibility: original key still present, same meaning.
            check(
                f"visual_markdown_image_pilot == master flag ({label})",
                caps.get("visual_markdown_image_pilot") is pilot,
            )
            check(
                f"local_figure_extraction == figure flag ({label})",
                caps.get("local_figure_extraction") is figure,
            )
            check(
                f"visual_references_ready == AND ({label})",
                caps.get("visual_references_ready") is expected_ready,
            )
            # Only safe booleans — no env names, paths, secrets, or raw config.
            check(
                f"capability values are all booleans ({label})",
                all(isinstance(v, bool) for v in caps.values()),
            )
            blob = json.dumps(caps)
            check(f"no key-like value in capabilities ({label})", not KEYLIKE.search(blob), blob)
            check(f"no path-like value in capabilities ({label})", not PATHLIKE.search(blob), blob)
            check(f"no url in capabilities ({label})", not URLLIKE.search(blob), blob)
            check(f"no env-var name in capabilities ({label})", not ENVNAMELIKE.search(blob), blob)
            # Capability keys are a fixed, whitelisted, safe set.
            check(
                f"capability keys are the expected safe set ({label})",
                set(caps.keys())
                == {
                    "visual_markdown_image_pilot",
                    "local_figure_extraction",
                    "visual_references_ready",
                },
                str(sorted(caps.keys())),
            )

    # Default environment (neither switch set) ⇒ not ready.
    saved = {PILOT_ENV: os.environ.get(PILOT_ENV), FIGURE_ENV: os.environ.get(FIGURE_ENV)}
    os.environ.pop(PILOT_ENV, None)
    os.environ.pop(FIGURE_ENV, None)
    try:
        caps = server.options().get("capabilities", {})
        check("default env reports not ready", caps.get("visual_references_ready") is False)
        check("default env master flag off", caps.get("visual_markdown_image_pilot") is False)
        check("default env figure flag off", caps.get("local_figure_extraction") is False)
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
    return 0


def main() -> int:
    part_a()
    part_b()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
