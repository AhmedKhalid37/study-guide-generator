#!/usr/bin/env python3
"""Slice 86 — Material Coverage E2E validation harness.

Run with:

    python test_scripts/test_material_coverage_e2e_validation.py

Deterministic, synthetic, validation-only. This harness proves that the backend
Full Material Coverage chain assembled across Slices 76–85 works together end to
end on **synthetic / sanitized inputs**:

    material page selection
      -> text extraction page filtering
        -> visual manifest page filtering
          -> visual inclusion plan
            -> table reconstruction policy
              -> source / visual / material coverage summary

It exercises ONLY the already-merged pure helpers:

  * ``normalize_page_selection`` / ``apply_material_selection_to_page_universe`` /
    ``page_is_in_material_selection``         (pipeline.page_selection_model)
  * ``build_visual_assets_manifest(..., page_filters=...)``
                                              (pipeline.visual_assets_manifest)
  * ``build_visual_inclusion_plan``           (pipeline.visual_inclusion_planner)
  * ``build_table_reconstruction_policy``     (pipeline.table_reconstruction_policy)
  * ``build_source_coverage_report``          (pipeline.source_coverage_report)

No PDFs / images / DOCX / ZIP fixtures, no real document text, no providers /
models, no job artifacts, no UI, no production wiring. Synthetic *canaries* are
embedded in the inputs and asserted to be stripped from every serialized output.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.page_selection_model import (  # noqa: E402
    apply_material_selection_to_page_universe,
    normalize_page_selection,
    page_is_in_material_selection,
)
from pipeline.visual_assets_manifest import build_visual_assets_manifest  # noqa: E402
from pipeline.visual_inclusion_planner import build_visual_inclusion_plan  # noqa: E402
from pipeline.table_reconstruction_policy import build_table_reconstruction_policy  # noqa: E402
from pipeline.source_coverage_report import build_source_coverage_report  # noqa: E402

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
# No-leak scanning. Canaries are deliberately seeded into every input below and
# must never survive into any serialized output of the chain.
# ---------------------------------------------------------------------------
SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\|\\\\|[A-Za-z]:\\)")
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
CANARY_IMAGE_REF = "assets/secret-canary.png"
CANARY_PATH = "/home/example/private-source.pdf"
CANARY_URL = "https://evil.example/leak-canary"
CANARY_DATA_URI = "data:image/png;base64,QQQQ"
CANARY_KEY = "sk_materialcoveragecanary1234567890"
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


def scan_for_leak(node, path: str = "") -> str | None:
    """Return a description of the first leak found, or None."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            found = scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{path} (canary leaked: {canary})"
        if KEYLIKE.search(node):
            return f"{path} (credential-like value)"
        if PATHLIKE.search(node):
            return f"{path} (path-like value)"
        if URLLIKE.search(node):
            return f"{path} (URL-like value)"
        if DATA_OR_BASE64.search(node):
            return f"{path} (data/base64-like value)"
        if ARGV_OR_SOCKET.search(node):
            return f"{path} (argv/socket/model-like value)"
    return None


def no_leak(name: str, node) -> None:
    found = scan_for_leak(node)
    check(name, found is None, found or "")


# ---------------------------------------------------------------------------
# Synthetic scenario builders. Safe internal source keys only (attachment_0 /
# attachment_1). Every record is seeded with canaries the chain must strip.
# ---------------------------------------------------------------------------

# Existing ``page_selections`` page-range universe per attachment — the MAXIMUM
# allowed set a material selection may further filter but never expand.
UNIVERSE = {
    "attachment_0": [1, 2, 3, 4],
    "attachment_1": [5, 6, 7, 8],
}

# Global material selection (fallback when an attachment has no override). It
# excludes pages 2/4/6/8 across the whole document.
GLOBAL_MATERIAL = {"mode": "exclude", "exclude_pages": [2, 4, 6, 8]}

