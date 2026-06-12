#!/usr/bin/env python3
"""Focused tests for the pure Chandra output normalizer (Slice 42).

Run with:

    python test_scripts/test_chandra_normalizer.py

No external APIs and no PyMuPDF/Tesseract/llama.cpp/Mistral/Gemini/Chandra-runtime
or Local-Model-Manager dependency: the normalizer is a pure function of one raw
string, so these tests feed it tiny *handcrafted synthetic* layout strings based
on the observed Chandra shape. No real model dumps, private documents, screenshots,
or local paths are used.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear anywhere in normalizer output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
ARGVLIKE = re.compile(r"(?<!\S)--[A-Za-z]")
BASE64URI = re.compile(r"data:[^;]+;base64,")
SCRIPTLIKE = re.compile(r"<\s*(script|style)\b", re.IGNORECASE)

from pipeline.chandra_normalizer import (  # noqa: E402
    OUTPUT_KIND,
    OUTPUT_VERSION,
    RECOMMENDED_ACTION_UNKNOWN,
    SOURCE_PROVIDER_CHANDRA_LOCAL,
    chandra_blocks_to_manifest_assets,
    chandra_blocks_to_source_text,
    extract_chandra_blocks,
    normalize_chandra_output,
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


def _assets_of_type(out: dict, asset_type: str) -> list[dict]:
    return [a for a in out["assets"] if a["asset_type"] == asset_type]


def _is_json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


# --- 1. Envelope & determinism ------------------------------------------------

def test_envelope_and_determinism() -> None:
    raw = '<div data-label="Text" data-bbox="0 0 10 10">Hello world.</div>'
    out1 = normalize_chandra_output(raw, source_page=2)
    out2 = normalize_chandra_output(raw, source_page=2)
    check("envelope.version", out1["version"] == OUTPUT_VERSION)
    check("envelope.kind", out1["kind"] == OUTPUT_KIND == "chandra_normalized_output")
    check("envelope.status", out1["status"] == "completed")
    check("envelope.provider", out1["source_provider"] == SOURCE_PROVIDER_CHANDRA_LOCAL == "chandra_local")
    check("envelope.json_safe", _is_json_safe(out1))
    check("determinism.identical", json.dumps(out1, sort_keys=True) == json.dumps(out2, sort_keys=True))
    check("text.simple_text", out1["source_text"] == "Hello world.", out1["source_text"])
    check("text.no_text_asset", out1["assets"] == [], "text blocks must not be visual assets")


# --- 2. Table ----------------------------------------------------------------

def test_table_block() -> None:
    raw = (
        '<table data-label="Table" data-bbox="10 10 200 80">'
        "<tr><th>Layer</th><th>Activation</th></tr>"
        "<tr><td>Hidden</td><td>ReLU</td></tr>"
        "</table>"
    )
    out = normalize_chandra_output(raw, source_page=1)
    tables = _assets_of_type(out, "table")
    check("table.asset_present", len(tables) == 1)
    check("table.provider", tables and tables[0]["source_provider"] == "chandra_local")
    check("table.bbox", tables and tables[0]["bbox"] == [10.0, 10.0, 200.0, 80.0])
    md = out["source_text"]
    check("table.markdown_header", "| Layer | Activation |" in md, md)
    check("table.markdown_separator", "| --- | --- |" in md, md)
    check("table.markdown_row", "| Hidden | ReLU |" in md, md)


# --- 3. Equation -------------------------------------------------------------

def test_equation_block() -> None:
    raw = r'<div data-label="Equation" data-bbox="5 5 90 30">E = mc^2</div>'
    out = normalize_chandra_output(raw)
    eqs = _assets_of_type(out, "equation_block")
    check("equation.asset_present", len(eqs) == 1)
    check("equation.text_preserved", "E = mc^2" in out["source_text"], out["source_text"])
    check("equation.label", eqs and eqs[0]["signals"]["chandra_label"] == "Equation")


# --- 4. Diagram + caption ----------------------------------------------------

def test_diagram_with_caption() -> None:
    raw = (
        '<figure data-label="Diagram" data-bbox="50 120 500 430">'
        "<figcaption>Backpropagation flow through an MLP.</figcaption>"
        "</figure>"
    )
    out = normalize_chandra_output(raw, source_page=1)
    diagrams = _assets_of_type(out, "diagram")
    check("diagram.asset_present", len(diagrams) == 1)
    a = diagrams[0] if diagrams else {}
    check("diagram.bbox", a.get("bbox") == [50.0, 120.0, 500.0, 430.0])
    check("diagram.caption", a.get("caption") == "Backpropagation flow through an MLP.")
    check("diagram.provider", a.get("source_provider") == "chandra_local")
    check("diagram.action_unknown", a.get("recommended_action") == RECOMMENDED_ACTION_UNKNOWN == "unknown")
    check("diagram.asset_ref_null", a.get("asset_ref") is None, "no file is written this slice")
    check("diagram.dedupe_null", a.get("dedupe_group") is None)
    check("diagram.scores_empty", a.get("scores") == {})
    check("diagram.id_shape", a.get("asset_id") == "page_0001_chandra_01", a.get("asset_id"))
    check("diagram.caption_in_text", "Backpropagation flow through an MLP." in out["source_text"])


# --- 5. Invalid / missing bbox ------------------------------------------------

def test_bbox_invalid_and_missing() -> None:
    raw_invalid = '<figure data-label="Figure" data-bbox="not a box">x</figure>'
    out = normalize_chandra_output(raw_invalid)
    figs = _assets_of_type(out, "figure")
    check("bbox.invalid_to_null", figs and figs[0]["bbox"] is None)
    check("bbox.invalid_warning", figs and "bbox_invalid" in figs[0]["warnings"])
    check("bbox.invalid_top_warning", "bbox_invalid" in out["warnings"])

    raw_bad_order = '<figure data-label="Figure" data-bbox="500 500 10 10">x</figure>'
    out2 = normalize_chandra_output(raw_bad_order)
    figs2 = _assets_of_type(out2, "figure")
    check("bbox.illordered_to_null", figs2 and figs2[0]["bbox"] is None)
    check("bbox.illordered_warning", figs2 and "bbox_invalid" in figs2[0]["warnings"])

    raw_missing = '<figure data-label="Diagram">no box here</figure>'
    out3 = normalize_chandra_output(raw_missing)
    digs = _assets_of_type(out3, "diagram")
    check("bbox.missing_to_null", digs and digs[0]["bbox"] is None)
    check("bbox.missing_warning", digs and "bbox_missing" in digs[0]["warnings"])
    # The raw invalid bbox string must never be echoed anywhere.
    check("bbox.no_raw_echo", "not a box" not in json.dumps(out))


# --- 6. Unrecognized label ----------------------------------------------------

def test_unrecognized_label() -> None:
    raw = '<div data-label="Sparkle9000" data-bbox="1 1 9 9">mystery</div>'
    out = normalize_chandra_output(raw)
    unknown = _assets_of_type(out, "unknown_region")
    check("label.unknown_region", len(unknown) == 1)
    check("label.unknown_warning", unknown and "label_unrecognized" in unknown[0]["warnings"])
    check("label.display_unknown", unknown and unknown[0]["signals"]["chandra_label"] == "Unknown")
    check("label.raw_not_echoed", "Sparkle9000" not in json.dumps(out), "raw label must not survive")


# --- 7. Plain text / markdown fallback ---------------------------------------

def test_plain_text_fallback() -> None:
    raw = "# Title\n\nJust some plain markdown text with no layout tags.\n"
    out = normalize_chandra_output(raw)
    check("fallback.text_present", "plain markdown text" in out["source_text"])
    check("fallback.no_assets", out["assets"] == [], "plain text yields no visual assets")
    check("fallback.json_safe", _is_json_safe(out))


# --- 8. Never raises on malformed -------------------------------------------

def test_never_raises_on_malformed() -> None:
    bad_inputs = [
        "",
        "   ",
        "<div data-label=",
        "<<<>>><figure data-bbox=",
        "<table><tr><td>unclosed",
        '<div data-label="Diagram" data-bbox="1 2 3">missing one coord</div>',
        "\x00\x01\x02 garbage \x7f",
        "<figure data-label='Diagram' data-bbox='a b c d'>no numbers</figure>",
    ]
    ok = True
    for bad in bad_inputs:
        try:
            out = normalize_chandra_output(bad)
            ok = ok and out["status"] == "completed" and _is_json_safe(out)
        except Exception as exc:  # noqa: BLE001
            ok = False
            check("malformed.input", False, f"raised on {bad!r}: {exc}")
            break
    check("malformed.never_raises", ok)

    # Non-string inputs must also be tolerated.
    ok2 = True
    for weird in (None, 123, [], {}, object()):
        try:
            out = normalize_chandra_output(weird)  # type: ignore[arg-type]
            ok2 = ok2 and out["kind"] == OUTPUT_KIND and _is_json_safe(out)
        except Exception:  # noqa: BLE001
            ok2 = False
            break
    check("malformed.nonstring_tolerated", ok2)


# --- 9. Smuggled-secret / injection hygiene ----------------------------------

def test_smuggled_content_does_not_leak() -> None:
    raw = (
        '<div data-label="Text" data-bbox="0 0 10 10">'
        "Visit https://evil.example.com/leak now. "
        "Path /home/victim/secret.pdf and /etc/passwd and C:\\Users\\me\\key.txt. "
        "Authorization: Bearer sk-ABCDEF0123456789ABCDEF. "
        "api key sk_live_0123456789ABCDEFGHIJ . "
        "socket /run/companion/host.sock here. "
        "flags --image-min-tokens 1024 --model /opt/models/x.gguf . "
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg== ."
        "</div>"
        '<script>alert("xss")</script>'
        '<style>body{display:none}</style>'
    )
    out = normalize_chandra_output(raw, source_page=7)
    blob = json.dumps(out)
    check("leak.no_url", not URLLIKE.search(blob), blob)
    check("leak.no_path", not PATHLIKE.search(blob), blob)
    check("leak.no_auth", not AUTHLIKE.search(blob), blob)
    check("leak.no_socket", not SOCKETLIKE.search(blob), blob)
    check("leak.no_argv", not ARGVLIKE.search(blob), blob)
    check("leak.no_keylike", not KEYLIKE.search(blob), blob)
    check("leak.no_base64uri", not BASE64URI.search(blob), blob)
    check("leak.no_script_tag", not SCRIPTLIKE.search(blob), blob)
    check("leak.no_xss_text", "alert(" not in blob and "display:none" not in blob, blob)
    check("leak.no_gguf", ".gguf" not in blob, blob)
    check("leak.json_safe", _is_json_safe(out))
    # Some legitimate words should still survive scrubbing (deterministic).
    check("leak.keeps_prose", "Visit" in out["source_text"] and "now" in out["source_text"])


# --- 10. Multiple regions / ordering & ids -----------------------------------

def test_multiple_regions_ids() -> None:
    raw = (
        '<div data-label="Text" data-bbox="0 0 5 5">intro</div>'
        '<figure data-label="Diagram" data-bbox="0 10 5 20">d</figure>'
        '<table data-label="Table" data-bbox="0 30 5 40"><tr><td>a</td></tr></table>'
        '<div data-label="Image" data-bbox="0 50 5 60">img</div>'
    )
    out = normalize_chandra_output(raw, source_page=12)
    ids = [a["asset_id"] for a in out["assets"]]
    check("multi.three_assets", len(out["assets"]) == 3, str(ids))
    check("multi.id_sequence", ids == ["page_0012_chandra_01", "page_0012_chandra_02", "page_0012_chandra_03"], str(ids))
    types = [a["asset_type"] for a in out["assets"]]
    check("multi.types", types == ["diagram", "table", "image_region"], str(types))


# --- 11. Helper functions are independently usable ----------------------------

def test_helpers() -> None:
    blocks = extract_chandra_blocks('<div data-label="Text">hi</div>')
    check("helper.extract_list", isinstance(blocks, list) and len(blocks) == 1)
    check("helper.block_keys", blocks and set(blocks[0]) == {"block_type", "chandra_label", "bbox", "text", "caption", "warnings"})
    text = chandra_blocks_to_source_text(blocks)
    check("helper.source_text", text == "hi", text)
    assets = chandra_blocks_to_manifest_assets(blocks, source_page=1)
    check("helper.no_text_asset", assets == [])
    # Bad inputs to helpers are tolerated.
    check("helper.bad_blocks_text", chandra_blocks_to_source_text("nope") == "")
    check("helper.bad_blocks_assets", chandra_blocks_to_manifest_assets(None) == [])


# --- 12. No forbidden imports -------------------------------------------------

def test_no_forbidden_imports() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "pipeline", "chandra_normalizer.py")
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    # Only inspect real import statements (the module docstring legitimately names
    # these libraries to assert it does NOT import them).
    import_lines = [
        ln.strip().lower()
        for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    forbidden = ["fitz", "pymupdf", "pytesseract", "tesseract", "llama_cpp",
                 "llama-cpp", "mistral", "google.generativeai", "genai", "gemini",
                 "chandra", "local_model", "companion", "requests", "httpx", "urllib"]
    leaks = sorted({tok for ln in import_lines for tok in forbidden if tok in ln})
    check("imports.none_forbidden", not leaks, f"found in imports: {leaks}")
    check("imports.stdlib_only", "from html.parser import HTMLParser" in src)
    allowed_prefixes = ("import re", "import os", "from __future__",
                        "from html.parser import", "from typing import")
    unexpected = [ln for ln in import_lines if not ln.startswith(allowed_prefixes)]
    check("imports.only_expected_stdlib", not unexpected, f"unexpected: {unexpected}")


def main() -> int:
    test_envelope_and_determinism()
    test_table_block()
    test_equation_block()
    test_diagram_with_caption()
    test_bbox_invalid_and_missing()
    test_unrecognized_label()
    test_plain_text_fallback()
    test_never_raises_on_malformed()
    test_smuggled_content_does_not_leak()
    test_multiple_regions_ids()
    test_helpers()
    test_no_forbidden_imports()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
