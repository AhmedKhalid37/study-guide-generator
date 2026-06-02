#!/usr/bin/env python3
"""Regression test for mixed scanned/text PDF extraction (per-page OCR fallback).

Builds a synthetic 3-page PDF entirely in-memory:

  * page 1 — real embedded (selectable) text
  * page 2 — image-only "scanned" page (no text layer; words drawn as pixels)
  * page 3 — image-only "scanned" page

then runs ``pipeline.extract.extract_file`` and asserts the document is treated
as MIXED: page 1 comes from embedded text, pages 2-3 from OCR, every ``## Page N``
heading is present, the extractor reports ``pdf_mixed``, and the total extracted
text is far larger than page-1-only. This pins the fix for the all-or-nothing bug
where one page of embedded text suppressed OCR for the rest of the document.

No external APIs (no DeepSeek/Qwen). Requires PyMuPDF + tesseract + Pillow; when
those are unavailable (e.g. a host without the OCR stack) the test SKIPS cleanly
with exit 0. Run it inside the Docker image for full coverage.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

# Make the repo root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _skip(msg: str) -> "None":
    print(f"[SKIP] {msg}")
    sys.exit(0)


try:
    import fitz  # PyMuPDF
except ImportError:
    _skip("PyMuPDF (fitz) not installed — mixed-PDF OCR test needs it.")

from pipeline.extract import _ocr_available, extract_file

_ready, _reason = _ocr_available()
if not _ready:
    _skip(f"OCR prerequisites unavailable: {_reason}")

from PIL import Image, ImageDraw, ImageFont

EMBEDDED_P1 = "Page one carries real embedded selectable text about neural networks."
OCR_WORDS_P2 = ["BACKPROPAGATION", "GRADIENT", "DESCENT"]
OCR_WORDS_P3 = ["NEURON", "ACTIVATION", "SIGMOID"]
ALL_OCR_WORDS = OCR_WORDS_P2 + OCR_WORDS_P3

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
)


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _image_only_page(doc, words: list[str]) -> None:
    """Add a page whose content is a rasterised image with NO text layer."""
    canvas = Image.new("RGB", (1240, 1754), "white")  # ~A4 @ ~150 dpi
    draw = ImageDraw.Draw(canvas)
    font = _font(72)
    y = 160
    for word in words:
        draw.text((120, y), word, fill="black", font=font)
        y += 200
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    page = doc.new_page(width=595, height=842)  # A4 in points
    page.insert_image(page.rect, stream=buf.getvalue())


def _build_pdf(path: Path) -> None:
    doc = fitz.open()
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((72, 100), EMBEDDED_P1, fontsize=14)
    _image_only_page(doc, OCR_WORDS_P2)
    _image_only_page(doc, OCR_WORDS_P3)
    doc.save(str(path))
    doc.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "mixed.pdf"
        _build_pdf(pdf_path)

        result = extract_file(pdf_path)
        text = result.text
        print(f"mode={result.mode}  total_chars={len(text)}")

        # Every page anchor survives extraction.
        for n in (1, 2, 3):
            assert f"## Page {n}" in text, f"missing '## Page {n}' heading"

        # Page 1 used its embedded text (not OCR).
        assert "embedded" in text.lower(), "page 1 embedded text not carried through"

        # Pages 2-3 went through OCR -> the document is reported as mixed.
        assert result.mode == "pdf_mixed", f"expected mode 'pdf_mixed', got '{result.mode}'"

        # OCR produced real content (lenient: tesseract isn't perfect, so require
        # at least 3 of the 6 distinctive words across the two image pages).
        upper = text.upper()
        hits = [w for w in ALL_OCR_WORDS if w in upper]
        assert len(hits) >= 3, f"OCR output too weak; recognised only {hits}"

        # Pages 2-3 (the OCR'd ones) must contribute real content beyond page 1.
        # This is the exact regression: the all-or-nothing gate dropped every page
        # after the first text page (e.g. pages 2-118 of a scanned deck).
        sections = text.split("## Page ")  # [0]=preamble, [1]=page1, [2]=page2, ...
        assert len(sections) >= 4, f"expected 3 page sections, got {len(sections) - 1}"
        beyond_page1 = sum(len(s.strip()) for s in sections[2:])
        assert beyond_page1 > 20, f"pages 2-3 contributed too little OCR text ({beyond_page1} chars)"

        print(f"OCR words recognised: {hits}; chars beyond page 1: {beyond_page1}")
        print("[PASS] mixed-PDF per-page OCR fallback (page 1 text + pages 2-3 OCR)")


if __name__ == "__main__":
    main()
