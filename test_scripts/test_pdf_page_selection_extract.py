#!/usr/bin/env python3
"""Focused test for PDF page-selection extraction (Large-PDF Slice 4).

Proves that `pipeline.extract.extract_file(path, pages=...)` / `_extract_pdf`
honor a selection of ORIGINAL 1-based page numbers:

  * text PDF with pages 2-3 selected -> output has `## Page 2`, `## Page 3`, and
    NOT `## Page 1` (anchors keep their original numbers, never renumbered);
  * no selection (pages=None) == selecting every page (byte-identical text);
  * out-of-range selection -> safe warning, no crash, "no pages extracted" when
    nothing is in range;
  * (OCR-gated) scanned/image PDF with a selected subset -> OCR runs ONLY the
    selected pages, mode stays `pdf_ocr`;
  * (OCR-gated) mixed text/scanned PDF with a selected subset -> mode reflects the
    selected subset (`pdf_text` / `pdf_ocr` / `pdf_mixed`).

Also threads through `run_llm_job._attach_sources` to confirm a `page_selections`
map keyed by the ORIGINAL filename restricts extraction for the matching PDF only.

No external APIs. Requires PyMuPDF (fitz); OCR-specific checks additionally need
tesseract + Pillow and are SKIPPED (not failed) when the OCR stack is absent.
The whole test SKIPS cleanly (exit 0) without fitz. Run inside Docker for full
coverage.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0


def check(label: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}")


def _skip(msg: str) -> None:
    print(f"[SKIP] {msg}")
    sys.exit(0)


try:
    import fitz  # PyMuPDF
except ImportError:
    _skip("PyMuPDF (fitz) not installed — page-selection extraction test needs it.")

from pipeline.extract import _ocr_available, extract_file

_OCR_READY, _OCR_REASON = _ocr_available()

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
)


def _font(size: int):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text_page(doc, body: str) -> None:
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), body, fontsize=14)


def _image_only_page(doc, words: list[str]) -> None:
    """A page whose content is a rasterised image with NO embedded text layer."""
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(canvas)
    font = _font(72)
    y = 160
    for word in words:
        draw.text((120, y), word, fill="black", font=font)
        y += 200
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buf.getvalue())


# Distinctive per-page text so we can assert which pages were extracted.
TEXT_PAGES = [
    "Page one is all about thermodynamics and the first law of energy conservation.",
    "Page two covers entropy and the second law with several illustrative examples.",
    "Page three discusses enthalpy, Gibbs free energy, and spontaneous reactions here.",
]


def _build_text_pdf(path: Path) -> None:
    doc = fitz.open()
    for body in TEXT_PAGES:
        _text_page(doc, body)
    doc.save(str(path))
    doc.close()


def _build_scanned_pdf(path: Path) -> None:
    """3 image-only pages (each needs OCR)."""
    doc = fitz.open()
    _image_only_page(doc, ["ALPHA", "BETA"])
    _image_only_page(doc, ["GAMMA", "DELTA"])
    _image_only_page(doc, ["EPSILON", "ZETA"])
    doc.save(str(path))
    doc.close()


def _build_mixed_pdf(path: Path) -> None:
    """p1 text, p2 text, p3 image(OCR), p4 image(OCR)."""
    doc = fitz.open()
    _text_page(doc, TEXT_PAGES[0])
    _text_page(doc, TEXT_PAGES[1])
    _image_only_page(doc, ["BACKPROP", "GRADIENT"])
    _image_only_page(doc, ["NEURON", "SIGMOID"])
    doc.save(str(path))
    doc.close()


def test_text_selection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "text.pdf"
        _build_text_pdf(pdf)

        # pages 2-3 selected -> anchors Page 2 & 3, NOT Page 1.
        res = extract_file(pdf, pages={2, 3})
        check("text pages 2-3: has '## Page 2'", "## Page 2" in res.text)
        check("text pages 2-3: has '## Page 3'", "## Page 3" in res.text)
        check("text pages 2-3: NO '## Page 1'", "## Page 1" not in res.text)
        check("text pages 2-3: page-1 body absent", "thermodynamics" not in res.text.lower())
        check("text pages 2-3: page-2 body present", "entropy" in res.text.lower())
        check("text pages 2-3: mode pdf_text", res.mode == "pdf_text")
        check("text pages 2-3: no warnings", res.warnings == [])

        # Anchors keep ORIGINAL numbers (not renumbered to 1-2).
        check("text pages 2-3: not renumbered to Page 1/2 only", "## Page 1" not in res.text)

        # Single page deep in the doc.
        res_one = extract_file(pdf, pages={3})
        check("text page 3 only: only '## Page 3'", "## Page 3" in res_one.text and "## Page 1" not in res_one.text and "## Page 2" not in res_one.text)


def test_no_selection_identical() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "text.pdf"
        _build_text_pdf(pdf)

        full = extract_file(pdf)  # pages=None -> previous behaviour
        check("no selection: all three anchors present", all(f"## Page {n}" in full.text for n in (1, 2, 3)))
        check("no selection: mode pdf_text", full.mode == "pdf_text")

        # Selecting every page must be byte-identical to no selection at all.
        all_pages = extract_file(pdf, pages={1, 2, 3})
        check("select-all == no-selection (text identical)", all_pages.text == full.text)
        check("select-all == no-selection (mode identical)", all_pages.mode == full.mode)
        check("select-all == no-selection (warnings identical)", all_pages.warnings == full.warnings)


def test_out_of_range() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "text.pdf"
        _build_text_pdf(pdf)

        # Entirely out of range -> safe, empty, warned, no crash.
        res = extract_file(pdf, pages={99, 100})
        check("out-of-range only: empty text", res.text == "")
        check("out-of-range only: a warning was emitted", len(res.warnings) >= 1)
        check("out-of-range only: warning mentions no pages extracted", any("no pages were extracted" in w for w in res.warnings))
        check("out-of-range only: mode pdf_text (no crash)", res.mode == "pdf_text")

        # Partial out-of-range -> valid page kept, stray page warned.
        res2 = extract_file(pdf, pages={2, 99})
        check("partial out-of-range: keeps '## Page 2'", "## Page 2" in res2.text)
        check("partial out-of-range: drops page 1 & 3", "## Page 1" not in res2.text and "## Page 3" not in res2.text)
        check("partial out-of-range: warns about page 99", any("99" in w for w in res2.warnings))


def test_scanned_selection() -> None:
    if not _OCR_READY:
        print(f"[SKIP] scanned-PDF OCR selection: {_OCR_REASON}")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "scanned.pdf"
        _build_scanned_pdf(pdf)

        # Select only page 2 (image-only) -> OCR runs that page only, mode pdf_ocr.
        res = extract_file(pdf, pages={2})
        upper = res.text.upper()
        check("scanned page 2: '## Page 2' present", "## Page 2" in res.text)
        check("scanned page 2: page 1 & 3 absent", "## Page 1" not in res.text and "## Page 3" not in res.text)
        check("scanned page 2: mode pdf_ocr", res.mode == "pdf_ocr")
        # OCR of page 2 should surface GAMMA/DELTA, not ALPHA (p1) or EPSILON (p3).
        check("scanned page 2: page-1 OCR words absent", "ALPHA" not in upper and "BETA" not in upper)
        check("scanned page 2: page-3 OCR words absent", "EPSILON" not in upper and "ZETA" not in upper)
        check("scanned page 2: at least one of its words recognised", ("GAMMA" in upper) or ("DELTA" in upper))


def test_mixed_selection() -> None:
    if not _OCR_READY:
        print(f"[SKIP] mixed-PDF mode-by-subset: {_OCR_REASON}")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "mixed.pdf"
        _build_mixed_pdf(pdf)

        # Full doc is mixed.
        full = extract_file(pdf)
        check("mixed full: mode pdf_mixed", full.mode == "pdf_mixed")

        # Select the two text pages (1,2) -> pure text subset.
        text_only = extract_file(pdf, pages={1, 2})
        check("mixed subset {1,2}: mode pdf_text", text_only.mode == "pdf_text")
        check("mixed subset {1,2}: anchors 1 & 2 only", "## Page 1" in text_only.text and "## Page 2" in text_only.text and "## Page 3" not in text_only.text)

        # Select the two image pages (3,4) -> pure OCR subset.
        ocr_only = extract_file(pdf, pages={3, 4})
        check("mixed subset {3,4}: mode pdf_ocr", ocr_only.mode == "pdf_ocr")
        check("mixed subset {3,4}: original anchors 3 & 4 (not renumbered)", "## Page 3" in ocr_only.text and "## Page 4" in ocr_only.text and "## Page 1" not in ocr_only.text)

        # Select one text + one image page (2,3) -> mixed subset.
        mixed_subset = extract_file(pdf, pages={2, 3})
        check("mixed subset {2,3}: mode pdf_mixed", mixed_subset.mode == "pdf_mixed")
        check("mixed subset {2,3}: anchors 2 & 3 only", "## Page 2" in mixed_subset.text and "## Page 3" in mixed_subset.text and "## Page 1" not in mixed_subset.text and "## Page 4" not in mixed_subset.text)


def test_attach_sources_threads_selection() -> None:
    """`_attach_sources` keys selections by ORIGINAL filename, PDFs only."""
    from pipeline.job_manager import Job
    from pipeline.run_llm_job import AttachmentSource, _attach_sources

    job: Job | None = None
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "lecture.pdf"
        _build_text_pdf(pdf)

        try:
            job = Job.create({"path_mode": "generate", "input_type": "text", "title": "sel-test"})
            attachments = [AttachmentSource(path=pdf, filename="lecture.pdf")]

            # Selection keyed by the original filename -> only pages 2-3 extracted.
            augmented, report = _attach_sources(
                job,
                "Base source.",
                attachments,
                page_selections={"lecture.pdf": [[2, 3]]},
            )
            check("attach: pages 2-3 in augmented source", "## Page 2" in augmented and "## Page 3" in augmented)
            check("attach: page 1 excluded from augmented source", "## Page 1" not in augmented)
            entry = report["files"][0]
            check("attach: file extracted", entry["status"] == "extracted")
            check("attach: original_filename preserved as key", entry["original_filename"] == "lecture.pdf")

            # A selection for a DIFFERENT filename must NOT affect this PDF (all pages).
            augmented2, _ = _attach_sources(
                job,
                "Base source.",
                attachments,
                page_selections={"other.pdf": [[2, 3]]},
            )
            check("attach: non-matching key -> all pages kept", all(f"## Page {n}" in augmented2 for n in (1, 2, 3)))
        finally:
            if job is not None:
                import shutil

                shutil.rmtree(job.dir, ignore_errors=True)


if __name__ == "__main__":
    test_text_selection()
    test_no_selection_identical()
    test_out_of_range()
    test_scanned_selection()
    test_mixed_selection()
    test_attach_sources_threads_selection()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
