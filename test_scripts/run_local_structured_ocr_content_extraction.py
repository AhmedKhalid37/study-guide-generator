"""Slice 176I-real — run the **proven local structured OCR producer** on real
content-bearing slides and write a **private** extracted-content artifact.

This is NOT a seam/adapter/readiness slice (176H built the seam). It is the first
real content-extraction run using the local Chandra OCR 2 GGUF route proven in
Slice 176G (`llama.cpp` / `llama-server`, OpenAI-compatible `/v1/chat/completions`,
local-only, no cloud/API). It:

  1. selects content-bearing slides for one deck via a Tesseract keyword +
     numeric-density pre-scan over locally-rendered pages (same selection idea as
     176F/176G; avoids title/intro/text-layer pages);
  2. renders the selected pages locally (PyMuPDF) and OCRs each through the
     committed `pipeline.chandra_local_provider` payload builder + the running local
     `llama-server` (the 176G producer);
  3. writes raw OCR/structured output + a manifest **only** to a private,
     gitignored/temp directory;
  4. prints / writes a **committed-safe closed summary** — closed tokens / counts /
     buckets / bools only, never raw OCR / table / source text, paths, sizes, or
     model details.

Config is entirely env-driven so the committed code carries **no private paths**:

  DECK_PDF            absolute path to the private source deck (required)
  SOURCE_LABEL        closed source label (default "ensemble")
  PRIVATE_OCR_DIR     gitignored/temp output dir (required, must be private)
  CHANDRA_ENDPOINT    local llama-server chat endpoint (required); a loopback
                      OpenAI-compatible /v1/chat/completions URL on the operator port
  TESSERACT_BIN       tesseract binary (default "tesseract")
  SELECT_DPI          selection render DPI (default 110)
  OCR_DPI             extraction render DPI (default 200)
  MAX_PAGES_PER_CAT   cap of pages OCR'd per category (default 1)
  RESELECT            "1" to recompute selection even if cached (default reuse)

No cloud OCR. No provider/model generation. No guide-generation wiring. No
frontend/API. No numeric recompute claim (numeric stays needs_input_cell_parser).
judge_ready=false; repair_ready=false.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.chandra_local_provider import (  # noqa: E402
    build_chandra_image_message_payload,
    parse_chandra_chat_response,
)
from pipeline.chandra_normalizer import normalize_chandra_output  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

# Content-slide categories (closed). Title/intro pages are deliberately excluded.
CATEGORIES = {
    "ensemble_patient_dataset_table": ["patient", "dataset", "chest pain", "cholesterol", "blood pressure"],
    "ensemble_gini_or_leaf_count": ["gini", "leaf", "impurity", "entropy"],
    "ensemble_proximity_matrix": ["proximity"],
    "ensemble_decision_tree_or_split_diagram": ["decision tree", "split", "node", "branch", "tree"],
    "ensemble_weighted_frequency_or_total_error": ["weighted", "total error", "amount of say", "weight"],
}
# Intro/title noise tokens that disqualify a page from being a "content" slide.
_TITLEY = ("agenda", "outline", "references", "thank you", "introduction to")


def _bucket(n: int) -> str:
    if n <= 0:
        return "none"
    if n <= 2:
        return "low"
    if n <= 6:
        return "medium"
    return "high"


def _render_page(doc, index: int, dpi: int, out: Path) -> str | None:
    try:
        import fitz

        zoom = max(1.0, dpi / 72.0)
        pix = doc[index].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        target = out / f"page_{index:04d}_{dpi}.png"
        pix.save(str(target))
        return str(target)
    except Exception:
        return None


def _tesseract_text(tess_bin: str, image_path: str) -> str:
    try:
        proc = subprocess.run(
            [tess_bin, image_path, "stdout", "--psm", "6"],
            capture_output=True, text=True, timeout=60,
        )
        return proc.stdout or ""
    except Exception:
        return ""


def _numeric_density(text: str) -> int:
    return len(re.findall(r"\d", text or ""))


def select_content_pages(doc, tess_bin: str, dpi: int, scan_dir: Path) -> dict:
    """Tesseract keyword + numeric-density pre-scan → best page per category.

    Returns {category: {"page": idx, "numeric": n}} for matched categories only.
    Closed/structural only; never returns OCR text.
    """
    best: dict[str, dict] = {}
    n = doc.page_count
    for i in range(n):
        img = _render_page(doc, i, dpi, scan_dir)
        if not img:
            continue
        text = _tesseract_text(tess_bin, img).lower()
        try:
            os.remove(img)
        except OSError:
            pass
        if any(t in text for t in _TITLEY):
            continue
        numeric = _numeric_density(text)
        for cat, kws in CATEGORIES.items():
            if any(kw in text for kw in kws):
                # Prefer the most numeric-dense matching page (the real grid slide,
                # not a bullet mention) — the 176F/176G "max-numeric" rule.
                cur = best.get(cat)
                if cur is None or numeric > cur["numeric"]:
                    best[cat] = {"page": i, "numeric": numeric}
    return best


def _ocr_page(endpoint: str, image_path: str) -> tuple[str, list[str], float]:
    img = Path(image_path).read_bytes()
    payload = build_chandra_image_message_payload(img, mime_type="image/png")
    payload["temperature"] = 0.0
    # 176G ran the deterministic OCR with thinking DISABLED. Leaving thinking on
    # makes this qwen3vl-based server emit the whole transcription into the hidden
    # reasoning channel and return EMPTY content (observed on dense slides) — a
    # config confound, not an OCR-capability gap. Disable thinking and give the
    # dense layout-HTML a generous token budget.
    payload["chat_template_kwargs"] = {"enable_thinking": False}
    payload["max_tokens"] = 6144
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}
    )
    t = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read().decode())
    dt = time.time() - t
    parsed = parse_chandra_chat_response(resp)
    return parsed.get("content") or "", parsed.get("warnings") or [], dt


def _table_shapes(html: str) -> list[tuple[int, int]]:
    """Return (rows, max_cols) for each <table> — structural only, no cell text."""
    shapes = []
    for tbl in re.findall(r"<table\b.*?</table>", html, flags=re.I | re.S):
        rows = re.findall(r"<tr\b.*?</tr>", tbl, flags=re.I | re.S)
        max_cols = 0
        for row in rows:
            cols = len(re.findall(r"<t[dh]\b", row, flags=re.I))
            max_cols = max(max_cols, cols)
        if rows:
            shapes.append((len(rows), max_cols))
    return shapes


def _dense_grid_status(shapes: list[tuple[int, int]], min_rows: int, min_cols: int) -> str:
    if not shapes:
        return "failed"
    if any(r >= min_rows and c >= min_cols for r, c in shapes):
        return "recovered"
    if any(r >= 2 and c >= 2 for r, c in shapes):
        return "partial"
    return "failed"


def analyze(html: str) -> dict:
    """Closed structural signals from one page's layout-HTML. No raw text leaves."""
    low = html.lower()
    shapes = _table_shapes(html)
    labels = re.findall(r'data-label="([a-z\- ]+)"', html, flags=re.I)
    fig_like = sum(1 for l in labels if l.lower() in ("figure", "diagram", "image", "chart"))
    cap_like = sum(1 for l in labels if l.lower() in ("caption",))
    text_blocks = sum(1 for l in labels if l.lower() in ("text", "section-header", "title"))
    has_math = ("\\(" in html) or ("\\[" in html) or ("$$" in html) or ("\\frac" in html)
    return {
        "table_count": len(shapes),
        "table_shapes": shapes,
        "max_table_rows": max((r for r, _ in shapes), default=0),
        "max_table_cols": max((c for _, c in shapes), default=0),
        "figure_or_diagram_count": fig_like,
        "caption_count": cap_like,
        "text_block_count": text_blocks,
        "has_table": len(shapes) > 0,
        "has_math": has_math,
        "content_len_bucket": _bucket_len(len(html)),
    }


