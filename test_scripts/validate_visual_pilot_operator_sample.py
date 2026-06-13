#!/usr/bin/env python3
"""Slice 59 — manual, opt-in operator validation harness for the single-figure pilot.

This is a **manual validation harness / runbook tool**, NOT part of normal smoke and
NOT production behavior. It changes nothing in the app: it only *drives* the existing
pipeline helpers (local figure extraction -> manifest/scoring/plan -> markdown image
insertion -> render -> export) end-to-end so an operator can validate the **current
single-figure visual pilot** against a real, **non-private** sample PDF when one is
available. Slice 58 proved the stitched path with synthetic temp data; this slice makes
the same path safe and repeatable on a real sample.

Two modes:

  * ``--pdf <non-private-sample.pdf> [--output-dir <dir>]`` — real operator run. Drives
    the genuine pipeline over the supplied PDF. Refuses to run without ``--pdf``.
  * ``--self-test`` — synthetic dry run. Uses runtime-generated non-private temp data
    only (no operator PDF, no providers/models/cloud), exercises the SAME validation +
    summary code, and verifies the summary schema and no-leak behavior. It does NOT
    pretend to be a real operator PDF validation.

Safety / no-leak (enforced for BOTH modes):
  * Never prints the PDF path, basename, document text, OCR text, image bytes, base64,
    data URIs, tokens, headers, model/mmproj/executable paths, raw argv, or full URLs.
  * Emits only a fixed, closed-vocabulary summary (the ten fields below) plus closed
    closed-vocab step/skip markers. A final sweep scans every pipeline-derived string.
  * Exceptions are sanitized to closed ``failure_category`` tokens (only an exception
    *type name* is ever surfaced, never a message that could carry a path / private text).
  * All working files live under a temp/output directory; nothing is committed.

Single-figure boundary (unchanged): at most ONE ``fitz_local`` ``extracted_figure`` is
inserted, the ref is exactly ``assets/<slug>.png``, and no multi-figure / Chandra /
Mistral / Gemini / cloud / model / llama-server path is touched.

Run:

    python test_scripts/validate_visual_pilot_operator_sample.py --self-test
    python test_scripts/validate_visual_pilot_operator_sample.py --pdf "<non-private-sample.pdf>"

See docs/VISUAL_PILOT_OPERATOR_VALIDATION.md for the runbook.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import struct
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# --- Closed vocabularies ----------------------------------------------------------
STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

FAILURE_NONE = "none"
FAILURE_PDF_UNREADABLE = "pdf_unreadable"
FAILURE_EXTRACTION_DEP = "extraction_dependency_unavailable"
FAILURE_NO_SAFE_FIGURE = "no_safe_figure_found"
FAILURE_INSERTION = "insertion_failed"
FAILURE_RENDER = "render_failed"
FAILURE_EXPORT = "export_failed"
FAILURE_HARNESS = "harness_error"

FAILURE_VOCAB = frozenset({
    FAILURE_NONE, FAILURE_PDF_UNREADABLE, FAILURE_EXTRACTION_DEP, FAILURE_NO_SAFE_FIGURE,
    FAILURE_INSERTION, FAILURE_RENDER, FAILURE_EXPORT, FAILURE_HARNESS,
})

WARN_NO_FIGURE = "no_extracted_figure"
WARN_EXTRACTION_DEP = "extraction_dependency_unavailable"
WARN_HTML_SKIPPED = "html_render_skipped_no_dependency"
WARN_PDF_SKIPPED = "pdf_render_skipped_no_chromium"
WARN_DOCX_SKIPPED = "docx_render_skipped_no_dependency"
WARN_EXPORT_SKIPPED = "export_skipped_no_fastapi"
WARN_MULTI_FIGURE = "multiple_figures_present_one_inserted"

WARNING_VOCAB = frozenset({
    WARN_NO_FIGURE, WARN_EXTRACTION_DEP, WARN_HTML_SKIPPED, WARN_PDF_SKIPPED,
    WARN_DOCX_SKIPPED, WARN_EXPORT_SKIPPED, WARN_MULTI_FIGURE,
})

SUMMARY_FIELDS = (
    "status", "pilot_inserted", "safe_asset_ref_present", "html_render_ok",
    "pdf_render_ok", "docx_render_ok", "export_zip_ok", "export_png_included",
    "warnings", "failure_category",
)

# --- No-leak sweep (forbidden value shapes) ---------------------------------------
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/opt/|/tmp/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
DATAURI = re.compile(r"data:[^;]+;base64,", re.IGNORECASE)
GGUFLIKE = re.compile(r"\.gguf\b|mmproj|llama-server", re.IGNORECASE)
ARGVLIKE = re.compile(r"--\w+\s+\S")

_LEAK_PATTERNS = (
    ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
    ("socket", SOCKETLIKE), ("datauri", DATAURI), ("gguf", GGUFLIKE), ("argv", ARGVLIKE),
)

# Pipeline-derived strings collected for the final no-leak sweep. Only genuine outputs
# of the chain are recorded — never the banner / help text (which legitimately carries a
# placeholder ``--pdf`` command template).
_OUTPUTS: list[str] = []

BASE_MD = "# Operator Sample Guide\n\nGenerated for visual-pilot validation only.\n"


def _record(text) -> str:
    if isinstance(text, str):
        _OUTPUTS.append(text)
    return text


def _sweep_one(text) -> str | None:
    if not isinstance(text, str):
        return None
    for label, pat in _LEAK_PATTERNS:
        if pat.search(text):
            return label
    return None


def _emit(token: str) -> None:
    """Print a single closed-vocabulary status marker (no free text, no paths)."""
    print(f"[step] {token}")


# --- Synthetic PNG builder (stdlib only; self-test data, never committed) ----------
def _build_png(width: int = 2, height: int = 2) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# --- Summary ----------------------------------------------------------------------
def _new_summary() -> dict:
    return {
        "status": STATUS_SKIPPED,
        "pilot_inserted": False,
        "safe_asset_ref_present": False,
        "html_render_ok": None,
        "pdf_render_ok": None,
        "docx_render_ok": None,
        "export_zip_ok": None,
        "export_png_included": None,
        "warnings": [],
        "failure_category": FAILURE_NONE,
    }


def _warn(summary: dict, token: str) -> None:
    if token in WARNING_VOCAB and token not in summary["warnings"]:
        summary["warnings"].append(token)


def _set_failure(summary: dict, category: str) -> None:
    summary["status"] = STATUS_FAILED
    summary["failure_category"] = category


# --- Job construction --------------------------------------------------------------
def _new_job(output_dir: Path, job_id: str):
    from pipeline.job_manager import Job

    job = Job(id=job_id, root=output_dir)
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    # Per-job opt-in lives in the persisted manifest (the real Slice 55 switch).
    job._write_manifest({
        "id": job.id, "status": "completed", "title": "operator_sample",
        "visual_markdown_image_pilot": True,
    })
    return job


# --- Stage: prepare a real job from an operator PDF (genuine extraction path) -------
def _prepare_from_pdf(job, pdf_path: Path, summary: dict) -> bool:
    """Run the real fitz_local extractor + manifest/scoring/plan writers.

    Returns True when at least one safe extracted_figure manifest is ready. Never
    raises a path/private message: failures map to closed failure categories.
    """
    try:
        from pipeline.visual_asset_extractor import extract_local_figures
        from pipeline.visual_assets_manifest import write_visual_assets_manifest
        from pipeline.visual_asset_scoring import write_visual_asset_scoring_report
        from pipeline.visual_replacement_planner import write_visual_replacement_plan_report
    except Exception as exc:  # PyMuPDF / pipeline deps unavailable
        _emit(f"extraction_dependency_unavailable:{type(exc).__name__}")
        _warn(summary, WARN_EXTRACTION_DEP)
        summary["status"] = STATUS_SKIPPED
        return False

    try:
        import fitz  # noqa: F401
    except Exception as exc:
        _emit(f"extraction_dependency_unavailable:{type(exc).__name__}")
        _warn(summary, WARN_EXTRACTION_DEP)
        summary["status"] = STATUS_SKIPPED
        return False

    try:
        extracted = extract_local_figures(
            pdf_path, assets_dir=job.assets_dir, source_index=0,
            pages=None, remaining_budget=200,
        )
    except Exception as exc:
        _emit(f"pdf_unreadable:{type(exc).__name__}")
        _set_failure(summary, FAILURE_PDF_UNREADABLE)
        return False

    figure_count = sum(
        1 for a in (extracted or [])
        if isinstance(a, dict) and a.get("asset_type") == "extracted_figure"
    )
    _emit(f"extracted_figures:{ '0' if figure_count == 0 else 'one_or_more' }")
    if figure_count == 0:
        _warn(summary, WARN_NO_FIGURE)
        summary["status"] = STATUS_SKIPPED
        summary["failure_category"] = FAILURE_NONE
        return False
    if figure_count > 1:
        _warn(summary, WARN_MULTI_FIGURE)

    try:
        # sources=[] -> figures-only manifest (page_visual_signals are not pilot
        # candidates). Each figure is re-sanitised field-by-field by the manifest.
        write_visual_assets_manifest(job, [], extracted)
        manifest = json.loads(job.visual_assets_manifest_json.read_text(encoding="utf-8"))
        write_visual_asset_scoring_report(job, manifest)
        write_visual_replacement_plan_report(
            job, json.loads(job.visual_asset_scoring_json.read_text(encoding="utf-8"))
            if job.visual_asset_scoring_json.exists() else None,
        )
    except Exception as exc:
        _emit(f"harness_error:{type(exc).__name__}")
        _set_failure(summary, FAILURE_HARNESS)
        return False
    return True


# --- Stage: prepare a synthetic job (self-test; no fitz, no operator PDF) ----------
def _prepare_synthetic(job, summary: dict) -> bool:
    slug = "s00_page_0003_figure_01"
    asset_ref = f"assets/{slug}.png"
    (job.assets_dir / f"{slug}.png").write_bytes(_build_png())
    manifest = {
        "version": 1, "kind": "visual_assets_manifest", "status": "completed",
        "source": "extraction_metadata.json",
        "assets": [{
            "asset_id": slug, "source_page": 3, "asset_type": "extracted_figure",
            "bbox": [0.0, 0.0, 10.0, 10.0], "caption": None,
            "source_provider": "fitz_local", "image_ref": asset_ref,
            "scores": {}, "signals": {}, "warnings": [],
        }],
        "summary": {"asset_count": 1}, "warnings": [],
    }
    job.save_text(job.visual_assets_manifest_json, json.dumps(manifest, indent=2) + "\n")
    _emit("synthetic_manifest_ready")
    return True


# --- Stage: insertion + render + export over a prepared job ------------------------
def _validate_prepared_job(job, output_dir: Path, summary: dict) -> None:
    from pipeline import visual_markdown_insertion as vmi

    # --- insertion (the genuine pilot, both gates honoured) ---
    old = os.environ.get(vmi.ENABLE_ENV)
    os.environ[vmi.ENABLE_ENV] = "1"
    try:
        try:
            produced, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        except Exception as exc:
            _emit(f"insertion_failed:{type(exc).__name__}")
            _set_failure(summary, FAILURE_INSERTION)
            return
    finally:
        if old is None:
            os.environ.pop(vmi.ENABLE_ENV, None)
        else:
            os.environ[vmi.ENABLE_ENV] = old

    _record(produced)
    inserted = info.get("status") == vmi.STATUS_INSERTED
    summary["pilot_inserted"] = bool(inserted)
    if not inserted:
        _emit("no_safe_figure_found")
        # A real run that extracted a figure but inserted nothing is a genuine miss.
        summary["status"] = STATUS_SKIPPED
        summary["failure_category"] = FAILURE_NO_SAFE_FIGURE
        return

    refs = vmi.extract_visual_pilot_asset_refs(produced)
    one_image = produced.count("![") == 1
    safe_ref = bool(refs) and len(refs) == 1 and one_image and re.fullmatch(
        r"assets/[A-Za-z0-9_]+\.png", refs[0]
    ) is not None
    summary["safe_asset_ref_present"] = safe_ref
    _emit("safe_asset_ref_present" if safe_ref else "safe_asset_ref_absent")

    try:
        job.save_clean_md(produced, source="slice59_operator_validation")
    except Exception as exc:
        _emit(f"insertion_failed:{type(exc).__name__}")
        _set_failure(summary, FAILURE_INSERTION)
        return

    # --- HTML render ---
    try:
        from pipeline.html_renderer import render_markdown_file
    except Exception:
        _warn(summary, WARN_HTML_SKIPPED)
        _emit("html_render_skipped_no_dependency")
    else:
        try:
            html = _record(render_markdown_file(job.clean_md))
            summary["html_render_ok"] = ("<img" in html and "/home/" not in html
                                         and "file://" not in html)
            _emit("html_render_ok" if summary["html_render_ok"] else "html_render_unexpected")
        except Exception as exc:
            summary["html_render_ok"] = False
            _emit(f"render_failed:{type(exc).__name__}")
            _set_failure(summary, FAILURE_RENDER)

    # --- PDF render ---
    try:
        from pipeline.pdf_renderer import render_pdf, _find_chromium
    except Exception:
        _warn(summary, WARN_PDF_SKIPPED)
        _emit("pdf_render_skipped_no_chromium")
    else:
        if _find_chromium() is None:
            _warn(summary, WARN_PDF_SKIPPED)
            _emit("pdf_render_skipped_no_chromium")
        else:
            out_pdf = output_dir / "operator_final.pdf"
            try:
                render_pdf(job.clean_md, out_pdf)
                summary["pdf_render_ok"] = out_pdf.is_file() and out_pdf.stat().st_size > 0
                _emit("pdf_render_ok" if summary["pdf_render_ok"] else "pdf_render_empty")
            except Exception as exc:
                summary["pdf_render_ok"] = False
                _emit(f"render_failed:{type(exc).__name__}")
                _set_failure(summary, FAILURE_RENDER)

    # --- DOCX render ---
    try:
        import docx  # noqa: F401
        from pipeline.docx_renderer import render_docx
    except Exception:
        _warn(summary, WARN_DOCX_SKIPPED)
        _emit("docx_render_skipped_no_dependency")
    else:
        out_docx = output_dir / "operator_final.docx"
        try:
            render_docx(job.clean_md, out_docx, title="Operator Sample Guide")
            summary["docx_render_ok"] = out_docx.is_file() and out_docx.stat().st_size > 0
            _emit("docx_render_ok" if summary["docx_render_ok"] else "docx_render_empty")
        except Exception as exc:
            summary["docx_render_ok"] = False
            _emit(f"render_failed:{type(exc).__name__}")
            _set_failure(summary, FAILURE_RENDER)

    # --- Export ZIP portability ---
    _validate_export(job, summary)

    if summary["status"] != STATUS_FAILED:
        summary["status"] = STATUS_OK


def _validate_export(job, summary: dict) -> None:
    try:
        from fastapi import HTTPException  # noqa: F401
        from api import server
    except Exception:
        _warn(summary, WARN_EXPORT_SKIPPED)
        _emit("export_skipped_no_fastapi")
        return

    # A PDF artifact must exist for the bundle gate; synthesize a tiny one if the
    # Chromium render did not run, so export portability can still be exercised.
    if not job.final_pdf.exists():
        job.final_pdf.write_bytes(b"%PDF-1.4 operator harness placeholder")

    original = server._get_job

    def fake_get_job(raw_id):
        if str(raw_id) == str(job.id):
            return job
        from fastapi import HTTPException as _H
        raise _H(status_code=404, detail="Job not found.")

    server._get_job = fake_get_job
    try:
        resp = server.export_bundle(
            server.BundleRequest(job_ids=[str(job.id)], artifacts=["pdf", "markdown"])
        )
    except Exception as exc:
        summary["export_zip_ok"] = False
        _emit(f"export_failed:{type(exc).__name__}")
        _set_failure(summary, FAILURE_EXPORT)
        return
    finally:
        server._get_job = original

    try:
        with zipfile.ZipFile(io.BytesIO(resp.body)) as zf:
            names = zf.namelist()
            manifest_text = _record(zf.read("manifest.json").decode("utf-8"))
        png_entries = [n for n in names if n.lower().endswith(".png")]
        summary["export_zip_ok"] = True
        summary["export_png_included"] = (
            len(png_entries) == 1
            and all("/assets/" in p and not p.startswith("/") and ".." not in p
                    for p in png_entries)
        )
        # The bundle index must record only the safe relative ref, no bytes/paths.
        entry = json.loads(manifest_text)["jobs"][0]
        ref = entry.get("visual_pilot_asset")
        if ref is not None and re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", str(ref)) is None:
            summary["export_png_included"] = False
        _emit("export_zip_ok")
        _emit("export_png_included" if summary["export_png_included"] else "export_png_absent")
    except Exception as exc:
        summary["export_zip_ok"] = False
        _emit(f"export_failed:{type(exc).__name__}")
        _set_failure(summary, FAILURE_EXPORT)


# --- Summary printing + final sweep ------------------------------------------------
def _print_summary(summary: dict) -> str:
    ordered = {k: summary[k] for k in SUMMARY_FIELDS}
    text = json.dumps(ordered, indent=2, sort_keys=False)
    print("[summary]")
    print(text)
    return text


def _final_sweep(summary_text: str) -> bool:
    """True when no pipeline-derived output (incl. the summary) leaks a forbidden shape."""
    leaks: list[str] = []
    for blob in _OUTPUTS + [summary_text]:
        found = _sweep_one(blob)
        if found:
            leaks.append(found)
    if leaks:
        print(f"[leak] forbidden shapes detected: {','.join(sorted(set(leaks)))}")
        return False
    print("[ok] no-leak sweep clean")
    return True


# --- Modes -------------------------------------------------------------------------
def run_operator(pdf_arg: str, output_dir_arg: str | None) -> int:
    print("[warning] The sample PDF MUST be non-private. Do NOT run recorded validation")
    print("[warning] on student / private / confidential material. Output is sanitized;")
    print("[warning] this harness never prints the PDF path, filename, or document text.")
    _emit("mode=operator_sample")

    summary = _new_summary()
    pdf_path = Path(pdf_arg).expanduser()
    if not pdf_path.is_file():
        # No path echoed — only a closed category.
        _emit("pdf_unreadable:missing_or_not_a_file")
        _set_failure(summary, FAILURE_PDF_UNREADABLE)
        text = _print_summary(summary)
        _final_sweep(text)
        return 1

    made_temp = output_dir_arg is None
    base = Path(tempfile.mkdtemp(prefix="visual_pilot_operator_")) if made_temp \
        else Path(output_dir_arg).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    _emit("outputs_dir=temporary" if made_temp else "outputs_dir=provided")

    try:
        job = _new_job(base, "operator_sample")
        if _prepare_from_pdf(job, pdf_path, summary):
            _validate_prepared_job(job, base, summary)
    except Exception as exc:
        _emit(f"harness_error:{type(exc).__name__}")
        _set_failure(summary, FAILURE_HARNESS)

    text = _print_summary(summary)
    clean = _final_sweep(text)
    if not clean:
        return 1
    return 0 if summary["status"] in {STATUS_OK, STATUS_SKIPPED} else 1


def run_self_test() -> int:
    _emit("mode=self_test")
    print("[note] self-test uses synthetic non-private temp data; this is NOT a real")
    print("[note] operator PDF validation (manual_operator_pdf_validation stays not_run).")

    failures = 0
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        summary = _new_summary()
        try:
            job = _new_job(base, "selftest_sample")
            _prepare_synthetic(job, summary)
            _validate_prepared_job(job, base, summary)
        except Exception as exc:
            _emit(f"harness_error:{type(exc).__name__}")
            _set_failure(summary, FAILURE_HARNESS)

        text = _print_summary(summary)

        # --- meta-assertions on the harness itself (schema + closed vocab + no leak) ---
        def meta(name: str, ok: bool) -> None:
            nonlocal failures
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")
            if not ok:
                failures += 1

        meta("summary_has_exactly_required_fields",
             set(json.loads(text).keys()) == set(SUMMARY_FIELDS))
        meta("status_in_closed_vocab",
             summary["status"] in {STATUS_OK, STATUS_SKIPPED, STATUS_FAILED})
        meta("failure_category_in_closed_vocab",
             summary["failure_category"] in FAILURE_VOCAB)
        meta("warnings_all_closed_vocab",
             all(w in WARNING_VOCAB for w in summary["warnings"]))
        meta("booleans_are_tristate",
             all(summary[k] in (True, False, None) for k in (
                 "pilot_inserted", "safe_asset_ref_present", "html_render_ok",
                 "pdf_render_ok", "docx_render_ok", "export_zip_ok", "export_png_included")))
        meta("pilot_inserted_in_self_test", summary["pilot_inserted"] is True)
        meta("safe_asset_ref_present_in_self_test", summary["safe_asset_ref_present"] is True)
        meta("no_leak_sweep_clean", _final_sweep(text))

    print(f"\nself-test: {'PASS' if failures == 0 else 'FAIL'} ({failures} failed)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manual, opt-in visual-pilot operator validation harness (Slice 59).",
        epilog='Examples: --self-test  |  --pdf "<non-private-sample.pdf>" --output-dir "<dir>"',
    )
    parser.add_argument("--pdf", metavar="<non-private-sample.pdf>",
                        help="Path to a NON-PRIVATE sample PDF (never printed/recorded).")
    parser.add_argument("--output-dir", metavar="<dir>",
                        help="Working/output directory (defaults to a temp dir).")
    parser.add_argument("--self-test", action="store_true",
                        help="Synthetic dry run; verifies schema + no-leak without an operator PDF.")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()
    if not args.pdf:
        _emit("refused:missing_pdf_argument")
        print("[refused] Provide --pdf <non-private-sample.pdf>, or use --self-test.")
        return 2
    return run_operator(args.pdf, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
