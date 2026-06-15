#!/usr/bin/env python3
"""Slice 100 — Full Material Coverage E2E **release validation** harness.

Run with:

    python test_scripts/test_full_material_coverage_release_validation.py

Deterministic, synthetic, validation-only. Slices 82–99 built the Full Material
Coverage phase: page/slide inclusion + exclusion, source coverage reporting,
visual planning + full non-table figure insertion, render/export ride-along, table
candidate + policy artifacts, table reconstruction prompt context, missing
visual/table guidance, coverage-aware generation prompt, guide quality report v2,
the JobDetails final Material Coverage panel, Ask Guide coverage grounding, and the
optional dual explanation mode.

This harness proves the **whole phase coheres end to end** on synthetic / sanitized
inputs — it does NOT add product behaviour, call an LLM/provider/model/cloud,
inspect a PDF/image, OCR anything, or reconstruct a table. It assembles one
synthetic scenario and walks the real already-merged pure helpers in release order:

    material page selections
      -> source coverage report
        -> visual inclusion plan
          -> FULL non-table figure insertion (into synthetic clean Markdown)
            -> render/export asset ride-along (uncapped, safe refs only)
              -> table candidate manifest
                -> table reconstruction policy (+ artifact-shaped check)
                  -> table reconstruction prompt context
                    -> missing visual/table guidance
                      -> coverage-aware generation guidance
                        -> guide quality report v2
                          -> Ask Guide coverage grounding
                            -> dual explanation mode

Every leaky field a hostile upstream record might carry is seeded into the inputs
as a synthetic *canary*, and a deep walk over every serialized stage output asserts
none survive. No real PDF / image / DOCX / ZIP fixture is added; the only generated
bytes are a 1x1 PNG written to a temp dir (never committed, never asserted on).

This is a signal/coherence checkpoint, not a semantic grader: it proves the chain's
safe counts/statuses/refs line up and stay leak-free, not that any guide is *good*.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- The phase under validation (only already-merged pure helpers) -----------
from pipeline.page_selection_model import (  # noqa: E402
    apply_material_selection_to_page_universe,
    page_is_in_material_selection,
)
from pipeline.source_coverage_report import build_source_coverage_report  # noqa: E402
from pipeline.visual_assets_manifest import build_visual_assets_manifest  # noqa: E402
from pipeline.visual_inclusion_planner import build_visual_inclusion_plan  # noqa: E402
from pipeline import visual_markdown_insertion as vmi  # noqa: E402
from pipeline.table_candidate_manifest import (  # noqa: E402
    build_table_candidates_manifest,
    table_policy_candidates,
)
from pipeline.table_reconstruction_policy import (  # noqa: E402
    build_table_reconstruction_policy,
)
from pipeline.table_reconstruction_prompt_context import (  # noqa: E402
    build_table_reconstruction_prompt_context,
)
from pipeline.missing_material_explainer import (  # noqa: E402
    build_missing_material_explainer_context,
)
from pipeline.coverage_aware_prompt_context import (  # noqa: E402
    build_coverage_aware_prompt_context,
)
from pipeline.guide_quality_report_v2 import build_guide_quality_report_v2  # noqa: E402
from pipeline.ask_coverage_grounding import build_ask_coverage_grounding  # noqa: E402
from pipeline.dual_explanation_prompt_context import (  # noqa: E402
    build_dual_explanation_prompt_context,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


# ---------------------------------------------------------------------------
# No-leak scanning. Canaries are seeded into every input and must never survive
# into any serialized output of the chain. The leak regexes are belt-and-braces
# for categories no canary string happens to cover.
# ---------------------------------------------------------------------------
SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
# Word-boundary anchored so a legitimate closed token like ``ask_coverage_grounding``
# (which contains the substring ``sk_coverage_grounding``) is not a false positive.
KEYLIKE = re.compile(r"\b(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\|\\\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")

# Synthetic forbidden values seeded into the inputs (never real data).
CANARY_FILENAME = "private-source.pdf"
CANARY_TITLE = "Quarterly Private Plan"
CANARY_DOC_TEXT = "raw document paragraph canary"
CANARY_OCR_TEXT = "raw OCR dump canary"
CANARY_CAPTION = "source caption text canary"
CANARY_TABLE_TEXT = "table cell text canary"
CANARY_IMAGE_REF = "assets/secret-canary-not-referenced.png"
CANARY_PATH = "/home/example/private-source.pdf"
CANARY_URL = "https://evil.example/leak-canary"
CANARY_DATA_URI = "data:image/png;base64,QQQQ"
CANARY_KEY = "sk_fullcoveragereleasecanary1234567890"
CANARY_MODEL = "secret-model.gguf"
CANARY_SOCKET = "/run/companion-canary.sock"
CANARY_ARGV = "--model"

FORBIDDEN_CANARIES = [
    CANARY_FILENAME,
    CANARY_TITLE,
    CANARY_DOC_TEXT,
    CANARY_OCR_TEXT,
    CANARY_CAPTION,
    CANARY_TABLE_TEXT,
    CANARY_IMAGE_REF,
    CANARY_PATH,
    CANARY_URL,
    CANARY_DATA_URI,
    CANARY_KEY,
    CANARY_MODEL,
    CANARY_SOCKET,
]


def scan_for_leak(node, path: str = ""):
    """Return a description of the first leak found, or None."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            found = scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            found = scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{path} (canary leaked: {canary})"
        # The only legitimate path-like token is a safe ``assets/<slug>.png`` ref.
        stripped = node.replace("assets/", "")
        if KEYLIKE.search(node):
            return f"{path} (credential-like value)"
        if PATHLIKE.search(stripped):
            return f"{path} (path-like value)"
        if URLLIKE.search(node):
            return f"{path} (URL-like value)"
        if DATA_OR_BASE64.search(node):
            return f"{path} (data/base64-like value)"
        if ARGV_OR_SOCKET.search(stripped):
            return f"{path} (argv/socket/model-like value)"
    return None


