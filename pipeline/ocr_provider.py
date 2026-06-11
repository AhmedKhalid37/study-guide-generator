"""Backend-only OCR provider boundary (Slice 32).

A thin, internal abstraction that isolates *how* a page is OCR'd from the
extraction loop in :mod:`pipeline.extract`. Today there is exactly one provider —
:class:`TesseractLocalOcrProvider` (``provider_id == "tesseract_local"``) — which
is a **behaviour-identical** wrapper around the previous in-line Tesseract path
(``_ocr_available`` / ``_ocr_page`` / ``_preprocess_ocr_image``). Introducing the
boundary here lets later slices add a hybrid router and (eventually, gated) a
cloud OCR provider **without** touching the extraction control flow.

Scope guardrails for this slice (see ``docs/HYBRID_OCR_DESIGN.md`` §4):

- **Local behaviour unchanged.** The Tesseract provider rasterises, preprocesses
  and recognises exactly as before; the same pages are OCR'd, the same text comes
  out, and the same availability messages are surfaced. No exception that the old
  in-line path let propagate is newly swallowed here.
- **No cloud / Mistral provider, no routing change, no provider settings.**
- **JSON-safe, leak-free output.** :class:`OcrResult` carries only normalised,
  whitelisted fields (text, provider id, optional confidence, safe warning/error
  *categories*). No image bytes, raw page objects, file paths, argv, URLs, keys,
  tokens, or raw provider error strings ever appear on a result.

The richer degrade-not-fail contract (safe ``error_category`` on failure, cloud →
local fallback) described in the design doc is part of the *boundary shape* for
future providers; the local provider's externally observable behaviour is
deliberately identical to the pre-refactor code in this slice.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from PIL import Image as PILImage


TESSERACT_PROVIDER_ID = "tesseract_local"


@dataclass(frozen=True)
class OcrRequest:
    """A single page to OCR.

    ``page`` is a PyMuPDF (``fitz``) page handle that the provider rasterises
    itself — the extraction loop never passes whole documents, absolute paths, or
    job/user identifiers across the boundary. ``page_number`` is the 1-based
    *original* page number (used only for context/diagnostics; the local provider
    does not need it to recognise text).
    """

    page: Any
    page_number: int


@dataclass(frozen=True)
class OcrResult:
    """Normalised, JSON-safe OCR output for one page.

    Whitelisted fields only — never image bytes, raw page data, paths, URLs, keys,
    or raw provider error strings. ``warnings`` / ``error_category`` carry stable
    *category* tokens, not free text. ``confidence`` is ``None`` unless a provider
    reports it cheaply (the local Tesseract path does not, so it stays ``None``).
    """

    text: str
    provider_id: str
    confidence: float | None = None
    warnings: list[str] = field(default_factory=list)
    error_category: str | None = None


class OcrProvider:
    """Backend-only OCR provider contract.

    Implementations expose a stable ``provider_id``, an availability probe with the
    same ``(ready, reason)`` shape the extractor already consumes, and a per-page
    ``ocr_page`` that returns a normalised :class:`OcrResult`.
    """

    provider_id: str = "base"

    def is_available(self) -> tuple[bool, str | None]:
        """Return ``(ready, reason)``. ``reason`` is a safe, user-facing string
        explaining why OCR is unavailable, or ``None`` when ready."""
        raise NotImplementedError

    def ocr_page(self, request: OcrRequest) -> OcrResult:
        """OCR a single page. Callers should confirm :meth:`is_available` first."""
        raise NotImplementedError


def _preprocess_ocr_image(image: "PILImage.Image") -> "PILImage.Image":
    """Grayscale + optional upscale + binary threshold for better Tesseract accuracy.

    Only reached from the OCR path — text-based PDFs never hit this. The 2x fitz
    matrix already rasterises at double resolution; this adds a further scale step
    only when the result is still narrow (<2000 px), then applies autocontrast + a
    binary threshold to sharpen slide text. Behaviour-identical to the pre-Slice-32
    ``pipeline.extract._preprocess_ocr_image``.
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


class TesseractLocalOcrProvider(OcrProvider):
    """Local, Tesseract-only OCR — the default (and today only) provider.

    Behaviour-identical wrapper around the previous in-line extraction OCR path.
    Availability and recognition produce the same results and the same surfaced
    messages as before the boundary was introduced.
    """

    provider_id = TESSERACT_PROVIDER_ID

    def is_available(self) -> tuple[bool, str | None]:
        """Check OCR prerequisites (tesseract binary + python libs).

        Same checks, same order, and the **same** user-facing reason strings as the
        pre-Slice-32 ``_ocr_available`` so the warning surfaced once per document is
        unchanged.
        """
        if shutil.which("tesseract") is None:
            return False, "OCR skipped because the tesseract binary is not available."
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError:
            return False, "OCR skipped because pytesseract or pillow is not installed."
        return True, None

    def ocr_page(self, request: OcrRequest) -> OcrResult:
        """Rasterise + preprocess + recognise a single ``fitz`` page.

        Identical pipeline to the previous ``_ocr_page``: 2x matrix rasterise →
        shared image preprocessing → ``pytesseract.image_to_string`` → ``strip()``.
        As before, exceptions raised by the underlying libraries are **not** caught
        here (the local path preserves its prior propagate-on-error behaviour); the
        ``error_category`` contract on :class:`OcrResult` is reserved for future
        providers.
        """
        import fitz
        import pytesseract
        from PIL import Image

        page = request.page
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        image = _preprocess_ocr_image(image)
        text = pytesseract.image_to_string(image).strip()
        return OcrResult(text=text, provider_id=self.provider_id)


_DEFAULT_PROVIDER = TesseractLocalOcrProvider()


def get_default_ocr_provider() -> OcrProvider:
    """Return the default OCR provider (local Tesseract).

    A stable module-level singleton — cheap and stateless. Later slices will choose
    a provider via the hybrid router; today this always yields the local provider so
    behaviour is unchanged.
    """
    return _DEFAULT_PROVIDER
