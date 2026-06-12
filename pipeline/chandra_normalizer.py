"""Pure, deterministic **Chandra output normalizer** (Slice 42).

Slice 39/41 confirmed that Chandra GGUF can run locally through ``llama-server``
and emit layout-HTML-ish output: per-region elements carrying ``data-bbox`` and
``data-label`` attributes (text, tables, equations, diagrams, figures, captions).
This module turns *that already-produced raw string* into two GuideForge-shaped
products **without ever calling Chandra, llama-server, or any model**:

1. a safe ``source_text`` fragment suitable for *future* source ingestion, and
2. a list of *asset candidates* shaped like the entries in
   :mod:`pipeline.visual_assets_manifest` (Slice 38/40 normalization boundary).

What this slice does and does NOT do
------------------------------------
- It is a **normalization core only**. It does **not** run Chandra, does **not**
  call ``llama-server``, does **not** download or open any model / mmproj file,
  does **not** wire Chandra into extraction or OCR routing, does **not** write
  ``clean.md`` or any image bytes, does **not** score candidates (``recommended_action``
  stays ``"unknown"``), and does **not** change generated guides or rendering.
- ``asset_ref`` is always ``None`` here — Chandra normalization writes no files.

Purity & safety
---------------
:func:`normalize_chandra_output` is a pure, *total* function of one raw string.
It imports **nothing** from PyMuPDF (``fitz``), Tesseract, llama.cpp, Mistral,
Gemini, a Chandra runtime, or the Local Model Manager — only Python stdlib
(``re``, ``html.parser``, ``typing``). It **never raises** on malformed model
output. Every emitted field is a fixed token from a closed vocabulary, an
int/float, ``None``, an empty dict, a deterministic ``asset_id``, or text that has
been scrubbed field-by-field so that no absolute/host path, URL, ``Authorization``
header, API key/token, socket path, argv-like flag, base64/image byte, or raw
``<script>``/``<style>`` HTML can survive into the output even if the model (or a
hostile document) smuggles one in.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

OUTPUT_VERSION = 1
OUTPUT_KIND = "chandra_normalized_output"
SOURCE_PROVIDER_CHANDRA_LOCAL = "chandra_local"

# Default advisory action only. Candidate scoring / text-replacement is a later
# slice; reserved-not-emitted here: "include_as_figure", "convert_to_table",
# "summarize_as_text", "omit".
RECOMMENDED_ACTION_UNKNOWN = "unknown"

# --- Closed asset-type vocabulary (this module owns what it may emit) ---------
#
# Conservative, closed set. ``text_block`` and ``caption`` are tracked internally
# for source-text assembly but are deliberately NOT emitted as visual asset
# candidates (we only surface tables/equations/diagrams/figures/images and an
# explicit ``unknown_region`` bucket).
ASSET_TYPE_TEXT_BLOCK = "text_block"
ASSET_TYPE_TABLE = "table"
ASSET_TYPE_EQUATION_BLOCK = "equation_block"
ASSET_TYPE_DIAGRAM = "diagram"
ASSET_TYPE_FIGURE = "figure"
ASSET_TYPE_IMAGE_REGION = "image_region"
ASSET_TYPE_UNKNOWN_REGION = "unknown_region"
ASSET_TYPE_CAPTION = "caption"

# Block types that become emitted visual asset candidates.
VISUAL_ASSET_TYPES = {
    ASSET_TYPE_TABLE,
    ASSET_TYPE_EQUATION_BLOCK,
    ASSET_TYPE_DIAGRAM,
    ASSET_TYPE_FIGURE,
    ASSET_TYPE_IMAGE_REGION,
    ASSET_TYPE_UNKNOWN_REGION,
}

# Closed warning tokens (no raw payloads ever appear in a warning).
WARNINGS = {
    "bbox_missing",
    "bbox_invalid",
    "label_unrecognized",
    "output_malformed",
    "empty_output",
}

# --- Label / tag → (block_type, normalized display label) --------------------
#
# Display label is itself a closed, Title-cased token so the raw model label is
# never echoed verbatim. Anything unrecognized maps to ("unknown_region",
# "Unknown") plus a ``label_unrecognized`` warning.
_LABEL_MAP: dict[str, tuple[str, str]] = {
    "text": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "plain text": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "plain-text": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "paragraph": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "body": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "list": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "list-item": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "footnote": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "page-header": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "page-footer": (ASSET_TYPE_TEXT_BLOCK, "Text"),
    "title": (ASSET_TYPE_TEXT_BLOCK, "Title"),
    "subtitle": (ASSET_TYPE_TEXT_BLOCK, "Title"),
    "heading": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "header": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "section-header": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "section header": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "table": (ASSET_TYPE_TABLE, "Table"),
    "equation": (ASSET_TYPE_EQUATION_BLOCK, "Equation"),
    "formula": (ASSET_TYPE_EQUATION_BLOCK, "Equation"),
    "isolate_formula": (ASSET_TYPE_EQUATION_BLOCK, "Equation"),
    "math": (ASSET_TYPE_EQUATION_BLOCK, "Equation"),
    "diagram": (ASSET_TYPE_DIAGRAM, "Diagram"),
    "chart": (ASSET_TYPE_DIAGRAM, "Diagram"),
    "flowchart": (ASSET_TYPE_DIAGRAM, "Diagram"),
    "graph": (ASSET_TYPE_DIAGRAM, "Diagram"),
    "figure": (ASSET_TYPE_FIGURE, "Figure"),
    "image": (ASSET_TYPE_IMAGE_REGION, "Image"),
    "picture": (ASSET_TYPE_IMAGE_REGION, "Image"),
    "photo": (ASSET_TYPE_IMAGE_REGION, "Image"),
    "caption": (ASSET_TYPE_CAPTION, "Caption"),
    "figure-caption": (ASSET_TYPE_CAPTION, "Caption"),
}

# Semantic tags that open a region even without an explicit ``data-label``.
_TAG_DEFAULT: dict[str, tuple[str, str]] = {
    "table": (ASSET_TYPE_TABLE, "Table"),
    "figure": (ASSET_TYPE_FIGURE, "Figure"),
    "img": (ASSET_TYPE_IMAGE_REGION, "Image"),
    "math": (ASSET_TYPE_EQUATION_BLOCK, "Equation"),
    "h1": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "h2": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "h3": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "h4": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "h5": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
    "h6": (ASSET_TYPE_TEXT_BLOCK, "Section-Header"),
}

_VOID_TAGS = {
    "br", "img", "hr", "meta", "link", "input", "col", "area",
    "base", "source", "track", "wbr",
}
_CAPTION_TAGS = {"figcaption", "caption"}
_MAX_TEXT_LEN = 20000
_MAX_CAPTION_LEN = 600


def normalize_chandra_output(raw_output: str, *, source_page: int = 1) -> dict[str, Any]:
    """Normalize one raw Chandra layout output string into a safe, JSON-ready dict.

    Pure and total: never calls a model, never opens a file, never raises. On any
    unexpected/malformed input it degrades to a valid ``completed`` output with an
    empty ``source_text``/``assets`` and an ``output_malformed`` warning.
    """
    page = _safe_page_number(source_page)
    try:
        blocks = extract_chandra_blocks(raw_output)
        source_text = chandra_blocks_to_source_text(blocks)
        assets = chandra_blocks_to_manifest_assets(blocks, source_page=page)
        warnings = _collect_warnings(raw_output, blocks)
        return {
            "version": OUTPUT_VERSION,
            "kind": OUTPUT_KIND,
            "status": "completed",
            "source_provider": SOURCE_PROVIDER_CHANDRA_LOCAL,
            "source_text": source_text,
            "assets": assets,
            "warnings": warnings,
        }
    except Exception:
        return {
            "version": OUTPUT_VERSION,
            "kind": OUTPUT_KIND,
            "status": "completed",
            "source_provider": SOURCE_PROVIDER_CHANDRA_LOCAL,
            "source_text": "",
            "assets": [],
            "warnings": ["output_malformed"],
        }


# --- Block extraction --------------------------------------------------------


def extract_chandra_blocks(raw_output: str) -> list[dict[str, Any]]:
    """Parse the raw string into a list of safe, closed-vocabulary block dicts.

    Each block: ``{block_type, chandra_label, bbox, text, caption, warnings}``.
    Tolerant by construction — handles missing labels, missing/invalid bbox,
    malformed HTML, and plain Markdown/text fallback; never raises.
    """
    if not isinstance(raw_output, str) or not raw_output.strip():
        return []
    try:
        parser = _ChandraLayoutParser()
        parser.feed(raw_output)
        parser.close()
        parser.finalize()
        blocks = parser.blocks
    except Exception:
        blocks = []
    if not blocks:
        # Plain Markdown / text fallback: keep the scrubbed text as one block.
        text = _sanitize_text(raw_output)
        if text:
            return [_make_block(ASSET_TYPE_TEXT_BLOCK, "Text", None, text, None, ["output_malformed"])]
        return []
    return blocks


def chandra_blocks_to_source_text(blocks: Any) -> str:
    """Assemble a deterministic, safe source-text fragment from blocks.

    Headers are preserved as Markdown headings, tables as simple Markdown grids,
    equations as their (LaTeX/text) content; captions of visual regions are kept
    as plain lines. No raw HTML, image bytes, paths, URLs, or secrets survive.
    """
    if not isinstance(blocks, list):
        return ""
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        rendered = _block_to_text(block)
        if rendered:
            parts.append(rendered)
    joined = "\n\n".join(parts)
    # Deterministic whitespace normalization.
    joined = re.sub(r"\n{3,}", "\n\n", joined).strip()
    return joined


def chandra_blocks_to_manifest_assets(blocks: Any, *, source_page: int = 1) -> list[dict[str, Any]]:
    """Map visual/table/equation/diagram blocks to manifest-shaped asset candidates.

    Text-only and caption blocks are intentionally not surfaced as assets. Asset
    ids are deterministic (``page_<NNNN>_chandra_<II>``). ``asset_ref`` stays
    ``None`` (no files written) and ``recommended_action`` stays ``"unknown"``.
    """
    page = _safe_page_number(source_page)
    if not isinstance(blocks, list):
        return []
    assets: list[dict[str, Any]] = []
    index = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get("block_type")
        if block_type not in VISUAL_ASSET_TYPES:
            continue
        index += 1
        warnings = block.get("warnings")
        warnings = [w for w in warnings if w in WARNINGS] if isinstance(warnings, list) else []
        assets.append(
            {
                "asset_id": f"page_{page:04d}_chandra_{index:02d}",
                "source_page": page,
                "asset_type": block_type,
                "bbox": _safe_bbox(block.get("bbox")),
                "caption": _safe_caption(block.get("caption")),
                "source_provider": SOURCE_PROVIDER_CHANDRA_LOCAL,
                "recommended_action": RECOMMENDED_ACTION_UNKNOWN,
                "dedupe_group": None,
                "scores": {},
                "asset_ref": None,
                "signals": {"chandra_label": _safe_display_label(block.get("chandra_label"))},
                "warnings": warnings,
            }
        )
    return assets


# --- HTML-ish layout parser (stdlib, tolerant) -------------------------------


class _ChandraLayoutParser(HTMLParser):
    """Single-pass, depth-tracked parser that turns layout HTML into blocks.

    One *region* at a time: an element carrying ``data-label``/``data-bbox`` (or a
    semantic tag like ``table``/``figure``/``img``/``math``/``h1..h6``) opens a
    region; text up to its matching close is collected; a nested caption
    (``data-label="caption"`` or ``<figcaption>``) is routed to the region's
    caption. Text outside any region accumulates as loose ``text_block``s, which
    also gives a clean Markdown/plain-text fallback for non-HTML input.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self._region: dict[str, Any] | None = None
        self._depth = 0
        self._loose: list[str] = []
        self._skip_depth = 0  # inside <script>/<style>
        self._in_caption = False
        self._caption_depth = 0
        # table state
        self._rows: list[list[str]] = []
        self._cur_row: list[str] | None = None
        self._cur_cell: list[str] | None = None

    # -- start/void/end ----------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _VOID_TAGS:
            self._handle_void(tag, attrs)
            return
        attrs_d = {k.lower(): (v or "") for k, v in attrs}
        if self._region is None:
            opener = self._region_opener(tag, attrs_d)
            if opener is not None:
                self._open_region(*opener, attrs_d)
            return
        # Inside a region: track nesting and special children.
        self._depth += 1
        if self._region.get("is_table"):
            if tag == "tr":
                self._cur_row = []
            elif tag in ("td", "th"):
                self._cur_cell = []
        label = attrs_d.get("data-label", "").strip().lower()
        if tag in _CAPTION_TAGS or label in ("caption", "figure-caption"):
            self._in_caption = True
            self._caption_depth = self._depth

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._skip_depth or tag in ("script", "style"):
            return
        self._handle_void(tag, attrs)

    def _handle_void(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k.lower(): (v or "") for k, v in attrs}
        if tag == "br" and self._region is not None and not self._region.get("is_table"):
            self._region["text"].append("\n")
            return
        if tag == "img" and self._region is None:
            # Standalone image region (void, self-contained).
            opener = self._region_opener(tag, attrs_d)
            if opener is not None:
                self._open_region(*opener, attrs_d)
                self._close_region()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("script", "style"):
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth or self._region is None or tag in _VOID_TAGS:
            return
        if self._region.get("is_table"):
            if tag in ("td", "th") and self._cur_cell is not None:
                cell = _sanitize_text(" ".join(self._cur_cell)).replace("\n", " ").strip()
                if self._cur_row is not None:
                    self._cur_row.append(cell)
                self._cur_cell = None
            elif tag == "tr" and self._cur_row is not None:
                self._rows.append(self._cur_row)
                self._cur_row = None
        if self._in_caption and self._depth <= self._caption_depth:
            self._in_caption = False
        self._depth -= 1
        if self._depth <= 0:
            self._close_region()

    # -- text --------------------------------------------------------------

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data:
            return
        if self._region is None:
            self._loose.append(data)
            return
        if self._region.get("is_table"):
            if self._cur_cell is not None:
                self._cur_cell.append(data)
            return
        if self._in_caption:
            self._region["caption"].append(data)
        else:
            self._region["text"].append(data)

    # -- region lifecycle --------------------------------------------------

    def _region_opener(self, tag: str, attrs_d: dict[str, str]) -> tuple[str, str, str | None] | None:
        has_label = "data-label" in attrs_d
        has_bbox = "data-bbox" in attrs_d
        bbox_raw = attrs_d.get("data-bbox") if has_bbox else None
        if has_label:
            label = attrs_d["data-label"].strip().lower()
            if label in ("caption", "figure-caption"):
                # A standalone caption region is just text; treat as text block.
                return (ASSET_TYPE_TEXT_BLOCK, "Text", bbox_raw)
            mapped = _LABEL_MAP.get(label)
            if mapped is None:
                return ("__unrecognized__" + str(label), "Unknown", bbox_raw)
            return (mapped[0], mapped[1], bbox_raw)
        if tag in _TAG_DEFAULT:
            block_type, display = _TAG_DEFAULT[tag]
            return (block_type, display, bbox_raw)
        if has_bbox:
            # Region with a box but no label and no semantic tag → plain text.
            return (ASSET_TYPE_TEXT_BLOCK, "Text", bbox_raw)
        return None

    def _open_region(self, block_type: str, display: str, bbox_raw: str | None, attrs_d: dict[str, str]) -> None:
        self._flush_loose()
        warnings: list[str] = []
        label_unrecognized = block_type.startswith("__unrecognized__")
        if label_unrecognized:
            block_type = ASSET_TYPE_UNKNOWN_REGION
            warnings.append("label_unrecognized")
        bbox, bbox_warning = _parse_bbox_attr(bbox_raw, expect=block_type in VISUAL_ASSET_TYPES)
        if bbox_warning:
            warnings.append(bbox_warning)
        self._region = {
            "block_type": block_type,
            "chandra_label": display,
            "bbox": bbox,
            "text": [],
            "caption": [],
            "warnings": warnings,
            "is_table": block_type == ASSET_TYPE_TABLE,
        }
        self._depth = 1
        self._in_caption = False
        self._caption_depth = 0
        self._rows = []
        self._cur_row = None
        self._cur_cell = None

    def _close_region(self) -> None:
        region = self._region
        self._region = None
        self._depth = 0
        if region is None:
            return
        if region.get("is_table"):
            text = _rows_to_markdown(self._rows)
            if not text:
                text = _sanitize_text("".join(region["text"]))
        else:
            text = _sanitize_text("".join(region["text"]))
        caption = _sanitize_text("".join(region["caption"]))
        caption = caption[:_MAX_CAPTION_LEN].strip() or None
        self.blocks.append(
            _make_block(
                region["block_type"],
                region["chandra_label"],
                region["bbox"],
                text,
                caption,
                region["warnings"],
            )
        )
        self._rows = []
        self._cur_row = None
        self._cur_cell = None

    def _flush_loose(self) -> None:
        if not self._loose:
            return
        text = _sanitize_text("".join(self._loose))
        self._loose = []
        if text:
            self.blocks.append(_make_block(ASSET_TYPE_TEXT_BLOCK, "Text", None, text, None, []))

    def finalize(self) -> None:
        if self._region is not None:
            self._close_region()
        self._flush_loose()


