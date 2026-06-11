#!/usr/bin/env python3
"""Focused tests for Slice 34 — wiring the OCR routing policy into extraction.

Run with:

    python test_scripts/test_ocr_routing_integration.py

The routing policy (Slice 33) is now consulted *live* in
``pipeline.extract`` and recorded as additive, advisory ``ocr_route_*`` page
fields that flow into ``extraction_metadata.json`` via the sanitiser.

These tests prove:

- a page's route is recorded from its already-collected signals (no new I/O);
- the route is **local-only** (provider is ``tesseract_local`` or ``None`` — never
  a cloud provider);
- the route is a *recorder, not a router*: extracted text and ``## Page N``
  anchors are byte-identical to before, and OCR-availability behaviour is
  unchanged;
- routing failure degrades to a fixed safe route and never breaks extraction;
- the persisted route tokens are closed-vocabulary only — no path, secret, image
  blob, or free-text error can survive into the artifact.

Most cases use lightweight dict "records" so every route branch is deterministic
with no PyMuPDF dependency; the end-to-end case builds a tiny real PDF and SKIPS
cleanly when PyMuPDF (fitz) is unavailable.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import pipeline.extract as extract_mod  # noqa: E402
from pipeline.extract import (  # noqa: E402
    _pdf_page_metadata,
    _pdf_route_decision,
    extract_file,
)
from pipeline.extraction_metadata import _safe_page, pdf_source_metadata  # noqa: E402
from pipeline.ocr_routing import (  # noqa: E402
    ACTIONS,
    CONFIDENCES,
    LOCAL_OCR_PROVIDER_ID,
    REASONS,
    WARNINGS,
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


def _record(**overrides) -> dict:
    """A minimal page record (post-`_pdf_page_metadata` shape, pre-routing)."""
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


def _scan_for_secret(node, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            found = _scan_for_secret(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_secret(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str) and KEYLIKE.search(node):
        return f"{path} (value looks like a credential)"
    return None


def _route_tokens_valid(route: dict) -> bool:
    return (
        route.get("ocr_route_action") in ACTIONS
        and (route.get("ocr_route_provider") in (None, LOCAL_OCR_PROVIDER_ID))
        and route.get("ocr_route_reason") in REASONS
        and route.get("ocr_route_confidence") in CONFIDENCES
        and isinstance(route.get("ocr_route_warnings"), list)
        and all(w in WARNINGS for w in route.get("ocr_route_warnings", []))
    )


# --- per-page route branch coverage (no fitz) ------------------------------


def test_text_page_uses_embedded_text() -> None:
    rec = _record(
        method="embedded_text", text_chars=900, word_count=140,
        image_object_count=0, has_images=False,
        drawing_object_count=0, has_drawings=False,
    )
    route = _pdf_route_decision(rec, ocr_ready=True)
    check("text/action", route["ocr_route_action"] == "use_embedded_text", str(route))
    check("text/provider-none", route["ocr_route_provider"] is None, str(route))
    check("text/reason", route["ocr_route_reason"] == "embedded_text_sufficient", str(route))
    check("text/no-warnings", route["ocr_route_warnings"] == [], str(route))
    check("text/tokens-valid", _route_tokens_valid(route), str(route))


def test_ocr_applied_page_uses_existing_text() -> None:
    # A page that the extractor already OCR'd (method="ocr") — re-OCR is pointless,
    # so the policy says use the captured text. This is the "OCR fallback page".
    rec = _record(
        method="ocr", text_chars=300, word_count=55,
        image_object_count=1, has_images=True,
        drawing_object_count=0, has_drawings=False,
    )
    route = _pdf_route_decision(rec, ocr_ready=True)
    check("ocr-applied/action", route["ocr_route_action"] == "use_embedded_text", str(route))
    check("ocr-applied/reason", route["ocr_route_reason"] == "ocr_already_applied", str(route))
    check("ocr-applied/provider-none", route["ocr_route_provider"] is None, str(route))


def test_scanned_page_routes_to_local_ocr_when_available() -> None:
    # Image-heavy, no extractable text, OCR yielded nothing → likely_scanned.
    # With local OCR available the policy records the local provider.
    rec = _record(
        method="none", text_chars=0, word_count=0, warnings=["no_text_extracted"],
        image_object_count=3, has_images=True,
        drawing_object_count=0, has_drawings=False,
    )
    route = _pdf_route_decision(rec, ocr_ready=True)
    check("scanned/action", route["ocr_route_action"] == "use_local_ocr", str(route))
    check("scanned/provider-local", route["ocr_route_provider"] == LOCAL_OCR_PROVIDER_ID, str(route))
    check("scanned/reason", route["ocr_route_reason"] == "scanned_needs_ocr", str(route))
    # Local-only guarantee: provider is never a cloud id.
    check("scanned/provider-not-cloud", route["ocr_route_provider"] == "tesseract_local", str(route))


def test_scanned_page_skips_when_ocr_unavailable() -> None:
    # Same scanned page, but local OCR is unavailable. The policy records skip_ocr
    # with safe warnings — and (proven elsewhere) extraction still falls back as
    # before. Cloud is NOT offered (cloud stays off in this slice).
    rec = _record(
        method="none", text_chars=0, word_count=0, warnings=["ocr_unavailable"],
        image_object_count=3, has_images=True,
        drawing_object_count=0, has_drawings=False,
    )
    route = _pdf_route_decision(rec, ocr_ready=False)
    check("unavail/action", route["ocr_route_action"] == "skip_ocr", str(route))
    check("unavail/provider-none", route["ocr_route_provider"] is None, str(route))
    check("unavail/warn-local", "local_ocr_unavailable" in route["ocr_route_warnings"], str(route))
    check("unavail/warn-cloud-off", "cloud_ocr_disabled" in route["ocr_route_warnings"], str(route))
    check("unavail/no-cloud-candidate", route["ocr_route_action"] != "cloud_ocr_candidate", str(route))


def test_blank_page_skips_ocr() -> None:
    rec = _record(
        method="none", text_chars=0, word_count=0,
        image_object_count=0, has_images=False,
        drawing_object_count=0, has_drawings=False,
    )
    route = _pdf_route_decision(rec, ocr_ready=True)
    check("blank/action", route["ocr_route_action"] == "skip_ocr", str(route))
    check("blank/reason", route["ocr_route_reason"] == "blank_low_text_no_visual", str(route))


def test_unknown_when_visual_signals_missing() -> None:
    rec = _record(method="none", text_chars=0, word_count=0)
    route = _pdf_route_decision(rec, ocr_ready=True)
    check("unknown/action", route["ocr_route_action"] == "unknown", str(route))
    check("unknown/reason", route["ocr_route_reason"] == "unknown_classification", str(route))
    check("unknown/provider-none", route["ocr_route_provider"] is None, str(route))


def test_route_never_offers_cloud_provider() -> None:
    # Across every branch, the provider is only ever local or None.
    for ready in (True, False):
        for rec in (
            _record(method="embedded_text", text_chars=900, word_count=140,
                     image_object_count=0, has_images=False,
                     drawing_object_count=0, has_drawings=False),
            _record(method="none", text_chars=0, word_count=0, warnings=["no_text_extracted"],
                    image_object_count=3, has_images=True,
                    drawing_object_count=0, has_drawings=False),
            _record(method="ocr", text_chars=120, word_count=20,
                    image_object_count=1, has_images=True,
                    drawing_object_count=0, has_drawings=False),
        ):
            route = _pdf_route_decision(rec, ocr_ready=ready)
            check(
                f"local-only/ready={ready}/{rec['method']}",
                route["ocr_route_provider"] in (None, LOCAL_OCR_PROVIDER_ID),
                str(route),
            )


# --- degrade-not-fail -------------------------------------------------------


def test_routing_failure_degrades_safely() -> None:
    # If the classifier/policy unexpectedly raises, the adapter records a fixed
    # safe route and never propagates — extraction must not fail.
    original = extract_mod.classify_pdf_page_record

    def _boom(_record):  # noqa: ANN001, ANN202
        raise RuntimeError("synthetic routing failure sk-abcdef0123456789xyz /host/secret")

    rec = _record(method="embedded_text", text_chars=900, word_count=140)
    extract_mod.classify_pdf_page_record = _boom
    raised = False
    try:
        route = _pdf_route_decision(rec, ocr_ready=True)
    except Exception as exc:  # pragma: no cover - failure path
        raised = True
        route = {}
        print(f"  unexpected raise: {type(exc).__name__}")
    finally:
        extract_mod.classify_pdf_page_record = original

    check("degrade/no-raise", not raised)
    check("degrade/action-unknown", route.get("ocr_route_action") == "unknown", str(route))
    check("degrade/reason", route.get("ocr_route_reason") == "routing_unavailable", str(route))
    check(
        "degrade/warn",
        "routing_input_unrecognized" in route.get("ocr_route_warnings", []),
        str(route),
    )
    check("degrade/no-secret-leak", KEYLIKE.search(repr(route)) is None, str(route))
    check("degrade/no-path-leak", "/host" not in repr(route), str(route))
    check("degrade/tokens-valid", _route_tokens_valid(route), str(route))


def test_pdf_page_metadata_is_additive() -> None:
    # _pdf_page_metadata must keep all legacy fields and merely add the route.
    rec = _pdf_page_metadata(
        4, "embedded_text", "x" * 200,
        has_page_anchor=True, visual={"image_object_count": 0, "has_images": False},
        ocr_ready=True,
    )
    check("additive/page", rec["page"] == 4, str(rec))
    check("additive/method", rec["method"] == "embedded_text", str(rec))
    check("additive/text-chars", rec["text_chars"] == 200, str(rec))
    check("additive/visual-kept", rec.get("image_object_count") == 0, str(rec))
    check("additive/route-present", rec.get("ocr_route_action") == "use_embedded_text", str(rec))
    check("additive/route-valid", _route_tokens_valid(rec), str(rec))


# --- sanitiser carries route safely ----------------------------------------


def test_safe_page_sanitises_smuggled_route() -> None:
    # A hostile upstream record tries to smuggle non-vocab route tokens, a URL,
    # a host path, and a secret. _safe_page must coerce every route field to a
    # safe token and never echo the smuggled value.
    raw = {
        "page": 9,
        "method": "none",
        "text_chars": 0,
        "word_count": 0,
        "has_page_anchor": False,
        "warnings": ["no_text_extracted"],
        "image_object_count": 2,
        "has_images": True,
        "drawing_object_count": 0,
        "has_drawings": False,
        "ocr_route_action": "exfiltrate; rm -rf /",
        "ocr_route_provider": "https://evil.example/ocr?key=sk-leak0123456789abcd",
        "ocr_route_reason": "/host/secret/lecture.pdf",
        "ocr_route_confidence": "0.99",
        "ocr_route_warnings": ["/host/secret", "BASE64DEADBEEF", "ocr_budget_exhausted"],
    }
    out = _safe_page(raw)
    check("smuggle/action-coerced", out.get("ocr_route_action") == "unknown", str(out))
    check("smuggle/provider-coerced", out.get("ocr_route_provider") is None, str(out))
    check("smuggle/reason-coerced", out.get("ocr_route_reason") == "routing_unavailable", str(out))
    check("smuggle/confidence-coerced", out.get("ocr_route_confidence") == "low", str(out))
    check(
        "smuggle/warnings-whitelisted",
        out.get("ocr_route_warnings") == ["ocr_budget_exhausted"],
        str(out),
    )
    check("smuggle/no-secret-leak", KEYLIKE.search(repr(out)) is None, str(out))
    check("smuggle/no-path-leak", "/host" not in repr(out), str(out))
    check("smuggle/no-url-leak", "evil.example" not in repr(out), str(out))


def test_safe_page_carries_valid_route() -> None:
    raw = {
        "page": 1,
        "method": "none",
        "text_chars": 0,
        "word_count": 0,
        "has_page_anchor": False,
        "warnings": ["no_text_extracted"],
        "image_object_count": 3,
        "has_images": True,
        "drawing_object_count": 0,
        "has_drawings": False,
        "ocr_route_action": "use_local_ocr",
        "ocr_route_provider": "tesseract_local",
        "ocr_route_reason": "scanned_needs_ocr",
        "ocr_route_confidence": "high",
        "ocr_route_warnings": [],
    }
    out = _safe_page(raw)
    check("carry/action", out.get("ocr_route_action") == "use_local_ocr", str(out))
    check("carry/provider", out.get("ocr_route_provider") == "tesseract_local", str(out))
    check("carry/reason", out.get("ocr_route_reason") == "scanned_needs_ocr", str(out))
    check("carry/confidence", out.get("ocr_route_confidence") == "high", str(out))


def test_safe_page_legacy_record_has_no_route() -> None:
    # A route-less (legacy / hand-built / non-PDF) record must not gain route
    # fields, keeping older artifacts byte-identical.
    raw = {
        "page": 2,
        "method": "embedded_text",
        "text_chars": 55,
        "word_count": 8,
        "has_page_anchor": True,
        "warnings": [],
    }
    out = _safe_page(raw)
    check("legacy/no-action", "ocr_route_action" not in out, str(out))
    check("legacy/no-provider", "ocr_route_provider" not in out, str(out))
    check("legacy/classification-present", out.get("classification") == "embedded_text", str(out))


# --- end-to-end: real PDF, text unchanged ----------------------------------

TEXT_PAGES = [
    "Page one contains enough embedded selectable text for routing metadata.",
    "Page two contains enough embedded selectable text for routing metadata.",
]


def _build_text_pdf(path: Path) -> None:
    doc = fitz.open()
    for body in TEXT_PAGES:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), body, fontsize=14)
    doc.save(str(path))
    doc.close()


def test_end_to_end_text_pdf_unchanged_text_with_route() -> None:
    if fitz is None:
        print("[SKIP] end-to-end text PDF routing - PyMuPDF (fitz) unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "lecture.pdf"
        _build_text_pdf(pdf)
        result = extract_file(pdf)

        # Extracted text + anchors are exactly as before routing was wired in.
        check("e2e/mode", result.mode == "pdf_text", result.mode)
        check("e2e/anchor-1", "## Page 1" in result.text, result.text[:80])
        check("e2e/anchor-2", "## Page 2" in result.text, result.text[:160])
        check("e2e/body-1", TEXT_PAGES[0] in result.text, result.text[:120])
        expected = "\n\n".join(f"## Page {i}\n{b}" for i, b in enumerate(TEXT_PAGES, start=1))
        check("e2e/text-byte-identical", result.text == expected, repr(result.text[:120]))

        pages = (result.metadata or {}).get("pages") or []
        check("e2e/page-count", len(pages) == 2, str(len(pages)))
        check(
            "e2e/page-route-embedded",
            all(p.get("ocr_route_action") == "use_embedded_text" for p in pages),
            str(pages),
        )
        check(
            "e2e/page-route-provider-none",
            all(p.get("ocr_route_provider") is None for p in pages),
            str(pages),
        )

        # Through the artifact sanitiser, the route survives, stays valid, and is
        # leak-free; the artifact version is unchanged (additive-field rule).
        source = pdf_source_metadata(
            filename="lecture.pdf",
            content_type="application/pdf",
            extraction_metadata=result.metadata,
        )
        spages = (source or {}).get("pages") or []
        check("e2e/safe-route-valid", all(_route_tokens_valid(p) for p in spages), str(spages))
        check("e2e/no-secret-leak", _scan_for_secret(source) is None, str(source)[:200])
        check(
            "e2e/no-path-or-image-keys",
            all(
                k not in p
                for p in spages
                for k in ("host_path", "image_data", "source_path", "argv")
            ),
            str(spages),
        )
        # Round-trips as JSON (closed-vocab tokens are all JSON-safe).
        check("e2e/json-safe", bool(json.dumps(source)))


if __name__ == "__main__":
    test_text_page_uses_embedded_text()
    test_ocr_applied_page_uses_existing_text()
    test_scanned_page_routes_to_local_ocr_when_available()
    test_scanned_page_skips_when_ocr_unavailable()
    test_blank_page_skips_ocr()
    test_unknown_when_visual_signals_missing()
    test_route_never_offers_cloud_provider()
    test_routing_failure_degrades_safely()
    test_pdf_page_metadata_is_additive()
    test_safe_page_sanitises_smuggled_route()
    test_safe_page_carries_valid_route()
    test_safe_page_legacy_record_has_no_route()
    test_end_to_end_text_pdf_unchanged_text_with_route()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"OCR routing integration tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