def no_leak(name: str, node) -> None:
    found = scan_for_leak(node)
    check(name, found is None, found or "")


def text_no_leak(name: str, text: str) -> None:
    # Markdown is a flat string; reuse the same scanner on a wrapped value.
    no_leak(name, text)


# ---------------------------------------------------------------------------
# Synthetic scenario. Two attachments addressed ONLY by safe positional ids.
# Material page exclusions active. Canaries seeded onto every record.
# ---------------------------------------------------------------------------

# A minimal valid 1x1 PNG; bytes exist only so the on-disk asset gate finds a file.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# page_selections universe per attachment (the MAX set material may filter).
UNIVERSE = {
    "attachment_0": [1, 2, 3, 4, 5, 6],
    "attachment_1": [1, 2, 3, 4],
}

# Per-attachment material selection: attachment_0 excludes pages 2 & 4;
# attachment_1 falls back to the global exclude of page 3.
PER_ATTACHMENT_MATERIAL = {
    "attachment_0": {"mode": "exclude", "exclude_pages": [2, 4]},
}
GLOBAL_MATERIAL = {"mode": "exclude", "exclude_pages": [3]}

# The job-request page-selection envelope the coverage/ask builders read.
MATERIAL_PAGE_SELECTIONS = {
    "version": 1,
    "attachment_0": {"mode": "exclude", "exclude_pages": [2, 4]},
}
JOB_REQUEST = {"material_page_selections": MATERIAL_PAGE_SELECTIONS}


def _seed_canaries() -> dict:
    """A bundle of leaky fields stuffed onto synthetic records (read, never echoed)."""
    return {
        "filename": CANARY_FILENAME,
        "title": CANARY_TITLE,
        "path": CANARY_PATH,
        "source_path": CANARY_PATH,
        "source_filename": CANARY_FILENAME,
        "text": CANARY_DOC_TEXT,
        "ocr_text": CANARY_OCR_TEXT,
        "caption": CANARY_CAPTION,
        "table_text": CANARY_TABLE_TEXT,
        "image_ref": CANARY_IMAGE_REF,
        "url": CANARY_URL,
        "data_uri": CANARY_DATA_URI,
        "api_key_value": CANARY_KEY,  # value canary under a non-secret key name
        "model_path": CANARY_MODEL,
        "socket_path": CANARY_SOCKET,
        "argv": [CANARY_ARGV, CANARY_MODEL],
    }


# --- Effective page sets after the material selection -------------------------


def _effective(key: str, material) -> set:
    res = apply_material_selection_to_page_universe(
        material, existing_allowed_pages=UNIVERSE[key]
    )
    return set(res["included_pages"]), res


# --- Visual manifest (non-table figures + table-like records) -----------------