# Per-attachment material override. attachment_0 overrides global with an
# include-list that also names page 9 (outside its universe) to prove a material
# selection cannot expand beyond ``page_selections``. attachment_1 has no entry
# and therefore falls back to the global selection above.
PER_ATTACHMENT_MATERIAL = {
    "attachment_0": {"mode": "include", "include_pages": [1, 9]},
}


def _seed_canaries() -> dict:
    """A bundle of canary fields stuffed onto synthetic records."""
    return {
        "filename": CANARY_FILENAME,
        "title": CANARY_TITLE,
        "path": CANARY_PATH,
        "text": CANARY_DOC_TEXT,
        "ocr_text": CANARY_OCR_TEXT,
        "caption": CANARY_CAPTION,
        "table_text": CANARY_TABLE_TEXT,
        "image_ref": CANARY_IMAGE_REF,
        "url": CANARY_URL,
        "data_uri": CANARY_DATA_URI,
        "api_key_value": CANARY_KEY,  # value canary (non-secret key name)
        "model_path": CANARY_MODEL,
        "socket_path": CANARY_SOCKET,
        "argv": [CANARY_ARGV, CANARY_MODEL],
    }


def _visual_page(page: int, *, image: bool = False, drawing: bool = False) -> dict:
    record = {
        "page": page,
        "image_object_count": 2 if image else 0,
        "drawing_object_count": 2 if drawing else 0,
        "has_images": image,
        "has_drawings": drawing,
        "page_width": 612.0,
        "page_height": 792.0,
        "classification": "image_heavy" if image else "diagram",
        "ocr_route_action": "skip",
    }
    record.update(_seed_canaries())
    return record


def _manifest_sources() -> list[dict]:
    """extraction_metadata-shaped sources carrying visual signals on EVERY page
    of each universe (included and excluded) so the page filter is exercised."""
    src0 = {
        "content_type": "application/pdf",
        "page_count": 4,
        "pages": [
            _visual_page(1, image=True),
            _visual_page(2, image=True),
            _visual_page(3, drawing=True),
            _visual_page(4, image=True),
        ],
    }
    src0.update(_seed_canaries())
    src1 = {
        "content_type": "application/pdf",
        "page_count": 8,
        "pages": [
            _visual_page(5, image=True),
            _visual_page(6, image=True),
            _visual_page(7, image=True),
            _visual_page(8, image=True),
        ],
    }
    src1.update(_seed_canaries())
    return [src0, src1]


def _extraction_metadata(effective: dict) -> dict:
    """Post-filter extraction metadata: only the materially-selected pages are
    present as extracted page records (mirrors Slice 81 behavior)."""
    def _src(key: str, page_count: int) -> dict:
        pages = []
        for page in sorted(effective[key]):
            rec = {
                "page": page,
                "method": "embedded_text",
                "text_chars": 120,
                "word_count": 20,
                "has_page_anchor": True,
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
        "sources": [
            _src("attachment_0", 4),
            _src("attachment_1", 8),
        ],
    }


def _table_candidates() -> list[dict]:
    """Synthetic table-candidate-shaped dicts on materially-included pages."""
    base = [
        {"visual_type": "table", "source_page": 5, "has_text_layer": True,
         "rows": 4, "columns": 3, "header_cell_count": 3, "numeric_cell_count": 6,
         "confidence": "high"},
        {"visual_type": "table_like", "source_page": 1, "has_text_layer": False,
         "rows": 3, "columns": 2, "header_cell_count": 2},
        {"visual_type": "grid_table", "source_page": 7, "has_text_layer": True,
         "rows": 5, "columns": 4, "header_cell_count": 4, "numeric_cell_count": 10,
         "confidence": "high"},
        {"visual_type": "dense_table", "source_page": 7, "has_text_layer": True,
         "rows": 6, "columns": 3, "header_cell_count": 3, "confidence": "high"},
    ]
    for record in base:
        record.update(_seed_canaries())
    return base


