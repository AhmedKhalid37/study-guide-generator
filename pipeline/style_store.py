"""File-based persistence for study-guide prompt styles.

Two kinds of styles are exposed through a single id namespace:

* built-in styles  -> read-only templates shipped in ``prompts/``
* custom styles    -> user-created templates stored in ``user_prompts/`` with
  metadata tracked in ``user_prompts/styles.json``

The module is intentionally dependency-free (stdlib only) so it can be imported
from both the pipeline and the API layer. All identifiers and filenames are
sanitised and every resolved path is checked to stay inside ``user_prompts/`` so
a crafted id cannot escape via ``..`` or absolute paths.
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

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"
USER_PROMPTS_DIR = BASE_DIR / "user_prompts"
STYLES_JSON = USER_PROMPTS_DIR / "styles.json"

# Required placeholders a usable template must contain. ``generate`` and the
# create/update endpoints surface a warning when one is missing rather than
# hard-failing, because a draft can still be edited by hand afterwards.
REQUIRED_PLACEHOLDERS = ("{title}", "{mode}", "{source}")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

MAX_NAME_CHARS = 120
MAX_DESCRIPTION_CHARS = 600
MAX_CONTENT_CHARS = 50_000
MAX_TAGS = 12
MAX_TAG_CHARS = 32

# Canonical built-in styles. Order is the display order. Only ids listed here
# are treated as styles; helper prompts in ``prompts/`` (e.g. the system/user
# scaffolding) are deliberately excluded.
BUILTIN_STYLES: dict[str, dict[str, str]] = {
    "basic_study_guide": {
        "name": "Basic Study Guide",
        "description": "Complete, student-friendly guide with key ideas, definitions, formulas, and practice.",
    },
    "baby_steps": {
        "name": "Baby Steps",
        "description": "Gentle step-by-step explanations in plain language with tiny examples.",
    },
    "exam_cram": {
        "name": "Exam Cram",
        "description": "Condensed high-yield material with memory cues for last-minute revision.",
    },
    "mcq_training": {
        "name": "MCQ Training",
        "description": "Active-recall multiple-choice questions with rationales.",
    },
    "final_solution": {
        "name": "Final Solutions",
        "description": "Clean, ordered worked solutions for assignments.",
    },
    "claude_study_guide": {
        "name": "Editorial",
        "description": "Narrative, magazine-style chapter for deep reading.",
    },
    "master_longform": {
        "name": "Master Longform",
        "description": "Detailed long-form guide for full chapters.",
    },
}

BUILTIN_STYLE_IDS = tuple(BUILTIN_STYLES.keys())


class StyleStoreError(RuntimeError):
    """Raised for invalid input or forbidden operations on styles."""


class StyleNotFoundError(StyleStoreError):
    pass


# ---------------------------------------------------------------------------
# Identifier / value helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    slug = slug[:48].strip("-")
    return slug or "style"


def is_valid_custom_id(style_id: str) -> bool:
    return bool(ID_PATTERN.match(style_id))


def _safe_custom_path(filename: str) -> Path:
    """Return the absolute path for a custom style file, refusing traversal."""
    name = Path(filename).name  # strip any directory component
    if name != filename or not name.endswith(".md"):
        raise StyleStoreError("Invalid style filename.")
    candidate = (USER_PROMPTS_DIR / name).resolve()
    user_dir = USER_PROMPTS_DIR.resolve()
    if not candidate.is_relative_to(user_dir):
        raise StyleStoreError("Invalid style filename.")
    return candidate


def _clean_name(name: str) -> str:
    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        raise StyleStoreError("name must not be empty.")
    return cleaned[:MAX_NAME_CHARS]


def _clean_description(description: str | None) -> str:
    return " ".join(str(description or "").split())[:MAX_DESCRIPTION_CHARS]


def _clean_content(content: str) -> str:
    text = str(content or "").strip()
    if not text:
        raise StyleStoreError("Style prompt content must not be empty.")
    if len(text) > MAX_CONTENT_CHARS:
        raise StyleStoreError(
            f"Style prompt content exceeds the {MAX_CONTENT_CHARS} character limit."
        )
    return text


def _clean_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    cleaned: list[str] = []
    for tag in tags:
        value = " ".join(str(tag or "").split())[:MAX_TAG_CHARS]
        if value and value not in cleaned:
            cleaned.append(value)
        if len(cleaned) >= MAX_TAGS:
            break
    return cleaned


def missing_placeholders(content: str) -> list[str]:
    return [token for token in REQUIRED_PLACEHOLDERS if token not in content]


# ---------------------------------------------------------------------------
# styles.json registry I/O
# ---------------------------------------------------------------------------

def _read_registry() -> dict[str, Any]:
    if not STYLES_JSON.exists():
        return {"version": 1, "styles": []}
    try:
        data = json.loads(STYLES_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "styles": []}
    if not isinstance(data, dict) or not isinstance(data.get("styles"), list):
        return {"version": 1, "styles": []}
    return data


def _write_registry(registry: dict[str, Any]) -> None:
    USER_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=USER_PROMPTS_DIR, prefix=".styles-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(registry, handle, ensure_ascii=False, indent=2)
        # mkstemp creates 0600; match the 0644 used elsewhere so a local
        # (non-Docker) process can still read styles the container wrote.
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, STYLES_JSON)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _valid_custom_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _read_registry().get("styles", []):
        if not isinstance(entry, dict):
            continue
        style_id = str(entry.get("id") or "")
        filename = str(entry.get("filename") or "")
        if not is_valid_custom_id(style_id) or style_id in seen:
            continue
        if filename != f"{style_id}.md":
            continue
        seen.add(style_id)
        records.append(entry)
    return records


# ---------------------------------------------------------------------------
# Public metadata views
# ---------------------------------------------------------------------------

def _builtin_meta(style_id: str) -> dict[str, Any]:
    info = BUILTIN_STYLES[style_id]
    return {
        "id": style_id,
        "prompt_name": style_id,
        "name": info["name"],
        "description": info["description"],
        "source": "builtin",
        "builtin": True,
        "editable": False,
        "base_style": None,
        "tags": [],
        "created_at": None,
        "updated_at": None,
    }


def _custom_meta(entry: dict[str, Any]) -> dict[str, Any]:
    style_id = str(entry["id"])
    base_style = entry.get("base_style")
    return {
        "id": style_id,
        "prompt_name": style_id,
        "name": str(entry.get("name") or style_id),
        "description": str(entry.get("description") or ""),
        "source": "custom",
        "builtin": False,
        "editable": True,
        "base_style": base_style if base_style in BUILTIN_STYLES or base_style is None else base_style,
        "tags": _clean_tags(entry.get("tags")),
        "created_at": entry.get("created_at"),
        "updated_at": entry.get("updated_at"),
    }


def list_builtin_styles() -> list[dict[str, Any]]:
    return [_builtin_meta(style_id) for style_id in BUILTIN_STYLE_IDS if (PROMPTS_DIR / f"{style_id}.md").exists()]


def list_custom_styles() -> list[dict[str, Any]]:
    styles = [_custom_meta(entry) for entry in _valid_custom_records()]
    styles.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return styles


def list_styles() -> dict[str, Any]:
    builtin = list_builtin_styles()
    custom = list_custom_styles()
    return {"styles": [*builtin, *custom], "builtin": builtin, "custom": custom}


def is_builtin(style_id: str) -> bool:
    return style_id in BUILTIN_STYLES


def _find_custom(style_id: str) -> dict[str, Any] | None:
    for entry in _valid_custom_records():
        if entry["id"] == style_id:
            return entry
    return None


def style_exists(style_id: str) -> bool:
    if is_builtin(style_id):
        return (PROMPTS_DIR / f"{style_id}.md").exists()
    return is_valid_custom_id(style_id) and _find_custom(style_id) is not None


def resolve_prompt_text(style_id: str) -> str:
    """Return the raw template markdown for a built-in or custom style."""
    if is_builtin(style_id):
        path = PROMPTS_DIR / f"{style_id}.md"
        if not path.exists():
            raise StyleNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    if not is_valid_custom_id(style_id):
        raise StyleNotFoundError(f"Unknown style: {style_id}")
    entry = _find_custom(style_id)
    if entry is None:
        raise StyleNotFoundError(f"Unknown style: {style_id}")
    path = _safe_custom_path(str(entry["filename"]))
    if not path.exists():
        raise StyleNotFoundError(f"Custom style file is missing: {style_id}")
    return path.read_text(encoding="utf-8")


def get_style(style_id: str) -> dict[str, Any]:
    """Return safe metadata plus the prompt markdown content for one style."""
    if is_builtin(style_id):
        meta = _builtin_meta(style_id)
        meta["content"] = resolve_prompt_text(style_id)
        meta["missing_placeholders"] = missing_placeholders(meta["content"])
        return meta

    if not is_valid_custom_id(style_id):
        raise StyleNotFoundError(f"Unknown style: {style_id}")
    entry = _find_custom(style_id)
    if entry is None:
        raise StyleNotFoundError(f"Unknown style: {style_id}")
    meta = _custom_meta(entry)
    meta["content"] = resolve_prompt_text(style_id)
    meta["missing_placeholders"] = missing_placeholders(meta["content"])
    return meta


# ---------------------------------------------------------------------------
# Mutations (custom styles only)
# ---------------------------------------------------------------------------

def _generate_unique_id(name: str, existing: set[str]) -> str:
    base = _slugify(name)
    for _ in range(20):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if is_valid_custom_id(candidate) and candidate not in existing and not is_builtin(candidate):
            return candidate
    # Fall back to a fully random id if slug-based attempts keep colliding.
    while True:
        candidate = f"style-{secrets.token_hex(4)}"
        if candidate not in existing:
            return candidate


def create_custom_style(
    *,
    name: str,
    description: str | None = None,
    content: str,
    base_style: str | None = None,
    tags: Any = None,
) -> dict[str, Any]:
    clean_name = _clean_name(name)
    clean_desc = _clean_description(description)
    clean_content = _clean_content(content)
    clean_tags = _clean_tags(tags)
    resolved_base = base_style if (base_style in BUILTIN_STYLES) else None

    registry = _read_registry()
    styles = [entry for entry in registry.get("styles", []) if isinstance(entry, dict)]
    existing_ids = {str(entry.get("id")) for entry in styles}
    style_id = _generate_unique_id(clean_name, existing_ids)
    filename = f"{style_id}.md"
    timestamp = _now_iso()

    record = {
        "id": style_id,
        "name": clean_name,
        "description": clean_desc,
        "filename": filename,
        "created_at": timestamp,
        "updated_at": timestamp,
        "source": "custom",
        "base_style": resolved_base,
        "tags": clean_tags,
    }

    path = _safe_custom_path(filename)
    USER_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(clean_content, encoding="utf-8")
    try:
        registry["version"] = registry.get("version", 1)
        registry["styles"] = [*styles, record]
        _write_registry(registry)
    except Exception:
        path.unlink(missing_ok=True)
        raise

    return get_style(style_id)


def update_custom_style(
    style_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    content: str | None = None,
    tags: Any = None,
) -> dict[str, Any]:
    if is_builtin(style_id):
        raise StyleStoreError("Built-in styles cannot be edited.")
    if not is_valid_custom_id(style_id):
        raise StyleNotFoundError(f"Unknown style: {style_id}")

    registry = _read_registry()
    styles = [entry for entry in registry.get("styles", []) if isinstance(entry, dict)]
    record = next((entry for entry in styles if str(entry.get("id")) == style_id), None)
    if record is None:
        raise StyleNotFoundError(f"Unknown style: {style_id}")

    if name is not None:
        record["name"] = _clean_name(name)
    if description is not None:
        record["description"] = _clean_description(description)
    if tags is not None:
        record["tags"] = _clean_tags(tags)
    if content is not None:
        path = _safe_custom_path(str(record.get("filename") or f"{style_id}.md"))
        path.write_text(_clean_content(content), encoding="utf-8")
    record["updated_at"] = _now_iso()

    registry["styles"] = styles
    _write_registry(registry)
    return get_style(style_id)


def delete_custom_style(style_id: str) -> None:
    if is_builtin(style_id):
        raise StyleStoreError("Built-in styles cannot be deleted.")
    if not is_valid_custom_id(style_id):
        raise StyleNotFoundError(f"Unknown style: {style_id}")

    registry = _read_registry()
    styles = [entry for entry in registry.get("styles", []) if isinstance(entry, dict)]
    record = next((entry for entry in styles if str(entry.get("id")) == style_id), None)
    if record is None:
        raise StyleNotFoundError(f"Unknown style: {style_id}")

    filename = str(record.get("filename") or f"{style_id}.md")
    try:
        _safe_custom_path(filename).unlink(missing_ok=True)
    except StyleStoreError:
        pass
    registry["styles"] = [entry for entry in styles if str(entry.get("id")) != style_id]
    _write_registry(registry)
