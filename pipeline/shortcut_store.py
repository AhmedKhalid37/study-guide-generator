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
    INCLUDE_SECTION_ALIASES,
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
# Inspection (Slice 1) — richer, additive read-only validity
#
# This is ADDITIVE. ``_evaluate_validity`` above (and therefore the public
# ``valid``/``reason`` fields) is left EXACTLY as-is for backward compatibility
# with the existing activation guard. The inspector adds a parallel ``validity``
# object that (a) distinguishes ``valid``/``degraded``/``broken`` instead of a
# single boolean, (b) returns the FULL list of findings rather than first-failure-
# only, and (c) validates the saved ``model`` reference (which ``_evaluate_validity``
# never did). It is read-only: it reads live, redacted registries and never mutates
# ``shortcuts.json``, never exposes a raw key.
#
# Deliberate divergence (see DECISIONS.md): a degraded-only shortcut keeps
# ``valid:false`` (unchanged), but a NEW degraded case such as ``model_unavailable``
# / ``section_unknown`` leaves the legacy ``valid:true`` it has today while
# ``validity.status`` becomes ``degraded`` — so the new model check does not flip
# the activation guard's decision for shortcuts it currently allows.
# ---------------------------------------------------------------------------

# Stable, frontend-friendly finding codes.
FINDING_PROVIDER_MISSING = "provider_missing"
FINDING_PROVIDER_UNCONFIGURED = "provider_unconfigured"
FINDING_MODEL_UNAVAILABLE = "model_unavailable"
FINDING_STYLE_MISSING = "style_missing"
FINDING_GENERATOR_PRESET_MISSING = "generator_preset_missing"
FINDING_SECTION_UNKNOWN = "section_unknown"
FINDING_OUTPUT_DEPTH_INVALID = "output_depth_invalid"
FINDING_DIFFICULTY_INVALID = "difficulty_invalid"
FINDING_TOOL_ROUTE_MISSING = "tool_route_missing"
FINDING_LEGACY_FIELD_IGNORED = "legacy_field_ignored"
FINDING_PAYLOAD_SHAPE_INVALID = "payload_shape_invalid"
FINDING_INSPECTION_ERROR = "inspection_error"

# Severity → status tier. error ⇒ broken, warning ⇒ degraded, info ⇒ valid.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

STATUS_VALID = "valid"
STATUS_DEGRADED = "degraded"
STATUS_BROKEN = "broken"


