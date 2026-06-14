#!/usr/bin/env python3
"""Focused tests for applying material page selections to the visual manifest (Slice 82).

Two layers, both synthetic — no real PDFs/images/DOCX, no OCR, no providers, no
network, no Chromium:

* **Pure builder + helper** — drives ``build_visual_assets_manifest(..., page_filters=...)``
  and ``page_is_in_material_selection`` with synthetic source dicts. Asserts that an
  active filter drops candidates from excluded source pages, that absent/None filters
  are byte-identical to before Slice 82, that a missing/invalid ``source_page`` drops
  conservatively, that an all-dropped source degrades to a closed warning (not a
  failure), and that no smuggled path/text/base64/token can survive into the manifest.
* **Integration** — drives ``pipeline.run_llm_job._attach_sources`` with
  ``extract_file`` / ``pdf_source_metadata`` / the downstream writers STUBBED, capturing
  the ``page_filters`` passed to ``write_visual_assets_manifest``. Asserts precedence
  (per-attachment over global), that the visual filter is the SAME effective set as
  Slice 81's extraction set (so it never keeps a page ``page_selections`` excluded nor
  expands beyond it), and that a deferred / non-PDF / absent selection yields no filter.

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
from pipeline.page_selection_model import (
    VISUAL_FILTER_DROPPED,
    VISUAL_FILTER_NO_MATCHING_PAGES,
    VISUAL_FILTER_PAGE_UNKNOWN,
    page_is_in_material_selection,
)
from pipeline.visual_assets_manifest import build_visual_assets_manifest

# Leak detection over the serialized manifest. The manifest must never echo a raw
# path, document/OCR/caption text, image bytes, base64/data URI, provider payload,
# token, or URL — only its own closed vocabulary, ints, floats, None, and asset ids.
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\|[A-Za-z]:\\)")
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)


def _page(n: int, *, images: int = 1, **extra) -> dict:
    page = {
        "page": n,
        "image_object_count": images,
        "drawing_object_count": 0,
        "has_images": images > 0,
        "has_drawings": False,
        "page_width": 600.0,
        "page_height": 800.0,
        "classification": "embedded_text",
        "ocr_route_action": "use_embedded_text",
    }
    page.update(extra)
    return page


def _source(pages: list) -> dict:
    return {"pages": pages}


# ── helper: page_is_in_material_selection ────────────────────────────────────

def test_helper_no_active_filter_keeps() -> None:
    d = page_is_in_material_selection(5, None)
    check("helper None filter -> kept", d == {"kept": True, "status": None}, str(d))


def test_helper_in_set_keeps() -> None:
    d = page_is_in_material_selection(3, {1, 3, 4})
    check("helper in-set -> kept, no status", d == {"kept": True, "status": None}, str(d))


def test_helper_out_of_set_filtered() -> None:
    d = page_is_in_material_selection(2, {1, 3, 4})
    check("helper out-of-set -> filtered", d == {"kept": False, "status": VISUAL_FILTER_DROPPED}, str(d))


def test_helper_unknown_page_dropped() -> None:
    for bad in (0, None, -1, "x"):
        d = page_is_in_material_selection(bad, {1, 2})
        check(f"helper unknown page {bad!r} -> page_unknown drop",
              d == {"kept": False, "status": VISUAL_FILTER_PAGE_UNKNOWN}, str(d))


def test_helper_empty_allowed_drops_all() -> None:
    d = page_is_in_material_selection(1, set())
    check("helper empty allowed -> filtered", d == {"kept": False, "status": VISUAL_FILTER_DROPPED}, str(d))


# ── pure builder: absent filter preserves existing behaviour ─────────────────

def test_builder_no_filter_byte_identical() -> None:
    sources = [_source([_page(1), _page(2, images=0), _page(3)])]
    base = build_visual_assets_manifest(sources)
    none_filter = build_visual_assets_manifest(sources, page_filters=None)
    all_none = build_visual_assets_manifest(sources, page_filters=[None])
    # page 2 has no image/drawing signal => not a candidate; pages 1 & 3 are.
    check("no filter -> 2 candidates", base["summary"]["asset_count"] == 2, str(base["summary"]))
    check("page_filters=None identical", none_filter == base)
    check("page_filters=[None] identical to base", all_none["assets"] == base["assets"])
    check("no filter -> empty warnings", base["warnings"] == [])
    check("no filter -> filtered count 0", base["summary"]["pages_filtered_by_material_selection"] == 0)


# ── pure builder: include / exclude effect via effective allowed set ─────────

def test_builder_include_keeps_only_allowed() -> None:
    sources = [_source([_page(1), _page(2), _page(3)])]
    m = build_visual_assets_manifest(sources, page_filters=[{1, 3}])
    pages = sorted(a["source_page"] for a in m["assets"])
    check("include -> only pages {1,3} survive", pages == [1, 3], str(pages))
    check("include -> dropped count 1", m["summary"]["pages_filtered_by_material_selection"] == 1)
    check("include -> filtered warning", m["warnings"] == [VISUAL_FILTER_DROPPED], str(m["warnings"]))
    check("include -> still completed", m["status"] == "completed")


def test_builder_exclude_removes_page() -> None:
    # Effective allowed set after an exclude of page 2 within universe {1,2,3,4}.
    sources = [_source([_page(1), _page(2), _page(3), _page(4)])]
    m = build_visual_assets_manifest(sources, page_filters=[{1, 3, 4}])
    pages = sorted(a["source_page"] for a in m["assets"])
    check("exclude -> page 2 removed", pages == [1, 3, 4], str(pages))


def test_builder_cannot_keep_outside_universe() -> None:
    # page_selections universe is {1,2,3}; a material include of {1,2,5} intersects to
    # {1,2} (Slice 81). Page 5 is not even a candidate here, but prove that even if a
    # source carried a page-5 candidate, an effective set of {1,2} drops it.
    sources = [_source([_page(1), _page(2), _page(5)])]
    m = build_visual_assets_manifest(sources, page_filters=[{1, 2}])
    pages = sorted(a["source_page"] for a in m["assets"])
    check("universe-bounded -> {1,2} only (5 dropped)", pages == [1, 2], str(pages))


# ── pure builder: missing/invalid source_page degrades conservatively ────────

def test_builder_unknown_source_page_dropped() -> None:
    # page=0 => _safe_page_number coerces to 0 (unknown); under an active filter the
    # conservative rule drops it so an unverifiable page can never surface a visual.
    sources = [_source([_page(0), _page(1)])]
    m = build_visual_assets_manifest(sources, page_filters=[{1}])
    pages = sorted(a["source_page"] for a in m["assets"])
    check("unknown page dropped under filter", pages == [1], str(pages))
    check("unknown page -> page_unknown warning", VISUAL_FILTER_PAGE_UNKNOWN in m["warnings"], str(m["warnings"]))


def test_builder_unknown_source_page_kept_without_filter() -> None:
    sources = [_source([_page(0), _page(1)])]
    m = build_visual_assets_manifest(sources, page_filters=[None])
    check("no filter -> unknown page kept", m["summary"]["asset_count"] == 2, str(m["summary"]))
    check("no filter -> no warnings", m["warnings"] == [])


# ── pure builder: all candidates filtered out is safe ────────────────────────

def test_builder_all_filtered_is_safe() -> None:
    sources = [_source([_page(1), _page(2)])]
    m = build_visual_assets_manifest(sources, page_filters=[set()])  # empty allowed set
    check("all filtered -> no assets", m["assets"] == [], str(m["assets"]))
    check("all filtered -> completed (not failed)", m["status"] == "completed")
    check("all filtered -> no_matching_pages warning",
          VISUAL_FILTER_NO_MATCHING_PAGES in m["warnings"], str(m["warnings"]))
    check("all filtered -> dropped count 2", m["summary"]["pages_filtered_by_material_selection"] == 2)


# ── pure builder: per-source independence ────────────────────────────────────

def test_builder_per_source_independent() -> None:
    sources = [_source([_page(1), _page(2)]), _source([_page(1), _page(2)])]
    # Source 0 filtered to {1}; source 1 unfiltered (None).
    m = build_visual_assets_manifest(sources, page_filters=[{1}, None])
    check("per-source -> 3 assets (1 dropped from source0)", m["summary"]["asset_count"] == 3, str(m["summary"]))
    check("per-source -> dropped count 1", m["summary"]["pages_filtered_by_material_selection"] == 1)


def test_builder_short_page_filters_list_safe() -> None:
    # Fewer filter entries than sources => later sources are unfiltered (None).
    sources = [_source([_page(1), _page(2)]), _source([_page(3)])]
    m = build_visual_assets_manifest(sources, page_filters=[{1}])
    pages = sorted(a["source_page"] for a in m["assets"])
    check("short filter list -> source1 unfiltered", pages == [1, 3], str(pages))


# ── pure builder: no leak even from hostile records ──────────────────────────

def test_builder_no_leak_with_filter() -> None:
    leak_path = "/home/secret/real_document.pdf"
    leak_uri = "data:image/png;base64,QUJDREVG"
    leak_token = "sk-ABCDEFGHIJKLMNOP0123456789"
    sources = [
        _source([
            _page(1, caption=leak_path, raw_text="document body text", extra_url="https://evil.example/x"),
            _page(2, image_ref=leak_uri, token=leak_token, ocr_text="scanned words"),
        ])
    ]
    m = build_visual_assets_manifest(sources, page_filters=[{1}])
    blob = json.dumps(m)
    check("no leak: path absent", not PATHLIKE.search(blob), "pathlike survived")
    check("no leak: data URI absent", not DATAURI.search(blob), "data uri survived")
    check("no leak: key absent", not KEYLIKE.search(blob), "key survived")
    check("no leak: caption text absent", "real_document" not in blob and "document body" not in blob)
    check("no leak: ocr text absent", "scanned words" not in blob)
    check("no leak: url absent", "evil.example" not in blob)
    # warnings only ever contain closed tokens.
    closed = {VISUAL_FILTER_DROPPED, VISUAL_FILTER_PAGE_UNKNOWN, VISUAL_FILTER_NO_MATCHING_PAGES}
    check("warnings are closed tokens", all(w in closed for w in m["warnings"]), str(m["warnings"]))


# ── integration: _attach_sources passes the right page_filters ───────────────

class _IntegHarness:
    """Drive _attach_sources with extract_file + downstream writers stubbed,
    capturing the page_filters handed to write_visual_assets_manifest."""

    def __init__(self) -> None:
        self.page_filters = None
        self.manifest_called = False
        self._tmp = Path(tempfile.mkdtemp(prefix="s82-"))
        self.job: Job | None = None
        self._orig: dict = {}

    def __enter__(self) -> "_IntegHarness":
        def fake_extract_file(path, pages=None):
            text = "" if (pages is not None and len(pages) == 0) else "synthetic-extracted-text"
            return ExtractionResult(text=text, mode="text", warnings=[], metadata={"pages": []})

        def fake_meta(*_a, **_k):
            # Truthy synthetic source => appended to extraction_metadata_sources.
            return {"filename": "f", "pages": []}

        def fake_write_manifest(job, sources, extracted_assets=None, *, page_filters=None):
            self.manifest_called = True
            self.page_filters = page_filters

        self._orig = {
            "extract_file": rlj.extract_file,
            "pdf_source_metadata": rlj.pdf_source_metadata,
            "write_visual_assets_manifest": rlj.write_visual_assets_manifest,
            "write_extraction_metadata": rlj.write_extraction_metadata,
            "_extract_local_figures": rlj._extract_local_figures,
            "_write_source_coverage_report_safely": rlj._write_source_coverage_report_safely,
            "_read_visual_manifest_for_scoring": rlj._read_visual_manifest_for_scoring,
            "write_visual_asset_scoring_report": rlj.write_visual_asset_scoring_report,
            "write_visual_replacement_plan_report": rlj.write_visual_replacement_plan_report,
        }
        rlj.extract_file = fake_extract_file
        rlj.pdf_source_metadata = fake_meta
        rlj.write_visual_assets_manifest = fake_write_manifest
        rlj.write_extraction_metadata = lambda *a, **k: None
        rlj._extract_local_figures = lambda *a, **k: []
        rlj._write_source_coverage_report_safely = lambda *a, **k: None
        rlj._read_visual_manifest_for_scoring = lambda *a, **k: None
        rlj.write_visual_asset_scoring_report = lambda *a, **k: None
        rlj.write_visual_replacement_plan_report = lambda *a, **k: None
        return self

    def __exit__(self, *exc) -> None:
        for name, fn in self._orig.items():
            setattr(rlj, name, fn)
        shutil.rmtree(self._tmp, ignore_errors=True)
        if self.job is not None:
            shutil.rmtree(self.job.dir, ignore_errors=True)

    def attachment(self, name: str) -> "rlj.AttachmentSource":
        p = self._tmp / name
        p.write_bytes(b"%PDF-stub-bytes" if name.lower().endswith(".pdf") else b"text bytes")
        return rlj.AttachmentSource(path=p, filename=name)

    def run(self, attachments, **kwargs):
        self.page_filters = None
        self.manifest_called = False
        job = Job(id=job_manager._timestamp_id(), root=self._tmp / "jobs")
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job.id, "status": "created", "path_mode": "generate",
                             "title": "S82", "mode": "study_guide"})
        self.job = job
        rlj._attach_sources(job, "Base source.", attachments, **kwargs)


def _env(attachments: dict) -> dict:
    return {"version": 1, "attachments": attachments, "warnings": []}


def test_integ_absent_no_filter() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("a.pdf")])
        check("absent -> manifest called", h.manifest_called)
        check("absent -> page_filters [None]", h.page_filters == [None], str(h.page_filters))


def test_integ_global_include_filter() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("a.pdf")],
              material_page_selection={"mode": "include", "include_pages": [1, 3]})
        check("global include -> filter [{1,3}]", h.page_filters == [{1, 3}], str(h.page_filters))


def test_integ_per_attachment_overrides_global() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("a.pdf"), h.attachment("b.pdf")],
              material_page_selection={"mode": "include", "include_pages": [9]},
              material_page_selections=_env({
                  "attachment_0": {"mode": "include", "include_pages": [1, 2]},
              }))
        # attachment_0 uses its per-attachment include {1,2}; attachment_1 falls back
        # to the global include {9}.
        check("precedence -> [{1,2}, {9}]", h.page_filters == [{1, 2}, {9}], str(h.page_filters))


def test_integ_intersects_existing_page_selections() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("deck.pdf")],
              page_selections={"deck.pdf": [[1, 4]]},
              material_page_selection={"mode": "exclude", "exclude_pages": [2]})
        check("exclude within universe -> filter [{1,3,4}]", h.page_filters == [{1, 3, 4}], str(h.page_filters))


def test_integ_include_cannot_expand_universe() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("deck.pdf")],
              page_selections={"deck.pdf": [[1, 3]]},
              material_page_selection={"mode": "include", "include_pages": [1, 2, 5]})
        # 5 is outside the page_selections universe {1,2,3}; the visual filter is the
        # intersection {1,2}, never expanding beyond what page_selections allowed.
        check("include bounded by universe -> filter [{1,2}]", h.page_filters == [{1, 2}], str(h.page_filters))


def test_integ_deferred_selection_no_filter() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("a.pdf")],
              material_page_selection={"mode": "exclude", "exclude_pages": [2]})
        # exclude with no known universe defers (extraction unchanged) => no visual
        # filter either, so existing manifest behaviour is preserved.
        check("deferred -> page_filters [None]", h.page_filters == [None], str(h.page_filters))


def test_integ_no_matching_pages_empty_filter() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("deck.pdf")],
              page_selections={"deck.pdf": [[1, 2]]},
              material_page_selection={"mode": "exclude", "exclude_pages": [1, 2]})
        # Everything excluded within the universe => empty effective set; the manifest
        # builder turns this into a closed no_matching_pages warning (tested above).
        check("all excluded -> filter [set()]", h.page_filters == [set()], str(h.page_filters))


def test_integ_non_pdf_no_source_entry() -> None:
    with _IntegHarness() as h:
        h.run([h.attachment("notes.txt")],
              material_page_selection={"mode": "include", "include_pages": [1]})
        # Non-PDF attachments contribute no extraction-metadata source, so there is no
        # filter entry (and the manifest writer is not even invoked here).
        check("non-pdf -> manifest not called", not h.manifest_called)
        check("non-pdf -> page_filters None/empty", h.page_filters in (None, []), str(h.page_filters))


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
