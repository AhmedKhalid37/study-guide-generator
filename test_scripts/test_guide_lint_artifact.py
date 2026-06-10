"""Unit tests for the Slice 27 per-job guide_lint.json artifact.

Plain-Python assertion style (matches the rest of test_scripts/). Run with:

    python test_scripts/test_guide_lint_artifact.py

Covers the defensive pipeline helper ``run_markdown_job._write_guide_lint``
(clean guide, guide with structural findings, zero findings, and a lint crash
that degrades to a safe ``skipped`` artifact), proves job completion is never
failed and validation.json / math_verification.json are never touched, scans the
artifact for secret-looking content, and — only when FastAPI is importable —
checks that the artifact download route resolves ``guide_lint.json`` safely
without surfacing it in the listed-artifact dict.

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

import pipeline.guide_lint as guide_lint
from pipeline.job_manager import Job
from pipeline.run_markdown_job import _write_guide_lint

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
        # Direct write is fine in a fixture: we are exercising the read-only lint
        # helper, not a clean.md write path (which still goes through
        # JobManager.save_clean_md in production).
        job.clean_md.write_text(clean_text, encoding="utf-8")
    return job


def _read_artifact(job: Job) -> dict:
    return json.loads(job.guide_lint_json.read_text(encoding="utf-8"))


# ── 1. clean guide → completed artifact, job not failed ─────────────────────

def test_clean_guide_completed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nSome prose.\n\n## Section\n\nMore prose.\n")
        _write_guide_lint(job)
        check("clean/artifact-exists", job.guide_lint_json.exists())
        art = _read_artifact(job)
        check("clean/kind", art.get("kind") == "guide_lint", str(art.get("kind")))
        check("clean/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("clean/source", art.get("source") == "clean.md", str(art.get("source")))
        summary = art.get("report", {}).get("summary", {})
        check("clean/has-summary", "total" in summary, str(summary))
        # Job status must be untouched by the advisory helper.
        check("clean/status-unchanged", job.read_manifest().get("status") == "done")


# ── 2. structural problems recorded, job not failed ─────────────────────────

def test_findings_recorded_not_failed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # An empty heading + an unbalanced display-math delimiter → findings.
        job = _make_job(tmp, "# Guide\n\n## Empty\n## Next\n\nText with $$ x = 1\n")
        _write_guide_lint(job)
        art = _read_artifact(job)
        summary = art.get("report", {}).get("summary", {})
        check("findings/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("findings/total>=1", summary.get("total", 0) >= 1, str(summary))
        rules = {f.get("rule") for f in art.get("report", {}).get("findings", [])}
        check("findings/has-expected-rules",
              {"empty_heading", "unbalanced_math"} & rules != set(), str(rules))
        check("findings/job-not-failed", job.read_manifest().get("status") == "done")


# ── 3. zero findings → completed artifact with total 0 ──────────────────────

def test_zero_findings_completed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Single heading with body and no math/tables → no structural findings
        # (run_katex degrades to an info finding only if KaTeX is unavailable, so
        # we avoid math entirely to keep total at 0).
        job = _make_job(tmp, "# Guide\n\nPlain prose with no tables or math.\n")
        _write_guide_lint(job)
        art = _read_artifact(job)
        summary = art.get("report", {}).get("summary", {})
        check("zero/status-completed", art.get("status") == "completed", str(art.get("status")))
        check("zero/total-0", summary.get("total", -1) == 0, str(summary))


# ── 4. lint crash → safe skipped artifact, job continues ────────────────────

def test_lint_crash_degrades_safely() -> None:
    original = guide_lint.lint_guide_markdown

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("synthetic lint failure with secret sk-abcdef0123456789xyz")

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nSome prose.\n")
        guide_lint.lint_guide_markdown = _boom
        try:
            # Must not raise.
            _write_guide_lint(job)
        finally:
            guide_lint.lint_guide_markdown = original
        check("crash/artifact-exists", job.guide_lint_json.exists())
        art = _read_artifact(job)
        check("crash/status-skipped", art.get("status") == "skipped", str(art.get("status")))
        check("crash/reason", art.get("reason") == "lint_error", str(art.get("reason")))
        check("crash/safe-message", bool(art.get("safe_message")), str(art.get("safe_message")))
        check("crash/no-report", "report" not in art, str(list(art.keys())))
        raw = job.guide_lint_json.read_text(encoding="utf-8")
        check("crash/no-traceback", "Traceback" not in raw and "RuntimeError" not in raw, raw[:120])
        check("crash/no-exc-message", "synthetic lint failure" not in raw, raw[:120])
        check("crash/job-not-failed", job.read_manifest().get("status") == "done")


# ── 5. artifact contains no secret-like field names or values ───────────────

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
        job = _make_job(tmp, "# Guide\n\n## Empty\n## Next\n\nText $$ x = 1\n")
        _write_guide_lint(job)
        art = _read_artifact(job)
        leak = _scan_for_secret(art)
        check("secret/clean-completed", leak is None, leak or "")
        # Even the degraded artifact must be clean.
        original = guide_lint.lint_guide_markdown
        guide_lint.lint_guide_markdown = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
        try:
            _write_guide_lint(job)
        finally:
            guide_lint.lint_guide_markdown = original
        leak2 = _scan_for_secret(_read_artifact(job))
        check("secret/clean-skipped", leak2 is None, leak2 or "")


# ── 6. validation.json + math_verification.json untouched; report shape ─────

def test_sibling_artifacts_untouched() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nSome prose.\n")
        validation_sentinel = '{"ok": true, "display_blocks": 0, "inline_formulas": 0, "errors": []}\n'
        validation_path = job.logs_dir / "validation.json"
        validation_path.write_text(validation_sentinel, encoding="utf-8")
        math_sentinel = '{"version": 1, "kind": "math_verification", "status": "completed"}\n'
        job.math_verification_json.write_text(math_sentinel, encoding="utf-8")

        _write_guide_lint(job)

        check("sibling/validation-untouched",
              validation_path.read_text(encoding="utf-8") == validation_sentinel)
        check("sibling/math-untouched",
              job.math_verification_json.read_text(encoding="utf-8") == math_sentinel)
        # The persisted report must carry the guide_lint shape, confirming it did
        # not piggyback on another checker's output.
        report = _read_artifact(job).get("report", {})
        shape_ok = set(report.keys()) >= {"version", "source_name", "summary", "findings"}
        check("sibling/lint-shape", shape_ok, str(sorted(report.keys())))
        check("sibling/report-version", report.get("version") == guide_lint.VERSION, str(report.get("version")))


# ── 7. artifact download route resolves safely (FastAPI optional) ───────────

def test_artifact_route_safe() -> None:
    try:
        import api.server as server  # noqa: PLC0415 - optional host dependency
    except Exception as exc:  # FastAPI / deps unavailable on bare host Python
        print(f"[SKIP] route/import — FastAPI unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "# Guide\n\nSome prose.\n")
        _write_guide_lint(job)
        path, media = server._artifact_path(job, "guide_lint.json")
        check("route/path", path == job.guide_lint_json, str(path))
        check("route/media-json", media == "application/json", media)
        check("route/not-in-ARTIFACTS", "guide_lint.json" not in server.ARTIFACTS)
        # Not surfaced in the UI-facing artifact url/detail lists this slice.
        avail = server._artifact_availability(job)
        urls = server._artifact_urls(job, avail)
        check("route/not-in-urls", "guide_lint.json" not in urls, str(list(urls.keys())))
        details_names = {d["name"] for d in server._artifact_details(job, avail)}
        check("route/not-in-details", "guide_lint.json" not in details_names, str(details_names))
        # Unknown / traversal-ish names still 404 (HTTPException) via the dict path.
        try:
            server._artifact_path(job, "../job.json")
            check("route/traversal-blocked", False, "no exception raised")
        except Exception as exc:
            check("route/traversal-blocked", exc.__class__.__name__ == "HTTPException", type(exc).__name__)


if __name__ == "__main__":
    test_clean_guide_completed()
    test_findings_recorded_not_failed()
    test_zero_findings_completed()
    test_lint_crash_degrades_safely()
    test_no_secret_fields()
    test_sibling_artifacts_untouched()
    test_artifact_route_safe()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Guide lint artifact tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
