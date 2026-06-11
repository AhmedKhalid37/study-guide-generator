#!/usr/bin/env python3
"""Focused tests for the Slice 32 OCR provider boundary.

Run with:

    python test_scripts/test_ocr_provider.py

No external APIs and no real Tesseract required: the success/degrade paths are
exercised with a stub provider injected into the extraction loop. The optional
real-Tesseract end-to-end path is gated on availability and SKIPS cleanly when a
binary/lib is missing (mirroring test_mixed_pdf_ocr.py). PyMuPDF (fitz) is needed
for the synthetic PDF fixtures and is SKIPPED cleanly when unavailable.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Anything that must NEVER appear in a provider result/reason (paths, creds, argv).
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/[A-Za-z0-9_.\-]+){2,}")


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


try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import pipeline.extract as extract  # noqa: E402
from pipeline.extract import extract_file  # noqa: E402
from pipeline.ocr_provider import (  # noqa: E402
    TESSERACT_PROVIDER_ID,
    OcrProvider,
    OcrRequest,
    OcrResult,
    TesseractLocalOcrProvider,
    get_default_ocr_provider,
)


class _StubProvider(OcrProvider):
    """Deterministic, dependency-free provider for behaviour tests."""

    def __init__(self, *, ready: bool, reason: str | None, text: str, calls: list | None = None):
        self.provider_id = TESSERACT_PROVIDER_ID
        self._ready = ready
        self._reason = reason
        self._text = text
        self.calls = calls if calls is not None else []

    def is_available(self) -> tuple[bool, str | None]:
        return self._ready, self._reason

    def ocr_page(self, request: OcrRequest) -> OcrResult:
        self.calls.append(request.page_number)
        return OcrResult(text=self._text, provider_id=self.provider_id)


class _ExplodingProvider(OcrProvider):
    """Fails the test if OCR is ever invoked (used to prove text pages skip OCR)."""

    provider_id = TESSERACT_PROVIDER_ID

    def is_available(self) -> tuple[bool, str | None]:
        return True, None

    def ocr_page(self, request: OcrRequest) -> OcrResult:  # pragma: no cover - must not run
        raise AssertionError("OCR provider must not be called for a meaningful-text page")


def _build_blank_pdf(path: Path, *, page_texts: list[str | None]) -> None:
    """One page per entry; None => truly blank, str => that embedded text."""
    if fitz is None:
        raise RuntimeError("PyMuPDF unavailable")
    doc = fitz.open()
    for body in page_texts:
        page = doc.new_page(width=595, height=842)
        if body:
            page.insert_text((72, 100), body, fontsize=14)
    doc.save(str(path))
    doc.close()


def test_result_and_request_shape() -> None:
    result = OcrResult(text="hello", provider_id=TESSERACT_PROVIDER_ID)
    check("shape/text", result.text == "hello")
    check("shape/provider-id", result.provider_id == "tesseract_local")
    check("shape/confidence-default-none", result.confidence is None)
    check("shape/warnings-default-empty", result.warnings == [])
    check("shape/error-category-default-none", result.error_category is None)
    # Independent default lists per instance (no shared mutable default).
    other = OcrResult(text="", provider_id=TESSERACT_PROVIDER_ID)
    other.warnings.append("x")
    check("shape/warnings-not-shared", result.warnings == [])

    request = OcrRequest(page=object(), page_number=7)
    check("shape/request-page-number", request.page_number == 7)


def test_default_provider_identity() -> None:
    provider = get_default_ocr_provider()
    check("default/is-tesseract", isinstance(provider, TesseractLocalOcrProvider))
    check("default/provider-id", provider.provider_id == TESSERACT_PROVIDER_ID)
    check("default/singleton", get_default_ocr_provider() is provider)


def test_is_available_shape_and_safety() -> None:
    ready, reason = TesseractLocalOcrProvider().is_available()
    check("available/returns-bool", isinstance(ready, bool), repr(ready))
    check("available/reason-type", reason is None or isinstance(reason, str), repr(reason))
    if reason is not None:
        check("available/reason-no-path", PATHLIKE.search(reason) is None, reason)
        check("available/reason-no-key", KEYLIKE.search(reason) is None, reason)
        check(
            "available/reason-known",
            reason
            in {
                "OCR skipped because the tesseract binary is not available.",
                "OCR skipped because pytesseract or pillow is not installed.",
            },
            reason,
        )
    else:
        check("available/ready-when-no-reason", ready is True)


def test_extract_uses_provider_text_for_scanned_page() -> None:
    if fitz is None:
        print("[SKIP] provider success path - PyMuPDF (fitz) unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "scan.pdf"
        _build_blank_pdf(pdf, page_texts=[None])  # blank page -> wants OCR
        calls: list = []
        stub = _StubProvider(ready=True, reason=None, text="STUB OCR PAGE TEXT", calls=calls)
        original = extract.get_default_ocr_provider
        extract.get_default_ocr_provider = lambda: stub
        try:
            result = extract_file(pdf)
        finally:
            extract.get_default_ocr_provider = original
        check("success/provider-invoked", calls == [1], str(calls))
        check("success/text-used", "STUB OCR PAGE TEXT" in result.text, result.text)
        check("success/anchor-preserved", "## Page 1" in result.text, result.text)
        check("success/mode-ocr", result.mode == "pdf_ocr", result.mode)
        # Metadata records the OCR method exactly as before (no provider-id field
        # added to the artifact in this slice).
        page0 = (result.metadata or {}).get("pages", [{}])[0]
        check("success/method-ocr", page0.get("method") == "ocr", str(page0))
        check("success/no-ocr-provider-field", "ocr_provider" not in page0, str(page0))


def test_meaningful_text_page_skips_provider() -> None:
    if fitz is None:
        print("[SKIP] text page skips OCR - PyMuPDF (fitz) unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "text.pdf"
        _build_blank_pdf(
            pdf,
            page_texts=["This page has plenty of selectable embedded text for extraction."],
        )
        original = extract.get_default_ocr_provider
        extract.get_default_ocr_provider = lambda: _ExplodingProvider()
        try:
            result = extract_file(pdf)  # must not raise -> provider never called
        finally:
            extract.get_default_ocr_provider = original
        check("text/mode-text", result.mode == "pdf_text", result.mode)
        check("text/embedded-used", "plenty of selectable" in result.text, result.text)


def test_unavailable_provider_degrades_not_fails() -> None:
    if fitz is None:
        print("[SKIP] unavailable degrade path - PyMuPDF (fitz) unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "scan.pdf"
        # Page 1 blank (would OCR) ; page 2 sparse embedded text below the
        # meaningful gate (OCR fallback to embedded text).
        _build_blank_pdf(pdf, page_texts=[None, "hi"])
        reason = "OCR skipped because the tesseract binary is not available."
        stub = _StubProvider(ready=False, reason=reason, text="")
        original = extract.get_default_ocr_provider
        extract.get_default_ocr_provider = lambda: stub
        try:
            result = extract_file(pdf)  # must not raise
        finally:
            extract.get_default_ocr_provider = original
        check("degrade/no-raise", True)
        check("degrade/doc-warning", reason in result.warnings, str(result.warnings))
        # Page 2's sparse embedded text is kept as a fallback (used_text=True), so
        # the document mode resolves to pdf_text exactly as the pre-refactor code
        # did — degradation never fails or changes this derivation.
        check("degrade/mode-text", result.mode == "pdf_text", result.mode)
        pages = (result.metadata or {}).get("pages", [])
        by_num = {p.get("page"): p for p in pages}
        # Blank page dropped from text but represented in metadata with ocr_unavailable.
        check("degrade/page1-method-none", by_num.get(1, {}).get("method") == "none", str(by_num.get(1)))
        check(
            "degrade/page1-warning",
            "ocr_unavailable" in (by_num.get(1, {}).get("warnings") or []),
            str(by_num.get(1)),
        )
        # Sparse page kept as embedded-text fallback with ocr_unavailable warning.
        check("degrade/page2-method-embedded", by_num.get(2, {}).get("method") == "embedded_text", str(by_num.get(2)))
        check("degrade/page2-text-kept", "## Page 2" in result.text, result.text)


def test_provider_empty_result_drops_blank_page() -> None:
    if fitz is None:
        print("[SKIP] empty-OCR drop path - PyMuPDF (fitz) unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "scan.pdf"
        _build_blank_pdf(pdf, page_texts=[None])
        stub = _StubProvider(ready=True, reason=None, text="")  # OCR ran, found nothing
        original = extract.get_default_ocr_provider
        extract.get_default_ocr_provider = lambda: stub
        try:
            result = extract_file(pdf)
        finally:
            extract.get_default_ocr_provider = original
        check("empty/no-raise", True)
        check("empty/text-empty", result.text.strip() == "", repr(result.text))
        page0 = (result.metadata or {}).get("pages", [{}])[0]
        check("empty/method-none", page0.get("method") == "none", str(page0))
        check(
            "empty/no-text-warning",
            "no_text_extracted" in (page0.get("warnings") or []),
            str(page0),
        )


def test_no_leak_in_result_objects() -> None:
    result = OcrResult(
        text="ordinary recognised text",
        provider_id=TESSERACT_PROVIDER_ID,
        warnings=["provider_unavailable"],
        error_category=None,
    )
    blob = repr(result)
    check("leak/no-key", KEYLIKE.search(blob) is None, blob)
    check("leak/provider-id-only", result.provider_id == "tesseract_local")
    check("leak/warnings-are-tokens", all(" " not in w for w in result.warnings), str(result.warnings))


def test_real_tesseract_end_to_end_optional() -> None:
    if fitz is None:
        print("[SKIP] real-tesseract e2e - PyMuPDF (fitz) unavailable")
        return
    ready, _ = TesseractLocalOcrProvider().is_available()
    if not ready:
        print("[SKIP] real-tesseract e2e - tesseract/pytesseract/PIL unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "render.pdf"
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        # Large text the rasterise+OCR path should recover; not selectable as a
        # text layer? It is selectable, so this just confirms the provider runs
        # without error end-to-end. We don't assert exact OCR output.
        page.insert_text((72, 200), "HELLO", fontsize=48)
        doc.save(str(pdf))
        doc.close()
        request = OcrRequest(page=fitz.open(str(pdf))[0], page_number=1)
        out = TesseractLocalOcrProvider().ocr_page(request)
        check("e2e/provider-id", out.provider_id == "tesseract_local")
        check("e2e/text-is-str", isinstance(out.text, str), repr(out.text))


if __name__ == "__main__":
    test_result_and_request_shape()
    test_default_provider_identity()
    test_is_available_shape_and_safety()
    test_extract_uses_provider_text_for_scanned_page()
    test_meaningful_text_page_skips_provider()
    test_unavailable_provider_degrades_not_fails()
    test_provider_empty_result_drops_blank_page()
    test_no_leak_in_result_objects()
    test_real_tesseract_end_to_end_optional()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"OCR provider boundary tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