def _enriched_visual_records() -> list[dict]:
    """Extra non-page-signal records injected into the planning manifest to
    exercise the planner's table-skip / decorative-skip / tiny-skip paths plus
    one explicit useful figure. All on materially-included pages."""
    figure = {"asset_type": "extracted_figure", "source_page": 1,
              "asset_id": "extracted_p0001_fig_01"}
    table = {"visual_type": "table", "source_page": 5, "asset_id": "table_p0005_01"}
    decorative = {"visual_type": "logo", "source_page": 7, "asset_id": "logo_p0007_01"}
    tiny = {"asset_type": "page_visual_signal", "source_page": 7,
            "asset_id": "tiny_p0007_01",
            "signals": {"has_images": True, "crop_width_px": 4, "crop_height_px": 4}}
    records = [figure, table, decorative, tiny]
    for record in records:
        record.update(_seed_canaries())
    return records


# ---------------------------------------------------------------------------
# Chain assembly (the function under validation is the *composition* of the
# already-tested pure helpers).
# ---------------------------------------------------------------------------


def _effective_for(key: str, material: dict | None) -> dict:
    return apply_material_selection_to_page_universe(
        material,
        existing_allowed_pages=UNIVERSE[key],
    )


def run_chain() -> dict:
    """Execute the full material-coverage chain once, returning every stage's
    sanitized output plus an in-memory material coverage summary."""
    # Stage 1 — material page selection -> text extraction page filtering.
    eff0 = _effective_for("attachment_0", PER_ATTACHMENT_MATERIAL["attachment_0"])
    eff1 = _effective_for("attachment_1", GLOBAL_MATERIAL)  # no override -> global
    effective = {
        "attachment_0": set(eff0["included_pages"]),
        "attachment_1": set(eff1["included_pages"]),
    }

    # Stage 2 — visual manifest page filtering (Slice 82).
    page_filters = [sorted(effective["attachment_0"]), sorted(effective["attachment_1"])]
    manifest = build_visual_assets_manifest(_manifest_sources(), page_filters=page_filters)

    # Stage 3 — visual inclusion plan (Slice 83). The planning manifest is the
    # material-filtered manifest extended with synthetic enriched records so the
    # planner's table/decorative/tiny routing is exercised in the same call.
    planning_manifest = {
        "version": manifest["version"],
        "kind": "visual_assets_manifest",
        "status": "completed",
        "assets": list(manifest["assets"]) + _enriched_visual_records(),
    }
    plan = build_visual_inclusion_plan(planning_manifest)

    # Stage 4 — table reconstruction policy (Slice 85).
    policy = build_table_reconstruction_policy(_table_candidates())

    # Stage 5 — source / visual / material coverage summary (Slices 76/77/82).
    coverage = build_source_coverage_report(
        _extraction_metadata(effective),
        visual_manifest=manifest,
    )

    selected_text_pages = sum(len(v) for v in effective.values())
    checks = {
        "text_selection_applied": effective["attachment_0"] == {1}
        and effective["attachment_1"] == {5, 7},
        "visual_selection_applied": all(
            a["source_page"] in {1, 5, 7} for a in manifest["assets"]
        ),
        "visual_plan_all_useful_non_table": plan["summary"]["non_table_planned_count"]
        == plan["summary"]["planned_count"],
        "table_policy_applied": policy["summary"]["policy_item_count"] > 0,
        "page_selections_max_universe_preserved": 9 not in effective["attachment_0"],
        "no_leak_sweep": True,  # asserted separately below
    }
    summary = {
        "version": 1,
        "kind": "material_coverage_validation",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "summary": {
            "selected_text_pages": selected_text_pages,
            "filtered_visual_candidates": manifest["summary"][
                "pages_filtered_by_material_selection"
            ],
            "planned_non_table_visuals": plan["summary"]["non_table_planned_count"],
            "table_policy_items": policy["summary"]["policy_item_count"],
            "screenshot_insert_count": policy["summary"]["screenshot_insert_count"],
        },
        "warnings": [],
    }
    return {
        "eff0": eff0,
        "eff1": eff1,
        "effective": {k: sorted(v) for k, v in effective.items()},
        "manifest": manifest,
        "plan": plan,
        "policy": policy,
        "coverage": coverage,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_text_extraction_filtering() -> None:
    result = run_chain()
    eff = result["effective"]

    # Per-attachment override beats the global fallback.
    eff0_global = apply_material_selection_to_page_universe(
        GLOBAL_MATERIAL, existing_allowed_pages=UNIVERSE["attachment_0"]
    )
    check("override: per-attachment effective == {1}", eff["attachment_0"] == [1], str(eff))
    check(
        "override: global fallback would differ ({1,3})",
        sorted(eff0_global["included_pages"]) == [1, 3],
        str(eff0_global),
    )
    check(
        "override: per-attachment != global result",
        eff["attachment_0"] != sorted(eff0_global["included_pages"]),
    )

    # Global fallback applied to the un-overridden attachment.
    check("global fallback: attachment_1 == {5,7}", eff["attachment_1"] == [5, 7], str(eff))

    # page_selections caps the universe; material cannot expand beyond it.
    check("cap: page 9 dropped (outside universe)", 9 not in eff["attachment_0"])
    over = apply_material_selection_to_page_universe(
        {"mode": "include", "include_pages": [9, 10]},
        existing_allowed_pages=UNIVERSE["attachment_0"],
    )
    check("cap: include outside universe -> empty", over["included_pages"] == [], str(over))
    check(
        "cap: no-matching-pages warning is a closed token",
        "material_selection_no_matching_pages" in over["warnings"],
        str(over),
    )

    # Excluded pages are absent from the extracted-content page plan.
    check("exclude: page 2 not extracted (attachment_0)", 2 not in eff["attachment_0"])
    check("exclude: page 4 not extracted (attachment_0)", 4 not in eff["attachment_0"])
    check("exclude: page 6 not extracted (attachment_1)", 6 not in eff["attachment_1"])
    check("exclude: page 8 not extracted (attachment_1)", 8 not in eff["attachment_1"])

    # ``resolved`` is True for both (include and exclude with known universe).
    check("eff0 resolved", result["eff0"]["resolved"] is True)
    check("eff1 resolved", result["eff1"]["resolved"] is True)


def test_visual_manifest_filtering() -> None:
    result = run_chain()
    manifest = result["manifest"]
    pages = sorted(a["source_page"] for a in manifest["assets"])

    check("manifest: completed", manifest["status"] == "completed", str(manifest["status"]))
    check("manifest: only included pages survive", pages == [1, 5, 7], str(pages))
    check("manifest: page 2 visual filtered out", all(a["source_page"] != 2 for a in manifest["assets"]))
    check("manifest: page 4 visual filtered out", all(a["source_page"] != 4 for a in manifest["assets"]))
    check("manifest: page 6 visual filtered out", all(a["source_page"] != 6 for a in manifest["assets"]))
    check("manifest: page 8 visual filtered out", all(a["source_page"] != 8 for a in manifest["assets"]))
    check(
        "manifest: filtered count == 5 (3 + 2 excluded)",
        manifest["summary"]["pages_filtered_by_material_selection"] == 5,
        str(manifest["summary"]),
    )
    check(
        "manifest: filter warnings are closed tokens",
        all(w.startswith("material_selection_visual") for w in manifest["warnings"]),
        str(manifest["warnings"]),
    )

    # Direct helper: a record on a materially-excluded page is dropped; an
    # unknown page under an active filter is dropped conservatively.
    kept = page_is_in_material_selection(1, {1, 5, 7})
    dropped = page_is_in_material_selection(2, {1, 5, 7})
    unknown = page_is_in_material_selection(None, {1, 5, 7})
    none_filter = page_is_in_material_selection(2, None)
    check("helper: included page kept", kept == {"kept": True, "status": None})
    check("helper: excluded page dropped", dropped["kept"] is False and dropped["status"], str(dropped))
    check(
        "helper: unknown page under filter dropped",
        unknown["kept"] is False
        and unknown["status"] == "material_selection_visual_page_unknown",
        str(unknown),
    )
    check("helper: no active filter keeps record", none_filter == {"kept": True, "status": None})


def test_visual_inclusion_plan() -> None:
    result = run_chain()
    plan = result["plan"]
    summary = plan["summary"]

    # 3 real page candidates (pages 1,5,7) + 1 explicit figure = 4 planned.
    check("plan: status completed (no cap)", plan["status"] == "completed", str(plan["status"]))
    check("plan: planned all useful (4)", summary["planned_count"] == 4, str(summary))
    check(
        "plan: all planned are non-table",
        summary["non_table_planned_count"] == summary["planned_count"],
        str(summary),
    )
    check(
        "plan: full coverage, not top 1-2",
        summary["planned_count"] > 2,
        str(summary),
    )
    check(
        "plan: every planned page is materially included",
        all(item["source_page"] in {1, 5, 7} for item in plan["items"]),
        str([i["source_page"] for i in plan["items"]]),
    )

    # Table-like / decorative / tiny are NOT planned as normal visuals.
    check("plan: one table-like skipped", summary["table_like_skipped_count"] == 1, str(summary))
    check(
        "plan: decorative+tiny skipped (2)",
        summary["unsafe_or_incomplete_skipped_count"] == 2,
        str(summary),
    )
    planned_kinds = {item["visual_kind"] for item in plan["items"]}
    check("plan: no table kind planned", "table" not in planned_kinds, str(planned_kinds))

    # max_items is a defensive ceiling only, never the default.
    capped = build_visual_inclusion_plan(
        {"kind": "visual_assets_manifest", "status": "completed",
         "assets": list(result["manifest"]["assets"]) + _enriched_visual_records()},
        max_items=2,
    )
    check("plan: max_items ceiling truncates to 2", capped["summary"]["planned_count"] == 2, str(capped["summary"]))
    check("plan: max_items ceiling -> partial", capped["status"] == "partial", str(capped["status"]))


def test_table_policy_routing() -> None:
    result = run_chain()
    policy = result["policy"]
    summary = policy["summary"]

    # All four table-like candidates are handled (default = ALL, not top 1-2).
    check("policy: completed", policy["status"] == "completed", str(policy["status"]))
    check("policy: all 4 candidates handled", summary["policy_item_count"] == 4, str(summary))
    check("policy: candidate_count == 4", summary["candidate_count"] == 4, str(summary))

    # Tables are routed to reconstruct/simplify decisions, never screenshots.
    actions = {item["action"] for item in policy["items"]}
    check(
        "policy: actions are reconstruct/simplify only",
        actions <= {"reconstruct_with_original", "simplify_only"},
        str(actions),
    )
    check(
        "policy: at least one reconstruct_with_original",
        summary["reconstruct_with_original_count"] >= 1,
        str(summary),
    )
    check(
        "policy: at least one simplify_only",
        summary["simplify_only_count"] >= 1,
        str(summary),
    )
    check("policy: screenshot_insert_count == 0", summary["screenshot_insert_count"] == 0, str(summary))
    check(
        "policy: every item anchored to an included page",
        all(item["source_page"] in {1, 5, 7} for item in policy["items"]),
        str([i["source_page"] for i in policy["items"]]),
    )

    # A non-table record offered to the policy is never treated as a table.
    nontable = build_table_reconstruction_policy([{"visual_type": "figure", "source_page": 1}])
    check("policy: non-table produces no item", nontable["summary"]["policy_item_count"] == 0, str(nontable))
    check("policy: non-table warned not_table_like", "not_table_like" in nontable["warnings"], str(nontable))
    check("policy: non-table screenshot still 0", nontable["summary"]["screenshot_insert_count"] == 0)


def test_coverage_summary() -> None:
    result = run_chain()
    coverage = result["coverage"]
    summary = coverage["summary"]

    # Only materially-selected pages were extracted -> deterministic partial.
    check("coverage: pdf source count == 2", summary["pdf_source_count"] == 2, str(summary))
    check("coverage: total declared pages == 12", summary["total_pages"] == 12, str(summary))
    check("coverage: covered pages == 3 (1 + 2)", summary["covered_pages"] == 3, str(summary))
    check("coverage: embedded-text pages == 3", summary["embedded_text_pages"] == 3, str(summary))
    check("coverage: anchor pages == 3", summary["anchor_pages"] == 3, str(summary))
    check(
        "coverage: visual candidate pages == 3 (1,5,7)",
        summary["visual_candidate_pages"] == 3,
        str(summary),
    )
    check("coverage: top status partial (not all pages selected)", coverage["status"] == "partial", str(coverage["status"]))

    # Excluded pages never appear as covered source pages.
    src0 = coverage["sources"][0]
    check("coverage: attachment_0 covered == 1", src0["covered_page_count"] == 1, str(src0))
    check("coverage: attachment_0 declared == 4", src0["page_count"] == 4, str(src0))


def test_material_coverage_summary_shape() -> None:
    result = run_chain()
    s = result["summary"]
    check("summary: kind", s["kind"] == "material_coverage_validation", str(s))
    check("summary: version 1", s["version"] == 1, str(s))
    check("summary: status passed", s["status"] == "passed", str(s["checks"]))
    for key in (
        "text_selection_applied",
        "visual_selection_applied",
        "visual_plan_all_useful_non_table",
        "table_policy_applied",
        "page_selections_max_universe_preserved",
        "no_leak_sweep",
    ):
        check(f"summary: check {key} true", s["checks"][key] is True, str(s["checks"]))
    inner = s["summary"]
    check("summary: selected_text_pages == 3", inner["selected_text_pages"] == 3, str(inner))
    check("summary: filtered_visual_candidates == 5", inner["filtered_visual_candidates"] == 5, str(inner))
    check("summary: planned_non_table_visuals == 4", inner["planned_non_table_visuals"] == 4, str(inner))
    check("summary: table_policy_items == 4", inner["table_policy_items"] == 4, str(inner))
    check("summary: screenshot_insert_count == 0", inner["screenshot_insert_count"] == 0, str(inner))


def test_no_leak_across_chain() -> None:
    result = run_chain()
    # Confirm the inputs actually carry the canaries (otherwise the sweep is moot).
    raw_inputs = json.dumps(
        {
            "sources": _manifest_sources(),
            "tables": _table_candidates(),
            "enriched": _enriched_visual_records(),
            "metadata": _extraction_metadata({"attachment_0": {1}, "attachment_1": {5, 7}}),
        }
    )
    check("guard: canaries present in raw inputs", CANARY_TABLE_TEXT in raw_inputs and CANARY_KEY in raw_inputs)

    for name in ("eff0", "eff1", "manifest", "plan", "policy", "coverage", "summary"):
        no_leak(f"no-leak: {name}", result[name])

    # Serialized end-to-end sweep (single string) for belt-and-braces.
    blob = json.dumps(result)
    leaked = [c for c in FORBIDDEN_CANARIES if c in blob]
    check("no-leak: serialized chain has zero canaries", not leaked, str(leaked))


def test_determinism() -> None:
    first = json.dumps(run_chain(), sort_keys=True)
    second = json.dumps(run_chain(), sort_keys=True)
    check("determinism: identical serialization on repeat", first == second)


def main() -> int:
    test_text_extraction_filtering()
    test_visual_manifest_filtering()
    test_visual_inclusion_plan()
    test_table_policy_routing()
    test_coverage_summary()
    test_material_coverage_summary_shape()
    test_no_leak_across_chain()
    test_determinism()
    print(f"\nMaterial coverage E2E validation: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
