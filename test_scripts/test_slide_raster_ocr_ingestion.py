"""Slice 176H — local slide-raster OCR ingestion seam (public-safe test).

Exercises the seam's *logic* on synthetic, public-safe tokens only — no private
decks, no real OCR, no raster images, no source PDFs. Asserts (closed vocabulary
only):

  1. text-layer classification (near_empty / usable / partial) from text lengths.
  2. full-page raster-slide content-form detection from synthetic visual signals.
  3. closed summary construction coerces every field to its closed set and never
     carries raw OCR / paths / sizes; cloud_ocr_used + *_committed flags hardwired.
  4. private-artifact directory policy: tracked repo paths are refused; temp /
     gitignored-segment paths are accepted.
  5. raw OCR text never appears anywhere in the closed summary.
  6. engine-unavailable / no-private-dir paths degrade to blocked/degraded/skipped
     closed status rather than crashing.
  7. structured_ocr_engine labels stay closed and a GGUF/VLM route is NOT relabelled
     hf/cli.
  8. numeric_recompute_readiness never becomes ready_for_masked_recompute from this
     seam (it is a later consumer's responsibility).

No cloud OCR, no provider/model generation, no guide regeneration, no Layer-2 judge,
no repair. judge_ready=false; repair_ready=false.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import (
    SlideOcrIngestionConfig,
    _STRUCTURED_ENGINE,
    bulk_text_quality_from_confidence,
    build_closed_slide_ocr_summary,
    classify_pdf_text_layer,
    detect_full_page_image_blocks,
    is_private_artifact_dir,
    run_local_structured_ocr_if_configured,
    run_slide_raster_ocr_ingestion,
    write_private_ocr_artifact,
)

# A synthetic, public-safe "raw OCR" marker. If this string ever appears in a
# committed-safe summary, raw content leaked — assertion (5) catches that.
_CANARY = "SYNTHETIC_RAW_OCR_CANARY_TOKEN"


def _check(label, condition):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    return bool(condition)


def main() -> int:
    ok = True

    # (1) text-layer classification.
    near_empty_pages = ["", " ", "x", "12", ""]  # all near-empty
    usable_pages = ["word " * 30] * 5  # all meaningful
    # 2 meaningful, 2 near-empty, 1 mid-length (>=10 chars, <5 words): neither
    # bucket reaches the 60% threshold -> partial.
    mixed_pages = ["word " * 30, "word " * 30, "", "abcdefghijklmnopqrst", "x"]
    ok &= _check("near-empty text layer -> near_empty",
                 classify_pdf_text_layer(near_empty_pages) == "near_empty")
    ok &= _check("rich text layer -> usable",
                 classify_pdf_text_layer(usable_pages) == "usable")
    ok &= _check("mixed text layer -> partial",
                 classify_pdf_text_layer(mixed_pages) == "partial")
    ok &= _check("empty input -> unknown", classify_pdf_text_layer([]) == "unknown")

    # (2) full-page raster-slide content-form detection (synthetic signals).
    raster_signals = [
        {"image_object_count": 1, "has_images": True, "text_chars": 3, "word_count": 1}
        for _ in range(5)
    ]
    text_signals = [
        {"image_object_count": 0, "has_images": False, "text_chars": 800, "word_count": 120}
        for _ in range(5)
    ]
    ok &= _check("full-page images -> full_page_raster_slide_images",
                 detect_full_page_image_blocks(raster_signals) == "full_page_raster_slide_images")
    ok &= _check("text-only pages -> text_layer",
                 detect_full_page_image_blocks(text_signals) == "text_layer")
    ok &= _check("no signals -> unknown",
                 detect_full_page_image_blocks([]) == "unknown")

    # (3) closed summary construction coerces out-of-vocab values.
    summary = build_closed_slide_ocr_summary(
        status="not_a_status",
        source_label="Ensemble Deck / private path",
        pages_considered_count=-4,
        pages_rendered_count="oops",
        text_layer_status="bogus",
        effective_content_form="bogus",
        tesseract_status="bogus",
        structured_ocr_status="bogus",
        structured_ocr_engine="bogus",
        private_artifact_written=True,
        private_artifact_gitignored=True,
        bulk_text_quality="bogus",
        downstream_readiness="bogus",
        numeric_recompute_readiness="bogus",
        warnings=["off_by_default_skipped", "not_a_real_warning"],
    )
    ok &= _check("status coerced to closed default", summary["status"] == "blocked")
    ok &= _check("counts coerced to safe non-negative ints",
                 summary["pages_considered_count"] == 0 and summary["pages_rendered_count"] == 0)
    ok &= _check("source_label sanitised (no slashes/spaces)",
                 "/" not in summary["source_label"] and " " not in summary["source_label"])
    ok &= _check("text_layer_status coerced", summary["text_layer_status"] == "unknown")
    ok &= _check("structured_ocr_engine coerced to closed default",
                 summary["structured_ocr_engine"] == "none")
    ok &= _check("cloud_ocr_used hardwired false", summary["cloud_ocr_used"] is False)
    ok &= _check("all *_committed flags hardwired false", all(
        summary[k] is False for k in (
            "raw_ocr_committed", "raw_table_text_committed", "rendered_images_committed",
            "model_files_committed", "model_cache_committed",
        )
    ))
    ok &= _check("unknown warning dropped", summary["warnings"] == ["off_by_default_skipped"])
    ok &= _check("numeric readiness coerced (not ready_for_masked_recompute)",
                 summary["numeric_recompute_readiness"] == "not_attempted")

    # numeric readiness can never be forced to ready from this seam.
    forced = build_closed_slide_ocr_summary(
        status="completed", source_label="x", pages_considered_count=1,
        pages_rendered_count=1, text_layer_status="near_empty",
        effective_content_form="full_page_raster_slide_images",
        tesseract_status="ran", structured_ocr_status="ran_local",
        structured_ocr_engine="chandra_gguf_local",
        private_artifact_written=True, private_artifact_gitignored=True,
        numeric_recompute_readiness="ready_for_masked_recompute",
    )
    ok &= _check("ready_for_masked_recompute refused -> needs_input_cell_parser",
                 forced["numeric_recompute_readiness"] == "needs_input_cell_parser")

    # (4) private-artifact directory policy.
    repo_tracked = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    ok &= _check("tracked repo dir refused as private", not is_private_artifact_dir(repo_tracked))
    ok &= _check("None dir refused", not is_private_artifact_dir(None))
    with tempfile.TemporaryDirectory() as tmp:
        ok &= _check("temp dir accepted as private", is_private_artifact_dir(tmp))
        # (4b) write refused into a tracked dir; accepted into temp.
        written, private = write_private_ocr_artifact(repo_tracked, _CANARY)
        ok &= _check("write into tracked repo dir refused", written is False and private is False)
        written2, private2 = write_private_ocr_artifact(tmp, _CANARY)
        ok &= _check("write into temp dir accepted", written2 is True and private2 is True)
    ok &= _check("gitignored-segment path accepted",
                 is_private_artifact_dir("/some/local_operator_baselines/run1"))

    # (5) raw OCR text never appears in the closed summary (serialise + scan).
    serialised = json.dumps(summary) + json.dumps(forced)
    ok &= _check("no raw OCR canary in any closed summary", _CANARY not in serialised)

    # (6) off-by-default + no-private-dir degrade paths (no crash, closed status).
    skipped = run_slide_raster_ocr_ingestion(
        SlideOcrIngestionConfig(enabled=False, source_label="ensemble"),
        page_texts=near_empty_pages, page_signals=raster_signals,
    )
    ok &= _check("disabled runner -> skipped", skipped["status"] == "skipped")
    ok &= _check("disabled runner still classifies text layer",
                 skipped["text_layer_status"] == "near_empty")
    ok &= _check("disabled runner -> off_by_default_skipped warning",
                 "off_by_default_skipped" in skipped["warnings"])

    blocked = run_slide_raster_ocr_ingestion(
        SlideOcrIngestionConfig(enabled=True, source_label="ensemble",
                                private_artifact_dir=repo_tracked,
                                pdf_path="/nope.pdf", page_indices=[0]),
        page_texts=near_empty_pages, page_signals=raster_signals,
    )
    ok &= _check("enabled but non-private dir -> blocked", blocked["status"] == "blocked")
    ok &= _check("blocked path writes nothing private",
                 blocked["private_artifact_written"] is False)
    ok &= _check("blocked path defers numeric to blocked",
                 blocked["numeric_recompute_readiness"] == "blocked")

    # enabled + private dir but no renderable pages -> degraded, no crash.
    with tempfile.TemporaryDirectory() as tmp:
        degraded = run_slide_raster_ocr_ingestion(
            SlideOcrIngestionConfig(enabled=True, source_label="ensemble",
                                    private_artifact_dir=tmp,
                                    pdf_path=None, page_indices=[]),
            page_texts=near_empty_pages, page_signals=raster_signals,
        )
    ok &= _check("enabled + private dir + no pages -> degraded",
                 degraded["status"] == "degraded")
    ok &= _check("degraded numeric readiness stays needs_input_cell_parser",
                 degraded["numeric_recompute_readiness"] == "needs_input_cell_parser")

    # (7) structured engine labels closed; GGUF/VLM not relabelled hf/cli.
    status_uc, engine_uc = run_local_structured_ocr_if_configured(
        [], configured=False, engine="chandra_gguf_local", endpoint_reachable=False)
    ok &= _check("unconfigured structured OCR -> not_available/none",
                 status_uc == "not_available" and engine_uc == "none")
    status_av, engine_av = run_local_structured_ocr_if_configured(
        ["/tmp/p.png"], configured=True, engine="chandra_gguf_local", endpoint_reachable=True)
    ok &= _check("configured GGUF stays chandra_gguf_local (not hf/cli)",
                 engine_av == "chandra_gguf_local")
    _, engine_bad = run_local_structured_ocr_if_configured(
        [], configured=True, engine="totally_made_up", endpoint_reachable=False)
    ok &= _check("unknown engine coerced to closed set",
                 engine_bad in _STRUCTURED_ENGINE)

    # (8) bulk-text quality bucketer (closed).
    ok &= _check("conf 82 -> clean", bulk_text_quality_from_confidence(82) == "clean")
    ok &= _check("conf 50 -> partial", bulk_text_quality_from_confidence(50) == "partial")
    ok &= _check("conf 20 -> failed", bulk_text_quality_from_confidence(20) == "failed")
    ok &= _check("conf None -> not_run", bulk_text_quality_from_confidence(None) == "not_run")

    print(f"slide_raster_ocr_ingestion: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
