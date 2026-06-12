#!/usr/bin/env python3
"""Focused tests for the disabled/unwired Chandra local provider skeleton (Slice 43).

Run with:

    python test_scripts/test_chandra_local_provider.py

No real model, no ``llama-server``, no socket, no network: every test feeds tiny
*handcrafted* request inputs and *injected fake* chat-response objects. No real
Chandra dump, private document, screenshot, model/mmproj/quant file, or local path
is used. The module under test only builds a request *shape*, parses a response
*shape*, and bridges to the Slice 42 normalizer.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear anywhere in parsed/normalized output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
ARGVLIKE = re.compile(r"(?<!\S)--[A-Za-z]")
BASE64URI = re.compile(r"data:[^;]+;base64,")

from pipeline.chandra_local_provider import (  # noqa: E402
    CHANDRA_OCR_LAYOUT_PROMPT,
    PROVIDER_ID,
    RESPONSE_WARNINGS,
    ChandraLocalProvider,
    build_chandra_image_message_payload,
    normalize_chandra_chat_response,
    parse_chandra_chat_response,
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


def _is_json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


# A minimal SDK-like response object (attribute access, not dict access).
class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


# --- 1. Payload builder shape -------------------------------------------------

def test_payload_shape() -> None:
    payload = build_chandra_image_message_payload(b"\x89PNG\r\n\x1a\n", mime_type="image/png")
    check("payload.json_safe", _is_json_safe(payload))
    msgs = payload.get("messages")
    check("payload.messages_list", isinstance(msgs, list) and len(msgs) == 1)
    msg = msgs[0]
    check("payload.role_user", msg.get("role") == "user")
    content = msg.get("content")
    check("payload.content_list", isinstance(content, list) and len(content) == 2)
    text_parts = [p for p in content if p.get("type") == "text"]
    image_parts = [p for p in content if p.get("type") == "image_url"]
    check("payload.has_text_part", len(text_parts) == 1)
    check("payload.has_image_part", len(image_parts) == 1)
    check("payload.temperature", payload.get("temperature") == 0.0)
    check("payload.max_tokens", isinstance(payload.get("max_tokens"), int))
    # No model id / base url / path / argv leaks into the request shape.
    blob = json.dumps(payload)
    check("payload.no_model_field", "model" not in payload)
    check("payload.no_path", not PATHLIKE.search(blob), blob[:200])
    check("payload.no_argv", not ARGVLIKE.search(blob), blob[:200])


def test_payload_prompt_requests_labels_and_bbox() -> None:
    payload = build_chandra_image_message_payload(b"abc")
    text = payload["messages"][0]["content"][0]["text"]
    check("prompt.default_used", text == CHANDRA_OCR_LAYOUT_PROMPT)
    check("prompt.requests_data_label", "data-label" in text)
    check("prompt.requests_data_bbox", "data-bbox" in text)
    check("prompt.requests_table", "<table>" in text.lower())
    check("prompt.requests_latex", "latex" in text.lower())
    check("prompt.requests_caption", "caption" in text.lower())


def test_payload_image_data_uri_only_in_request() -> None:
    payload = build_chandra_image_message_payload(b"\x00\x01\x02\x03binary", mime_type="image/png")
    image_part = payload["messages"][0]["content"][1]
    uri = image_part["image_url"]["url"]
    check("image.is_data_uri", uri.startswith("data:image/png;base64,"))
    check("image.has_base64", BASE64URI.search(uri) is not None)
    # The data URI must NOT survive into parsed/normalized outputs (a different path).
    normalized = normalize_chandra_chat_response(_Resp("<div data-label=\"Text\" data-bbox=\"0 0 9 9\">hi</div>"))
    blob = json.dumps(normalized)
    check("image.uri_not_in_normalized", not BASE64URI.search(blob), blob[:200])


def test_payload_mime_whitelist() -> None:
    # Unknown / hostile mime collapses to png — no arbitrary string in the prefix.
    payload = build_chandra_image_message_payload(b"x", mime_type="image/png; rm -rf /")
    uri = payload["messages"][0]["content"][1]["image_url"]["url"]
    check("mime.collapses_to_png", uri.startswith("data:image/png;base64,"), uri[:40])
    payload2 = build_chandra_image_message_payload(b"x", mime_type="image/jpeg")
    uri2 = payload2["messages"][0]["content"][1]["image_url"]["url"]
    check("mime.allows_jpeg", uri2.startswith("data:image/jpeg;base64,"))


def test_payload_rejects_non_bytes() -> None:
    raised = False
    try:
        build_chandra_image_message_payload("not bytes")  # type: ignore[arg-type]
    except TypeError as exc:
        raised = True
        # The error message must not echo the offending value.
        check("payload.error_no_echo", "not bytes" not in str(exc))
    check("payload.rejects_non_bytes", raised)


# --- 2. Response parsing ------------------------------------------------------

def test_parse_normal_dict() -> None:
    response = {"choices": [{"message": {"content": "<div data-label=\"Text\">hello</div>"}}]}
    parsed = parse_chandra_chat_response(response)
    check("parse.dict_content", parsed["content"] == "<div data-label=\"Text\">hello</div>")
    check("parse.dict_no_warnings", parsed["warnings"] == [])


def test_parse_object_form() -> None:
    parsed = parse_chandra_chat_response(_Resp("layout html here"))
    check("parse.obj_content", parsed["content"] == "layout html here")
    check("parse.obj_no_warnings", parsed["warnings"] == [])


def test_parse_degrades_safely() -> None:
    cases = [
        (None, "empty_response"),
        ({}, "empty_response"),
        ({"choices": []}, "no_choices"),
        ({"choices": [{}]}, "no_message"),
        ({"choices": [{"message": {}}]}, "no_content"),
        ({"choices": [{"message": {"content": "   "}}]}, "no_content"),
        ("garbage string", "no_choices"),
        (12345, "no_choices"),
    ]
    ok = True
    for response, expected in cases:
        try:
            parsed = parse_chandra_chat_response(response)
        except Exception as exc:  # noqa: BLE001
            ok = False
            check("parse.degrade", False, f"raised on {response!r}: {exc}")
            break
        ok = ok and parsed["content"] == "" and expected in parsed["warnings"]
        ok = ok and all(w in RESPONSE_WARNINGS for w in parsed["warnings"])
    check("parse.degrades_safely", ok)


def test_parse_does_not_echo_payload() -> None:
    # A malformed response carrying secrets must not have them echoed by the parser.
    response = {
        "choices": "Authorization: Bearer sk-SECRET0123456789ABCDEF /home/victim/x.gguf",
        "error": "https://evil.example.com socket /run/host.sock --model /opt/m.gguf",
    }
    parsed = parse_chandra_chat_response(response)
    blob = json.dumps(parsed)
    check("parse.no_auth_echo", not AUTHLIKE.search(blob), blob)
    check("parse.no_url_echo", not URLLIKE.search(blob), blob)
    check("parse.no_path_echo", not PATHLIKE.search(blob), blob)
    check("parse.no_socket_echo", not SOCKETLIKE.search(blob), blob)
    check("parse.no_key_echo", not KEYLIKE.search(blob), blob)
    check("parse.warns_no_choices", parsed["warnings"] == ["no_choices"])


# --- 3. Normalizer bridge -----------------------------------------------------

def test_normalize_bridge() -> None:
    response = _Resp(
        '<table data-label="Table" data-bbox="10 10 200 80">'
        "<tr><th>K</th><th>V</th></tr><tr><td>a</td><td>b</td></tr></table>"
    )
    out = normalize_chandra_chat_response(response, source_page=3)
    check("bridge.kind", out.get("kind") == "chandra_normalized_output")
    check("bridge.status", out.get("status") == "completed")
    check("bridge.provider", out.get("source_provider") == "chandra_local")
    tables = [a for a in out["assets"] if a["asset_type"] == "table"]
    check("bridge.table_asset", len(tables) == 1)
    check("bridge.table_page", tables and tables[0]["source_page"] == 3)
    check("bridge.markdown", "| K | V |" in out["source_text"], out["source_text"])
    check("bridge.json_safe", _is_json_safe(out))


def test_normalize_bridge_empty() -> None:
    out = normalize_chandra_chat_response(None)
    check("bridge.empty_completed", out.get("status") == "completed")
    check("bridge.empty_kind", out.get("kind") == "chandra_normalized_output")
    check("bridge.empty_source_text", out.get("source_text") == "")
    check("bridge.empty_assets", out.get("assets") == [])
    check("bridge.empty_warning", "empty_output" in out.get("warnings", []))


def test_normalize_bridge_scrubs_malicious_content() -> None:
    malicious = (
        '<div data-label="Text" data-bbox="0 0 10 10">'
        "Visit https://evil.example.com/leak. /home/victim/secret.pdf /etc/passwd. "
        "Authorization: Bearer sk-ABCDEF0123456789ABCDEF. api sk_live_0123456789ABCDEF . "
        "socket /run/companion/host.sock . flags --model /opt/models/x.gguf . "
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg== ."
        "</div>"
        '<script>alert("xss")</script>'
    )
    out = normalize_chandra_chat_response(_Resp(malicious), source_page=7)
    blob = json.dumps(out)
    check("scrub.no_url", not URLLIKE.search(blob), blob)
    check("scrub.no_path", not PATHLIKE.search(blob), blob)
    check("scrub.no_auth", not AUTHLIKE.search(blob), blob)
    check("scrub.no_socket", not SOCKETLIKE.search(blob), blob)
    check("scrub.no_argv", not ARGVLIKE.search(blob), blob)
    check("scrub.no_keylike", not KEYLIKE.search(blob), blob)
    check("scrub.no_base64uri", not BASE64URI.search(blob), blob)
    check("scrub.no_gguf", ".gguf" not in blob, blob)
    check("scrub.no_xss", "alert(" not in blob and "<script" not in blob.lower(), blob)
    check("scrub.keeps_prose", "Visit" in out["source_text"])
    check("scrub.json_safe", _is_json_safe(out))


# --- 4. Provider handle is disabled/unwired -----------------------------------

def test_provider_disabled() -> None:
    provider = ChandraLocalProvider()
    check("provider.id", provider.provider_id == PROVIDER_ID == "chandra_local")
    check("provider.enabled_false", provider.enabled is False)
    check("provider.is_enabled_false", provider.is_enabled() is False)
    # The handle's methods delegate to the same safe module functions.
    payload = provider.build_image_message_payload(b"x")
    check("provider.build_delegates", payload["messages"][0]["role"] == "user")
    parsed = provider.parse_response(_Resp("hi"))
    check("provider.parse_delegates", parsed["content"] == "hi")
    out = provider.normalize_response(_Resp('<div data-label="Text" data-bbox="0 0 9 9">x</div>'))
    check("provider.normalize_delegates", out["kind"] == "chandra_normalized_output")


# --- 5. No forbidden imports / dependencies -----------------------------------

def test_no_forbidden_imports() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "pipeline", "chandra_local_provider.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    import_lines = [
        ln.strip().lower()
        for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    forbidden = ["fitz", "pymupdf", "pytesseract", "tesseract", "llama_cpp",
                 "llama-cpp", "mistral", "google.generativeai", "genai", "gemini",
                 "openai", "local_model", "companion", "requests", "httpx",
                 "urllib", "socket", "subprocess"]
    leaks = sorted({tok for ln in import_lines for tok in forbidden if tok in ln})
    check("imports.none_forbidden", not leaks, f"found in imports: {leaks}")
    check("imports.stdlib_base64", "import base64" in src)
    check("imports.uses_slice42", "from pipeline.chandra_normalizer import" in src)
    allowed_prefixes = ("import base64", "from __future__", "from typing import",
                        "from pipeline.chandra_normalizer import")
    unexpected = [ln for ln in import_lines if not ln.startswith(allowed_prefixes)]
    check("imports.only_expected", not unexpected, f"unexpected: {unexpected}")


def main() -> int:
    test_payload_shape()
    test_payload_prompt_requests_labels_and_bbox()
    test_payload_image_data_uri_only_in_request()
    test_payload_mime_whitelist()
    test_payload_rejects_non_bytes()
    test_parse_normal_dict()
    test_parse_object_form()
    test_parse_degrades_safely()
    test_parse_does_not_echo_payload()
    test_normalize_bridge()
    test_normalize_bridge_empty()
    test_normalize_bridge_scrubs_malicious_content()
    test_provider_disabled()
    test_no_forbidden_imports()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
