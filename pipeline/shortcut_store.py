"""File-based persistence for Home shortcuts (Slice 2A — backend store).

Shortcuts are real user data: small, named launchers that drop the user into a
preconfigured Builder setup, a tool, or a Library view. They are durable,
editable, deletable, importable, and exportable.

Storage mirrors the existing stores (``style_store`` / ``library_store``):
a single versioned JSON file written atomically (temp file + ``os.replace``),
stdlib-only, no database. The file lives at ``library/shortcuts.json`` so it
rides the existing ``./library`` volume mount and survives container restarts.

Security model — **whitelist parsing**. Both ``create`` and ``import`` build a
*fresh* shortcut object by reading ONLY the fields defined in this module. Every
unknown / extra field in the incoming JSON is discarded by construction (it is
never read), so an imported file can never smuggle in shell args, file paths,
command strings, or backend-action fields — they are not in the schema, so they
are never copied into a saved shortcut. See :func:`_normalize_shortcut` and
:func:`_normalize_payload`.

References inside a shortcut (provider / generator_preset / style) are validated
against the app's *actual* current config (the provider registry, the real
generator presets, the real style store) — never a hardcoded list. A shortcut
that points at something unavailable still SAVES, but its public view is flagged
``valid: false`` with a ``reason`` so the UI can warn instead of silently loading
a broken setup into the Builder.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline import generator_presets, provider_config, style_store
from pipeline.orchestrator import (
    DIFFICULTY_VALUES,
    INCLUDE_SECTION_FRAGMENTS,
    OUTPUT_DEPTH_VALUES,
    normalize_include_sections,
)

BASE_DIR = Path(__file__).resolve().parents[1]
SHORTCUTS_DIR = BASE_DIR / "library"
SHORTCUTS_JSON = SHORTCUTS_DIR / "shortcuts.json"

ID_PATTERN = re.compile(r"^sc_[a-z0-9]{6,}$")
COLOR_PATTERN = re.compile(r"^#?[0-9a-zA-Z]{2,16}$")

MAX_NAME_CHARS = 120
MAX_DESCRIPTION_CHARS = 400
MAX_ICON_CHARS = 40
MAX_STR_CHARS = 120
MAX_VIEW_CHARS = 200
MAX_SHORTCUTS = 200
MIN_TARGET_PAGES = 1
MAX_TARGET_PAGES = 100

# The three shortcut types and the payload shape each one carries.
TYPE_BUILDER = "builder_setup"
TYPE_TOOL = "tool"
TYPE_LIBRARY_VIEW = "library_view"
SHORTCUT_TYPES = (TYPE_BUILDER, TYPE_TOOL, TYPE_LIBRARY_VIEW)

# Known keys for the constrained payloads. Anything outside these sets is
# discarded (tool/view) or flagged invalid (so the UI can warn).
KNOWN_TOOL_KEYS = {
    "clean_markdown",
    "improve_guide",
    "add_style",
    "compare_styles",
    "export_center",
    "find_guide",
    "quiz",
    "outline",
}
# Base library views plus three prefixed forms: ``folder:<id>``, ``tag:<name>``,
# ``search:<query>``.
KNOWN_VIEW_BASES = {"recent", "pinned", "failed", "favorites", "all"}
VIEW_PREFIXES = ("folder:", "tag:", "search:")

# builder_setup payload whitelist.
KNOWN_INPUT_TYPES = {"upload_markdown", "paste_text", "generate_llm"}
KNOWN_MODULE_KEYS = {
    "mcqs",
    "glossary",
    "flashcards",
    "summary",
    "worked_examples",
    "formulas",
    "key_concepts",
    "practice_problems",
    "diagrams",
}
KNOWN_EXPORT_FORMATS = {"pdf", "docx", "markdown", "html"}
DEFAULT_INPUT_TYPE = "generate_llm"
DEFAULT_MODE = "study_guide"


class ShortcutStoreError(RuntimeError):
    """Raised for invalid input or forbidden operations on shortcuts."""


class ShortcutNotFoundError(ShortcutStoreError):
    pass


# ---------------------------------------------------------------------------
# Small value helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_valid_shortcut_id(shortcut_id: str) -> bool:
    return bool(ID_PATTERN.match(str(shortcut_id or "")))


def _new_id(existing: set[str]) -> str:
    while True:
        candidate = f"sc_{secrets.token_hex(6)}"
        if candidate not in existing:
            return candidate


def _clean_name(name: Any) -> str:
    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        raise ShortcutStoreError("name must not be empty.")
    return cleaned[:MAX_NAME_CHARS]


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _clean_icon(value: Any) -> str:
    # Icons may be an emoji or a short token; strip control chars and cap length.
    text = "".join(ch for ch in str(value or "") if ch.isprintable()).strip()
    return text[:MAX_ICON_CHARS]


def _clean_color(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text if COLOR_PATTERN.match(text) else None


def _clean_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_str_field(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:MAX_STR_CHARS] if text else None


def _clean_include_sections(value: Any) -> dict[str, bool]:
    """Normalize an ``include_sections`` map to a canonical dict-of-bool.

    Reuses the C1 normalization (``normalize_include_sections`` +
    ``INCLUDE_SECTION_ALIASES`` in ``pipeline.orchestrator``) — no second alias
    table lives here. Only canonical, enabled keys survive: unknown keys are
    dropped (the repo's whitelist convention for untrusted toggle input), and
    false/unset keys are not persisted (mirroring how ``normalize_include_sections``
    returns only enabled keys). Keys come back in ``INCLUDE_SECTION_FRAGMENTS``
    order so the stored shape is deterministic regardless of incoming dict order.
    """
    if not isinstance(value, dict):
        return {}
    return {key: True for key in normalize_include_sections(value)}


def _clean_axis(value: Any, allowed: tuple[str, ...], field: str) -> str | None:
    """Validate an optional scalar-enum axis (``output_depth`` / ``difficulty``).

    Unset (``None``/empty) → ``None`` (omitted, matching the store's convention for
    optional scalar fields like ``provider``). An invalid value is **rejected** by
    raising ``ShortcutStoreError`` rather than silently coerced/persisted — on
    create/update this surfaces as HTTP 400, and on import the offending shortcut is
    skipped into the batch ``errors`` list (the existing rejection convention used by
    ``name``/``type``)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in allowed:
        raise ShortcutStoreError(
            f"{field} must be one of {sorted(allowed)}; got {text!r}."
        )
    return text


# ---------------------------------------------------------------------------
# WHITELIST parsing — the security boundary
# ---------------------------------------------------------------------------

def _normalize_payload(shortcut_type: str, raw: Any) -> dict[str, Any]:
    """Build a fresh payload reading ONLY the known keys for ``shortcut_type``.

    This is the whitelist: a brand-new dict is constructed and only explicitly
    named fields are copied across. Any extra/unknown/dangerous keys present in
    ``raw`` (e.g. ``cmd``, ``path``, ``args``) are never read, so they cannot
    ride along into a saved shortcut.
    """
    raw = raw if isinstance(raw, dict) else {}

    if shortcut_type == TYPE_TOOL:
        return {"tool": _clean_str_field(raw.get("tool")) or ""}

    if shortcut_type == TYPE_LIBRARY_VIEW:
        view = (str(raw.get("view") or "").strip())[:MAX_VIEW_CHARS]
        return {"view": view}

    # builder_setup — parse each known field, discard everything else.
    modules_raw = raw.get("modules")
    modules: dict[str, bool] = {}
    if isinstance(modules_raw, dict):
        for key in KNOWN_MODULE_KEYS:
            if key in modules_raw:
                modules[key] = _clean_bool(modules_raw.get(key))

    formats_raw = raw.get("export_formats")
    export_formats: list[str] = []
    if isinstance(formats_raw, list):
        for fmt in formats_raw:
            value = str(fmt or "").strip().lower()
            if value in KNOWN_EXPORT_FORMATS and value not in export_formats:
                export_formats.append(value)

    input_type = str(raw.get("input_type") or "").strip()
    if input_type not in KNOWN_INPUT_TYPES:
        input_type = DEFAULT_INPUT_TYPE

    target_pages = raw.get("target_pages")
    if target_pages is not None:
        target_pages = max(MIN_TARGET_PAGES, min(MAX_TARGET_PAGES, _clean_int(target_pages, MIN_TARGET_PAGES)))

    mode = (str(raw.get("mode") or "").strip() or DEFAULT_MODE)[:MAX_STR_CHARS]

    return {
        "input_type": input_type,
        "provider": _clean_str_field(raw.get("provider")),
        "model": _clean_str_field(raw.get("model")),
        "generator_preset": _clean_str_field(raw.get("generator_preset")),
        "style": _clean_str_field(raw.get("style")),
        "mode": mode,
        "target_pages": target_pages,
        # Legacy UI-only toggles, kept for backward compat with old shortcuts and the
        # current Builder. They are bridged to canonical ``include_sections`` on read
        # (see ``_bridge_payload``); the real generation-affecting field below.
        "modules": modules,
        # Canonical generation-affecting options (C1/C2). ``include_sections`` is the
        # real prompt-assembly toggle map; the two axes shape the whole guide.
        "include_sections": _clean_include_sections(raw.get("include_sections")),
        "output_depth": _clean_axis(raw.get("output_depth"), OUTPUT_DEPTH_VALUES, "output_depth"),
        "difficulty": _clean_axis(raw.get("difficulty"), DIFFICULTY_VALUES, "difficulty"),
        "strict_math": _clean_bool(raw.get("strict_math"), default=True),
        "export_formats": export_formats,
    }


def _normalize_shortcut(
    raw: Any,
    *,
    existing_ids: set[str],
    keep_id: bool = False,
) -> dict[str, Any]:
    """Build a fresh, validated shortcut record from arbitrary input.

    Only the named schema fields are read; everything else is discarded. ``id``
    is regenerated unless ``keep_id`` is set and the incoming id is well-formed.
    The caller (import) decides ``keep_id`` based on conflict + overwrite policy;
    ``create`` always regenerates (``keep_id=False``). ``existing_ids`` seeds the
    uniqueness search when a fresh id is needed.
    """
    raw = raw if isinstance(raw, dict) else {}

    name = _clean_name(raw.get("name"))
    shortcut_type = str(raw.get("type") or "").strip()
    if shortcut_type not in SHORTCUT_TYPES:
        raise ShortcutStoreError(
            f"type must be one of {sorted(SHORTCUT_TYPES)}; got {shortcut_type!r}."
        )

    incoming_id = str(raw.get("id") or "")
    if keep_id and is_valid_shortcut_id(incoming_id):
        shortcut_id = incoming_id
    else:
        shortcut_id = _new_id(existing_ids)

    timestamp = _now_iso()
    return {
        "id": shortcut_id,
        "name": name,
        "description": _clean_text(raw.get("description"), MAX_DESCRIPTION_CHARS),
        "type": shortcut_type,
        "icon": _clean_icon(raw.get("icon")),
        "color": _clean_color(raw.get("color")),
        "pinned": _clean_bool(raw.get("pinned")),
        "order": _clean_int(raw.get("order"), 0),
        "created_at": timestamp,
        "updated_at": timestamp,
        "payload": _normalize_payload(shortcut_type, raw.get("payload")),
    }


# ---------------------------------------------------------------------------
# Reference validation (against the app's ACTUAL config) -> valid flag
# ---------------------------------------------------------------------------

def _provider_is_configured(provider: str | None) -> bool:
    if not provider:
        return False
    try:
        entry = provider_config.get_provider_entry(provider, discover_local=False)
    except Exception:
        return False
    return bool(entry and entry.configured)


def _evaluate_validity(record: dict[str, Any]) -> tuple[bool, str | None]:
    """Return ``(valid, reason)`` by checking references against live config.

    Computed at read time (not stored), because configured providers / presets /
    styles can change between save and load.
    """
    shortcut_type = record.get("type")
    payload = record.get("payload") or {}

    if shortcut_type == TYPE_TOOL:
        if payload.get("tool") not in KNOWN_TOOL_KEYS:
            return False, "references unavailable tool"
        return True, None

    if shortcut_type == TYPE_LIBRARY_VIEW:
        view = str(payload.get("view") or "")
        if view in KNOWN_VIEW_BASES or any(view.startswith(p) for p in VIEW_PREFIXES):
            return True, None
        return False, "references unavailable view"

    if shortcut_type == TYPE_BUILDER:
        provider = payload.get("provider")
        if not _provider_is_configured(provider):
            return False, "references unavailable provider"
        preset = payload.get("generator_preset")
        if preset and not generator_presets.generator_preset_exists(preset):
            return False, "references unavailable generator preset"
        style = payload.get("style")
        if style and not style_store.style_exists(style):
            return False, "references unavailable style"
        return True, None

    return False, "unknown shortcut type"


# ---------------------------------------------------------------------------
# Translate-on-read bridge: legacy ``modules`` -> canonical ``include_sections``
# ---------------------------------------------------------------------------

def _merge_include_sections(payload: dict[str, Any]) -> dict[str, bool]:
    """Compute the effective ``include_sections`` for a builder payload.

    Legacy ``modules`` are translated through the C1 normalization
    (``normalize_include_sections`` + ``INCLUDE_SECTION_ALIASES``) and used to
    **fill** sections; an explicit ``include_sections`` is normalized the same way
    and layered on top so it **wins**. Both sides are reduced to canonical,
    enabled-only keys, so legacy modules can only add missing sections — never
    override an explicit choice. Result keys are in ``INCLUDE_SECTION_FRAGMENTS``
    order for determinism."""
    enabled: set[str] = set()
    enabled.update(normalize_include_sections(payload.get("modules")))
    enabled.update(normalize_include_sections(payload.get("include_sections")))
    return {key: True for key in INCLUDE_SECTION_FRAGMENTS if key in enabled}


def _bridge_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Return a fresh copy of a builder payload with ``include_sections`` derived.

    This is read-only: it never mutates the stored record and never writes
    ``shortcuts.json``. A legacy shortcut (only ``modules``) gains a derived
    ``include_sections`` in its returned/exported representation while the on-disk
    JSON stays untouched until the user explicitly creates/updates/imports it.
    ``include_sections`` is only added when there is something to show or the stored
    payload already carried the key, so an old shortcut with no sections is not
    forced to grow one."""
    if record.get("type") != TYPE_BUILDER:
        return record.get("payload")
    payload = dict(record.get("payload") or {})
    merged = _merge_include_sections(payload)
    if merged or isinstance(payload.get("include_sections"), dict):
        payload["include_sections"] = merged
    return payload


def _public(record: dict[str, Any]) -> dict[str, Any]:
    valid, reason = _evaluate_validity(record)
    view = dict(record)
    if record.get("type") == TYPE_BUILDER:
        view["payload"] = _bridge_payload(record)
    view["valid"] = valid
    view["reason"] = reason
    return view


# ---------------------------------------------------------------------------
# Registry I/O (atomic write, mirrors style_store / library_store)
# ---------------------------------------------------------------------------

def _read_registry() -> dict[str, Any]:
    if not SHORTCUTS_JSON.exists():
        return _seed_defaults()
    try:
        data = json.loads(SHORTCUTS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "shortcuts": []}
    if not isinstance(data, dict) or not isinstance(data.get("shortcuts"), list):
        return {"version": 1, "shortcuts": []}
    return data


def _write_registry(registry: dict[str, Any]) -> None:
    SHORTCUTS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=SHORTCUTS_DIR, prefix=".shortcuts-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(registry, handle, ensure_ascii=False, indent=2)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, SHORTCUTS_JSON)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _valid_records(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return stored records that have a well-formed id + known type, de-duped."""
    registry = registry if registry is not None else _read_registry()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in registry.get("shortcuts", []):
        if not isinstance(entry, dict):
            continue
        sid = str(entry.get("id") or "")
        if not is_valid_shortcut_id(sid) or sid in seen:
            continue
        if entry.get("type") not in SHORTCUT_TYPES:
            continue
        seen.add(sid)
        records.append(entry)
    return records


def _sorted(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Pinned first, then by explicit order, then creation time for stability.
    return sorted(
        records,
        key=lambda r: (
            0 if r.get("pinned") else 1,
            _clean_int(r.get("order"), 0),
            str(r.get("created_at") or ""),
        ),
    )


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def _default_model_for(provider: str) -> str | None:
    """The provider's real default model from the live registry (env-derived)."""
    try:
        entry = provider_config.get_provider_entry(provider, discover_local=False)
    except Exception:
        return None
    return entry.default_model if entry else None


def _default_seed() -> list[dict[str, Any]]:
    """The default shortcut set, derived from the app's REAL current config.

    Provider/model/preset/style values are looked up live (not copied from any
    spec): real generator-preset ids (``claude_cram`` / ``claude_review``), real
    style ids, and each provider's real default model string.
    """
    return [
        {
            "name": "Exam Cram — Qwen",
            "description": "Dense, high-yield exam guide via Qwen with MCQs and a glossary.",
            "type": TYPE_BUILDER,
            "icon": "📝",
            "color": "#F59E0B",
            "pinned": True,
            "order": 0,
            "payload": {
                "input_type": "generate_llm",
                "provider": "qwen",
                "model": _default_model_for("qwen"),
                "generator_preset": "claude_cram",
                "style": "exam_cram",
                "mode": DEFAULT_MODE,
                "target_pages": 8,
                "modules": {"mcqs": True, "glossary": True},
                "strict_math": True,
                "export_formats": ["pdf"],
            },
        },
        {
            "name": "Full Guide — DeepSeek",
            "description": "Thorough study guide via DeepSeek with the Claude-Review prompt.",
            "type": TYPE_BUILDER,
            "icon": "📘",
            "color": "#60A5FA",
            "pinned": True,
            "order": 1,
            "payload": {
                "input_type": "generate_llm",
                "provider": "deepseek",
                "model": _default_model_for("deepseek"),
                "generator_preset": "claude_review",
                "style": "basic_study_guide",
                "mode": DEFAULT_MODE,
                "target_pages": 20,
                "modules": {},
                "strict_math": True,
                "export_formats": ["pdf"],
            },
        },
        {
            "name": "Clean Markdown",
            "description": "Sanitize and re-render an existing guide's markdown.",
            "type": TYPE_TOOL,
            "icon": "🧹",
            "color": "#34D399",
            "pinned": False,
            "order": 2,
            "payload": {"tool": "clean_markdown"},
        },
        {
            "name": "Improve Guide",
            "description": "Refine and expand an existing guide.",
            "type": TYPE_TOOL,
            "icon": "✨",
            "color": "#A855F7",
            "pinned": False,
            "order": 3,
            "payload": {"tool": "improve_guide"},
        },
        {
            "name": "Find Guide",
            "description": "Search the library for a guide.",
            "type": TYPE_LIBRARY_VIEW,
            "icon": "🔎",
            "color": "#38BDF8",
            "pinned": False,
            "order": 4,
            "payload": {"view": "search:"},
        },
        {
            "name": "Continue Last Guide",
            "description": "Jump back to the most recent guide.",
            "type": TYPE_LIBRARY_VIEW,
            "icon": "⏯️",
            "color": "#F472B6",
            "pinned": False,
            "order": 5,
            "payload": {"view": "recent"},
        },
    ]


def _build_default_records() -> list[dict[str, Any]]:
    existing: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, seed in enumerate(_default_seed()):
        record = _normalize_shortcut(seed, existing_ids=existing)
        record["order"] = index  # preserve seed display order
        existing.add(record["id"])
        records.append(record)
    return records


def _seed_defaults() -> dict[str, Any]:
    registry = {"version": 1, "shortcuts": _build_default_records()}
    _write_registry(registry)
    return registry


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------

def list_shortcuts() -> list[dict[str, Any]]:
    return [_public(record) for record in _sorted(_valid_records())]


def get_shortcut(shortcut_id: str) -> dict[str, Any]:
    if not is_valid_shortcut_id(shortcut_id):
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")
    for record in _valid_records():
        if record["id"] == shortcut_id:
            return _public(record)
    raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")


def create_shortcut(data: dict[str, Any]) -> dict[str, Any]:
    registry = _read_registry()
    records = _valid_records(registry)
    if len(records) >= MAX_SHORTCUTS:
        raise ShortcutStoreError("Shortcut limit reached.")
    existing_ids = {r["id"] for r in records}
    record = _normalize_shortcut(data, existing_ids=existing_ids)
    # New shortcuts go to the end of the (unpinned) order by default.
    record["order"] = max((_clean_int(r.get("order"), 0) for r in records), default=-1) + 1
    registry["version"] = registry.get("version", 1)
    registry["shortcuts"] = [*records, record]
    _write_registry(registry)
    return _public(record)


def update_shortcut(shortcut_id: str, data: dict[str, Any]) -> dict[str, Any]:
    if not is_valid_shortcut_id(shortcut_id):
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")
    registry = _read_registry()
    records = _valid_records(registry)
    record = next((r for r in records if r["id"] == shortcut_id), None)
    if record is None:
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")

    if "name" in data and data["name"] is not None:
        record["name"] = _clean_name(data["name"])
    if "description" in data and data["description"] is not None:
        record["description"] = _clean_text(data["description"], MAX_DESCRIPTION_CHARS)
    if "icon" in data and data["icon"] is not None:
        record["icon"] = _clean_icon(data["icon"])
    if "color" in data:
        record["color"] = _clean_color(data["color"])
    if "pinned" in data and data["pinned"] is not None:
        record["pinned"] = _clean_bool(data["pinned"])
    if "order" in data and data["order"] is not None:
        record["order"] = _clean_int(data["order"], record.get("order", 0))

    # A type change re-parses the payload under the new type's whitelist.
    new_type = data.get("type")
    if new_type is not None:
        if new_type not in SHORTCUT_TYPES:
            raise ShortcutStoreError(f"type must be one of {sorted(SHORTCUT_TYPES)}.")
        record["type"] = new_type
        record["payload"] = _normalize_payload(new_type, data.get("payload", record.get("payload")))
    elif "payload" in data:
        record["payload"] = _normalize_payload(record["type"], data.get("payload"))

    record["updated_at"] = _now_iso()
    registry["shortcuts"] = records
    _write_registry(registry)
    return _public(record)


def delete_shortcut(shortcut_id: str) -> None:
    if not is_valid_shortcut_id(shortcut_id):
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")
    registry = _read_registry()
    records = _valid_records(registry)
    if not any(r["id"] == shortcut_id for r in records):
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")
    registry["shortcuts"] = [r for r in records if r["id"] != shortcut_id]
    _write_registry(registry)


def reorder_shortcuts(items: Any) -> list[dict[str, Any]]:
    """Persist new ``order`` + ``pinned`` state from a list of ``{id, order, pinned}``."""
    if not isinstance(items, list):
        raise ShortcutStoreError("reorder expects a list of items.")
    updates: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or "")
        if is_valid_shortcut_id(sid):
            updates[sid] = item

    registry = _read_registry()
    records = _valid_records(registry)
    timestamp = _now_iso()
    for record in records:
        update = updates.get(record["id"])
        if not update:
            continue
        if "order" in update and update["order"] is not None:
            record["order"] = _clean_int(update["order"], record.get("order", 0))
        if "pinned" in update and update["pinned"] is not None:
            record["pinned"] = _clean_bool(update["pinned"])
        record["updated_at"] = timestamp

    registry["shortcuts"] = records
    _write_registry(registry)
    return [_public(record) for record in _sorted(records)]


def reset_defaults() -> list[dict[str, Any]]:
    """Replace the registry with a fresh default set."""
    registry = _seed_defaults()
    return [_public(record) for record in _sorted(_valid_records(registry))]


# ---------------------------------------------------------------------------
# Import / export
# ---------------------------------------------------------------------------

def _extract_incoming(data: Any) -> list[Any]:
    """Pull a list of candidate shortcut dicts out of flexible import shapes.

    Accepts a single shortcut object, a bare list, or a registry-style
    ``{"shortcuts": [...]}`` envelope.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("shortcuts"), list):
            return data["shortcuts"]
        return [data]
    return []


def _normalize_import_batch(
    data: Any,
    *,
    existing_ids: set[str],
    overwrite: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize an incoming batch. Returns ``(records, errors)``.

    Ids that collide with ``existing_ids`` get a fresh id unless ``overwrite`` is
    set; ``existing_ids`` is updated as we go so a batch can't self-collide.
    """
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, raw in enumerate(_extract_incoming(data)):
        incoming_id = str(raw.get("id") or "") if isinstance(raw, dict) else ""
        conflict = incoming_id in existing_ids
        keep_id = is_valid_shortcut_id(incoming_id) and (overwrite or not conflict)
        try:
            record = _normalize_shortcut(raw, existing_ids=existing_ids, keep_id=keep_id)
        except ShortcutStoreError as exc:
            errors.append({"index": index, "error": str(exc)})
            continue
        record["_conflict"] = bool(conflict)
        record["_overwritten"] = bool(conflict and overwrite)
        record["_id_regenerated"] = bool(conflict and not overwrite)
        existing_ids.add(record["id"])
        records.append(record)
    return records, errors


def preview_import(data: Any, *, overwrite: bool = False) -> dict[str, Any]:
    """Validate an import payload and return the normalized result WITHOUT saving."""
    existing_ids = {r["id"] for r in _valid_records()}
    records, errors = _normalize_import_batch(data, existing_ids=set(existing_ids), overwrite=overwrite)
    shortcuts = []
    for record in records:
        meta = {k: record.pop(k) for k in ("_conflict", "_overwritten", "_id_regenerated")}
        view = _public(record)
        view.update(meta)
        shortcuts.append(view)
    return {
        "shortcuts": shortcuts,
        "count": len(shortcuts),
        "errors": errors,
        "saved": False,
    }


def import_shortcuts(data: Any, *, overwrite: bool = False) -> dict[str, Any]:
    """Validate and SAVE an import. Conflicting ids get a new id unless overwrite."""
    registry = _read_registry()
    existing = _valid_records(registry)
    existing_by_id = {r["id"]: r for r in existing}
    records, errors = _normalize_import_batch(
        data, existing_ids=set(existing_by_id), overwrite=overwrite
    )

    next_order = max((_clean_int(r.get("order"), 0) for r in existing), default=-1) + 1
    saved_views: list[dict[str, Any]] = []
    for record in records:
        meta = {k: record.pop(k) for k in ("_conflict", "_overwritten", "_id_regenerated")}
        if meta["_overwritten"]:
            existing_by_id[record["id"]] = record  # replace in place
        else:
            record["order"] = next_order
            next_order += 1
            existing_by_id[record["id"]] = record
        view = _public(record)
        view.update(meta)
        saved_views.append(view)

    if len(existing_by_id) > MAX_SHORTCUTS:
        raise ShortcutStoreError("Shortcut limit reached.")

    registry["version"] = registry.get("version", 1)
    registry["shortcuts"] = list(existing_by_id.values())
    _write_registry(registry)
    return {
        "shortcuts": saved_views,
        "imported": len(saved_views),
        "errors": errors,
        "saved": True,
    }


def _exportable(record: dict[str, Any]) -> dict[str, Any]:
    """The clean stored shape (no computed valid/reason) for round-trip export."""
    keys = (
        "id", "name", "description", "type", "icon", "color",
        "pinned", "order", "created_at", "updated_at", "payload",
    )
    out = {k: record.get(k) for k in keys}
    # Export mirrors the normal sanitized read path: a legacy shortcut's derived
    # ``include_sections`` rides along (translate-on-read) so an exported file is a
    # forward-compatible bridge. Still read-only — the stored record is untouched.
    if record.get("type") == TYPE_BUILDER:
        out["payload"] = _bridge_payload(record)
    return out


def export_shortcut(shortcut_id: str) -> dict[str, Any]:
    if not is_valid_shortcut_id(shortcut_id):
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")
    for record in _valid_records():
        if record["id"] == shortcut_id:
            return _exportable(record)
    raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")


def export_all() -> dict[str, Any]:
    records = _sorted(_valid_records())
    return {"version": 1, "shortcuts": [_exportable(r) for r in records]}