def _figure_asset(slug: str, *, source_index: int, source_page: int) -> dict:
    rec = _seed_canaries()
    rec.update(
        {
            "asset_id": slug,
            "asset_type": "extracted_figure",
            "source_provider": "fitz_local",
            "source_index": source_index,
            "source_page": source_page,
            "image_ref": f"assets/{slug}.png",
            "bbox": [0.0, 0.0, 220.0, 200.0],
            "signals": {"crop_width_px": 220, "crop_height_px": 200},
            "warnings": [],
        }
    )
    return rec


def _table_record(
    slug: str,
    *,
    source_index: int,
    source_page: int,
    visual_type: str,
    has_text_layer,
    rows: int,
    columns: int,
    confidence: str = "high",
    header_cell_count: int = 2,
    unsafe: bool = False,
) -> dict:
    rec = _seed_canaries()
    signals = {
        "has_text_layer": has_text_layer,
        "rows": rows,
        "columns": columns,
        "header_cell_count": header_cell_count,
        "numeric_cell_count": rows * columns,
        "cell_text_count": rows * columns,
        "crop_width_px": 300,
        "crop_height_px": 200,
    }
    rec.update(
        {
            "asset_id": slug,
            "asset_type": "table_image",
            "visual_type": visual_type,
            "source_provider": "fitz_local",
            "source_index": source_index,
            "source_page": source_page,
            "image_ref": f"assets/{slug}.png",
            "confidence": confidence,
            "signals": signals,
        }
    )
    if unsafe:
        rec["unsafe"] = True
    return rec


# Figure slugs (4 useful non-table figures on materially-included pages of the
# two attachments). attachment_0 keeps pages 1,3,5,6 (2 & 4 excluded);
# attachment_1 keeps pages 1,2,4 (3 excluded).
FIGURE_SPECS = [
    ("s00_page_0001_figure_01", 0, 1),
    ("s00_page_0003_figure_01", 0, 3),
    ("s00_page_0005_figure_01", 0, 5),
    ("s01_page_0002_figure_01", 1, 2),
]
FIGURE_SLUGS = [s for (s, _i, _p) in FIGURE_SPECS]

# Table-like records. The manifest keeps the four readable/structured ones as
# candidates and skips the unsafe one (counted as unsafe-skipped). The policy then
# routes them to reconstruct / simplify / skip_unreadable / defer.
TABLE_SPECS = [
    # reconstruct_with_original: structured + text layer present + high confidence.
    dict(slug="s00_page_0001_table_01", source_index=0, source_page=1,
         visual_type="grid_table", has_text_layer=True, rows=4, columns=3),
    # simplify_only: structured, no text layer.
    dict(slug="s00_page_0005_table_01", source_index=0, source_page=5,
         visual_type="table", has_text_layer=False, rows=3, columns=2),
    # skip_unreadable: page present but not enough structure to act on.
    dict(slug="s01_page_0004_table_01", source_index=1, source_page=4,
         visual_type="table_like", has_text_layer=True, rows=1, columns=1,
         header_cell_count=0),
    # defer: structured but low confidence.
    dict(slug="s00_page_0006_table_01", source_index=0, source_page=6,
         visual_type="dense_table", has_text_layer=True, rows=5, columns=4,
         confidence="low"),
    # unsafe: dropped by the candidate manifest (unsafe-skipped), never a screenshot.
    dict(slug="s01_page_0001_table_01", source_index=1, source_page=1,
         visual_type="table", has_text_layer=True, rows=4, columns=3, unsafe=True),
]


def _visual_manifest() -> dict:
    """Hand-built ``visual_assets_manifest.json``-shaped dict (the asset list the
    Slice 83/90/92 helpers consume). Only materially-included pages are present —
    mirroring the Slice 82 upstream page filter — so an excluded-page figure simply
    has no record and can never be planned or inserted."""
    assets = [
        _figure_asset(slug, source_index=i, source_page=p) for (slug, i, p) in FIGURE_SPECS
    ]
    for spec in TABLE_SPECS:
        assets.append(_table_record(**spec))
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "assets": assets,
        "summary": {"asset_count": len(assets)},
        "warnings": [],
    }


