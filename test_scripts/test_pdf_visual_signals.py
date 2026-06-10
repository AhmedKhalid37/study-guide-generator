#!/usr/bin/env python3
"""Focused tests for Slice 30 PDF page visual/object signals.

Run with:

    python test_scripts/test_pdf_visual_signals.py

No external APIs and no PyMuPDF dependency: the extractor helper is exercised
with lightweight fake "page" objects so failure paths and safety can be proven
deterministically. The artifact sanitiser (`_safe_page`) is checked directly to
prove the new additive fields are carried through safely and that no smuggled,
non-whitelisted keys (paths, image data) can leak into the artifact.
"""
from __future__ import annotations

import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")

from pipeline.extract import _pdf_visual_signals  # noqa: E402
from pipeline.extraction_metadata import _safe_page  # noqa: E402


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


class _Rect:
    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height


class _GoodPage:
    """A fake fitz page that reports two images, three drawings, and a size."""

    def get_images(self, full: bool = False):  # noqa: ANN001, FBT002
        return [("img1",), ("img2",)]

    def get_drawings(self):
        return [{"op": "l"}, {"op": "re"}, {"op": "c"}]

    @property
    def rect(self):
        return _Rect(595.0, 842.0)


class _EmptyPage:
    """A fake fitz page with no images and no drawings."""

    def get_images(self, full: bool = False):  # noqa: ANN001, FBT002
        return []

    def get_drawings(self):
        return []

    @property
    def rect(self):
        return _Rect(612.0, 792.0)


class _BrokenPage:
    """A fake fitz page whose every signal call raises — must degrade, not fail."""

    def get_images(self, full: bool = False):  # noqa: ANN001, FBT002
        raise RuntimeError("boom with secret sk-abcdef0123456789xyz and /host/secret/path")

    def get_drawings(self):
        raise ValueError("vector parse failed at /abs/host/path")

    @property
    def rect(self):
        raise AttributeError("no rect")


def test_good_page_signals() -> None:
    sig = _pdf_visual_signals(_GoodPage())
    check("good/image-count", sig.get("image_object_count") == 2, str(sig))
    check("good/drawing-count", sig.get("drawing_object_count") == 3, str(sig))
    check("good/has-images", sig.get("has_images") is True, str(sig))
    check("good/has-drawings", sig.get("has_drawings") is True, str(sig))
    check("good/width", sig.get("page_width") == 595.0, str(sig))
    check("good/height", sig.get("page_height") == 842.0, str(sig))
    check("good/no-visual-warnings", "visual_warnings" not in sig, str(sig))
    check("good/numeric-bool-only", _values_are_simple(sig), str(sig))


def test_empty_page_signals() -> None:
    sig = _pdf_visual_signals(_EmptyPage())
    check("empty/image-count", sig.get("image_object_count") == 0, str(sig))
    check("empty/drawing-count", sig.get("drawing_object_count") == 0, str(sig))
    check("empty/has-images", sig.get("has_images") is False, str(sig))
    check("empty/has-drawings", sig.get("has_drawings") is False, str(sig))
    check("empty/no-visual-warnings", "visual_warnings" not in sig, str(sig))


def test_broken_page_degrades_safely() -> None:
    # Must not raise, must return unknown-safe values, and must not leak the
    # exception message / secret / host path.
    raised = False
    try:
        sig = _pdf_visual_signals(_BrokenPage())
    except Exception as exc:  # pragma: no cover - failure path
        raised = True
        sig = {}
        print(f"  unexpected raise: {type(exc).__name__}")
    check("broken/no-raise", not raised)
    check("broken/image-none", sig.get("image_object_count") is None, str(sig))
    check("broken/drawing-none", sig.get("drawing_object_count") is None, str(sig))
    check("broken/has-images-none", sig.get("has_images") is None, str(sig))
    check("broken/has-drawings-none", sig.get("has_drawings") is None, str(sig))
    check("broken/width-none", sig.get("page_width") is None, str(sig))
    check("broken/height-none", sig.get("page_height") is None, str(sig))
    warns = sig.get("visual_warnings") or []
    check("broken/warns-categories", set(warns) == {
        "visual_image_signal_unavailable",
        "visual_drawing_signal_unavailable",
        "visual_dimension_signal_unavailable",
    }, str(warns))
    blob = repr(sig)
    check("broken/no-secret-leak", KEYLIKE.search(blob) is None, blob)
    check("broken/no-path-leak", "/host" not in blob and "/abs" not in blob, blob)
    check("broken/no-exc-message", "boom" not in blob and "parse failed" not in blob, blob)


