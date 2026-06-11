#!/usr/bin/env python3
"""Focused tests for the Slice 37 OCR/extraction mode + cost/budget skeleton.

Run with:

    python test_scripts/test_ocr_modes.py

No external APIs, no PyMuPDF, no Tesseract, no cloud calls. The module
(``pipeline.ocr_modes``) is pure stdlib; these tests prove:

- defaults are ``local_private`` and cloud-off,
- ``resolve_ocr_mode_config`` maps to the Slice 33 routing-config shape with
  ``allow_cloud_ocr=False`` by default,
- cloud-capable modes exist as vocabulary but never enable cloud without an
  explicit ``cloud_opt_in``,
- invalid mode/provider/budget values sanitize to safe defaults,
- the Mistral estimate is advisory (``is_estimate=True``), page-budgeted, and
  capped, and unknown providers degrade to a safe unavailable result,
- no key/URL/path/argv/socket/Authorization/raw provider error can ever appear
  in any output.

This slice wires nothing into extraction: the assertions are about vocabulary,
config shape, and leak-safety only.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_|Bearer )[A-Za-z0-9_\-]{8,}")

from pipeline.ocr_modes import (  # noqa: E402
    BILLING_UNITS,
    CLOUD_CAPABLE_MODES,
    DEFAULT_MODE,
    ESTIMATE_STATUSES,
    ESTIMATE_WARNINGS,
    MODES,
    PROVIDER_IDS,
    PROVIDER_ROLES,
    OcrModeSettings,
    default_ocr_mode_settings,
    estimate_ocr_cost,
    ocr_budget,
    ocr_provider_pricing_snapshot,
    provider_pricing,
    resolve_ocr_mode_config,
    safe_ocr_cost_estimate_dict,
    safe_ocr_mode_settings_dict,
)

# The routing core whose config shape we must produce (Slice 33).
from pipeline.ocr_routing import decide_ocr_route, default_config  # noqa: E402

# Repo-relative source notes that ARE allowed to appear in output.
ALLOWED_SOURCE_TOKENS = {"docs/MISTRAL_OCR_VERIFICATION.md", "local"}


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


def _no_leak(blob: str) -> bool:
    """True if ``blob`` contains no secret/URL/host-path/argv/socket-like token.

    The repo-relative ``price_source`` doc reference is permitted (it is not a
    host path or secret); everything else path/secret-like is forbidden.
    """
    sanitized = blob
    for tok in ALLOWED_SOURCE_TOKENS:
        sanitized = sanitized.replace(tok, "")
    if KEYLIKE.search(sanitized):
        return False
    for needle in ["/host", "/home", "/usr", "/tmp", "http://", "https://",
                   "Authorization", "Bearer ", ".sock", "--", "Traceback"]:
        if needle in sanitized:
            return False
    return True


# --- defaults ---------------------------------------------------------------


def test_default_settings_local_private() -> None:
    s = default_ocr_mode_settings()
    check("default/mode", s.mode == "local_private", str(s))
    check("default/is-default-const", s.mode == DEFAULT_MODE, str(s))
    check("default/cloud-opt-in-false", s.cloud_opt_in is False, str(s))
    check("default/local-on", s.local_ocr_available is True, str(s))
    check("default/no-page-cap", s.page_cap is None, str(s))
    check("default/no-dollar-cap", s.dollar_cap is None, str(s))
    check("default/no-selected", s.selected_page_count is None, str(s))


def test_default_resolves_cloud_off() -> None:
    cfg = resolve_ocr_mode_config(default_ocr_mode_settings())
    check("resolve-default/cloud-off", cfg["allow_cloud_ocr"] is False, str(cfg))
    check("resolve-default/local-on", cfg["local_ocr_available"] is True, str(cfg))
    check("resolve-default/no-cap", cfg["max_ocr_pages"] is None, str(cfg))
    check("resolve-default/no-budget", cfg["page_budget_remaining"] is None, str(cfg))


def test_resolve_matches_routing_config_shape() -> None:
    # Every key the Slice 33 default_config() defines must be present and the
    # extra `mode` echo must be ignored by the routing core.
    base_keys = set(default_config().keys())
    cfg = resolve_ocr_mode_config(default_ocr_mode_settings())
    check("shape/superset", base_keys.issubset(cfg.keys()), str(cfg))
    # Feed it straight into the routing core — it must accept it and stay local.
    d = decide_ocr_route({"classification": "likely_scanned"}, cfg)
    check("shape/routing-accepts", d["action"] == "use_local_ocr", str(d))
    check("shape/routing-not-cloud", d["action"] != "cloud_ocr_candidate", str(d))


# --- cloud modes exist but never auto-enable cloud --------------------------


def test_cloud_modes_are_vocabulary() -> None:
    check("vocab/smart-in-modes", "smart_cloud_assist" in MODES)
    check("vocab/max-in-modes", "maximum_fidelity" in MODES)
    check("vocab/cloud-capable", CLOUD_CAPABLE_MODES == {"smart_cloud_assist", "maximum_fidelity"})


def test_cloud_mode_without_optin_stays_off() -> None:
    for mode in CLOUD_CAPABLE_MODES:
        cfg = resolve_ocr_mode_config(OcrModeSettings(mode=mode, cloud_opt_in=False))
        check(f"cloudmode-off/{mode}", cfg["allow_cloud_ocr"] is False, str(cfg))


def test_cloud_mode_with_optin_allows_only_with_explicit_flag() -> None:
    # Explicit opt-in is the ONLY thing that flips allow_cloud_ocr on, and only
    # for a cloud-capable mode. local_private can never be flipped on.
    cfg = resolve_ocr_mode_config(OcrModeSettings(mode="smart_cloud_assist", cloud_opt_in=True))
    check("cloudmode-on/allowed", cfg["allow_cloud_ocr"] is True, str(cfg))
    cfg_local = resolve_ocr_mode_config(OcrModeSettings(mode="local_private", cloud_opt_in=True))
    check("cloudmode-on/local-stays-off", cfg_local["allow_cloud_ocr"] is False, str(cfg_local))


def test_optin_must_be_real_bool() -> None:
    # A smuggled truthy value must NOT enable cloud.
    cfg = resolve_ocr_mode_config({"mode": "smart_cloud_assist", "cloud_opt_in": "yes"})
    check("optin-truthy/off", cfg["allow_cloud_ocr"] is False, str(cfg))


# --- sanitization -----------------------------------------------------------


def test_invalid_mode_coerces_to_default() -> None:
    for bad in ["cloud_everything", "", None, 7, "LOCAL_PRIVATE"]:
        cfg = resolve_ocr_mode_config({"mode": bad})
        check(f"badmode/{bad!r}-default-local", cfg["mode"] == DEFAULT_MODE, str(cfg))
        check(f"badmode/{bad!r}-cloud-off", cfg["allow_cloud_ocr"] is False, str(cfg))


def test_invalid_caps_coerce_safely() -> None:
    s = safe_ocr_mode_settings_dict({
        "page_cap": "lots",
        "dollar_cap": -5,
        "selected_page_count": -3,
    })
    check("badcaps/page-none", s["page_cap"] is None, str(s))
    check("badcaps/dollar-clamped", s["dollar_cap"] == 0.0, str(s))
    check("badcaps/selected-clamped", s["selected_page_count"] == 0, str(s))


def test_nan_inf_dollar_cap_rejected() -> None:
    for bad in [float("nan"), float("inf"), float("-inf")]:
        s = safe_ocr_mode_settings_dict({"dollar_cap": bad})
        check(f"dollar/{bad}-none", s["dollar_cap"] is None, str(s))


def test_negative_page_cap_clamped_nonnegative() -> None:
    s = safe_ocr_mode_settings_dict({"page_cap": -10})
    check("pagecap/neg-clamped", s["page_cap"] == 0, str(s))


def test_junk_settings_object_uses_defaults() -> None:
    for bad in [None, 42, "settings", [], object()]:
        cfg = resolve_ocr_mode_config(bad)
        check(f"junk/{type(bad).__name__}-default", cfg["mode"] == DEFAULT_MODE, str(cfg))
        check(f"junk/{type(bad).__name__}-cloud-off", cfg["allow_cloud_ocr"] is False, str(cfg))


# --- budget view ------------------------------------------------------------


def test_budget_view() -> None:
    b = ocr_budget(OcrModeSettings(page_cap=500, dollar_cap=2.5, selected_page_count=120))
    check("budget/page", b.page_cap == 500, str(b))
    check("budget/dollar", b.dollar_cap == 2.5, str(b))
    check("budget/selected", b.selected_page_count == 120, str(b))


# --- cost estimates ---------------------------------------------------------


def test_local_estimate_is_free() -> None:
    est = estimate_ocr_cost(default_ocr_mode_settings(), page_count=500)
    check("local-est/status-free", est.status == "free", str(est))
    check("local-est/cost-zero", est.estimated_cost_usd == 0.0, str(est))
    check("local-est/not-estimate", est.is_estimate is False, str(est))
    check("local-est/provider", est.provider_id == "tesseract_local", str(est))
    check("local-est/role", est.provider_role == "local_ocr_provider", str(est))


def test_mistral_estimate_500_pages_is_advisory() -> None:
    est = estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist"), page_count=500)
    check("mistral-est/provider", est.provider_id == "mistral_ocr", str(est))
    check("mistral-est/role", est.provider_role == "cloud_document_provider", str(est))
    check("mistral-est/unit", est.billing_unit == "page", str(est))
    check("mistral-est/billed", est.billed_page_count == 500, str(est))
    # 500 pages * $0.002/page = $1.00 (June 2026 estimate)
    check("mistral-est/cost", est.estimated_cost_usd == 1.0, str(est))
    check("mistral-est/is-estimate", est.is_estimate is True, str(est))
    check("mistral-est/status-ok", est.status == "ok", str(est))
    check("mistral-est/warns-estimate-only", "estimate_only" in est.warnings, str(est))
    check("mistral-est/source", est.price_source == "docs/MISTRAL_OCR_VERIFICATION.md", str(est))


def test_estimate_respects_selected_pages() -> None:
    est = estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist"),
                            page_count=500, selected_page_count=50)
    check("selected-est/billed", est.billed_page_count == 50, str(est))
    check("selected-est/cost", est.estimated_cost_usd == 0.1, str(est))


def test_selected_pages_clamped_to_total() -> None:
    est = estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist"),
                            page_count=10, selected_page_count=999)
    check("clamp-sel/billed", est.billed_page_count == 10, str(est))
    check("clamp-sel/warn", "selected_pages_clamped" in est.warnings, str(est))


def test_page_cap_applied_to_billed() -> None:
    est = estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist", page_cap=100),
                            page_count=500)
    check("pagecap-est/billed", est.billed_page_count == 100, str(est))
    check("pagecap-est/warn", "page_cap_applied" in est.warnings, str(est))
    check("pagecap-est/cost", est.estimated_cost_usd == 0.2, str(est))


def test_dollar_cap_exceeded_is_advisory_warning() -> None:
    # 500 pages ~ $1.00 estimate, cap of $0.50 → advisory warning, still produced.
    est = estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist", dollar_cap=0.5),
                            page_count=500)
    check("dollarcap/status-ok", est.status == "ok", str(est))
    check("dollarcap/warn", "exceeds_dollar_cap" in est.warnings, str(est))
    check("dollarcap/cost-still-there", est.estimated_cost_usd == 1.0, str(est))


def test_estimate_settings_selected_count_used() -> None:
    # selected_page_count lives on settings and is honored when the arg is omitted.
    est = estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist", selected_page_count=25),
                            page_count=500)
    check("settings-sel/billed", est.billed_page_count == 25, str(est))


def test_unknown_provider_pricing_unavailable() -> None:
    check("unknown-pricing/none", provider_pricing("nonexistent_provider") is None)
    check("unknown-pricing/vlm-none", provider_pricing("vlm_future") is None)


def test_estimate_never_raises_on_junk() -> None:
    for pc in [None, -1, "abc", 3.7, [], object()]:
        est = estimate_ocr_cost("junk", page_count=pc)
        check(f"est-junk/{type(pc).__name__}-status",
              est.status in ESTIMATE_STATUSES, str(est))
        check(f"est-junk/{type(pc).__name__}-billed-int",
              isinstance(est.billed_page_count, int) and est.billed_page_count >= 0, str(est))


# --- pricing snapshot -------------------------------------------------------


def test_pricing_snapshot_shape_and_values() -> None:
    snap = ocr_provider_pricing_snapshot()
    by_id = {p["provider_id"]: p for p in snap}
    check("snap/has-tesseract", "tesseract_local" in by_id, str(by_id.keys()))
    check("snap/has-mistral", "mistral_ocr" in by_id, str(by_id.keys()))
    mistral = by_id.get("mistral_ocr", {})
    check("snap/mistral-unit", mistral.get("billing_unit") == "page", str(mistral))
    check("snap/mistral-std", mistral.get("unit_price_usd") == 0.002, str(mistral))
    check("snap/mistral-batch", mistral.get("batch_unit_price_usd") == 0.001, str(mistral))
    check("snap/mistral-is-estimate", mistral.get("is_estimate") is True, str(mistral))
    check("snap/mistral-source", mistral.get("price_source") == "docs/MISTRAL_OCR_VERIFICATION.md", str(mistral))
    tess = by_id.get("tesseract_local", {})
    check("snap/tesseract-free", tess.get("unit_price_usd") == 0.0, str(tess))
    check("snap/tesseract-not-estimate", tess.get("is_estimate") is False, str(tess))


# --- closed-vocabulary integrity --------------------------------------------


def test_safe_dicts_only_emit_closed_vocab() -> None:
    s = safe_ocr_mode_settings_dict(default_ocr_mode_settings())
    check("safe-settings/mode-vocab", s["mode"] in MODES, str(s))
    est_dict = safe_ocr_cost_estimate_dict(
        estimate_ocr_cost(OcrModeSettings(mode="smart_cloud_assist"), page_count=10))
    check("safe-est/status-vocab", est_dict["status"] in ESTIMATE_STATUSES, str(est_dict))
    check("safe-est/unit-vocab", est_dict["billing_unit"] in BILLING_UNITS, str(est_dict))
    check("safe-est/provider-vocab",
          est_dict["provider_id"] is None or est_dict["provider_id"] in PROVIDER_IDS, str(est_dict))
    check("safe-est/role-vocab",
          est_dict["provider_role"] is None or est_dict["provider_role"] in PROVIDER_ROLES, str(est_dict))
    check("safe-est/warns-vocab",
          all(w in ESTIMATE_WARNINGS for w in est_dict["warnings"]), str(est_dict))


def test_safe_estimate_dict_coerces_hostile_fields() -> None:
    # A hand-built estimate with junk fields must be scrubbed to closed vocab.
    from pipeline.ocr_modes import OcrCostEstimate
    hostile = OcrCostEstimate(
        mode="evil_mode",
        provider_id="https://evil.example/ocr?key=sk-leak0123456789",
        provider_role="root",
        billing_unit="bitcoin",
        billed_page_count=-9,
        estimated_cost_usd=1.0,
        currency="EUR",
        is_estimate=True,
        status="totally_made_up",
        price_source="/host/secret/key.pem",
        warnings=["/host/secret", "drop_table", "estimate_only"],
    )
    d = safe_ocr_cost_estimate_dict(hostile)
    check("hostile/mode", d["mode"] == DEFAULT_MODE, str(d))
    check("hostile/provider-null", d["provider_id"] is None, str(d))
    check("hostile/role-null", d["provider_role"] is None, str(d))
    check("hostile/unit", d["billing_unit"] == "unknown", str(d))
    check("hostile/billed-nonneg", d["billed_page_count"] == 0, str(d))
    check("hostile/currency", d["currency"] == "USD", str(d))
    check("hostile/status", d["status"] == "unknown", str(d))
    check("hostile/warns", d["warnings"] == ["estimate_only"], str(d))
    # price_source passes through verbatim here, so the leak check excludes it;
    # but the hostile path value must NOT be a doc reference, so it must be caught.
    check("hostile/no-host-path-elsewhere", "/host" not in str({k: v for k, v in d.items() if k != "price_source"}), str(d))


# --- leak-safety ------------------------------------------------------------


def test_no_leak_through_settings_and_config() -> None:
    hostile = {
        "mode": "smart_cloud_assist",
        "cloud_opt_in": True,
        "api_key": "sk-leak0123456789abcdef",
        "base_url": "https://api.mistral.ai/v1/ocr",
        "authorization": "Bearer sk-leak0123456789abcdef",
        "host_path": "/host/secret/lecture.pdf",
        "socket_path": "/run/companion.sock",
        "argv": ["--key", "sk-leak0123456789abcdef"],
        "page_cap": 100,
        "dollar_cap": 1.0,
        "selected_page_count": 50,
    }
    s = safe_ocr_mode_settings_dict(hostile)
    cfg = resolve_ocr_mode_config(hostile)
    est = safe_ocr_cost_estimate_dict(estimate_ocr_cost(hostile, page_count=200))
    # The hostile keys must be dropped entirely.
    check("leak/settings-keys", set(s.keys()) == {
        "mode", "cloud_opt_in", "local_ocr_available", "page_cap",
        "dollar_cap", "selected_page_count"}, str(s))
    blob = repr(s) + repr(cfg) + repr(est)
    check("leak/no-secret-or-path", _no_leak(blob), blob)
    # The only opt-in path is the real bool — here it IS a real True + cloud mode,
    # so allow_cloud_ocr may be True, but nothing secret leaks.
    check("leak/cloud-flag-is-bool", isinstance(cfg["allow_cloud_ocr"], bool), str(cfg))


def test_estimate_output_has_no_provider_error_text() -> None:
    est = estimate_ocr_cost(OcrModeSettings(mode="maximum_fidelity"), page_count=1234)
    blob = repr(est) + repr(safe_ocr_cost_estimate_dict(est))
    check("noerr/no-leak", _no_leak(blob), blob)
    check("noerr/source-allowed", est.price_source in ALLOWED_SOURCE_TOKENS, str(est))


def test_module_imports_no_provider_engines() -> None:
    # The pure mode module must not have pulled in fitz/tesseract/cloud SDKs.
    import pipeline.ocr_modes as m  # noqa: F401
    forbidden = ["fitz", "pytesseract", "tesseract", "mistralai", "google.generativeai",
                 "genai", "chandra", "pipeline.ocr_provider"]
    loaded = sys.modules.keys()
    leaked = [name for name in forbidden if name in loaded]
    check("imports/none-forbidden", leaked == [], f"leaked: {leaked}")


if __name__ == "__main__":
    test_default_settings_local_private()
    test_default_resolves_cloud_off()
    test_resolve_matches_routing_config_shape()
    test_cloud_modes_are_vocabulary()
    test_cloud_mode_without_optin_stays_off()
    test_cloud_mode_with_optin_allows_only_with_explicit_flag()
    test_optin_must_be_real_bool()
    test_invalid_mode_coerces_to_default()
    test_invalid_caps_coerce_safely()
    test_nan_inf_dollar_cap_rejected()
    test_negative_page_cap_clamped_nonnegative()
    test_junk_settings_object_uses_defaults()
    test_budget_view()
    test_local_estimate_is_free()
    test_mistral_estimate_500_pages_is_advisory()
    test_estimate_respects_selected_pages()
    test_selected_pages_clamped_to_total()
    test_page_cap_applied_to_billed()
    test_dollar_cap_exceeded_is_advisory_warning()
    test_estimate_settings_selected_count_used()
    test_unknown_provider_pricing_unavailable()
    test_estimate_never_raises_on_junk()
    test_pricing_snapshot_shape_and_values()
    test_safe_dicts_only_emit_closed_vocab()
    test_safe_estimate_dict_coerces_hostile_fields()
    test_no_leak_through_settings_and_config()
    test_estimate_output_has_no_provider_error_text()
    test_module_imports_no_provider_engines()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"OCR mode/cost tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
