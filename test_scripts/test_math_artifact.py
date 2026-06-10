"""Unit tests for the Slice 21 per-job math_verification.json artifact.

Plain-Python assertion style (matches the rest of test_scripts/). Run with:

    python test_scripts/test_math_artifact.py

Covers the defensive pipeline helper ``run_markdown_job._write_math_verification``
(valid / mismatch / unparseable claims, zero claims, and a verifier crash that
degrades to a safe ``skipped`` artifact), proves job completion is never failed
and validation.json is never touched, scans the artifact for secret-looking
content, and — only when FastAPI is importable — checks that the artifact
download route resolves ``math_verification.json`` safely without surfacing it in
the listed-artifact dict.

No hosted LLM calls; everything runs against tiny in-memory fixtures.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pipeline.math_verifier as math_verifier
from pipeline.job_manager import Job
from pipeline.run_markdown_job import _write_math_verification

PASS = 0
FAIL = 0

# Field names / value shapes that would indicate a leaked credential in the
# artifact. A bare "key" is intentionally NOT flagged (legitimate non-secret).
SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def _make_job(tmp: str, clean_text: str | None) -> Job:
    """Build a throwaway Job rooted in *tmp* with an optional clean.md."""
    job = Job(id="job-test", root=Path(tmp))
    job.dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "done"})
    if clean_text is not None:
        # Direct write is fine in a fixture: we are exercising the read-only
        # verification helper, not a clean.md write path (which still goes
        # through JobManager.save_clean_md in production).
        job.clean_md.write_text(clean_text, encoding="utf-8")
    return job


def _read_artifact(job: Job) -> dict:
    return json.loads(job.math_verification_json.read_text(encoding="utf-8"))


# ── 1. valid claims → completed artifact, job not failed ────────────────────

def test_valid_claims_completed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Line-start claims so the conservative verifier parses them cleanly (it
        # deliberately leaves word-glued expressions unparseable, and a leading
        # list dash would be read as a unary minus).
        job = _make_job(tmp, "# Guide\n\n2 + 3 = 5\n\n3 * 4 = 12\n")
        _write_math_verification(job)
        check("valid/artifact-exists", job.math_verification_json.exists())
        art = _read_artifact(job)
        check("valid/kind", art.get("kind") == "math_verification", str(art.get("kind")))
        check("valid/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("valid/source", art.get("source") == "clean.md", str(art.get("source")))
        summary = art.get("report", {}).get("summary", {})
        check("valid/total>=2", summary.get("total", 0) >= 2, str(summary))
        check("valid/ok>=2", summary.get("ok", 0) >= 2, str(summary))
        check("valid/no-mismatch", summary.get("mismatch", 0) == 0, str(summary))
        # Job status must be untouched by the advisory helper.
        check("valid/status-unchanged", job.read_manifest().get("status") == "done")


# ── 2. mismatch claims recorded, job not failed ─────────────────────────────

def test_mismatch_recorded_not_failed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nA wrong claim: 2 + 2 = 5.\n")
        _write_math_verification(job)
        art = _read_artifact(job)
        summary = art.get("report", {}).get("summary", {})
        check("mismatch/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("mismatch/mismatch>=1", summary.get("mismatch", 0) >= 1, str(summary))
        check("mismatch/job-not-failed", job.read_manifest().get("status") == "done")


# ── 3. unparseable claims recorded, job not failed ──────────────────────────

def test_unparseable_recorded_not_failed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nWith a variable: x + 2 = 5.\n")
        _write_math_verification(job)
        art = _read_artifact(job)
        summary = art.get("report", {}).get("summary", {})
        check("unparseable/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("unparseable/unparseable>=1", summary.get("unparseable", 0) >= 1, str(summary))
        check("unparseable/job-not-failed", job.read_manifest().get("status") == "done")


# ── 4. zero claims → completed artifact with total 0 ────────────────────────

def test_zero_claims_completed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nPure prose with no numeric claims at all.\n")
        _write_math_verification(job)
        art = _read_artifact(job)
        summary = art.get("report", {}).get("summary", {})
        check("zero/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("zero/total-0", summary.get("total", -1) == 0, str(summary))


# ── 5. verifier crash → safe skipped artifact, job continues ────────────────

def test_verifier_crash_degrades_safely() -> None:
    original = math_verifier.verify_math_claims

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("synthetic verifier failure with secret sk-abcdef0123456789xyz")

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\n2 + 3 = 5.\n")
        math_verifier.verify_math_claims = _boom
        try:
            # Must not raise.
            _write_math_verification(job)
        finally:
            math_verifier.verify_math_claims = original
        check("crash/artifact-exists", job.math_verification_json.exists())
        art = _read_artifact(job)
        check("crash/status-skipped", art.get("status") == "skipped", str(art.get("status")))
        check("crash/reason", art.get("reason") == "verifier_error", str(art.get("reason")))
        check("crash/safe-message", bool(art.get("safe_message")), str(art.get("safe_message")))
        check("crash/no-report", "report" not in art, str(list(art.keys())))
        raw = job.math_verification_json.read_text(encoding="utf-8")
        check("crash/no-traceback", "Traceback" not in raw and "RuntimeError" not in raw, raw[:120])
        check("crash/no-exc-message", "synthetic verifier failure" not in raw, raw[:120])
        check("crash/job-not-failed", job.read_manifest().get("status") == "done")


# ── 6. artifact contains no secret-like field names or values ───────────────

def _scan_for_secret(node, path: str = "") -> str | None:
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).lower() in SECRET_KEY_NAMES:
                return f"{path}.{k} (secret-like field name)"
            found = _scan_for_secret(v, f"{path}.{k}")
            if found:
                return found
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found = _scan_for_secret(v, f"{path}[{i}]")
            if found:
                return found
    elif isinstance(node, str):
        if KEYLIKE.search(node):
            return f"{path} (value looks like a credential)"
    return None


def test_no_secret_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\n2 + 3 = 5 and exp(0) = 1.\n")
        _write_math_verification(job)
        art = _read_artifact(job)
        leak = _scan_for_secret(art)
        check("secret/clean-completed", leak is None, leak or "")
        # Even the degraded artifact must be clean.
        original = math_verifier.verify_math_claims
        math_verifier.verify_math_claims = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
        try:
            _write_math_verification(job)
        finally:
            math_verifier.verify_math_claims = original
        leak2 = _scan_for_secret(_read_artifact(job))
        check("secret/clean-skipped", leak2 is None, leak2 or "")


# ── 7. validation.json untouched; report has verifier shape (not validator) ──

def test_validation_json_untouched() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\n2 + 3 = 5.\n")
        sentinel = '{"ok": true, "display_blocks": 0, "inline_formulas": 0, "errors": []}\n'
        validation_path = job.logs_dir / "validation.json"
        validation_path.write_text(sentinel, encoding="utf-8")
        _write_math_verification(job)
        check("validation/untouched", validation_path.read_text(encoding="utf-8") == sentinel)
        # The persisted report must carry the math_verifier shape (numeric
        # correctness), confirming it did not piggyback on math_validator output.
        report = _read_artifact(job).get("report", {})
        shape_ok = set(report.keys()) >= {"version", "source_name", "summary", "claims"}
        check("validation/verifier-shape", shape_ok, str(sorted(report.keys())))
        check("validation/report-version", report.get("version") == math_verifier.VERSION, str(report.get("version")))


# ── 8. artifact download route resolves safely (FastAPI optional) ───────────

def test_artifact_route_safe() -> None:
    try:
        import api.server as server  # noqa: PLC0415 - optional host dependency
    except Exception as exc:  # FastAPI / deps unavailable on bare host Python
        print(f"[SKIP] route/import — FastAPI unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\n2 + 3 = 5.\n")
        _write_math_verification(job)
        path, media = server._artifact_path(job, "math_verification.json")
        check("route/path", path == job.math_verification_json, str(path))
        check("route/media-json", media == "application/json", media)
        check("route/not-in-ARTIFACTS", "math_verification.json" not in server.ARTIFACTS)
        # Not surfaced in the UI-facing artifact url/detail lists this slice.
        avail = server._artifact_availability(job)
        urls = server._artifact_urls(job, avail)
        check("route/not-in-urls", "math_verification.json" not in urls, str(list(urls.keys())))
        details_names = {d["name"] for d in server._artifact_details(job, avail)}
        check("route/not-in-details", "math_verification.json" not in details_names, str(details_names))
        # Unknown / traversal-ish names still 404 (HTTPException) via the dict path.
        try:
            server._artifact_path(job, "../job.json")
            check("route/traversal-blocked", False, "no exception raised")
        except Exception as exc:
            check("route/traversal-blocked", exc.__class__.__name__ == "HTTPException", type(exc).__name__)


if __name__ == "__main__":
    test_valid_claims_completed()
    test_mismatch_recorded_not_failed()
    test_unparseable_recorded_not_failed()
    test_zero_claims_completed()
    test_verifier_crash_degrades_safely()
    test_no_secret_fields()
    test_validation_json_untouched()
    test_artifact_route_safe()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Math artifact tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