# --- Block / text helpers ----------------------------------------------------


def _make_block(
    block_type: str,
    display: str,
    bbox: Any,
    text: str,
    caption: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    safe_warnings: list[str] = []
    for w in warnings:
        if w in WARNINGS and w not in safe_warnings:
            safe_warnings.append(w)
    return {
        "block_type": block_type if block_type in (VISUAL_ASSET_TYPES | {ASSET_TYPE_TEXT_BLOCK, ASSET_TYPE_CAPTION}) else ASSET_TYPE_UNKNOWN_REGION,
        "chandra_label": _safe_display_label(display),
        "bbox": _safe_bbox(bbox),
        "text": (text or "")[:_MAX_TEXT_LEN],
        "caption": _safe_caption(caption),
        "warnings": safe_warnings,
    }


def _block_to_text(block: dict[str, Any]) -> str:
    block_type = block.get("block_type")
    text = block.get("text") or ""
    text = text.strip()
    caption = block.get("caption")
    label = block.get("chandra_label")
    if block_type == ASSET_TYPE_TEXT_BLOCK:
        if not text:
            return ""
        if label == "Section-Header":
            return f"## {text}"
        if label == "Title":
            return f"# {text}"
        return text
    if block_type == ASSET_TYPE_TABLE:
        return text
    if block_type == ASSET_TYPE_EQUATION_BLOCK:
        return text
    if block_type == ASSET_TYPE_CAPTION:
        return text
    # Visual regions (diagram/figure/image/unknown): keep only a safe caption line.
    if caption:
        return caption
    return ""


# --- Sanitization & coercion (never echo raw, untrusted input) ---------------

_URL_RE = re.compile(r"\b(?:https?|ftp|file|ws|wss)://\S+", re.IGNORECASE)
_DATA_URI_RE = re.compile(r"data:[^\s;]+;base64,[A-Za-z0-9+/=]+", re.IGNORECASE)
_BASE64_BLOB_RE = re.compile(r"\b[A-Za-z0-9+/]{120,}={0,2}\b")
_ABS_UNIX_PATH_RE = re.compile(r"(?<!\w)/(?:home|usr|etc|var|root|tmp|opt|bin|sbin|lib|proc|sys|dev|mnt|media|srv|boot)(?:/[^\s\"'<>]*)?")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'<>]*")
_UNC_PATH_RE = re.compile(r"\\\\[^\s\"'<>]+")
_SOCKET_RE = re.compile(r"\S*\.sock\b")
_AUTH_RE = re.compile(r"Authorization\s*:?\s*\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"\bBearer\s+\S+", re.IGNORECASE)
_APIKEY_RE = re.compile(r"\b(?:sk|pk|rk)[-_][A-Za-z0-9_\-]{12,}")
_ARGV_FLAG_RE = re.compile(r"(?<!\S)--[A-Za-z][\w-]*")
_TAG_RE = re.compile(r"<[^>]*>")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_text(value: Any) -> str:
    """Scrub a captured/raw string into a deterministic, leak-free fragment."""
    if not isinstance(value, str) or not value:
        return ""
    s = value
    # Drop any residual tags first (fallback path / smuggled inline HTML).
    s = _TAG_RE.sub(" ", s)
    s = _DATA_URI_RE.sub(" ", s)
    s = _URL_RE.sub(" ", s)
    s = _AUTH_RE.sub(" ", s)
    s = _BEARER_RE.sub(" ", s)
    s = _APIKEY_RE.sub(" ", s)
    s = _WIN_PATH_RE.sub(" ", s)
    s = _UNC_PATH_RE.sub(" ", s)
    s = _ABS_UNIX_PATH_RE.sub(" ", s)
    s = _SOCKET_RE.sub(" ", s)
    s = _BASE64_BLOB_RE.sub(" ", s)
    s = _ARGV_FLAG_RE.sub(" ", s)
    s = _CTRL_RE.sub(" ", s)
    # Deterministic whitespace: trim each line, drop blank runs.
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    out_lines: list[str] = []
    blank = False
    for ln in lines:
        if ln:
            out_lines.append(ln)
            blank = False
        elif not blank and out_lines:
            out_lines.append("")
            blank = True
    return "\n".join(out_lines).strip()


def _safe_caption(value: Any) -> str | None:
    if value is None:
        return None
    text = _sanitize_text(value)
    text = text.replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:_MAX_CAPTION_LEN] or None


def _safe_display_label(value: Any) -> str:
    allowed = {"Text", "Title", "Section-Header", "Table", "Equation",
               "Diagram", "Figure", "Image", "Caption", "Unknown"}
    return value if value in allowed else "Unknown"


def _rows_to_markdown(rows: list[list[str]]) -> str:
    rows = [r for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [[*(r[:width]), *([""] * (width - len(r)))] for r in rows]
    header = norm[0]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for r in norm[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _parse_bbox_attr(raw: Any, *, expect: bool) -> tuple[list[float] | None, str | None]:
    """Parse a ``data-bbox`` attribute → (bbox|None, warning|None).

    ``expect`` is True for visual regions where a bbox is meaningful; a missing
    box there yields ``bbox_missing``. An unparseable/ill-ordered box yields
    ``bbox_invalid``. The raw attribute string is never echoed.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return (None, "bbox_missing" if expect else None)
    if not isinstance(raw, str):
        return (None, "bbox_invalid")
    numbers = re.findall(r"-?\d+(?:\.\d+)?", raw)
    if len(numbers) != 4:
        return (None, "bbox_invalid")
    bbox = _safe_bbox(numbers)
    if bbox is None:
        return (None, "bbox_invalid")
    return (bbox, None)


def _safe_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    coords: list[float] = []
    for item in value:
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
            return None
        coords.append(round(max(0.0, number), 2))
    x0, y0, x1, y1 = coords
    if x1 <= x0 or y1 <= y0:  # must be a well-ordered, positive-area box
        return None
    return [x0, y0, x1, y1]


def _safe_page_number(value: Any) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return page if page > 0 else 1


def _collect_warnings(raw_output: Any, blocks: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if not isinstance(raw_output, str) or not raw_output.strip():
        return ["empty_output"]
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for w in block.get("warnings", []):
            if w in WARNINGS and w not in warnings:
                warnings.append(w)
    return warnings
