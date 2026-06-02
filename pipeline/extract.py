from __future__ import annotations

import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".docx",
    ".pptx",
    ".pdf",
}


class ExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    mode: str
    warnings: list[str]


def extract_file(path: Path) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ExtractionError(f"Unsupported attachment type: {suffix or 'unknown'}")

    if suffix in {".txt", ".md", ".markdown"}:
        return ExtractionResult(path.read_text(encoding="utf-8", errors="replace"), "text", [])
    if suffix in {".csv", ".tsv"}:
        return ExtractionResult(_extract_table(path, delimiter="\t" if suffix == ".tsv" else ","), "table", [])
    if suffix == ".docx":
        return ExtractionResult(_extract_docx(path), "docx", [])
    if suffix == ".pptx":
        return ExtractionResult(_extract_pptx(path), "pptx", [])
    if suffix == ".pdf":
        return _extract_pdf(path)

    raise ExtractionError(f"Unsupported attachment type: {suffix or 'unknown'}")


def _extract_table(path: Path, *, delimiter: str) -> str:
    rows: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for row in reader:
            rows.append(" | ".join(cell.strip() for cell in row))
    return "\n".join(rows)


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ExtractionError("python-docx is not installed.") from exc

    try:
        document = Document(path)
    except Exception as exc:
        raise ExtractionError(
            f"the file may be corrupt or unreadable ({type(exc).__name__})"
        ) from exc
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_pptx(path: Path) -> str:
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise ExtractionError("python-pptx is not installed.") from exc

    try:
        presentation = Presentation(path)
    except Exception as exc:
        raise ExtractionError(
            f"the file may be corrupt or unreadable ({type(exc).__name__})"
        ) from exc
    parts: list[str] = []
    for index, slide in enumerate(presentation.slides, start=1):
        slide_parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_parts.append(shape.text.strip())
        if slide_parts:
            parts.append(f"Slide {index}\n" + "\n".join(slide_parts))
    return "\n\n".join(parts)


def _extract_pdf(path: Path) -> ExtractionResult:
    try:
        import fitz
    except ImportError as exc:
        raise ExtractionError("PyMuPDF is not installed.") from exc

    warnings: list[str] = []
    try:
        document_ctx = fitz.open(path)
    except Exception as exc:
        raise ExtractionError(
            f"the file may be corrupt or an unreadable scan ({type(exc).__name__})"
        ) from exc
    with document_ctx as document:
        # Prefix each page with a "## Page N" anchor (mirroring the pptx "Slide N"
        # marker) so positional references survive extraction — study-guide prompts
        # cite these. The index is the physical page number; blank pages are dropped
        # without shifting the numbering of the pages that follow.
        #
        # Page-level (not whole-document) text/OCR fallback: a mostly-scanned PDF
        # whose title slide happens to carry a few words of embedded text must not
        # be treated as "fully text-extracted". Each page decides independently —
        # pages with meaningful embedded text use it; sparse/scanned pages get OCR'd
        # on their own — so a 118-page scanned deck yields all its pages, not just
        # page 1.
        ocr_ready, ocr_unavailable_reason = _ocr_available()

        pages: list[str] = []
        used_text = False
        used_ocr = False
        wanted_ocr = False
        for index, page in enumerate(document, start=1):
            body = page.get_text("text").strip()
            if _is_meaningful_page_text(body):
                pages.append(f"## Page {index}\n{body}")
                used_text = True
                continue

            # Sparse/empty page → OCR it individually. A page uses embedded text
            # XOR OCR (never both), so the same content is not duplicated.
            wanted_ocr = True
            page_ocr = _ocr_page(page) if ocr_ready else ""
            if page_ocr:
                pages.append(f"## Page {index}\n{page_ocr}")
                used_ocr = True
            elif body:
                # OCR produced nothing (or is unavailable) but the page had a little
                # embedded text — keep it rather than dropping the page entirely.
                pages.append(f"## Page {index}\n{body}")
                used_text = True
            # else: genuinely blank page → dropped (numbering preserved by index).

        if wanted_ocr and not ocr_ready and ocr_unavailable_reason:
            warnings.append(ocr_unavailable_reason)

        text = "\n\n".join(pages)
        if used_ocr and used_text:
            mode = "pdf_mixed"
        elif used_ocr:
            mode = "pdf_ocr"
        elif used_text:
            mode = "pdf_text"
        else:
            # No usable text at all: OCR was intended but produced nothing
            # (unavailable, or genuinely empty scans). Report the OCR mode as the
            # all-or-nothing path did, so downstream "no text extracted" handling
            # is unchanged.
            mode = "pdf_ocr" if wanted_ocr else "pdf_text"
        return ExtractionResult(text, mode, warnings)


def _preprocess_ocr_image(image: "Image.Image") -> "Image.Image":
    """Grayscale + optional upscale + binary threshold for better Tesseract accuracy.

    Only called from the OCR path — text-based PDFs never reach this function.
    The 2x fitz matrix already rasterises at double resolution; this adds an
    additional scale step only when the result is still narrow (<2000 px), then
    applies autocontrast + a binary threshold to sharpen slide text.
    """
    from PIL import Image, ImageOps

    image = image.convert("L")
    if image.width < 2000:
        scale = 2000 / image.width
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            resample=Image.Resampling.LANCZOS,
        )
    image = ImageOps.autocontrast(image, cutoff=1)
    return image.point(lambda x: 0 if x < 128 else 255)


def _is_meaningful_page_text(text: str) -> bool:
    """Whether a page's embedded text is rich enough to skip OCR for that page.

    Conservative gate for the mixed scanned/text PDF path: a page counts as a real
    text page when it has either a reasonable amount of characters (>= 40) or
    several word-like tokens (>= 5). Sparse pages — blank scans, or image-only
    slides carrying just a stray label — fall through to per-page OCR instead of
    being accepted as "text extracted".
    """
    stripped = text.strip()
    if len(stripped) >= 40:
        return True
    return len(re.findall(r"\w+", stripped)) >= 5


def _ocr_available() -> tuple[bool, str | None]:
    """Check OCR prerequisites once (tesseract binary + python libs).

    Returns (ready, reason). When not ready, ``reason`` is a user-facing warning
    explaining why OCR was skipped — surfaced once per document rather than once
    per page.
    """
    if shutil.which("tesseract") is None:
        return False, "OCR skipped because the tesseract binary is not available."
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False, "OCR skipped because pytesseract or pillow is not installed."
    return True, None


def _ocr_page(page) -> str:
    """OCR a single fitz page, reusing the shared image preprocessing.

    Callers must confirm OCR is available via ``_ocr_available`` first; this keeps
    the per-page hot loop free of repeated binary/import probing.
    """
    import fitz
    import pytesseract
    from PIL import Image

    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    image = _preprocess_ocr_image(image)
    return pytesseract.image_to_string(image).strip()
