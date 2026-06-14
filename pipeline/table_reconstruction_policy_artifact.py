"""Artifact writer for ``table_reconstruction_policy.json`` (Slice 92).

Persists the Slice 85 pure :func:`pipeline.table_reconstruction_policy.
build_table_reconstruction_policy` output as a safe exact-name job artifact, fed by
the Slice 92 sanitized **table candidate manifest** (``pipeline.
table_candidate_manifest``) rather than synthetic dicts. It reads no source
documents, no images, no OCR output, no providers, no prompts, and no rendered
artifacts, never reconstructs a table, and never lets policy writing fail guide
generation.

Both the candidate builder and the policy core are pure and total (they never
raise and degrade to safe ``skipped`` outputs on any unexpected input). This writer
adds only persistence:

* a present visual manifest dict → table candidates → a ``table_reconstruction_
  policy.json`` decided by the Slice 85 policy;
* a missing / ``None`` / malformed / skipped manifest → no candidates → a safe
  ``skipped`` policy (closed warning tokens only);
* any disk-write failure → degrade-never-fail (a safe message to stderr, no raw
  exception serialized, generation continues).

The emitted JSON is exactly the Slice 85 policy schema: only closed tokens, ints,
``None``, and fixed strings. ``screenshot_insert_count`` is always ``0`` — a table
is never inserted as a screenshot. No filename, path, source title, caption,
document/OCR/table text, image ref, asset ref, image bytes, base64/data URI,
provider payload, token, URL, argv, socket path, model path, or raw exception
string can survive into it.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from pipeline.table_candidate_manifest import (
    build_table_candidates_manifest,
    table_policy_candidates,
)
from pipeline.table_reconstruction_policy import build_table_reconstruction_policy

TABLE_RECONSTRUCTION_POLICY_FILENAME = "table_reconstruction_policy.json"


def write_table_reconstruction_policy(
    job: Any,
    visual_manifest: Any = None,
    *,
    table_candidates_manifest: Any = None,
) -> dict[str, Any]:
    """Persist ``table_reconstruction_policy.json`` under ``job.dir``.

    The policy is decided over the sanitized table candidates derived from the
    already-safe ``visual_assets_manifest.json``-shaped ``visual_manifest`` dict (or
    a pre-built ``table_candidates_manifest`` dict, if the caller already built one).
    A missing/malformed/skipped manifest yields no candidates and therefore a safe
    ``skipped`` policy. Any disk-write failure is swallowed (a safe message to
    stderr, no raw exception text) and the in-memory policy is returned; policy
    writing never gates or fails guide generation.

    Returns the policy dict that was built (whether or not the file write
    succeeded).
    """
    try:
        manifest = (
            table_candidates_manifest
            if isinstance(table_candidates_manifest, dict)
            else build_table_candidates_manifest(visual_manifest)
        )
        # A genuinely skipped candidate manifest (missing/malformed/skipped visual
        # manifest) has no candidates to decide over, so the policy is built from
        # ``None`` → a safe ``skipped`` policy. A ``completed``/``partial`` manifest
        # (even with an empty candidate list) is decided normally, yielding a
        # ``completed`` policy with zero actionable items.
        if isinstance(manifest, dict) and manifest.get("status") == "skipped":
            policy = build_table_reconstruction_policy(None)
        else:
            candidates = table_policy_candidates(manifest)
            policy = build_table_reconstruction_policy(candidates)
    except Exception:
        # Defensive: both helpers are total, but a future surprise still degrades to
        # a safe skipped policy built from no candidates. No raw exception serialized.
        policy = build_table_reconstruction_policy(None)

    try:
        job.save_text(
            job.table_reconstruction_policy_json,
            json.dumps(policy, indent=2, sort_keys=True) + "\n",
        )
    except Exception as exc:  # never let an advisory artifact break a job
        print(
            f"Table reconstruction policy skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
    return policy