def _visual_signal_source(key: str, page_count: int) -> dict:
    """extraction-style page-signal source: every universe page (included AND
    excluded) carries a visual signal, so ``build_visual_assets_manifest``'s
    material page filter is genuinely exercised (excluded pages are dropped)."""
    pages = []
    for page in UNIVERSE[key]:
        rec = {
            "page": page,
            "image_object_count": 2,
            "drawing_object_count": 0,
            "has_images": True,
            "has_drawings": False,
            "page_width": 612.0,
            "page_height": 792.0,
            "classification": "image_heavy",
            "ocr_route_action": "skip",
        }
        rec.update(_seed_canaries())
        pages.append(rec)
    src = {"content_type": "application/pdf", "page_count": page_count, "pages": pages}
    src.update(_seed_canaries())
    return src


def _visual_signal_sources() -> list:
    return [_visual_signal_source("attachment_0", 6), _visual_signal_source("attachment_1", 4)]


# --- Extraction metadata (post material-selection page filtering) -------------


def _extraction_metadata(effective: dict) -> dict:
    """Only materially-selected pages survive as extracted records. attachment_1
    page 2 is a deliberate UNREADABLE page (method 'none', no text) so the source
    coverage report carries at least one covered and one unreadable page."""
    def _src(key: str, page_count: int) -> dict:
        pages = []
        for page in sorted(effective[key]):
            unreadable = key == "attachment_1" and page == 2
            rec = {
                "page": page,
                "method": "none" if unreadable else "embedded_text",
                "text_chars": 0 if unreadable else 140,
                "word_count": 0 if unreadable else 24,
                "has_page_anchor": not unreadable,
            }
            rec.update(_seed_canaries())
            pages.append(rec)
        src = {"content_type": "application/pdf", "page_count": page_count, "pages": pages}
        src.update(_seed_canaries())
        return src

    return {
        "version": 2,
        "kind": "extraction_metadata",
        "status": "completed",
        "sources": [_src("attachment_0", 6), _src("attachment_1", 4)],
    }


# --- A duck-typed Job for the full-insertion + export-ride-along helpers -------


class _FakeJob:
    def __init__(self, root: Path):
        self.dir = root
        self.assets_dir = root / "assets"
        self.visual_assets_manifest_json = root / "visual_assets_manifest.json"
        self.clean_md = root / "clean.md"
        self.visual_markdown_image_pilot = True


def _full_env(fn):
    """Run ``fn`` with BOTH the visual master switch and the Slice 90 mode switch on."""
    saved = {k: os.environ.get(k) for k in (vmi.ENABLE_ENV, vmi.FULL_INSERTION_ENABLE_ENV)}
    os.environ[vmi.ENABLE_ENV] = "1"
    os.environ[vmi.FULL_INSERTION_ENABLE_ENV] = "1"
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# Static app-authored guidance headings the guide-quality scanner recognizes.
_BASE_GUIDE_MD = (
    "# Study Guide\n\n"
    "Intro paragraph grounded on the selected material.\n\n"
    "## Coverage-aware generation guidance\n\n"
    "This guide uses the selected pages.\n\n"
    "## Table reconstruction guidance\n\n"
    "Tables are reconstructed from source text where readable.\n\n"
    "## Missing visual and table guidance\n\n"
    "Some material could not be reconstructed and is noted honestly.\n\n"
    "Key concept on page 1 and a follow-up on page 5.\n"
)


# ---------------------------------------------------------------------------
# Chain assembly
# ---------------------------------------------------------------------------