def test_safe_page_carries_visual_fields() -> None:
    raw = {
        "page": 4,
        "method": "embedded_text",
        "text_chars": 100,
        "word_count": 18,
        "has_page_anchor": True,
        "warnings": [],
        "image_object_count": 2,
        "drawing_object_count": 0,
        "has_images": True,
        "has_drawings": False,
        "page_width": 595.0,
        "page_height": 842.0,
    }
    out = _safe_page(raw)
    check("safe/image-count", out.get("image_object_count") == 2, str(out))
    check("safe/drawing-count", out.get("drawing_object_count") == 0, str(out))
    check("safe/has-images", out.get("has_images") is True, str(out))
    check("safe/has-drawings", out.get("has_drawings") is False, str(out))
    check("safe/width", out.get("page_width") == 595.0, str(out))
    check("safe/height", out.get("page_height") == 842.0, str(out))


def test_safe_page_unknown_signals_round_trip() -> None:
    raw = {
        "page": 9,
        "method": "none",
        "text_chars": 0,
        "word_count": 0,
        "has_page_anchor": False,
        "warnings": ["no_text_extracted"],
        "image_object_count": None,
        "drawing_object_count": None,
        "has_images": None,
        "has_drawings": None,
        "page_width": None,
        "page_height": None,
        "visual_warnings": ["visual_image_signal_unavailable"],
    }
    out = _safe_page(raw)
    check("unknown/image-none", out.get("image_object_count") is None, str(out))
    check("unknown/has-images-none", out.get("has_images") is None, str(out))
    check("unknown/width-none", out.get("page_width") is None, str(out))
    check("unknown/visual-warns", out.get("visual_warnings") == ["visual_image_signal_unavailable"], str(out))


def test_safe_page_strips_smuggled_keys() -> None:
    # A malformed/hostile upstream record must not be able to push extra keys
    # (paths, image bytes) into the artifact. _safe_page whitelists fields.
    raw = {
        "page": 1,
        "method": "embedded_text",
        "text_chars": 10,
        "word_count": 2,
        "has_page_anchor": True,
        "warnings": [],
        "image_object_count": 1,
        "host_path": "/host/secret/lecture.pdf",
        "image_data": "BASE64DEADBEEF",
        "authorization": "Bearer sk-leak0123456789abcdef",
    }
    out = _safe_page(raw)
    check("strip/no-host-path", "host_path" not in out, str(out))
    check("strip/no-image-data", "image_data" not in out, str(out))
    check("strip/no-authorization", "authorization" not in out, str(out))
    check("strip/kept-count", out.get("image_object_count") == 1, str(out))
    check("strip/no-secret-leak", KEYLIKE.search(repr(out)) is None, str(out))


def test_safe_page_legacy_record_unchanged() -> None:
    # A version-1 page record (no visual keys) must round-trip with no new keys.
    raw = {
        "page": 2,
        "method": "ocr",
        "text_chars": 50,
        "word_count": 9,
        "has_page_anchor": True,
        "warnings": [],
    }
    out = _safe_page(raw)
    visual_keys = {
        "image_object_count",
        "drawing_object_count",
        "has_images",
        "has_drawings",
        "page_width",
        "page_height",
        "visual_warnings",
    }
    check("legacy/no-visual-keys", not (visual_keys & set(out)), str(out))
    check("legacy/method", out.get("method") == "ocr", str(out))


def test_safe_page_coerces_bad_numbers() -> None:
    raw = {
        "page": 1,
        "method": "embedded_text",
        "text_chars": 10,
        "word_count": 2,
        "has_page_anchor": True,
        "warnings": [],
        "image_object_count": -5,
        "page_width": float("inf"),
        "page_height": float("nan"),
    }
    out = _safe_page(raw)
    check("coerce/nonneg-count", out.get("image_object_count") == 0, str(out))
    check("coerce/inf-width-none", out.get("page_width") is None, str(out))
    check("coerce/nan-height-none", out.get("page_height") is None, str(out))


def _values_are_simple(node) -> bool:
    if isinstance(node, dict):
        return all(_values_are_simple(v) for v in node.values())
    if isinstance(node, list):
        return all(_values_are_simple(v) for v in node)
    if isinstance(node, float):
        return not (math.isinf(node) or math.isnan(node))
    return node is None or isinstance(node, (int, bool, str))


if __name__ == "__main__":
    test_good_page_signals()
    test_empty_page_signals()
    test_broken_page_degrades_safely()
    test_safe_page_carries_visual_fields()
    test_safe_page_unknown_signals_round_trip()
    test_safe_page_strips_smuggled_keys()
    test_safe_page_legacy_record_unchanged()
    test_safe_page_coerces_bad_numbers()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"PDF visual-signal tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
