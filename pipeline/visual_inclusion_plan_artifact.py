"""Artifact writer for ``visual_inclusion_plan.json`` (Slice 84).

Persists the Slice 83 pure full non-table visual inclusion planner output as a
safe exact-name job artifact, derived only from the already-sanitized
``visual_assets_manifest.json``-shaped dict. It reads no source documents, no
images, no OCR output, no providers, no prompts, and no rendered artifacts, and
it never lets plan writing fail guide generation.

The planner (:func:`pipeline.visual_inclusion_planner.build_visual_inclusion_plan`)
is pure and total — it never raises and degrades to a safe ``skipped`` plan on any
unexpected input. This writer adds only persistence:

* a present (and non-skipped) manifest dict → a planned ``visual_inclusion_plan.json``;
* a missing / ``None`` / malformed / skipped manifest → a safe ``skipped`` plan
  written via the same planner (closed warning tokens only);
* any disk-write failure → degrade-never-fail (a safe message to stderr, no raw
  exception serialized, generation continues).

The emitted JSON is exactly the Slice 83 plan schema: only closed tokens, ints,
``None``, and fixed strings. No filename, path, source title, caption,
document/OCR/table text, image ref, asset ref, image bytes, base64/data URI,
provider payload, token, URL, argv, socket path, model path, or raw exception
string can survive into it.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from pipeline.visual_inclusion_planner import build_visual_inclusion_plan

VISUAL_INCLUSION_PLAN_FILENAME = "visual_inclusion_plan.json"


def write_visual_inclusion_plan(
    job: Any,
    visual_manifest: Any = None,
) -> dict[str, Any]:
    """Persist ``visual_inclusion_plan.json`` under ``job.dir``.

    ``visual_manifest`` is the already-sanitized ``visual_assets_manifest.json``-
    shaped dict (or ``None`` / a skipped stand-in). The plan is built by the pure
    Slice 83 planner, which handles missing/malformed/skipped manifests by
    returning a safe ``skipped`` plan. Any disk-write failure is swallowed (a safe
    message to stderr, no raw exception text) and the in-memory plan is returned;
    plan writing never gates or fails guide generation.

    Returns the plan dict that was built (whether or not the file write succeeded).
    """
    # The planner is pure/total and never raises, but stay defensive: an
    # unexpected failure still degrades to a safe skipped plan (built from None).
    try:
        plan = build_visual_inclusion_plan(visual_manifest)
    except Exception:
        plan = build_visual_inclusion_plan(None)

    try:
        job.save_text(
            job.visual_inclusion_plan_json,
            json.dumps(plan, indent=2, sort_keys=True) + "\n",
        )
    except Exception as exc:  # never let an advisory artifact break a job
        print(
            f"Visual inclusion plan skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
    return plan