def run_release_chain() -> dict:
    # Stage 1 — material page selection.
    eff0, res0 = _effective("attachment_0", PER_ATTACHMENT_MATERIAL["attachment_0"])
    eff1, res1 = _effective("attachment_1", GLOBAL_MATERIAL)
    effective = {"attachment_0": eff0, "attachment_1": eff1}

    # Stage 2 — visual manifest material-page filtering (Slice 82). The page-signal
    # sources carry a visual on every universe page; the filter drops excluded ones.
    page_filters = [sorted(effective["attachment_0"]), sorted(effective["attachment_1"])]
    vis_filter_manifest = build_visual_assets_manifest(
        _visual_signal_sources(), page_filters=page_filters
    )

    # The asset-record manifest the planner / inserter / table-candidate helpers
    # consume (already page-filtered upstream, Slice 82 convention).
    manifest = _visual_manifest()

    # Stage 3 — visual inclusion plan (Slice 83/84).
    plan = build_visual_inclusion_plan(manifest)

    # Stage 4 — FULL non-table figure insertion into synthetic clean Markdown.
    with tempfile.TemporaryDirectory() as d:
        job = _FakeJob(Path(d))
        job.assets_dir.mkdir(parents=True, exist_ok=True)
        # Only the safe non-table figures (on included pages) get on-disk assets.
        for slug in FIGURE_SLUGS:
            (job.assets_dir / f"{slug}.png").write_bytes(_PNG_1x1)
        job.visual_assets_manifest_json.write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        inserted_md, insertion_info = _full_env(
            lambda: vmi.apply_visual_markdown_pilot(job, _BASE_GUIDE_MD)
        )
        # Stage 5 — render/export asset ride-along (uncapped, safe refs only).
        job.clean_md.write_text(inserted_md, encoding="utf-8")
        export_refs = vmi.find_all_exportable_visual_assets(job)

    # Stage 6 — table candidate manifest (Slice 92) from the filtered visual manifest.
    table_manifest = build_table_candidates_manifest(manifest)

    # Stage 7 — table reconstruction policy (Slice 85/92) over the candidates.
    policy_candidates = table_policy_candidates(table_manifest)
    policy = build_table_reconstruction_policy(policy_candidates)

    # Stage 8 — table reconstruction prompt context (Slice 93).
    table_prompt = build_table_reconstruction_prompt_context(table_manifest, policy)

    # Stage 9 — missing visual/table guidance (Slice 94). Full insertion is ON, so
    # planned visuals are NOT marked missing; only deferred/unreadable tables are.
    missing = build_missing_material_explainer_context(
        plan, table_manifest, policy, full_visual_insertion_enabled=True
    )

    # Stage 10 — source coverage report (Slices 76/77/82). Uses the page-signal
    # filtered visual manifest for visual-candidate-page counting.
    coverage = build_source_coverage_report(
        _extraction_metadata(effective), visual_manifest=vis_filter_manifest
    )

    # Stage 11 — coverage-aware generation guidance (Slice 95).
    coverage_aware = build_coverage_aware_prompt_context(
        job_request=JOB_REQUEST,
        source_coverage_report=coverage,
        visual_inclusion_plan=plan,
        table_candidates_manifest=table_manifest,
        table_reconstruction_policy=policy,
        table_prompt_context=table_prompt,
        missing_material_context=missing,
        full_visual_insertion_enabled=True,
    )

    # Stage 12 — guide quality report v2 (Slice 96) over the inserted guide.
    guide_quality = build_guide_quality_report_v2(
        inserted_md,
        source_coverage_report=coverage,
        visual_inclusion_plan=plan,
        table_candidates_manifest=table_manifest,
        table_reconstruction_policy=policy,
        missing_material_context=missing,
        coverage_aware_context=coverage_aware,
        full_visual_insertion_enabled=True,
    )

    # Stage 13 — Ask Guide coverage grounding (Slice 98).
    ask_grounding = build_ask_coverage_grounding(
        job=JOB_REQUEST,
        source_coverage_report=coverage,
        visual_inclusion_plan=plan,
        table_candidates_manifest=table_manifest,
        table_reconstruction_policy=policy,
        guide_quality_report_v2=guide_quality,
    )

    # Stage 14 — dual explanation mode (Slice 99): off (byte-equivalent) + on.
    dual_off = build_dual_explanation_prompt_context(False)
    dual_on = build_dual_explanation_prompt_context(True)

    return {
        "res0": res0,
        "res1": res1,
        "effective": {k: sorted(v) for k, v in effective.items()},
        "vis_filter_manifest": vis_filter_manifest,
        "manifest": manifest,
        "plan": plan,
        "inserted_md": inserted_md,
        "insertion_info": insertion_info,
        "export_refs": export_refs,
        "table_manifest": table_manifest,
        "policy_candidates": policy_candidates,
        "policy": policy,
        "table_prompt": table_prompt,
        "missing": missing,
        "coverage": coverage,
        "coverage_aware": coverage_aware,
        "guide_quality": guide_quality,
        "ask_grounding": ask_grounding,
        "dual_off": dual_off,
        "dual_on": dual_on,
    }


# ---------------------------------------------------------------------------
# Tests — one per phase dimension, all over the single assembled scenario.
# ---------------------------------------------------------------------------