def _bucket_len(n: int) -> str:
    if n <= 0:
        return "none"
    if n < 200:
        return "low"
    if n < 800:
        return "medium"
    return "high"


def main() -> int:
    deck = os.environ.get("DECK_PDF")
    source_label = os.environ.get("SOURCE_LABEL", "ensemble")
    private_dir = os.environ.get("PRIVATE_OCR_DIR")
    endpoint = os.environ.get("CHANDRA_ENDPOINT")
    tess_bin = os.environ.get("TESSERACT_BIN", "tesseract")
    select_dpi = int(os.environ.get("SELECT_DPI", "110"))
    ocr_dpi = int(os.environ.get("OCR_DPI", "200"))
    max_per_cat = int(os.environ.get("MAX_PAGES_PER_CAT", "1"))
    reselect = os.environ.get("RESELECT", "0") == "1"

    if not deck or not private_dir or not endpoint:
        print("BLOCKED: DECK_PDF, PRIVATE_OCR_DIR, CHANDRA_ENDPOINT required")
        return 2
    if not is_private_artifact_dir(private_dir):
        print("BLOCKED: PRIVATE_OCR_DIR is not a private (gitignored/temp) directory")
        return 2

    import fitz

    out = Path(private_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(deck)

    # --- selection (cached) ---
    sel_path = out / "selection.json"
    if sel_path.exists() and not reselect:
        selection = json.loads(sel_path.read_text())
    else:
        with tempfile.TemporaryDirectory() as scan:
            selection = select_content_pages(doc, tess_bin, select_dpi, Path(scan))
        sel_path.write_text(json.dumps(selection))

    # flatten to a capped page list per category
    selected = []
    for cat, info in selection.items():
        selected.append({"slide_category": cat, "page": info["page"]})
    selected = selected[: max(1, max_per_cat) * len(CATEGORIES)]

    # --- extraction ---
    per_slide = []
    manifest_entries = []
    render_dir = out / "rendered"
    render_dir.mkdir(exist_ok=True)
    structured_status = "skipped"
    engine = "chandra_gguf_local"
    pages_rendered = 0
    for item in selected:
        idx = item["page"]
        cat = item["slide_category"]
        img = _render_page(doc, idx, ocr_dpi, render_dir)
        if not img:
            per_slide.append({"slide_category": cat, "structured_ocr_status": "failed_local",
                              "table_recovered": "na", "figure_or_diagram_recovered": "na",
                              "dense_grid_recovered": "na", "caption_or_context_recovered": "na"})
            continue
        pages_rendered += 1
        try:
            html, warns, dt = _ocr_page(endpoint, img)
            structured_status = "ran_local"
        except Exception as e:
            per_slide.append({"slide_category": cat, "structured_ocr_status": "failed_local",
                              "error_type": type(e).__name__,
                              "table_recovered": "no", "figure_or_diagram_recovered": "no",
                              "dense_grid_recovered": "no", "caption_or_context_recovered": "no"})
            if structured_status != "ran_local":
                structured_status = "failed_local"
            continue
        norm = normalize_chandra_output(html, source_page=idx)
        sig = analyze(html)
        # private manifest carries the raw layout-HTML + normalized output for
        # downstream consumers — this file never leaves the private dir.
        manifest_entries.append({
            "slide_category": cat, "page": idx, "ocr_seconds": round(dt, 1),
            "raw_layout_html": html, "normalized": norm, "signals": sig,
            "response_warnings": warns,
        })
        # closed per-slide record (no raw text)
        if cat == "ensemble_proximity_matrix":
            dense = _dense_grid_status(sig["table_shapes"], 5, 5)
        elif cat in ("ensemble_patient_dataset_table", "ensemble_gini_or_leaf_count"):
            dense = _dense_grid_status(sig["table_shapes"], 3, 3)
        else:
            dense = _dense_grid_status(sig["table_shapes"], 2, 2)
        per_slide.append({
            "slide_category": cat,
            "structured_ocr_status": "ran_local",
            "table_recovered": "yes" if sig["has_table"] else "no",
            "figure_or_diagram_recovered": "yes" if sig["figure_or_diagram_count"] > 0 else "no",
            "dense_grid_recovered": {"recovered": "yes", "partial": "partial", "failed": "no"}[dense],
            "caption_or_context_recovered": "yes" if (sig["caption_count"] or sig["text_block_count"]) else "no",
            "table_shape_max_rows": sig["max_table_rows"],
            "table_shape_max_cols": sig["max_table_cols"],
            "has_math": sig["has_math"],
            "raw_output_committed": False,
            "screenshot_committed": False,
            "raw_values_committed": False,
        })

    # private manifest write (raw content stays here only)
    manifest_path = out / "extracted_content_manifest.json"
    manifest_path.write_text(json.dumps({"source_label": source_label,
                                         "entries": manifest_entries}, ensure_ascii=False))
    private_written = manifest_path.exists() and len(manifest_entries) > 0
    private_gitignored = is_private_artifact_dir(private_dir)

    # --- closed extraction summary ---
    def cat_status(cat: str) -> dict | None:
        for s in per_slide:
            if s["slide_category"] == cat and s["structured_ocr_status"] == "ran_local":
                return s
        return None

    tables = sum(1 for s in per_slide if s.get("table_recovered") == "yes")
    figs = sum(1 for s in per_slide if s.get("figure_or_diagram_recovered") == "yes")
    text_blocks_total = sum(e["signals"]["text_block_count"] for e in manifest_entries)

    prox = cat_status("ensemble_proximity_matrix")
    patient = cat_status("ensemble_patient_dataset_table")
    gini = cat_status("ensemble_gini_or_leaf_count")

    def grid_to_status(rec: dict | None) -> str:
        if rec is None:
            return "not_checked"
        return {"yes": "recovered", "partial": "partial", "no": "failed"}[rec["dense_grid_recovered"]]

    # Gini: structural recovery is NOT numeric verification. If a credible >=2-class
    # integer grid was not recovered, this is at best answer/output-table material.
    if gini is None:
        gini_status = "not_checked"
    elif gini["dense_grid_recovered"] == "yes":
        gini_status = "partial"  # raw grid present but masked recompute NOT run -> never "recovered"
    elif gini["table_recovered"] == "yes":
        gini_status = "answer_only"
    else:
        gini_status = "failed"

    ran_any = structured_status == "ran_local"
    visible_ready = "ready_for_visible_table_pilot" if tables > 0 else "needs_cleanup"
    guide_ready = "ready_for_private_prompt_context_pilot" if (text_blocks_total > 0 or tables > 0) else "needs_cleanup"

    summary = {
        "artifact_name": "local_structured_ocr_content_extraction",
        "status": "completed" if ran_any and pages_rendered > 0 else ("degraded" if pages_rendered else "blocked"),
        "source_label": source_label,
        "selected_slide_categories_count": len(selected),
        "pages_rendered_count": pages_rendered,
        "structured_ocr_status": structured_status,
        "structured_ocr_engine": engine if ran_any else "none",
        "cloud_ocr_used": False,
        "private_artifact_written": bool(private_written),
        "private_artifact_gitignored": bool(private_gitignored),
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "rendered_images_committed": False,
        "source_pdf_committed": False,
        "model_files_committed": False,
        "model_cache_committed": False,
        "content_extraction_status": "extracted" if tables or figs or text_blocks_total else ("partial" if ran_any else "failed"),
        "extracted_text_block_count_bucket": _bucket(text_blocks_total),
        "extracted_table_count_bucket": _bucket(tables),
        "extracted_figure_or_diagram_count_bucket": _bucket(figs),
        "dense_grid_recovery_status": grid_to_status(prox if prox else (patient if patient else gini)),
        "patient_dataset_table_status": grid_to_status(patient),
        "gini_or_leaf_count_status": gini_status,
        "proximity_matrix_status": grid_to_status(prox),
        "guide_content_readiness": guide_ready,
        "visible_table_readiness": visible_ready,
        "numeric_recompute_readiness": "needs_input_cell_parser",
        "gini_masked_recompute_from_ocr_status": "not_attempted",
        "recommended_next_step": "run_gini_input_cell_parser_on_private_artifact" if tables else "improve_structured_ocr_prompt",
        "per_slide": per_slide,
    }
    (out / "closed_extraction_summary.json").write_text(json.dumps(summary, indent=2))
    # print closed summary only (no raw text)
    public = {k: v for k, v in summary.items() if k != "per_slide"}
    print(json.dumps(public, indent=2))
    print("--- per slide (closed) ---")
    for s in per_slide:
        print(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
