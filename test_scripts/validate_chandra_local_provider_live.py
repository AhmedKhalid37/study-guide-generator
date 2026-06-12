#!/usr/bin/env python3
"""Manual, opt-in **live validation harness** for the Chandra local provider (Slice 44).

This script is **not** part of production app behavior and is **not** part of the
release smoke run. It exists so an operator can validate, *by hand*, that a local
Chandra-capable ``llama-server`` they started themselves can accept one page image
and return output that flows cleanly through the Slice 43 boundary:

    operator's local llama-server response
      → parse_chandra_chat_response(...)      (Slice 43)
      → normalize_chandra_chat_response(...)   (Slice 43 → Slice 42 normalizer)
      → safe, closed-vocabulary summary only

What this slice does and does NOT do
------------------------------------
- It does **not** wire Chandra into :mod:`pipeline.extract`, OCR routing,
  ``extraction_metadata.json`` / ``visual_assets_manifest.json``, ``clean.md``,
  prompts, rendering, exports, the API, the frontend, Provider Settings, or the
  Local Model Manager. It adds no API route and starts/stops no process.
- It performs a real HTTP request **only** when an operator runs the CLI with their
  own ``--endpoint`` and ``--image``. Automated tests inject a fake transport and
  never touch a real server. Importing this module triggers no network, file read,
  model call, subprocess, Docker, or server check.
- It does **not** start, stop, or manage ``llama-server``; it uses no subprocess or
  shell; it supports no auth header (none is sent, none is accepted).

Leak safety
-----------
The harness prints **only** closed-vocabulary fields — booleans, counts, fixed
status/category tokens, and a redacted endpoint label. It never prints (or returns
in its summary) raw OCR text, the raw provider payload, the image path, image bytes,
a base64/data URI, a full URL, query strings, headers, ``Authorization``/``Bearer``
fragments, raw argv, or model/mmproj/executable/socket paths. All scrubbing of model
*content* is owned by the Slice 42 normalizer; this harness additionally guarantees
that none of the safe-summary fields can carry such content (the source text is
reported only as a character count, never echoed).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.chandra_local_provider import (  # noqa: E402
    RESPONSE_WARNINGS,
    build_chandra_image_message_payload,
    normalize_chandra_chat_response,
    parse_chandra_chat_response,
)
from pipeline.chandra_normalizer import OUTPUT_KIND, WARNINGS as NORMALIZER_WARNINGS  # noqa: E402

DEFAULT_TIMEOUT_SECONDS = 60.0

# Closed vocabularies for the summary. Nothing else is ever emitted.
PARSE_STATUSES = ("none", "ok", "empty", "malformed")
NORMALIZED_STATUSES = ("completed",)
FAILURE_CATEGORIES = (
    "connection_failed",
    "request_failed",
    "response_malformed",
    "provider_empty_content",
    "normalization_failed",
    "image_read_failed",
    "invalid_endpoint",
)

# Only these keys are ever printed. Whitelisting at print time guarantees no stray
# field (and therefore no raw content) can leak into operator-visible output.
_CORE_DISPLAY_KEYS = (
    "reachable",
    "request_ok",
    "image_supplied",
    "endpoint_display",
    "parse_status",
    "normalized_kind",
    "normalized_status",
    "source_text_char_count",
    "asset_count",
    "parse_warnings",
    "normalize_warnings",
    "failure_category",
)
_VERBOSE_DISPLAY_KEYS = ("elapsed_ms",)

# Extension → page-image mime. Derived from the supplied path's extension only; the
# path itself and the image bytes are never echoed.
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_DEFAULT_IMAGE_MIME = "image/png"

# A transport is ``(url, payload, timeout_seconds) -> decoded response object``. It
# may raise :class:`HarnessTransportError` with a safe category. The real transport
# is used only when the operator runs the CLI; tests inject a fake one.
Transport = Callable[[str, "dict[str, Any]", float], Any]


class HarnessTransportError(Exception):
    """A transport failure carrying one closed-vocabulary failure category."""

    def __init__(self, category: str) -> None:
        self.category = category if category in FAILURE_CATEGORIES else "request_failed"
        super().__init__(self.category)


class _InvalidEndpoint(Exception):
    pass


class _ImageReadError(Exception):
    pass


# --- Endpoint handling --------------------------------------------------------


def redact_endpoint_for_display(endpoint: Any) -> str:
    """Reduce an operator endpoint to a leak-safe display label.

    Keeps only the scheme and host; the port is masked, the path/query are dropped,
    and any ``user:token@`` userinfo is discarded (``urlsplit().hostname`` strips it).
    A token, ``Authorization``/``Bearer`` fragment, or unsafe path embedded anywhere
    in the URL therefore cannot survive. Anything unparseable or non-http(s) collapses
    to ``"local_endpoint_supplied"``.
    """
    if not isinstance(endpoint, str) or not endpoint.strip():
        return "local_endpoint_supplied"
    try:
        parsed = urllib.parse.urlsplit(endpoint.strip())
    except (ValueError, AttributeError):
        return "local_endpoint_supplied"
    scheme = (parsed.scheme or "").lower()
    try:
        host = parsed.hostname
    except ValueError:
        return "local_endpoint_supplied"
    if scheme not in ("http", "https") or not host:
        return "local_endpoint_supplied"
    return f"{scheme}://{host}:<port>/..."


def _resolve_endpoint_url(endpoint: Any) -> str:
    """Resolve an operator endpoint to a concrete chat-completions URL (internal only).

    Accepts either a base URL (``http://127.0.0.1:8080``) or a full chat-completions
    URL; only ``http``/``https`` with a host are allowed. The resolved URL is used
    only inside the transport — it is never printed.
    """
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise _InvalidEndpoint()
    raw = endpoint.strip()
    try:
        parsed = urllib.parse.urlsplit(raw)
        host = parsed.hostname
    except (ValueError, AttributeError):
        raise _InvalidEndpoint()
    if (parsed.scheme or "").lower() not in ("http", "https") or not host:
        raise _InvalidEndpoint()
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/chat/completions"):
        return raw
    return raw.rstrip("/") + "/v1/chat/completions"


# --- Image handling -----------------------------------------------------------


def _read_image_bytes(image_path: Any) -> "tuple[bytes, str]":
    """Read page-image bytes and derive a mime from the extension (internal only)."""
    if not isinstance(image_path, str) or not image_path.strip():
        raise _ImageReadError()
    try:
        with open(image_path, "rb") as fh:
            data = fh.read()
    except OSError:
        raise _ImageReadError()
    if not data:
        raise _ImageReadError()
    ext = os.path.splitext(image_path)[1].lower()
    return data, _IMAGE_MIME.get(ext, _DEFAULT_IMAGE_MIME)


# --- Real HTTP transport (used only when the operator runs the CLI) -----------


def http_transport(url: str, payload: "dict[str, Any]", timeout_seconds: float) -> Any:
    """POST ``payload`` as JSON to ``url`` with stdlib ``urllib``; return decoded JSON.

    No auth header is sent. Connection-level problems map to ``connection_failed``,
    HTTP error responses to ``request_failed``, and undecodable bodies to
    ``response_malformed`` — always as a :class:`HarnessTransportError` carrying only
    the category (never the URL, headers, or body).
    """
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except urllib.error.HTTPError:
        raise HarnessTransportError("request_failed")
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError):
        raise HarnessTransportError("connection_failed")
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HarnessTransportError("response_malformed")


# --- Summary assembly (closed-vocabulary, JSON-safe) --------------------------


def _new_summary() -> "dict[str, Any]":
    return {
        "reachable": False,
        "request_ok": False,
        "image_supplied": False,
        "endpoint_display": "local_endpoint_supplied",
        "parse_status": "none",
        "normalized_kind": None,
        "normalized_status": None,
        "source_text_char_count": 0,
        "asset_count": 0,
        "parse_warnings": [],
        "normalize_warnings": [],
        "failure_category": None,
        "elapsed_ms": None,
    }


def _parse_status(parse_warnings: "list[str]", content: Any) -> str:
    if "malformed_response" in parse_warnings:
        return "malformed"
    if not parse_warnings and isinstance(content, str) and content.strip():
        return "ok"
    return "empty"


def safe_summary_from_normalized(
    normalized: Any, parse_warnings: "list[str] | None" = None
) -> "dict[str, Any]":
    """Project a Slice 42 normalized output into closed-vocabulary summary fields.

    Reports the source text only as a character count (never its content), the asset
    list only as a count, and warnings only as filtered closed-vocabulary tokens. The
    kind/status are echoed only if they match the known constants, otherwise ``None``.
    """
    norm = normalized if isinstance(normalized, dict) else {}
    kind = norm.get("kind")
    status = norm.get("status")
    text = norm.get("source_text")
    assets = norm.get("assets")
    norm_warnings = norm.get("warnings")
    return {
        "normalized_kind": kind if kind == OUTPUT_KIND else None,
        "normalized_status": status if status in NORMALIZED_STATUSES else None,
        "source_text_char_count": len(text) if isinstance(text, str) else 0,
        "asset_count": len(assets) if isinstance(assets, list) else 0,
        "normalize_warnings": (
            sorted({w for w in norm_warnings if w in NORMALIZER_WARNINGS})
            if isinstance(norm_warnings, list)
            else []
        ),
        "parse_warnings": sorted({w for w in (parse_warnings or []) if w in RESPONSE_WARNINGS}),
    }


def run_validation(
    endpoint: Any,
    image_path: Any,
    *,
    transport: "Transport | None" = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    prompt: "str | None" = None,
) -> "dict[str, Any]":
    """Run one end-to-end validation and return a leak-safe summary dict.

    Total and safe: every failure path resolves to a closed ``failure_category`` and a
    fully-populated summary; nothing here raises to the caller and no raw payload,
    image byte, path, or URL is ever placed into the returned dict. The ``transport``
    is injected by tests; the operator CLI uses :func:`http_transport`.
    """
    summary = _new_summary()
    summary["endpoint_display"] = redact_endpoint_for_display(endpoint)

    try:
        target_url = _resolve_endpoint_url(endpoint)
    except _InvalidEndpoint:
        summary["failure_category"] = "invalid_endpoint"
        return summary

    try:
        image_bytes, mime_type = _read_image_bytes(image_path)
    except _ImageReadError:
        summary["failure_category"] = "image_read_failed"
        return summary
    summary["image_supplied"] = True

    try:
        payload = build_chandra_image_message_payload(image_bytes, mime_type=mime_type, prompt=prompt)
    except Exception:  # noqa: BLE001 — malformed image input is a read failure, not a crash
        summary["failure_category"] = "image_read_failed"
        return summary

    send: Transport = transport or http_transport
    start = time.monotonic()
    try:
        response = send(target_url, payload, timeout_seconds)
    except HarnessTransportError as exc:
        summary["elapsed_ms"] = _elapsed_ms(start)
        summary["failure_category"] = exc.category
        summary["reachable"] = exc.category in ("request_failed", "response_malformed")
        return summary
    except Exception:  # noqa: BLE001 — any unexpected transport error degrades safely
        summary["elapsed_ms"] = _elapsed_ms(start)
        summary["failure_category"] = "request_failed"
        return summary
    summary["elapsed_ms"] = _elapsed_ms(start)
    summary["reachable"] = True
    summary["request_ok"] = True

    parsed = parse_chandra_chat_response(response)
    parse_warnings = [w for w in parsed.get("warnings", []) if w in RESPONSE_WARNINGS]
    summary["parse_status"] = _parse_status(parse_warnings, parsed.get("content"))

    try:
        normalized = normalize_chandra_chat_response(response)
    except Exception:  # noqa: BLE001 — defensive; the normalizer is total
        summary["failure_category"] = "normalization_failed"
        summary["parse_warnings"] = sorted(set(parse_warnings))
        return summary

    summary.update(safe_summary_from_normalized(normalized, parse_warnings))

    if summary["source_text_char_count"] == 0 and any(
        w in ("no_content", "no_message", "no_choices", "empty_response") for w in parse_warnings
    ):
        summary["failure_category"] = "provider_empty_content"
    return summary


def _elapsed_ms(start: float) -> int:
    return int(round((time.monotonic() - start) * 1000))


# --- Output -------------------------------------------------------------------


def print_safe_summary(summary: "dict[str, Any]", *, verbose: bool = False) -> None:
    """Print only the whitelisted, closed-vocabulary summary fields as JSON."""
    keys = list(_CORE_DISPLAY_KEYS) + (list(_VERBOSE_DISPLAY_KEYS) if verbose else [])
    safe = summary if isinstance(summary, dict) else {}
    display = {key: safe.get(key) for key in keys}
    print(json.dumps(display, indent=2, sort_keys=True))


# --- CLI ----------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_chandra_local_provider_live.py",
        description=(
            "Manual, opt-in live validation of the Chandra local provider against an "
            "operator-started local llama-server. Prints a leak-safe summary only."
        ),
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="Local base URL or chat-completions URL of your llama-server (http/https).",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to one page image to send (png/jpg/jpeg/webp). Never echoed.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Request timeout in seconds (default {DEFAULT_TIMEOUT_SECONDS:.0f}).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include elapsed timing in the summary (still leak-safe).",
    )
    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_validation(args.endpoint, args.image, timeout_seconds=args.timeout)
    except Exception:  # noqa: BLE001 — never surface a traceback; stay leak-safe
        summary = _new_summary()
        summary["failure_category"] = "request_failed"
    print_safe_summary(summary, verbose=args.verbose)
    ok = bool(summary.get("request_ok")) and summary.get("failure_category") is None
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
