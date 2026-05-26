from __future__ import annotations

import csv
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
        pages = [page.get_text("text").strip() for page in document]
        text = "\n\n".join(page for page in pages if page)
        if text.strip():
            return ExtractionResult(text, "pdf_text", warnings)

        ocr_text, ocr_warning = _ocr_pdf(document)
        if ocr_warning:
            warnings.append(ocr_warning)
        return ExtractionResult(ocr_text, "pdf_ocr", warnings)


def _ocr_pdf(document) -> tuple[str, str | None]:
    if shutil.which("tesseract") is None:
        return "", "OCR skipped because the tesseract binary is not available."

    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "OCR skipped because pytesseract or pillow is not installed."

    pages: list[str] = []
    for page in document:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        text = pytesseract.image_to_string(image).strip()
        if text:
            pages.append(text)
    return "\n\n".join(pages), None