def test_material_page_selections() -> None:
    r = run_release_chain()
    eff = r["effective"]
    # Safe positional keys only; include/exclude recognized; no filenames/paths.
    check("selection: attachment_0 excludes 2 & 4", eff["attachment_0"] == [1, 3, 5, 6], str(eff))
    check("selection: attachment_1 global-excludes 3", eff["attachment_1"] == [1, 2, 4], str(eff))
    check("selection: keys are positional attachment_<index>",
          set(eff.keys()) == {"attachment_0", "attachment_1"}, str(list(eff.keys())))
    check("selection: both resolved", r["res0"]["resolved"] is True and r["res1"]["resolved"] is True)
    # Material cannot expand beyond the page_selections universe.
    over = apply_material_selection_to_page_universe(
        {"mode": "include", "include_pages": [99]}, existing_allowed_pages=UNIVERSE["attachment_0"]
    )
    check("selection: include outside universe -> empty", over["included_pages"] == [], str(over))


def test_source_coverage() -> None:
    r = run_release_chain()
    s = r["coverage"]["summary"]
    # attachment_0 keeps 4 pages (1,3,5,6 covered); attachment_1 keeps 3 (1,4 covered,
    # 2 unreadable) -> 6 covered, 1 unreadable.
    check("coverage: pdf source count == 2", s["pdf_source_count"] == 2, str(s))
    check("coverage: covered pages == 6", s["covered_pages"] == 6, str(s))
    check("coverage: at least one unreadable page", s["empty_or_unreadable_pages"] >= 1, str(s))
    check("coverage: status is a closed token",
          r["coverage"]["status"] in {"complete", "partial", "skipped", "unreadable", "unknown"},
          str(r["coverage"]["status"]))


def test_visual_planning() -> None:
    r = run_release_chain()
    plan = r["plan"]
    summary = plan["summary"]
    # (source_index, source_page) pairs — a bare page number is ambiguous because a
    # page excluded for one attachment may be included for the other.
    pairs = {(a.get("source_index"), a["source_page"]) for a in r["manifest"]["assets"]}
    check("plan: completed", plan["status"] in {"completed", "partial"}, str(plan["status"]))
    # Every planned item carries a safe generated candidate_id and a non-table kind.
    check("plan: planned items have candidate_id",
          all(isinstance(i.get("candidate_id"), str) and i["candidate_id"] for i in plan["items"]),
          str(plan["items"][:1]))
    check("plan: all planned are non-table",
          summary["non_table_planned_count"] == summary["planned_count"], str(summary))
    check("plan: full coverage of useful figures (>2, not top 1-2)",
          summary["planned_count"] >= 4, str(summary))
    check("plan: table-like records skipped from figure planning",
          summary["table_like_skipped_count"] >= 1, str(summary))
    check("plan: excluded (attachment,page) combos absent from asset manifest",
          (0, 2) not in pairs and (0, 4) not in pairs and (1, 3) not in pairs, str(sorted(pairs)))
    # build_visual_assets_manifest material-page filtering dropped excluded pages.
    vf = r["vis_filter_manifest"]
    vf_pairs = {(a.get("source_index"), a["source_page"]) for a in vf["assets"]}
    check("filter: material page filter dropped excluded-page visuals",
          vf["summary"]["pages_filtered_by_material_selection"] >= 1, str(vf["summary"]))
    check("filter: excluded (attachment,page) combos absent from filtered manifest",
          (0, 2) not in vf_pairs and (0, 4) not in vf_pairs and (1, 3) not in vf_pairs,
          str(sorted(vf_pairs)))


def test_full_figure_insertion() -> None:
    r = run_release_chain()
    info = r["insertion_info"]
    md = r["inserted_md"]
    inserted = len(re.findall(r"!\[[^\]]*\]\(assets/[A-Za-z0-9_]+\.png\)", md))
    check("insertion: status inserted", info.get("status") == vmi.STATUS_INSERTED, str(info))
    check("insertion: full mode", info.get("mode") == vmi.MODE_FULL_INSERTION, str(info))
    check("insertion: all 4 planned figures inserted (not top 1-2)", inserted == 4, str(inserted))
    for slug in FIGURE_SLUGS:
        check(f"insertion: {slug} present", f"assets/{slug}.png" in md)
    # No table screenshot ever rides in as a figure.
    for spec in TABLE_SPECS:
        check(f"insertion: table {spec['slug']} absent", f"assets/{spec['slug']}.png" not in md)
    # Generic "Source visual, page N" captions only.
    check("insertion: generic source captions only",
          "Source visual, page" in md and CANARY_CAPTION not in md, "")


