#!/usr/bin/env python3
"""Focused tests for applying material page selections to extraction (Slice 81).

Exercises ``pipeline.run_llm_job._attach_sources`` directly with ``extract_file``
STUBBED to capture the effective ``pages`` argument — no real PDFs, no OCR, no
providers, no network, no Chromium. Asserts:

* absent material selection => extraction unchanged (pages=None);
* existing page_selections page-range behaviour preserved;
* global vs per-attachment precedence;
* include intersects, exclude subtracts, never expanding beyond page_selections;
* exclude/all with no known universe degrades (deferred) and leaves pages unchanged;
* non-PDF selections are ignored safely;
* closed-vocabulary warnings only, no filenames/paths/text leaked.

Runs on host (no FastAPI needed).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}" + (f" - {detail}" if detail else ""))


import pipeline.run_llm_job as rlj
from pipeline import job_manager
from pipeline.extract import ExtractionResult
from pipeline.job_manager import Job

# Leak-detection over the per-attachment material_selection summary we persist.
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\|[A-Za-z]:\\)")
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
ALLOWED_TOKENS = {
    "material_selection_applied",
    "material_selection_no_matching_pages",
    "material_selection_non_pdf_ignored",
    "material_selection_universe_unknown",
    "material_selection_filtered_by_existing_page_selection",
}


def _envelope(attachments: dict) -> dict:
    return {"version": 1, "attachments": attachments, "warnings": []}


class _Harness:
    """One _attach_sources invocation with extract_file stubbed."""

    def __init__(self) -> None:
        self.captured: list = []
        self._orig_extract = rlj.extract_file
        self._orig_meta = rlj.pdf_source_metadata
        self._tmp = Path(tempfile.mkdtemp(prefix="s81-"))
        self.job: Job | None = None

    def __enter__(self) -> "_Harness":
        def fake_extract_file(path, pages=None):
            self.captured.append(pages)
            text = "" if (pages is not None and len(pages) == 0) else "synthetic-extracted-text"
            return ExtractionResult(text=text, mode="text", warnings=[], metadata=None)

        def fake_meta(*_a, **_k):
            return None  # force the "metadata unavailable" path (skips PDF metadata writers)

        rlj.extract_file = fake_extract_file
        rlj.pdf_source_metadata = fake_meta
        return self

    def __exit__(self, *exc) -> None:
        rlj.extract_file = self._orig_extract
        rlj.pdf_source_metadata = self._orig_meta
        shutil.rmtree(self._tmp, ignore_errors=True)
        if self.job is not None:
            shutil.rmtree(self.job.dir, ignore_errors=True)

    def attachment(self, name: str) -> "rlj.AttachmentSource":
        p = self._tmp / name
        p.write_bytes(b"%PDF-stub-bytes" if name.lower().endswith(".pdf") else b"text bytes")
        return rlj.AttachmentSource(path=p, filename=name)

    def run(self, attachments, **kwargs):
        self.captured.clear()
        # Build the job under a TEMP root (the repo ./jobs is container-owned and not
        # host-writable); Job derives every path from its root, so _attach_sources
        # works against the temp dir without touching real jobs.
        job = Job(id=job_manager._timestamp_id(), root=self._tmp / "jobs")
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job.id, "status": "created", "path_mode": "generate",
                             "title": "S81", "mode": "study_guide"})
        self.job = job
        augmented, report = rlj._attach_sources(job, "Base source.", attachments, **kwargs)
        return augmented, report


def _entry(report: dict, idx: int = 0) -> dict:
    return report["files"][idx]


# ── absent / existing-behaviour preservation ─────────────────────────────────

def test_absent_material_unchanged() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf")])
        check("absent -> pages None (all)", h.captured == [None], str(h.captured))
        check("absent -> no material_selection field", "material_selection" not in _entry(report))


def test_existing_page_selections_preserved() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("deck.pdf")],
                             page_selections={"deck.pdf": [[1, 3]]})
        check("page_selections -> pages {1,2,3}", h.captured == [{1, 2, 3}], str(h.captured))
        check("page_selections only -> no material field", "material_selection" not in _entry(report))


# ── global material selection ────────────────────────────────────────────────

def test_global_include_filters() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "include", "include_pages": [1, 3]})
        check("global include -> pages {1,3}", h.captured == [{1, 3}], str(h.captured))
        check("global include -> applied", _entry(report)["material_selection"]["status"] == "applied")


def test_global_exclude_no_universe_defers() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "exclude", "exclude_pages": [2]})
        check("exclude w/o universe -> pages unchanged (None)", h.captured == [None], str(h.captured))
        ms = _entry(report)["material_selection"]
        check("exclude w/o universe -> deferred", ms["status"] == "deferred")
        check("exclude w/o universe -> universe_unknown warning",
              ms["warnings"] == ["material_selection_universe_unknown"])


# ── interaction with existing page_selections (never expand) ──────────────────

def test_exclude_within_existing_universe() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("deck.pdf")],
                             page_selections={"deck.pdf": [[1, 4]]},
                             material_page_selection={"mode": "exclude", "exclude_pages": [2]})
        check("exclude within universe -> {1,3,4}", h.captured == [{1, 3, 4}], str(h.captured))
        check("exclude within universe -> filtered_by_existing",
              "material_selection_filtered_by_existing_page_selection" in _entry(report)["material_selection"]["warnings"])


def test_include_cannot_expand_beyond_existing() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("deck.pdf")],
                             page_selections={"deck.pdf": [[1, 3]]},
                             material_page_selection={"mode": "include", "include_pages": [1, 2, 5]})
        check("include intersects existing -> {1,2} (5 dropped)", h.captured == [{1, 2}], str(h.captured))


# ── per-attachment precedence ────────────────────────────────────────────────

def test_per_attachment_overrides_global() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "include", "include_pages": [1]},
                             material_page_selections=_envelope(
                                 {"attachment_0": {"mode": "include", "include_pages": [2]}}))
        check("per-attachment wins -> {2}", h.captured == [{2}], str(h.captured))


def test_per_attachment_default_all_overrides_global() -> None:
    # Per-attachment present but default-all => global NOT consulted => no filtering.
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "include", "include_pages": [1]},
                             material_page_selections=_envelope({"attachment_0": {"mode": "all"}}))
        check("per-attachment all overrides global -> pages None", h.captured == [None], str(h.captured))
        check("per-attachment all -> no material field (inactive)", "material_selection" not in _entry(report))


def test_second_attachment_key_mapping() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf"), h.attachment("b.pdf")],
                             material_page_selections=_envelope({
                                 "attachment_1": {"mode": "include", "include_pages": [7]}}))
        check("attachment_1 maps to 2nd attachment", h.captured == [None, {7}], str(h.captured))
        check("1st attachment untouched", "material_selection" not in _entry(report, 0))
        check("2nd attachment applied", _entry(report, 1)["material_selection"]["status"] == "applied")


# ── empty include / non-pdf / malformed ──────────────────────────────────────

def test_empty_include_extracts_nothing() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "include", "include_pages": []})
        check("empty include -> empty page set", h.captured == [set()], str(h.captured))
        ms = _entry(report)["material_selection"]
        check("empty include -> no_matching_pages warning",
              "material_selection_no_matching_pages" in ms["warnings"])


def test_non_pdf_ignored() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("notes.txt")],
                             material_page_selection={"mode": "include", "include_pages": [1]})
        check("non-pdf -> pages None (unchanged)", h.captured == [None], str(h.captured))
        ms = _entry(report)["material_selection"]
        check("non-pdf -> not_applicable", ms["status"] == "not_applicable")
        check("non-pdf -> non_pdf_ignored warning", ms["warnings"] == ["material_selection_non_pdf_ignored"])


def test_malformed_degrades() -> None:
    with _Harness() as h:
        # Unknown mode normalizes to all with no excludes => inactive => no filtering.
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "bogus"})
        check("malformed inactive -> pages None", h.captured == [None], str(h.captured))
        check("malformed inactive -> no material field", "material_selection" not in _entry(report))
    with _Harness() as h:
        # Malformed-but-active: invalid page values dropped, valid kept.
        _aug, report = h.run([h.attachment("a.pdf")],
                             material_page_selection={"mode": "include", "include_pages": ["x", 0, 2]})
        check("malformed active include -> {2}", h.captured == [{2}], str(h.captured))


# ── no-leak over the persisted material_selection summary ─────────────────────

def test_no_leak_summary() -> None:
    with _Harness() as h:
        _aug, report = h.run([h.attachment("private-source.pdf")],
                             page_selections={"private-source.pdf": [[1, 4]]},
                             material_page_selection={"mode": "exclude", "exclude_pages": [2]})
        ms = _entry(report)["material_selection"]
        blob = json.dumps(ms)
        check("summary: no pathlike", not PATHLIKE.search(blob), blob)
        check("summary: no keylike", not KEYLIKE.search(blob), blob)
        check("summary: closed tokens only",
              all(w in ALLOWED_TOKENS for w in ms["warnings"]), str(ms["warnings"]))
        check("summary: status closed", ms["status"] in {"applied", "deferred", "not_applicable"})
        check("summary: no filename in blob", "private-source.pdf" not in blob)


def main() -> int:
    test_absent_material_unchanged()
    test_existing_page_selections_preserved()
    test_global_include_filters()
    test_global_exclude_no_universe_defers()
    test_exclude_within_existing_universe()
    test_include_cannot_expand_beyond_existing()
    test_per_attachment_overrides_global()
    test_per_attachment_default_all_overrides_global()
    test_second_attachment_key_mapping()
    test_empty_include_extracts_nothing()
    test_non_pdf_ignored()
    test_malformed_degrades()
    test_no_leak_summary()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
