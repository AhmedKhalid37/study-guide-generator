"""Safe app-side selected GGUF library model store (LMM Phase 2E).

This persists only whitelisted companion-library model metadata. It never stores
companion connection details, provider settings, host absolute paths, or raw
companion responses.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pipeline.local_model_companion_client import (
    _MODEL_FIELDS,
    _redact_text,
    _safe_str,
    _sanitize_model,
    get_companion_library,
)


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
SELECTION_JSON = CONFIG_DIR / "local_model_library_selection.json"

SELECTION_FIELDS = (*_MODEL_FIELDS, "selected_at")
FUTURE_LAUNCH_PROFILE = "gpu_default"


class LocalModelLibrarySelectionError(RuntimeError):
    """Raised for invalid selected-library-model input. Messages are client-safe."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=CONFIG_DIR, prefix=f".{path.stem}-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _safe_selected_at(value: Any) -> str | None:
    text = _safe_str(value, max_len=80)
    if not text:
        return None
    return _redact_text(text, max_len=80) or None


def _sanitize_selection(raw: Any, *, selected_at: str | None = None) -> dict[str, Any] | None:
    model = _sanitize_model(raw)
    if not model:
        return None
    safe_selected_at = selected_at or _safe_selected_at(raw.get("selected_at") if isinstance(raw, dict) else None)
    if safe_selected_at:
        model["selected_at"] = safe_selected_at
    return {field: model[field] for field in SELECTION_FIELDS if field in model}


def _read_store() -> dict[str, Any]:
    if not SELECTION_JSON.exists():
        return {"version": 1, "selected": None}
    try:
        data = json.loads(SELECTION_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "selected": None}
    if not isinstance(data, dict):
        return {"version": 1, "selected": None}
    selected = _sanitize_selection(data.get("selected"))
    return {"version": 1, "selected": selected}


def get_library_model_selection() -> dict[str, Any]:
    selected = _read_store()["selected"]
    return {
        "ok": True,
        "selected": selected,
        "future_launch_preview": build_future_launch_preview(selected),
    }


def clear_library_model_selection() -> dict[str, Any]:
    _atomic_write(SELECTION_JSON, {"version": 1, "selected": None})
    return get_library_model_selection()


def _payload_model(payload: dict[str, Any]) -> Any:
    if isinstance(payload.get("model"), dict):
        return payload["model"]
    return payload


def _payload_model_id(payload: dict[str, Any], model_snapshot: Any) -> str | None:
    raw_id = payload.get("model_id") or payload.get("id")
    if raw_id is None and isinstance(model_snapshot, dict):
        raw_id = model_snapshot.get("id")
    text = _safe_str(raw_id, max_len=500)
    if not text:
        return None
    redacted = _redact_text(text, max_len=500)
    return redacted or None


def _models_from_library(library: Any) -> list[dict[str, Any]]:
    if not isinstance(library, dict) or not isinstance(library.get("models"), list):
        return []
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in library["models"]:
        model = _sanitize_model(item)
        if not model or model["id"] in seen:
            continue
        seen.add(model["id"])
        models.append(model)
    return models


def _library_lookup(
    model_id: str | None,
    library_getter: Callable[[], dict[str, Any]] | None,
) -> tuple[dict[str, Any] | None, bool]:
    if not model_id or library_getter is None:
        return None, False
    try:
        library = library_getter()
    except Exception:
        return None, False
    models = _models_from_library(library)
    if not models:
        return None, False
    for model in models:
        if model.get("id") == model_id:
            return model, True
    return None, True


def save_library_model_selection(
    payload: Any,
    *,
    library_getter: Callable[[], dict[str, Any]] | None = get_companion_library,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LocalModelLibrarySelectionError("Selection payload must be an object.")

    model_snapshot = _payload_model(payload)
    model_id = _payload_model_id(payload, model_snapshot)
    if not model_id:
        raise LocalModelLibrarySelectionError("Selection requires a model_id.")

    snapshot_id = _payload_model_id({}, model_snapshot)
    if snapshot_id and snapshot_id != model_id:
        raise LocalModelLibrarySelectionError("Selection model_id does not match the model snapshot.")

    library_model, library_available = _library_lookup(model_id, library_getter)
    if library_model:
        selected = _sanitize_selection(library_model, selected_at=_utc_now())
    elif library_available:
        raise LocalModelLibrarySelectionError("Selected model is not present in the cached library.")
    else:
        selected = _sanitize_selection(model_snapshot, selected_at=_utc_now())

    if not selected:
        raise LocalModelLibrarySelectionError("Selection does not contain a valid model.")
    if selected.get("id") != model_id:
        raise LocalModelLibrarySelectionError("Selection model_id did not pass sanitization.")

    _atomic_write(SELECTION_JSON, {"version": 1, "selected": selected})
    return get_library_model_selection()


def build_future_launch_preview(selected: Any | None = None) -> dict[str, Any] | None:
    model = _sanitize_selection(selected) if selected else _read_store()["selected"]
    if not model:
        return None
    return {
        "profile": FUTURE_LAUNCH_PROFILE,
        "model_id": model.get("id"),
        "filename": model.get("filename"),
        "relative_path": model.get("relative_path"),
        "root_id": model.get("root_id"),
        "runnable_command": False,
        "resolver": "companion_model_id",
        "note": "Future companion launch will resolve the selected model id server-side.",
    }
