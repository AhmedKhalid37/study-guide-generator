"""Approved-root GGUF scanning for the host companion prototype."""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import ApprovedRoot, CompanionConfig

DEFAULT_MAX_FILES_INSPECTED = 10000
DEFAULT_MAX_MODELS_RETURNED = 500
DEFAULT_MAX_WARNINGS = 25
DEFAULT_TIMEOUT_SECONDS = 15.0
COMPANION_SCAN_VERSION = "0.1.0"


@dataclass(frozen=True)
class ScanLimits:
    max_files_inspected: int = DEFAULT_MAX_FILES_INSPECTED
    max_models_returned: int = DEFAULT_MAX_MODELS_RETURNED
    max_warnings: int = DEFAULT_MAX_WARNINGS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


class WarningCollector:
    def __init__(self, max_warnings: int):
        self.max_warnings = max(0, max_warnings)
        self.items: list[dict[str, object]] = []
        self.dropped = 0

    def add(self, code: str, message: str, root_id: str | None = None, relative_path: str | None = None) -> None:
        warning = {
            "code": code,
            "message": message,
        }
        if root_id:
            warning["root_id"] = root_id
        if relative_path:
            warning["relative_path"] = relative_path
        if len(self.items) < self.max_warnings:
            self.items.append(warning)
        else:
            self.dropped += 1

    def payload(self) -> list[dict[str, object]]:
        if self.dropped and len(self.items) < self.max_warnings:
            self.items.append(
                {
                    "code": "warnings_truncated",
                    "message": "additional scan warnings were suppressed",
                    "count": self.dropped,
                }
            )
        return list(self.items)


def _utc_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_relative(path: Path, root: Path) -> str | None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    if any(part in ("", ".", "..") for part in rel.parts):
        return None
    return rel.as_posix()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _display_relative(candidate: Path, root: Path) -> str | None:
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return None


def _family_hint(name: str) -> str | None:
    lowered = name.lower()
    for family in (
        "gemma",
        "llama",
        "mistral",
        "mixtral",
        "qwen",
        "deepseek",
        "phi",
        "yi",
        "codellama",
        "vicuna",
    ):
        if family in lowered:
            return family
    first = re.split(r"[-_.\s]+", lowered, maxsplit=1)[0]
    return first or None


def _quant_hint(name: str) -> str | None:
    match = re.search(r"(?:^|[-_.])((?:I|Q)\d(?:_[A-Z0-9]+)*)(?:[-_.]|$)", name.upper())
    return match.group(1) if match else None