def _finding(
    code: str,
    severity: str,
    field: str,
    message: str,
    *,
    current_value: Any = None,
    repairable: bool = False,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a stable finding object. ``current_value``/``candidates`` carry only
    non-secret ids/labels (provider/model/style/preset/section/axis) — never a key,
    Authorization header, secret URL, or upstream error body."""
    finding: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
        "current_value": current_value,
        "repairable": bool(repairable),
    }
    if candidates is not None:
        finding["candidates"] = candidates
    return finding


# -- Safe, redacted candidate sources (live registries; never a secret) -------

def _provider_candidates() -> list[dict[str, Any]]:
    """Public provider dicts reduced to ``{id, label, configured}`` — redacted."""
    try:
        registry = provider_config.get_provider_registry(discover_local=False)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for item in registry:
        pid = item.get("id")
        if not pid:
            continue
        out.append({
            "id": pid,
            "label": item.get("display_name") or pid,
            "configured": bool(item.get("configured")),
        })
    return out


def _provider_models(provider_id: str | None) -> list[str]:
    if not provider_id:
        return []
    try:
        entry = provider_config.get_provider_entry(provider_id, discover_local=False)
    except Exception:
        return []
    return list(entry.available_models) if entry and entry.available_models else []


def _style_candidates() -> list[dict[str, Any]]:
    try:
        styles = style_store.list_styles().get("styles", [])
    except Exception:
        return []
    return [
        {"id": s.get("id"), "label": s.get("name") or s.get("id")}
        for s in styles if s.get("id")
    ]


def _preset_candidates() -> list[dict[str, Any]]:
    try:
        presets = generator_presets.list_generator_presets()
    except Exception:
        return []
    return [
        {"id": p.get("id"), "label": p.get("name") or p.get("id")}
        for p in presets if p.get("id")
    ]


def _section_candidates() -> list[dict[str, Any]]:
    return [{"id": key, "label": key} for key in INCLUDE_SECTION_FRAGMENTS]


def _axis_candidates(values: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{"id": value, "label": value} for value in values]


def _safe_style_exists(style_id: str) -> bool:
    try:
        return style_store.style_exists(style_id)
    except Exception:
        # Fail-soft: a flaky read must not falsely flag a style as missing.
        return True


def _safe_preset_exists(preset_id: str) -> bool:
    try:
        return generator_presets.generator_preset_exists(preset_id)
    except Exception:
        return True


def _collect_findings_inner(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Full list of findings for a record (no first-failure short-circuit)."""
    findings: list[dict[str, Any]] = []
    shortcut_type = record.get("type")
    payload = record.get("payload")

    if shortcut_type == TYPE_TOOL:
        tool = payload.get("tool") if isinstance(payload, dict) else None
        if tool not in KNOWN_TOOL_KEYS:
            findings.append(_finding(
                FINDING_TOOL_ROUTE_MISSING, SEVERITY_ERROR, "payload.tool",
                "References a tool that is no longer available.",
                current_value=tool or None, repairable=True,
                candidates=[{"id": k, "label": k} for k in sorted(KNOWN_TOOL_KEYS)],
            ))
        return findings

    if shortcut_type == TYPE_LIBRARY_VIEW:
        view = str(payload.get("view") or "") if isinstance(payload, dict) else ""
        if not (view in KNOWN_VIEW_BASES or any(view.startswith(p) for p in VIEW_PREFIXES)):
            findings.append(_finding(
                FINDING_TOOL_ROUTE_MISSING, SEVERITY_ERROR, "payload.view",
                "References a library view that is no longer available.",
                current_value=view or None, repairable=True,
                candidates=[{"id": v, "label": v} for v in sorted(KNOWN_VIEW_BASES)],
            ))
        return findings

    if shortcut_type != TYPE_BUILDER:
        findings.append(_finding(
            FINDING_PAYLOAD_SHAPE_INVALID, SEVERITY_ERROR, "type",
            "Unknown shortcut type; cannot be applied.",
            current_value=shortcut_type, repairable=False,
        ))
        return findings

    if not isinstance(payload, dict):
        findings.append(_finding(
            FINDING_PAYLOAD_SHAPE_INVALID, SEVERITY_ERROR, "payload",
            "Shortcut payload is missing or malformed and cannot be applied.",
            repairable=False,
        ))
        return findings

    # --- provider (required for a generation shortcut) -> broken on failure ---
    providers = _provider_candidates()
    configured_ids = {p["id"] for p in providers if p["configured"]}
    configured_only = [p for p in providers if p["configured"]]
    provider = payload.get("provider")
    provider_id = provider_config.resolve_provider_id(provider) if provider else None
    provider_ok = bool(provider_id) and provider_id in configured_ids

    if not provider:
        findings.append(_finding(
            FINDING_PROVIDER_MISSING, SEVERITY_ERROR, "payload.provider",
            "No provider is set for this generation shortcut.",
            current_value=None, repairable=True, candidates=configured_only,
        ))
    elif not provider_id:
        findings.append(_finding(
            FINDING_PROVIDER_MISSING, SEVERITY_ERROR, "payload.provider",
            "References a provider that is not known to this server.",
            current_value=provider, repairable=True, candidates=configured_only,
        ))
    elif provider_id not in configured_ids:
        findings.append(_finding(
            FINDING_PROVIDER_UNCONFIGURED, SEVERITY_ERROR, "payload.provider",
            "The selected provider is not configured (no API key on the server).",
            current_value=provider, repairable=True, candidates=configured_only,
        ))

    # --- model (optional reference) -> degraded; provider default can serve ---
    model = payload.get("model")
    if model and provider_ok:
        models = _provider_models(provider_id)
        if models and model not in models:
            findings.append(_finding(
                FINDING_MODEL_UNAVAILABLE, SEVERITY_WARNING, "payload.model",
                "Saved model is no longer available for the selected provider; "
                "Builder will fall back to the provider default.",
                current_value=model, repairable=True,
                candidates=[{"id": m, "label": m} for m in models],
            ))

    # --- style (optional) -> degraded; a default style can be used -----------
    style = payload.get("style")
    if style and not _safe_style_exists(style):
        findings.append(_finding(
            FINDING_STYLE_MISSING, SEVERITY_WARNING, "payload.style",
            "Saved style is no longer available; a default style can be used.",
            current_value=style, repairable=True, candidates=_style_candidates(),
        ))

    # --- generator preset (optional) -> degraded; generation can proceed -----
    preset = payload.get("generator_preset")
    if preset and not _safe_preset_exists(preset):
        findings.append(_finding(
            FINDING_GENERATOR_PRESET_MISSING, SEVERITY_WARNING, "payload.generator_preset",
            "Saved generator preset is no longer available; generation can proceed without it.",
            current_value=preset, repairable=True, candidates=_preset_candidates(),
        ))

    # --- include_sections: unknown canonical keys -> degraded (dropped) ------
    sections = payload.get("include_sections")
    if isinstance(sections, dict):
        for key in sections:
            if key not in INCLUDE_SECTION_FRAGMENTS and key not in INCLUDE_SECTION_ALIASES:
                findings.append(_finding(
                    FINDING_SECTION_UNKNOWN, SEVERITY_WARNING, "payload.include_sections",
                    "An included section is not recognized and will be ignored.",
                    current_value=key, repairable=True, candidates=_section_candidates(),
                ))

    # --- axes: invalid stored value -> degraded (ignored/defaulted) ----------
    output_depth = payload.get("output_depth")
    if output_depth and output_depth not in OUTPUT_DEPTH_VALUES:
        findings.append(_finding(
            FINDING_OUTPUT_DEPTH_INVALID, SEVERITY_WARNING, "payload.output_depth",
            "Saved output depth is not a valid option and will be ignored.",
            current_value=output_depth, repairable=True,
            candidates=_axis_candidates(OUTPUT_DEPTH_VALUES),
        ))
    difficulty = payload.get("difficulty")
    if difficulty and difficulty not in DIFFICULTY_VALUES:
        findings.append(_finding(
            FINDING_DIFFICULTY_INVALID, SEVERITY_WARNING, "payload.difficulty",
            "Saved difficulty is not a valid option and will be ignored.",
            current_value=difficulty, repairable=True,
            candidates=_axis_candidates(DIFFICULTY_VALUES),
        ))

    # --- legacy modules: unknown keys -> info (inert; known keys bridged) -----
    modules = payload.get("modules")
    if isinstance(modules, dict):
        for key in modules:
            if key not in KNOWN_MODULE_KEYS:
                findings.append(_finding(
                    FINDING_LEGACY_FIELD_IGNORED, SEVERITY_INFO, "payload.modules",
                    "A legacy module key is not recognized and is ignored on read.",
                    current_value=key, repairable=True,
                ))

    return findings


def _collect_findings(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Fail-soft wrapper: inspection must never crash a list/read. On an
    unexpected error, return a single ``inspection_error`` (degraded) finding."""
    try:
        return _collect_findings_inner(record)
    except Exception:
        return [_finding(
            FINDING_INSPECTION_ERROR, SEVERITY_WARNING, "",
            "This shortcut could not be fully inspected; treat as needs-review.",
            repairable=False,
        )]


def _status_from_findings(findings: list[dict[str, Any]]) -> str:
    if any(f.get("severity") == SEVERITY_ERROR for f in findings):
        return STATUS_BROKEN
    if any(f.get("severity") == SEVERITY_WARNING for f in findings):
        return STATUS_DEGRADED
    return STATUS_VALID


def _validity(record: dict[str, Any]) -> dict[str, Any]:
    """The additive richer validity object: status + full findings + repairable."""
    findings = _collect_findings(record)
    return {
        "status": _status_from_findings(findings),
        "findings": findings,
        "repairable": any(f.get("repairable") for f in findings),
    }


def _repair_candidates() -> dict[str, Any]:
    """Live, redacted candidate registries for the inspect endpoint. No secrets."""
    providers = _provider_candidates()
    models_by_provider = {
        p["id"]: _provider_models(p["id"]) for p in providers if p["configured"]
    }
    return {
        "providers": providers,
        "models_by_provider": models_by_provider,
        "styles": _style_candidates(),
        "generator_presets": _preset_candidates(),
        "sections": _section_candidates(),
        "output_depth": _axis_candidates(OUTPUT_DEPTH_VALUES),
        "difficulty": _axis_candidates(DIFFICULTY_VALUES),
    }


def inspect_shortcut(shortcut_id: str) -> dict[str, Any]:
    """Read-only inspection of one shortcut: the legacy ``valid``/``reason`` plus
    the richer ``validity`` object and live repair candidates. Raises
    ``ShortcutNotFoundError`` for an unknown id. Never mutates ``shortcuts.json``."""
    view = get_shortcut(shortcut_id)  # raises ShortcutNotFoundError if unknown
    return {
        "id": view["id"],
        "name": view["name"],
        "type": view["type"],
        "valid": view["valid"],
        "reason": view["reason"],
        "validity": view["validity"],
        "repair_candidates": _repair_candidates(),
    }


# ---------------------------------------------------------------------------
# Repair (Slice 3A) — explicit, whitelisted, opt-in repair of one shortcut
#
# Two public entry points share ONE normalizer (`_prepare_repair`), so a
# `preview` is byte-for-byte the same computation an `apply` would persist:
#   - `preview_repair`  — READ-ONLY. Builds the proposed record + diff + the
#     resulting validity, writes nothing.
#   - `apply_repair`    — the ONLY write. Persists through the existing CRUD
#     (`update_shortcut` in place, or `create_shortcut` for a clone), so the
#     store's whitelist + atomic-write invariants hold automatically.
#
# Design constraints honoured here (see SHORTCUT_INSPECTOR_REPAIR_DESIGN.md §7
# + DECISIONS.md): explicit whitelisted operations only (NO arbitrary merge-
# patch), no unknown-field persistence, no auto-repair, no migration-on-read, no
# silent overwrite, no provider/model auto-switching (a model is only changed
# when the caller explicitly asks), and no raw key ever read or returned. Repair
# currently supports `builder_setup` shortcuts only (the type whose references
# rot against live config); other types raise a safe error.
# ---------------------------------------------------------------------------

REPAIR_MODE_IN_PLACE = "in_place"
REPAIR_MODE_CLONE = "clone"
REPAIR_MODES = (REPAIR_MODE_IN_PLACE, REPAIR_MODE_CLONE)

# Top-level repair request keys and the per-field change keys. Anything outside
# these sets is REJECTED (a mutation boundary — unknown ops are an error, not
# silently ignored).
REPAIR_BODY_KEYS = {"mode", "changes", "clone_name"}
REPAIR_CHANGE_KEYS = {
    "provider", "model", "style", "generator_preset",
    "output_depth", "difficulty", "include_sections", "remove_fields",
}
# Optional builder fields a repair may DROP (reset to provider/default behaviour).
# `provider` is intentionally NOT removable — a generation shortcut needs one.
REPAIR_REMOVABLE_FIELDS = {"model", "style", "generator_preset", "output_depth", "difficulty"}
# Scalar fields a repair may REPLACE with a value (None clears them).
REPAIR_SCALAR_FIELDS = ("provider", "model", "style", "generator_preset", "output_depth", "difficulty")

CLONE_NAME_SUFFIX = "(repaired copy)"


def _raw_record(shortcut_id: str) -> dict[str, Any]:
    """Return the stored (un-`_public`) record for an id or raise NotFound."""
    if not is_valid_shortcut_id(shortcut_id):
        raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")
    for record in _valid_records():
        if record["id"] == shortcut_id:
            return record
    raise ShortcutNotFoundError(f"Unknown shortcut: {shortcut_id}")


def _validate_repair_provider(provider: str) -> str:
    """Resolve + require a known, configured provider. Raises on failure."""
    provider_id = provider_config.resolve_provider_id(provider)
    if not provider_id:
        raise ShortcutStoreError(f"Unknown provider for repair: {provider!r}.")
    if not _provider_is_configured(provider_id):
        raise ShortcutStoreError(
            f"Provider {provider_id!r} is not configured (no API key on the server)."
        )
    return provider_id


def _apply_repair_changes(record: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Build a fresh, fully-normalized payload from the stored payload + an
    explicit change set. Validates every replacement against live config and
    re-runs the store whitelist (`_normalize_payload`) at the end, so the result
    is exactly what create/update would persist. Pure: never writes."""
    payload = dict(record.get("payload") or {})

    # --- remove_fields: drop whitelisted optional fields (reset to default) ---
    remove_fields = changes.get("remove_fields", [])
    if not isinstance(remove_fields, list):
        raise ShortcutStoreError("remove_fields must be a list of field names.")
    for field in remove_fields:
        if field not in REPAIR_REMOVABLE_FIELDS:
            raise ShortcutStoreError(
                f"Field {field!r} is not removable by repair; "
                f"removable: {sorted(REPAIR_REMOVABLE_FIELDS)}."
            )
        payload[field] = None

    # --- scalar replacements (None = clear) ----------------------------------
    for field in REPAIR_SCALAR_FIELDS:
        if field in changes:
            payload[field] = changes[field]

    # --- include_sections: explicit remove / set (canonical keys only) -------
    if "include_sections" in changes:
        sec = changes["include_sections"]
        if not isinstance(sec, dict):
            raise ShortcutStoreError("include_sections repair must be an object.")
        extra = set(sec) - {"remove", "set"}
        if extra:
            raise ShortcutStoreError(
                f"Unknown include_sections repair ops: {sorted(extra)}; allowed: ['remove', 'set']."
            )
        current = dict(payload.get("include_sections") or {})
        remove = sec.get("remove", [])
        if not isinstance(remove, list):
            raise ShortcutStoreError("include_sections.remove must be a list of keys.")
        for key in remove:
            current.pop(key, None)
        set_map = sec.get("set", {})
        if not isinstance(set_map, dict):
            raise ShortcutStoreError("include_sections.set must be an object of {key: bool}.")
        for key, value in set_map.items():
            if key not in INCLUDE_SECTION_FRAGMENTS and key not in INCLUDE_SECTION_ALIASES:
                raise ShortcutStoreError(f"Unknown include_sections key: {key!r}.")
            current[key] = bool(value)
        payload["include_sections"] = current

    # --- validate replacements against LIVE config ---------------------------
    effective_provider = payload.get("provider")
    if changes.get("provider"):
        # An explicit provider replacement must resolve + be configured.
        _validate_repair_provider(changes["provider"])

    model_value = changes.get("model")
    if model_value:
        # Model needs provider context (requirement #4): validate against the
        # repaired provider when one was supplied, else the existing provider.
        if not effective_provider:
            raise ShortcutStoreError(
                "Cannot set a model without a provider; include a provider in the "
                "same repair or repair the provider first."
            )
        provider_id = provider_config.resolve_provider_id(effective_provider)
        if not provider_id:
            raise ShortcutStoreError(
                f"Cannot validate model against unknown provider {effective_provider!r}."
            )
        models = _provider_models(provider_id)
        if models and model_value not in models:
            raise ShortcutStoreError(
                f"Model {model_value!r} is not available for provider {provider_id!r}."
            )

    if changes.get("style") and not _safe_style_exists(changes["style"]):
        raise ShortcutStoreError(f"Unknown style for repair: {changes['style']!r}.")
    if changes.get("generator_preset") and not _safe_preset_exists(changes["generator_preset"]):
        raise ShortcutStoreError(
            f"Unknown generator preset for repair: {changes['generator_preset']!r}."
        )

    # Final pass through the store whitelist: canonicalizes include_sections,
    # validates axes (raises ShortcutStoreError on a bad enum), cleans strings,
    # and discards anything not in the schema. This is the SAME normalizer
    # create/update use, so preview == apply.
    return _normalize_payload(TYPE_BUILDER, payload)


_REPAIR_DIFF_FIELDS = (
    "provider", "model", "style", "generator_preset",
    "output_depth", "difficulty", "include_sections",
)


def _repair_diff(old_payload: dict[str, Any], new_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Field-level diff (only changed fields) between two builder payloads."""
    diff: list[dict[str, Any]] = []
    for field in _REPAIR_DIFF_FIELDS:
        before = old_payload.get(field)
        after = new_payload.get(field)
        if before != after:
            diff.append({"field": f"payload.{field}", "from": before, "to": after})
    return diff


def _clone_name(record: dict[str, Any], requested: Any) -> str:
    """Clone name: the cleaned requested name, else a safe derived suffix."""
    if requested is not None and str(requested).strip():
        return _clean_name(requested)
    base = str(record.get("name") or "Shortcut")
    return _clean_name(f"{base} {CLONE_NAME_SUFFIX}")


def _prepare_repair(shortcut_id: str, body: Any) -> dict[str, Any]:
    """Shared, READ-ONLY normalizer for preview + apply. Validates the request,
    builds the proposed record, and computes the diff. Raises
    ``ShortcutNotFoundError`` (unknown id) / ``ShortcutStoreError`` (bad request)."""
    if not isinstance(body, dict):
        raise ShortcutStoreError("Repair request must be a JSON object.")
    extra = set(body) - REPAIR_BODY_KEYS
    if extra:
        raise ShortcutStoreError(f"Unknown repair fields: {sorted(extra)}.")

    mode = body.get("mode", REPAIR_MODE_IN_PLACE)
    if mode not in REPAIR_MODES:
        raise ShortcutStoreError(f"mode must be one of {sorted(REPAIR_MODES)}; got {mode!r}.")

    changes = body.get("changes", {})
    if not isinstance(changes, dict):
        raise ShortcutStoreError("changes must be an object.")
    extra_changes = set(changes) - REPAIR_CHANGE_KEYS
    if extra_changes:
        raise ShortcutStoreError(f"Unknown repair change fields: {sorted(extra_changes)}.")

    record = _raw_record(shortcut_id)  # raises NotFound
    if record.get("type") != TYPE_BUILDER:
        raise ShortcutStoreError(
            "Repair currently supports builder_setup shortcuts only."
        )

    proposed_payload = _apply_repair_changes(record, changes)
    proposed_record = dict(record)
    proposed_record["payload"] = proposed_payload

    clone_name = _clone_name(record, body.get("clone_name")) if mode == REPAIR_MODE_CLONE else None
    if mode == REPAIR_MODE_CLONE:
        proposed_record["name"] = clone_name

    diff = _repair_diff(record.get("payload") or {}, proposed_payload)
    return {
        "record": record,
        "proposed_record": proposed_record,
        "proposed_payload": proposed_payload,
        "mode": mode,
        "clone_name": clone_name,
        "diff": diff,
    }


def _repair_warnings(proposed_view: dict[str, Any]) -> list[str]:
    status = proposed_view.get("validity", {}).get("status")
    if status == STATUS_BROKEN:
        return ["The repaired shortcut is still broken; further repair is needed."]
    if status == STATUS_DEGRADED:
        return ["The repaired shortcut is usable but still degraded."]
    return []


def preview_repair(shortcut_id: str, body: Any) -> dict[str, Any]:
    """READ-ONLY: return the original + proposed summaries, the diff, and the
    resulting validity, WITHOUT saving. ``shortcuts.json`` is untouched."""
    prepared = _prepare_repair(shortcut_id, body)
    original_view = _public(prepared["record"])
    proposed_view = _public(prepared["proposed_record"])
    return {
        "ok": True,
        "mode": prepared["mode"],
        "shortcut_id": shortcut_id,
        "original": {
            "id": original_view["id"],
            "name": original_view["name"],
            "type": original_view["type"],
            "valid": original_view["valid"],
            "reason": original_view["reason"],
            "validity": original_view["validity"],
        },
        "proposed": {
            "name": proposed_view["name"],
            "type": proposed_view["type"],
            "payload": proposed_view["payload"],
            "valid": proposed_view["valid"],
            "reason": proposed_view["reason"],
            "validity": proposed_view["validity"],
        },
        "diff": prepared["diff"],
        "warnings": _repair_warnings(proposed_view),
    }


def apply_repair(shortcut_id: str, body: Any) -> dict[str, Any]:
    """The ONLY write: persist a repair. ``in_place`` updates the existing
    shortcut via ``update_shortcut``; ``clone`` creates a NEW shortcut via
    ``create_shortcut`` (original untouched). Both reuse the existing CRUD +
    atomic write + whitelist; nothing is overwritten silently."""
    prepared = _prepare_repair(shortcut_id, body)
    proposed_payload = prepared["proposed_payload"]
    mode = prepared["mode"]
    record = prepared["record"]

    if mode == REPAIR_MODE_CLONE:
        view = create_shortcut({
            "name": prepared["clone_name"],
            "description": record.get("description"),
            "type": TYPE_BUILDER,
            "icon": record.get("icon"),
            "color": record.get("color"),
            "pinned": False,
            "payload": proposed_payload,
        })
    else:
        view = update_shortcut(shortcut_id, {"payload": proposed_payload})

    return {
        "ok": True,
        "mode": mode,
        "shortcut": view,
        "diff": prepared["diff"],
        "warnings": _repair_warnings(view),
    }


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
    # Additive richer inspection (Slice 1). Legacy ``valid``/``reason`` above stay
    # exactly as before; this never mutates the stored record.
    view["validity"] = _validity(record)
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
