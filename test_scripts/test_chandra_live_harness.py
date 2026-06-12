#!/usr/bin/env python3
"""Focused tests for the manual Chandra local provider live harness (Slice 44).

Run with:

    python test_scripts/test_chandra_live_harness.py

No real model, no ``llama-server``, no socket, no network: every test injects a
**fake transport** and feeds tiny *handcrafted* response objects. The real
``http_transport`` is never invoked. Image inputs are tiny synthetic bytes written
to a temp file at runtime (no committed fixtures). The harness only builds a request
*shape*, parses a response *shape*, normalizes via Slice 42, and prints a leak-safe
summary.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear in any summary or printed output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|pk_|rk_)[A-Za-z0-9_\-]{8,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|/run/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://\S|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
ARGVLIKE = re.compile(r"(?<!\S)--[A-Za-z]")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

from test_scripts.validate_chandra_local_provider_live import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    FAILURE_CATEGORIES,
    HarnessTransportError,
    PARSE_STATUSES,
    print_safe_summary,
    redact_endpoint_for_display,
    run_validation,
    safe_summary_from_normalized,
)
from pipeline.chandra_normalizer import OUTPUT_KIND  # noqa: E402


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


def _summary_blob(summary: dict) -> str:
    return json.dumps(summary)


def _blob_without_endpoint(summary: dict) -> str:
    # ``endpoint_display`` legitimately carries the safe redacted
    # ``http://<host>:<port>/...`` form, so exclude it when sweeping for leaked URLs.
    return json.dumps({k: v for k, v in summary.items() if k != "endpoint_display"})


@contextlib.contextmanager
def _temp_image(data: bytes = b"\x89PNG\r\n\x1a\nFAKEPNGBYTES", suffix: str = ".png"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        yield path
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)


# A transport factory: records the payload it was handed and returns a fixed response.
class _RecordingTransport:
    def __init__(self, response):
        self.response = response
        self.calls = 0
        self.last_url = None
        self.last_payload = None

    def __call__(self, url, payload, timeout):
        self.calls += 1
        self.last_url = url
        self.last_payload = payload
        return self.response


def _raising_transport(category):
    def _t(url, payload, timeout):
        raise HarnessTransportError(category)

    return _t


def _ok_response(content):
    return {"choices": [{"message": {"content": content}}]}


# --- 1. Fake success parses and normalizes ------------------------------------

def test_success_parses_and_normalizes() -> None:
    content = (
        '<table data-label="Table" data-bbox="10 10 200 80">'
        "<tr><th>K</th><th>V</th></tr><tr><td>a</td><td>b</td></tr></table>"
    )
    transport = _RecordingTransport(_ok_response(content))
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    check("success.transport_called", transport.calls == 1)
    check("success.request_ok", summary["request_ok"] is True)
    check("success.reachable", summary["reachable"] is True)
    check("success.parse_status_ok", summary["parse_status"] == "ok")
    check("success.normalized_kind", summary["normalized_kind"] == OUTPUT_KIND)
    check("success.normalized_status", summary["normalized_status"] == "completed")
    check("success.asset_count", summary["asset_count"] == 1)
    check("success.char_count_positive", summary["source_text_char_count"] > 0)
    check("success.no_failure", summary["failure_category"] is None)
    check("success.json_safe", _is_json_safe(summary))


# --- 2. Safe summary includes counts + warning tokens only --------------------

def test_safe_summary_counts_and_tokens_only() -> None:
    normalized = {
        "kind": OUTPUT_KIND,
        "status": "completed",
        "source_text": "secret prose body about CONFIDENTIAL_TOPIC here",
        "assets": [{"asset_id": "page_0001_chandra_01"}, {"asset_id": "page_0001_chandra_02"}],
        "warnings": ["bbox_missing", "not_a_real_warning"],
    }
    summary = safe_summary_from_normalized(normalized, parse_warnings=["no_content", "bogus"])
    check("sumfields.char_count", summary["source_text_char_count"] == len(normalized["source_text"]))
    check("sumfields.asset_count", summary["asset_count"] == 2)
    # Closed-vocabulary filtering: bogus tokens dropped.
    check("sumfields.normalize_warn_closed", summary["normalize_warnings"] == ["bbox_missing"])
    check("sumfields.parse_warn_closed", summary["parse_warnings"] == ["no_content"])
    # No raw source text fields anywhere.
    check("sumfields.no_source_text_key", "source_text" not in summary)
    check("sumfields.no_assets_key", "assets" not in summary)


def test_safe_summary_does_not_include_raw_ocr_text() -> None:
    secret_marker = "ZZUNIQUEOCRMARKER42"
    content = f'<div data-label="Text" data-bbox="0 0 10 10">{secret_marker} body line</div>'
    transport = _RecordingTransport(_ok_response(content))
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080/v1/chat/completions", image_path, transport=transport)
    blob = _summary_blob(summary)
    check("noraw.marker_absent", secret_marker not in blob, blob)
    check("noraw.char_count_seen", summary["source_text_char_count"] > 0)
    # Print path must also not echo it.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_safe_summary(summary, verbose=True)
    check("noraw.print_no_marker", secret_marker not in buf.getvalue())


# --- 3. Malformed response → safe status, no raw payload ----------------------

def test_malformed_response_shape() -> None:
    # Valid JSON, but not a chat-completions shape; parser degrades safely.
    bad = {"unexpected": "ZZRAWPAYLOAD", "stuff": [1, 2, 3]}
    transport = _RecordingTransport(bad)
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    check("malformed.request_ok", summary["request_ok"] is True)
    check("malformed.parse_status", summary["parse_status"] in PARSE_STATUSES)
    check("malformed.parse_status_empty", summary["parse_status"] == "empty")
    blob = _summary_blob(summary)
    check("malformed.no_raw_payload", "ZZRAWPAYLOAD" not in blob, blob)
    check("malformed.no_unexpected_key", "unexpected" not in blob)
    check("malformed.json_safe", _is_json_safe(summary))


def test_transport_response_malformed_category() -> None:
    transport = _raising_transport("response_malformed")
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    check("respmalformed.category", summary["failure_category"] == "response_malformed")
    check("respmalformed.reachable", summary["reachable"] is True)
    check("respmalformed.not_request_ok", summary["request_ok"] is False)


# --- 4. Connection error → safe category, no traceback / private data ---------

def test_connection_failed_category() -> None:
    transport = _raising_transport("connection_failed")
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    check("conn.category", summary["failure_category"] == "connection_failed")
    check("conn.not_reachable", summary["reachable"] is False)
    check("conn.not_request_ok", summary["request_ok"] is False)
    check("conn.category_closed", summary["failure_category"] in FAILURE_CATEGORIES)
    blob = _summary_blob(summary)
    check("conn.no_traceback", "Traceback" not in blob and "Error" not in blob)
    check("conn.json_safe", _is_json_safe(summary))


def test_unexpected_transport_error_degrades() -> None:
    def _boom(url, payload, timeout):
        raise RuntimeError("Authorization: Bearer sk-LEAK0123456789ABCDEF /home/x/m.gguf")

    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=_boom)
    check("boom.category", summary["failure_category"] == "request_failed")
    blob = _summary_blob(summary)
    check("boom.no_auth", not AUTHLIKE.search(blob), blob)
    check("boom.no_key", not KEYLIKE.search(blob), blob)
    check("boom.no_path", not PATHLIKE.search(blob), blob)
    check("boom.no_gguf", not GGUFLIKE.search(blob), blob)


# --- 5. Endpoint display redaction --------------------------------------------

def test_endpoint_redacts_query_and_token() -> None:
    endpoint = "http://127.0.0.1:8080/v1/chat/completions?api_key=sk-SECRET0123456789ABCDEF&x=1"
    display = redact_endpoint_for_display(endpoint)
    check("redact.no_query", "api_key" not in display and "?" not in display, display)
    check("redact.no_key", not KEYLIKE.search(display), display)
    check("redact.no_port_digits", "8080" not in display, display)
    check("redact.no_path_tail", "completions" not in display, display)
    check("redact.expected_form", display == "http://127.0.0.1:<port>/...", display)


def test_endpoint_redacts_userinfo_and_auth() -> None:
    endpoint = "http://user:Bearer-sk_live_0123456789ABCDEF@127.0.0.1:9090/path/to/thing"
    display = redact_endpoint_for_display(endpoint)
    check("redact.no_userinfo", "user" not in display, display)
    check("redact.no_bearer", not AUTHLIKE.search(display), display)
    check("redact.no_key2", not KEYLIKE.search(display), display)
    check("redact.host_only", display == "http://127.0.0.1:<port>/...", display)


def test_endpoint_redacts_token_in_path() -> None:
    endpoint = "http://127.0.0.1:8080/v1/sk-PATHTOKEN0123456789/chat/completions"
    display = redact_endpoint_for_display(endpoint)
    check("redact.path_token_gone", not KEYLIKE.search(display), display)
    check("redact.path_collapsed", display == "http://127.0.0.1:<port>/...", display)


def test_endpoint_invalid_collapses() -> None:
    for bad in ["", "   ", None, 12345, "not a url", "ftp://127.0.0.1/x", "file:///etc/passwd"]:
        display = redact_endpoint_for_display(bad)
        check(f"redact.invalid_{bad!r}", display == "local_endpoint_supplied", display)


def test_invalid_endpoint_run() -> None:
    transport = _RecordingTransport(_ok_response("x"))
    with _temp_image() as image_path:
        summary = run_validation("not-a-valid-endpoint", image_path, transport=transport)
    check("invalidrun.category", summary["failure_category"] == "invalid_endpoint")
    check("invalidrun.transport_not_called", transport.calls == 0)
    check("invalidrun.display_safe", summary["endpoint_display"] == "local_endpoint_supplied")


# --- 6. Image path / bytes / base64 never leak --------------------------------

def test_image_path_not_echoed() -> None:
    content = '<div data-label="Text" data-bbox="0 0 9 9">hi</div>'
    transport = _RecordingTransport(_ok_response(content))
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
        blob = _summary_blob(summary)
        check("imgpath.not_in_summary", image_path not in blob, blob)
        base = os.path.basename(image_path)
        check("imgpath.basename_not_in_summary", base not in blob, blob)
    check("imgpath.image_supplied_flag", summary["image_supplied"] is True)
    check("imgpath.no_pathlike", not PATHLIKE.search(blob), blob)


def test_base64_data_uri_not_in_summary() -> None:
    # The payload the transport receives DOES carry a base64 data URI (correct), but
    # it must never appear in the returned/printed summary.
    content = '<div data-label="Text" data-bbox="0 0 9 9">ok</div>'
    transport = _RecordingTransport(_ok_response(content))
    with _temp_image(data=b"\x00\x01\x02\x03IMAGEBYTES") as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    # Transport really did get a data URI in the request payload.
    uri = transport.last_payload["messages"][0]["content"][1]["image_url"]["url"]
    check("b64.payload_has_uri", BASE64URI.search(uri) is not None)
    # ...but the summary does not.
    blob = _summary_blob(summary)
    check("b64.not_in_summary", not BASE64URI.search(blob), blob)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_safe_summary(summary, verbose=True)
    check("b64.not_printed", not BASE64URI.search(buf.getvalue()))


# --- 7. Raw provider payload & smuggled secrets never leak --------------------

def test_raw_provider_payload_not_leaked() -> None:
    malicious = (
        '<div data-label="Text" data-bbox="0 0 10 10">'
        "Visit https://evil.example.com/leak . /home/victim/secret.pdf /etc/passwd . "
        "Authorization: Bearer sk-ABCDEF0123456789ABCDEF . api sk_live_0123456789ABCDEF . "
        "socket /run/companion/host.sock . flags --model /opt/models/x.gguf and mmproj.gguf . "
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg== ."
        "</div>"
        '<script>alert("xss")</script>'
    )
    transport = _RecordingTransport(_ok_response(malicious))
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    blob = _summary_blob(summary)
    check("rawleak.no_url", not URLLIKE.search(_blob_without_endpoint(summary)), blob)
    check("rawleak.no_evil_host", "evil.example.com" not in blob, blob)
    check("rawleak.no_path", not PATHLIKE.search(blob), blob)
    check("rawleak.no_auth", not AUTHLIKE.search(blob), blob)
    check("rawleak.no_socket", not SOCKETLIKE.search(blob), blob)
    check("rawleak.no_argv", not ARGVLIKE.search(blob), blob)
    check("rawleak.no_key", not KEYLIKE.search(blob), blob)
    check("rawleak.no_base64uri", not BASE64URI.search(blob), blob)
    check("rawleak.no_gguf", not GGUFLIKE.search(blob), blob)
    check("rawleak.no_xss", "alert(" not in blob and "<script" not in blob.lower(), blob)
    # The full printed output is equally clean.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_safe_summary(summary, verbose=True)
    out = buf.getvalue()
    check("rawleak.print_clean", not ("evil.example.com" in out or PATHLIKE.search(out)
                                      or AUTHLIKE.search(out) or KEYLIKE.search(out)
                                      or BASE64URI.search(out) or GGUFLIKE.search(out)), out)


# --- 8. Request built via the Slice 43 payload builder ------------------------

def test_request_built_with_slice43_payload() -> None:
    content = '<div data-label="Text" data-bbox="0 0 9 9">ok</div>'
    transport = _RecordingTransport(_ok_response(content))
    with _temp_image() as image_path:
        run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    payload = transport.last_payload
    check("payload.has_messages", isinstance(payload.get("messages"), list))
    content_parts = payload["messages"][0]["content"]
    types = {p.get("type") for p in content_parts}
    check("payload.text_and_image", types == {"text", "image_url"})
    uri = [p for p in content_parts if p.get("type") == "image_url"][0]["image_url"]["url"]
    check("payload.image_is_data_uri", uri.startswith("data:image/png;base64,"))
    check("payload.temperature_zero", payload.get("temperature") == 0.0)
    # The resolved URL handed to the transport is internal, but must target the API.
    check("payload.url_targets_chat", transport.last_url.endswith("/v1/chat/completions"))


# --- 9. provider_empty_content category ---------------------------------------

def test_provider_empty_content_category() -> None:
    transport = _RecordingTransport(_ok_response("   "))  # whitespace-only content
    with _temp_image() as image_path:
        summary = run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    check("empty.category", summary["failure_category"] == "provider_empty_content")
    check("empty.char_count_zero", summary["source_text_char_count"] == 0)
    check("empty.parse_warn_closed", summary["parse_warnings"] == ["no_content"])


# --- 10. image read failure ---------------------------------------------------

def test_image_read_failed_category() -> None:
    transport = _RecordingTransport(_ok_response("x"))
    summary = run_validation("http://127.0.0.1:8080", "/no/such/image/path.png", transport=transport)
    check("imgread.category", summary["failure_category"] == "image_read_failed")
    check("imgread.transport_not_called", transport.calls == 0)
    blob = _summary_blob(summary)
    check("imgread.no_path_echo", "/no/such/image" not in blob, blob)


# --- 11. No live network during tests -----------------------------------------

def test_no_live_network_default_transport_untouched() -> None:
    # Every test injects a transport. Confirm the real http_transport is never the
    # default actually used here by patching it to explode if invoked.
    import test_scripts.validate_chandra_local_provider_live as mod

    original = mod.http_transport
    tripped = {"hit": False}

    def _explode(url, payload, timeout):
        tripped["hit"] = True
        raise AssertionError("real network transport must not run in tests")

    mod.http_transport = _explode
    try:
        transport = _RecordingTransport(_ok_response("<div data-label=\"Text\" data-bbox=\"0 0 9 9\">x</div>"))
        with _temp_image() as image_path:
            run_validation("http://127.0.0.1:8080", image_path, transport=transport)
    finally:
        mod.http_transport = original
    check("network.real_transport_not_hit", tripped["hit"] is False)


# --- 12. No forbidden imports -------------------------------------------------

def test_no_forbidden_imports() -> None:
    path = os.path.join(os.path.dirname(__file__), "validate_chandra_local_provider_live.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    import_lines = [
        ln.strip().lower()
        for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    forbidden = [
        "pipeline.extract", "ocr_routing", "ocr_provider", "run_llm_job",
        "job_manager", "orchestrator", "api.server", "fastapi", "render",
        "exporter", "local_model", "companion", "subprocess", "shutil",
        "fitz", "pytesseract", "requests", "httpx", "docker",
    ]
    leaks = sorted({tok for ln in import_lines for tok in forbidden if tok in ln})
    check("imports.none_forbidden", not leaks, f"found in imports: {leaks}")
    check("imports.uses_slice43", "from pipeline.chandra_local_provider import" in src)
    check("imports.uses_slice42", "from pipeline.chandra_normalizer import" in src)
    # No subprocess/docker *imports* (covered by the forbidden-import scan above; the
    # words may legitimately appear in the module docstring describing what it avoids).
    no_subprocess_import = not any("subprocess" in ln for ln in import_lines)
    no_docker_import = not any("docker" in ln for ln in import_lines)
    check("imports.no_subprocess_import", no_subprocess_import)
    check("imports.no_docker_import", no_docker_import)
    # Default timeout sanity (no behavior change, just a guard).
    check("config.default_timeout", DEFAULT_TIMEOUT_SECONDS == 60.0)


def main() -> int:
    test_success_parses_and_normalizes()
    test_safe_summary_counts_and_tokens_only()
    test_safe_summary_does_not_include_raw_ocr_text()
    test_malformed_response_shape()
    test_transport_response_malformed_category()
    test_connection_failed_category()
    test_unexpected_transport_error_degrades()
    test_endpoint_redacts_query_and_token()
    test_endpoint_redacts_userinfo_and_auth()
    test_endpoint_redacts_token_in_path()
    test_endpoint_invalid_collapses()
    test_invalid_endpoint_run()
    test_image_path_not_echoed()
    test_base64_data_uri_not_in_summary()
    test_raw_provider_payload_not_leaked()
    test_request_built_with_slice43_payload()
    test_provider_empty_content_category()
    test_image_read_failed_category()
    test_no_live_network_default_transport_untouched()
    test_no_forbidden_imports()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