def test_render_export_ride_along() -> None:
    r = run_release_chain()
    refs = r["export_refs"]
    check("export: all 4 referenced safe assets discovered (cap-2 not reintroduced)",
          len(refs) == 4, str(refs))
    check("export: every ref is a safe assets/<slug>.png",
          all(re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", ref) for ref in refs), str(refs))
    check("export: unreferenced canary asset not carried", CANARY_IMAGE_REF not in refs)


def test_table_candidate_and_policy() -> None:
    r = run_release_chain()
    tm = r["table_manifest"]
    policy = r["policy"]
    psum = policy["summary"]
    tsum = tm["summary"]
    check("table manifest: completed", tm["status"] in {"completed", "partial"}, str(tm["status"]))
    check("table manifest: 4 table-like candidates", tsum["table_like_candidate_count"] == 4, str(tsum))
    check("table manifest: non-table figures skipped",
          tsum["skipped_non_table_count"] >= 1, str(tsum))
    check("table manifest: unsafe record skipped (not a candidate)",
          tsum["unsafe_or_incomplete_skipped_count"] >= 1, str(tsum))
    check("policy: actionable items present", psum["policy_item_count"] >= 1, str(psum))
    check("policy: reconstruct present", psum["reconstruct_with_original_count"] >= 1, str(psum))
    check("policy: simplify present", psum["simplify_only_count"] >= 1, str(psum))
    check("policy: defer or skip_unreadable present",
          psum["defer_count"] + psum["skip_unreadable_count"] >= 1, str(psum))
    check("policy: screenshot_insert_count == 0", psum["screenshot_insert_count"] == 0, str(psum))


def test_table_prompt_context() -> None:
    r = run_release_chain()
    ctx = r["table_prompt"]
    check("table prompt: completed/partial", ctx["status"] in {"completed", "partial"}, str(ctx["status"]))
    check("table prompt: prompt_block non-empty", bool(ctx.get("prompt_block")), "")
    check("table prompt: items reference safe candidate_ids",
          all(("candidate_id" in i) for i in ctx.get("items", [])), str(ctx.get("items", [])[:1]))
    # Reconstruct/simplify only from source text; honest deferred notes; no raw table text.
    check("table prompt: no raw table text", CANARY_TABLE_TEXT not in json.dumps(ctx))


def test_missing_material_guidance() -> None:
    r = run_release_chain()
    ctx = r["missing"]
    blob = json.dumps(ctx)
    # Full insertion ON => no missing-visual items (no insertion-failure invented).
    summary = ctx.get("summary", {})
    check("missing: status is a closed token",
          ctx["status"] in {"completed", "partial", "skipped"}, str(ctx["status"]))
    check("missing: no missing-visual items while full insertion is on",
          summary.get("missing_visual_count", 0) == 0, str(summary))
    check("missing: deferred/unreadable tables surfaced as missing-table notes",
          summary.get("missing_table_count", 0) >= 1, str(summary))
    check("missing: no image-derived explanation text", CANARY_OCR_TEXT not in blob and CANARY_CAPTION not in blob)


def test_coverage_aware_guidance() -> None:
    r = run_release_chain()
    ctx = r["coverage_aware"]
    check("coverage-aware: activates on safe signals",
          ctx["status"] in {"completed", "partial"} and bool(ctx.get("prompt_block")), str(ctx["status"]))
    block = ctx.get("prompt_block", "").lower()
    check("coverage-aware: no-hallucination / excluded-material guidance present",
          ("exclud" in block) or ("not available" in block) or ("only" in block) or ("do not" in block),
          block[:160])


def test_guide_quality_report_v2() -> None:
    r = run_release_chain()
    report = r["guide_quality"]
    summary = report.get("summary", {})
    checks = report.get("checks", [])
    check("guide quality: completed/partial", report["status"] in {"completed", "partial"}, str(report["status"]))
    check("guide quality: counts safe page signals", summary.get("source_page_signal_count", 0) >= 1, str(summary))
    check("guide quality: counts safe figure refs", summary.get("safe_image_ref_count", 0) == 4, str(summary))
    check("guide quality: closed checks present", len(checks) >= 4, str(len(checks)))
    # The report must never persist a markdown snippet or an instruction/check_id string.
    blob = json.dumps(report)
    check("guide quality: no raw guide text persisted",
          CANARY_DOC_TEXT not in blob and "Intro paragraph" not in blob, "")


def test_ask_coverage_grounding() -> None:
    r = run_release_chain()
    g = r["ask_grounding"]
    check("ask grounding: completed/partial", g["status"] in {"completed", "partial"}, str(g["status"]))
    text = g.get("grounding_text", "")
    check("ask grounding: summarizes coverage meta-context", bool(text), "")
    # It is meta-context, not course content: a deep walk must be canary-free.
    no_leak("ask grounding: no leak", g)


def test_dual_explanation_mode() -> None:
    r = run_release_chain()
    off = r["dual_off"]
    on = r["dual_on"]
    check("dual: default off -> skipped + empty block",
          off["status"] == "skipped" and off["prompt_block"] == "", str(off))
    check("dual: enabled -> completed + guidance block",
          on["status"] == "completed" and bool(on["prompt_block"]), str(on))
    block = on["prompt_block"].lower()
    check("dual: enabled appends two-layer (simple + exam) guidance",
          "explain it simply" in block and "exam answer" in block, block[:160])


def test_byte_equivalence_when_features_off() -> None:
    # Dual-explanation OFF must leave the generation prompt byte-identical: the
    # builder yields an empty block, so appending it is a no-op.
    off = build_dual_explanation_prompt_context(False)
    base = "PROMPT BODY"
    appended = base + (off["prompt_block"] or "")
    check("byte-equiv: off block is empty", off["prompt_block"] == "")
    check("byte-equiv: prompt unchanged when off", appended == base)


def test_no_leak_deep_walk() -> None:
    r = run_release_chain()
    # Guard: confirm the inputs actually carried the canaries (else the sweep is moot).
    raw = json.dumps({"manifest": _visual_manifest(), "metadata": _extraction_metadata(
        {"attachment_0": {1, 3, 5, 6}, "attachment_1": {1, 2, 4}})})
    check("guard: canaries present in raw inputs",
          CANARY_TABLE_TEXT in raw and CANARY_KEY in raw and CANARY_PATH in raw)

    # The sanitized OUTPUT stages of the chain (the raw ``manifest`` is a seeded
    # *input* the helpers consume + sanitize — in production its sanitized form is
    # produced by build_visual_assets_manifest before any write — so it is not an
    # output and is intentionally excluded from the output sweep).
    output_stages = (
        "vis_filter_manifest", "plan", "export_refs", "table_manifest",
        "policy_candidates", "policy", "table_prompt", "missing", "coverage",
        "coverage_aware", "guide_quality", "ask_grounding", "dual_off", "dual_on",
    )
    for name in output_stages:
        no_leak(f"no-leak: {name}", r[name])
    text_no_leak("no-leak: inserted_md", r["inserted_md"])

    # Single end-to-end serialized sweep over the sanitized outputs (belt-and-braces).
    blob = json.dumps({k: r[k] for k in (*output_stages, "inserted_md")})
    leaked = [c for c in FORBIDDEN_CANARIES if c in blob]
    check("no-leak: serialized release chain has zero canaries", not leaked, str(leaked))


def test_helper_page_membership_safety() -> None:
    # A record on a materially-excluded page is dropped; an unknown page under an
    # active filter is dropped conservatively.
    kept = page_is_in_material_selection(1, {1, 3, 5, 6})
    dropped = page_is_in_material_selection(2, {1, 3, 5, 6})
    unknown = page_is_in_material_selection(None, {1, 3, 5, 6})
    check("helper: included page kept", kept == {"kept": True, "status": None})
    check("helper: excluded page dropped", dropped["kept"] is False and bool(dropped["status"]), str(dropped))
    check("helper: unknown page under filter dropped", unknown["kept"] is False, str(unknown))


def test_determinism() -> None:
    first = json.dumps(run_release_chain(), sort_keys=True)
    second = json.dumps(run_release_chain(), sort_keys=True)
    check("determinism: identical serialization on repeat", first == second)


def main() -> int:
    test_material_page_selections()
    test_source_coverage()
    test_visual_planning()
    test_full_figure_insertion()
    test_render_export_ride_along()
    test_table_candidate_and_policy()
    test_table_prompt_context()
    test_missing_material_guidance()
    test_coverage_aware_guidance()
    test_guide_quality_report_v2()
    test_ask_coverage_grounding()
    test_dual_explanation_mode()
    test_byte_equivalence_when_features_off()
    test_no_leak_deep_walk()
    test_helper_page_membership_safety()
    test_determinism()
    print(f"\nFull Material Coverage release validation: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