def _model_id(root_id: str, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lower()
    digest = hashlib.sha256(f"{root_id}\0{normalized}".encode("utf-8")).hexdigest()[:24]
    return f"gguf_{digest}"


def _record_for_candidate(
    root: ApprovedRoot,
    root_path: Path,
    candidate: Path,
    warnings: WarningCollector,
) -> tuple[dict[str, object] | None, bool]:
    """Return a safe model record and whether the candidate was rejected."""

    if candidate.suffix.lower() != ".gguf":
        return None, False

    display_rel = _display_relative(candidate, root_path)
    if display_rel is None:
        warnings.add("traversal_rejected", "candidate path is outside the approved root", root.id)
        return None, True

    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        warnings.add("broken_symlink", "candidate could not be resolved", root.id, display_rel)
        return None, True
    except OSError:
        warnings.add("path_unreadable", "candidate could not be resolved", root.id, display_rel)
        return None, True

    if not _is_within(resolved, root_path):
        warnings.add("symlink_escape_rejected", "candidate resolves outside the approved root", root.id, display_rel)
        return None, True
    if not resolved.is_file():
        return None, False

    relative_path = _safe_relative(resolved, root_path)
    if not relative_path:
        warnings.add("traversal_rejected", "resolved candidate is outside the approved root", root.id, display_rel)
        return None, True

    try:
        stat = resolved.stat()
    except PermissionError:
        warnings.add("permission_denied", "candidate metadata could not be read", root.id, relative_path)
        return None, True
    except OSError:
        warnings.add("path_unreadable", "candidate metadata could not be read", root.id, relative_path)
        return None, True

    display_name = resolved.name[:-5] if resolved.name.lower().endswith(".gguf") else resolved.stem
    record = {
        "id": _model_id(root.id, relative_path),
        "display_name": display_name,
        "filename": resolved.name,
        "relative_path": relative_path,
        "root_id": root.id,
        "size_bytes": stat.st_size,
        "modified_at": _utc_timestamp(stat.st_mtime),
        "family_hint": _family_hint(display_name),
        "quant_hint": _quant_hint(display_name),
        "server_compatible": True,
    }
    return record, False


def _iter_candidates(root: ApprovedRoot, root_path: Path, warnings: WarningCollector) -> Iterable[Path]:
    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    candidate = Path(entry.path)
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if root.recursive:
                                stack.append(candidate)
                            continue
                        if entry.is_symlink() and root.recursive:
                            try:
                                resolved = candidate.resolve(strict=True)
                            except FileNotFoundError:
                                rel = _display_relative(candidate, root_path)
                                warnings.add("broken_symlink", "symlink could not be resolved", root.id, rel)
                                continue
                            except OSError:
                                rel = _display_relative(candidate, root_path)
                                warnings.add("path_unreadable", "symlink could not be resolved", root.id, rel)
                                continue
                            if resolved.is_dir():
                                rel = _display_relative(candidate, root_path)
                                warnings.add("symlink_directory_skipped", "symlinked directories are not followed", root.id, rel)
                                continue
                        yield candidate
                    except PermissionError:
                        rel = _display_relative(candidate, root_path)
                        warnings.add("permission_denied", "directory entry could not be inspected", root.id, rel)
                    except OSError:
                        rel = _display_relative(candidate, root_path)
                        warnings.add("path_unreadable", "directory entry could not be inspected", root.id, rel)
        except PermissionError:
            rel = _display_relative(current, root_path)
            warnings.add("permission_denied", "approved-root directory could not be read", root.id, rel)
        except OSError:
            rel = _display_relative(current, root_path)
            warnings.add("path_unreadable", "approved-root directory could not be read", root.id, rel)


def scan_models(
    config: CompanionConfig,
    limits: ScanLimits | None = None,
    root_ids: list[str] | None = None,
) -> dict[str, object]:
    """Scan configured approved roots for GGUF files and return safe metadata."""

    limits = limits or ScanLimits()
    warnings = WarningCollector(limits.max_warnings)
    models: list[dict[str, object]] = []
    roots = list(config.approved_roots)
    if root_ids is not None:
        requested = set(root_ids)
        roots = [root for root in roots if root.id in requested]
        unknown = sorted(requested - {root.id for root in config.approved_roots})
        for root_id in unknown:
            warnings.add("unknown_root", "requested approved root is not configured", root_id)

    inspected = 0
    rejected = 0
    scanned_roots = 0
    seen_model_ids: set[str] = set()
    started = time.monotonic()

    if not roots:
        warnings.add("no_approved_roots", "no approved roots configured")
        return {
            "ok": True,
            "version": COMPANION_SCAN_VERSION,
            "models": [],
            "scanned_roots": 0,
            "roots_configured": len(config.approved_roots),
            "files_inspected": 0,
            "rejected_count": 0,
            "warnings": warnings.payload(),
            "limits": {
                "max_files_inspected": limits.max_files_inspected,
                "max_models_returned": limits.max_models_returned,
                "max_warnings": limits.max_warnings,
                "timeout_seconds": limits.timeout_seconds,
            },
        }

    for root in roots:
        root_path = root.path.resolve(strict=False)
        if time.monotonic() - started > limits.timeout_seconds:
            warnings.add("scan_timeout", "scan timeout reached")
            break
        if not root_path.exists():
            warnings.add("root_missing", "approved root does not exist", root.id)
            continue
        if not root_path.is_dir():
            warnings.add("root_not_directory", "approved root is not a directory", root.id)
            continue

        scanned_roots += 1
        for candidate in _iter_candidates(root, root_path, warnings):
            if inspected >= limits.max_files_inspected:
                warnings.add("max_files_inspected", "maximum file inspection limit reached", root.id)
                break
            if len(models) >= limits.max_models_returned:
                warnings.add("max_models_returned", "maximum returned model limit reached", root.id)
                break
            if time.monotonic() - started > limits.timeout_seconds:
                warnings.add("scan_timeout", "scan timeout reached", root.id)
                break

            inspected += 1
            record, was_rejected = _record_for_candidate(root, root_path, candidate, warnings)
            if was_rejected:
                rejected += 1
            if record:
                model_id = str(record["id"])
                if model_id not in seen_model_ids:
                    seen_model_ids.add(model_id)
                    models.append(record)

    models.sort(key=lambda item: (str(item["root_id"]), str(item["relative_path"]).lower()))
    return {
        "ok": True,
        "version": COMPANION_SCAN_VERSION,
        "models": models,
        "scanned_roots": scanned_roots,
        "roots_configured": len(config.approved_roots),
        "files_inspected": inspected,
        "rejected_count": rejected,
        "warnings": warnings.payload(),
        "limits": {
            "max_files_inspected": limits.max_files_inspected,
            "max_models_returned": limits.max_models_returned,
            "max_warnings": limits.max_warnings,
            "timeout_seconds": limits.timeout_seconds,
        },
    }
