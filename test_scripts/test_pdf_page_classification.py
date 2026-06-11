#!/usr/bin/env python3
"""Focused tests for Slice 31 advisory PDF page classification metadata.

Run with:

    python test_scripts/test_pdf_page_classification.py

No external APIs and no PyMuPDF dependency. The pure classifier
(`_classify_pdf_page`) and the artifact sanitiser (`_safe_page`) are exercised
directly with plain dicts so every classification branch, the degrade-not-fail
behaviour, and leak-safety can be proven deterministically.

Classification is advisory only: it never changes extracted text, OCR routing,
prompts, or generation. These tests assert the field values and that no smuggled
classification value, path, secret, or image data can survive into the artifact.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")

from pipeline.extraction_metadata import (  # noqa: E402
    _CLASSIFICATIONS,
    _CLASSIFICATION_REASONS,
    _classify_pdf_page,
    _safe_classification,
    _safe_page,
    _safe_reasons,
)


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


def _page(**overrides) -> dict:
    base = {
        "page": 1,
        "method": "embedded_text",
        "text_chars": 0,
        "word_count": 0,
        "has_page_anchor": True,
        "warnings": [],
    }
    base.update(overrides)
    return base


# --- direct classifier branch coverage -------------------------------------


def test_embedded_text_page() -> None:
    c = _classify_pdf_page(_page(
        method="embedded_text", text_chars=900, word_count=140,
        image_object_count=0, drawing_object_count=0,
        has_images=False, has_drawings=False,
    ))
    check("embedded/classification", c["classification"] == "embedded_text", str(c))
    check("embedded/reason", "meaningful_embedded_text" in c["classification_reasons"], str(c))
    check("embedded/ocr-not-recommended", c["ocr_recommended"] is False, str(c))


def test_ocr_fallback_page() -> None:
    c = _classify_pdf_page(_page(
        method="ocr", text_chars=300, word_count=55,
        image_object_count=1, has_images=True,
        drawing_object_count=0, has_drawings=False,
    ))
    check("ocr/classification", c["classification"] == "ocr_fallback", str(c))
    check("ocr/reason", "method_ocr" in c["classification_reasons"], str(c))
    check("ocr/ocr-not-recommended", c["ocr_recommended"] is False, str(c))


def test_likely_scanned_page() -> None:
    # Image-heavy, near-zero text, OCR could not produce text (method none).
    c = _classify_pdf_page(_page(
        method="none", text_chars=0, word_count=0,
        warnings=["no_text_extracted"],
        image_object_count=3, has_images=True,
        drawing_object_count=0, has_drawings=False,
    ))
    check("scanned/classification", c["classification"] == "likely_scanned", str(c))
    check("scanned/reason-images", "images_present" in c["classification_reasons"], str(c))
    check("scanned/ocr-recommended", c["ocr_recommended"] is True, str(c))


def test_blank_or_low_text_page() -> None:
    # Measured: no images, no drawings, no text → genuinely blank.
    c = _classify_pdf_page(_page(
        method="none", text_chars=0, word_count=0,
        image_object_count=0, has_images=False,
        drawing_object_count=0, has_drawings=False,
    ))
    check("blank/classification", c["classification"] == "blank_or_low_text", str(c))
    check("blank/reason", "no_visual_objects" in c["classification_reasons"], str(c))
    check("blank/ocr-not-recommended", c["ocr_recommended"] is False, str(c))


def test_mixed_page() -> None:
    # Meaningful embedded text AND image objects present.
    c = _classify_pdf_page(_page(
        method="embedded_text", text_chars=500, word_count=80,
        image_object_count=2, has_images=True,
        drawing_object_count=1, has_drawings=True,
    ))
    check("mixed/classification", c["classification"] == "mixed", str(c))
    check("mixed/reason-images", "images_present" in c["classification_reasons"], str(c))
    check("mixed/ocr-not-recommended", c["ocr_recommended"] is False, str(c))


def test_unknown_when_visual_signals_missing() -> None:
    # Low-text page with NO visual signals measured → cannot tell scan from blank.
    c = _classify_pdf_page(_page(method="none", text_chars=0, word_count=0))
    check("unknown/classification", c["classification"] == "unknown", str(c))
    check("unknown/reason", "visual_signals_unavailable" in c["classification_reasons"], str(c))
    check("unknown/ocr-not-recommended", c["ocr_recommended"] is False, str(c))


def test_unknown_method() -> None:
    c = _classify_pdf_page(_page(method="unknown", text_chars=0, word_count=0))
    check("unknown-method/classification", c["classification"] == "unknown", str(c))


def test_sparse_embedded_with_images_is_scanned() -> None:
    # embedded_text method but sparse text (OCR-empty fallback) + image present.
    c = _classify_pdf_page(_page(
        method="embedded_text", text_chars=12, word_count=2,
        warnings=["ocr_empty_fallback_embedded_text"],
        image_object_count=1, has_images=True,
        drawing_object_count=0, has_drawings=False,
    ))
    check("sparse/classification", c["classification"] == "likely_scanned", str(c))
    check("sparse/ocr-recommended", c["ocr_recommended"] is True, str(c))


def test_drawings_only_low_text_is_scanned() -> None:
    # Vector content, no images, near-zero text → likely_scanned (visual present).
    c = _classify_pdf_page(_page(
        method="none", text_chars=0, word_count=0,
        image_object_count=0, has_images=False,
        drawing_object_count=9, has_drawings=True,
    ))
    check("drawings/classification", c["classification"] == "likely_scanned", str(c))
    check("drawings/reason", "drawings_present" in c["classification_reasons"], str(c))


def test_partial_visual_measurement_is_unknown() -> None:
    # Image signal unavailable (None) but drawings measured-absent → can't be sure
    # there are no images, so a low-text page stays unknown rather than blank.
    c = _classify_pdf_page(_page(
        method="none", text_chars=0, word_count=0,
        image_object_count=None, has_images=None,
        drawing_object_count=0, has_drawings=False,
        visual_warnings=["visual_image_signal_unavailable"],
    ))
    check("partial/classification", c["classification"] == "unknown", str(c))
    check("partial/reason", "visual_signals_unavailable" in c["classification_reasons"], str(c))


def test_error_warning_classifies_error() -> None:
    c = _classify_pdf_page(_page(
        method="embedded_text", text_chars=900, word_count=140,
        warnings=["page_extraction_error"],
    ))
    check("error/classification", c["classification"] == "error", str(c))
    check("error/reason", c["classification_reasons"] == ["error_warning"], str(c))
    check("error/ocr-not-recommended", c["ocr_recommended"] is False, str(c))


def test_classifier_degrades_not_fails() -> None:
    # Hostile / malformed input must not raise; must degrade to unknown-safe.
    raised = False
    try:
        c = _classify_pdf_page({"method": object(), "text_chars": "oops", "word_count": None})
    except Exception as exc:  # pragma: no cover - failure path
        raised = True
        c = {}
        print(f"  unexpected raise: {type(exc).__name__}")
    check("degrade/no-raise", not raised)
    check("degrade/classification-valid", c.get("classification") in _CLASSIFICATIONS, str(c))


# --- sanitiser-level guarantees --------------------------------------------


def test_safe_classification_coerces_unknown() -> None:
    check("safe-class/known", _safe_classification("mixed") == "mixed")
    check("safe-class/bogus", _safe_classification("evil; rm -rf") == "unknown")
    check("safe-class/none", _safe_classification(None) == "unknown")
    check("safe-class/wrong-type", _safe_classification(42) == "unknown")


def test_safe_reasons_whitelists() -> None:
    check(
        "safe-reasons/keeps-known",
        _safe_reasons(["images_present", "method_ocr"]) == ["images_present", "method_ocr"],
    )
    check("safe-reasons/drops-unknown", _safe_reasons(["/host/path", "x"]) == ["classification_unavailable"])
    check("safe-reasons/non-list", _safe_reasons("oops") == ["classification_unavailable"])
    check("safe-reasons/all-in-vocab", all(r in _CLASSIFICATION_REASONS for r in _safe_reasons(["images_present"])) )


def test_safe_page_adds_classification_and_overwrites_smuggled() -> None:
    # A hostile upstream record tries to smuggle a fake classification, reasons,
    # paths, image data, and a secret. _safe_page must recompute classification
    # from the sanitized signals and drop every non-whitelisted key.
    raw = {
        "page": 7,
        "method": "embedded_text",
        "text_chars": 800,
        "word_count": 120,
        "has_page_anchor": True,
        "warnings": [],
        "image_object_count": 0,
        "has_images": False,
        "drawing_object_count": 0,
        "has_drawings": False,
        "classification": "totally_trusted_value",
        "classification_reasons": ["/host/secret/lecture.pdf", "BASE64DEADBEEF"],
        "ocr_recommended": True,
        "host_path": "/host/secret/lecture.pdf",
        "image_data": "BASE64DEADBEEF",
        "authorization": "Bearer sk-leak0123456789abcdef",
    }
    out = _safe_page(raw)
    check("overwrite/recomputed", out.get("classification") == "embedded_text", str(out))
    check(
        "overwrite/reasons-clean",
        all(r in _CLASSIFICATION_REASONS for r in out.get("classification_reasons", [])),
        str(out),
    )
    check("overwrite/ocr-recomputed", out.get("ocr_recommended") is False, str(out))
    check("overwrite/no-host-path", "host_path" not in out, str(out))
    check("overwrite/no-image-data", "image_data" not in out, str(out))
    check("overwrite/no-authorization", "authorization" not in out, str(out))
    check("overwrite/no-secret-leak", KEYLIKE.search(repr(out)) is None, str(out))
    check("overwrite/no-path-leak", "/host" not in repr(out), str(out))


def test_safe_page_legacy_record_gets_classification() -> None:
    # A version-1 page record (no visual signals) still gets an advisory
    # classification derived from method + text alone.
    raw = {
        "page": 2,
        "method": "ocr",
        "text_chars": 50,
        "word_count": 9,
        "has_page_anchor": True,
        "warnings": [],
    }
    out = _safe_page(raw)
    check("legacy/has-classification", out.get("classification") == "ocr_fallback", str(out))
    check("legacy/reasons-present", isinstance(out.get("classification_reasons"), list), str(out))
    check("legacy/ocr-recommended-bool", isinstance(out.get("ocr_recommended"), bool), str(out))
    # No visual signals must have been invented from a legacy record.
    check("legacy/no-image-count", "image_object_count" not in out, str(out))


def test_safe_page_always_valid_classification() -> None:
    # Whatever the inputs, the persisted classification is always in the vocab.
    for method in ["embedded_text", "ocr", "none", "unknown", "weird", None]:
        out = _safe_page(_page(method=method, text_chars=5, word_count=1))
        check(
            f"always-valid/{method}",
            out.get("classification") in _CLASSIFICATIONS,
            str(out),
        )


if __name__ == "__main__":
    test_embedded_text_page()
    test_ocr_fallback_page()
    test_likely_scanned_page()
    test_blank_or_low_text_page()
    test_mixed_page()
    test_unknown_when_visual_signals_missing()
    test_unknown_method()
    test_sparse_embedded_with_images_is_scanned()
    test_drawings_only_low_text_is_scanned()
    test_partial_visual_measurement_is_unknown()
    test_error_warning_classifies_error()
    test_classifier_degrades_not_fails()
    test_safe_classification_coerces_unknown()
    test_safe_reasons_whitelists()
    test_safe_page_adds_classification_and_overwrites_smuggled()
    test_safe_page_legacy_record_gets_classification()
    test_safe_page_always_valid_classification()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"PDF page-classification tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
