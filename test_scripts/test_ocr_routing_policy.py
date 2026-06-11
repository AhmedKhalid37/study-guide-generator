#!/usr/bin/env python3
"""Focused tests for the Slice 33 pure OCR routing-policy core.

Run with:

    python test_scripts/test_ocr_routing_policy.py

No external APIs, no PyMuPDF, no Tesseract, no cloud calls. The policy
(`decide_ocr_route` / `decide_ocr_routes`) is exercised directly with plain
dicts so every action branch, the local-first / cloud-off defaults, budget
handling, determinism, and leak-safety can be proven deterministically.

The policy is advisory and **not wired into extraction** in this slice: these
tests assert decision shape/values and that no smuggled path, secret, image
blob, or free text from the input can survive into a decision.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")

from pipeline.ocr_routing import (  # noqa: E402
    ACTIONS,
    CONFIDENCES,
    LOCAL_OCR_PROVIDER_ID,
    REASONS,
    WARNINGS,
    decide_ocr_route,
    decide_ocr_routes,
    default_config,
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


def _page(classification: str) -> dict:
    return {"classification": classification}


def _valid_shape(d: dict) -> bool:
    return (
        isinstance(d, dict)
        and d.get("action") in ACTIONS
        and (d.get("provider") is None or d.get("provider") == LOCAL_OCR_PROVIDER_ID)
        and d.get("reason") in REASONS
        and d.get("confidence") in CONFIDENCES
        and isinstance(d.get("warnings"), list)
        and all(w in WARNINGS for w in d.get("warnings", []))
    )


# --- per-classification routing (default local-first config) ----------------


def test_embedded_text_uses_text() -> None:
    d = decide_ocr_route(_page("embedded_text"))
    check("embedded/shape", _valid_shape(d), str(d))
    check("embedded/action", d["action"] == "use_embedded_text", str(d))
    check("embedded/reason", d["reason"] == "embedded_text_sufficient", str(d))
    check("embedded/provider-null", d["provider"] is None, str(d))
    check("embedded/no-warnings", d["warnings"] == [], str(d))


def test_mixed_uses_text() -> None:
    d = decide_ocr_route(_page("mixed"))
    check("mixed/action", d["action"] == "use_embedded_text", str(d))
    check("mixed/reason", d["reason"] == "mixed_has_meaningful_text", str(d))
    check("mixed/confidence", d["confidence"] == "medium", str(d))


def test_ocr_fallback_uses_text() -> None:
    # ocr_fallback = OCR already ran and its text is what extraction captured;
    # the policy must NOT recommend re-OCRing it.
    d = decide_ocr_route(_page("ocr_fallback"))
    check("ocr_fallback/action", d["action"] == "use_embedded_text", str(d))
    check("ocr_fallback/reason", d["reason"] == "ocr_already_applied", str(d))


def test_likely_scanned_uses_local_ocr() -> None:
    d = decide_ocr_route(_page("likely_scanned"))
    check("scanned/action", d["action"] == "use_local_ocr", str(d))
    check("scanned/provider", d["provider"] == LOCAL_OCR_PROVIDER_ID, str(d))
    check("scanned/reason", d["reason"] == "scanned_needs_ocr", str(d))


def test_blank_skips_ocr() -> None:
    d = decide_ocr_route(_page("blank_or_low_text"))
    check("blank/action", d["action"] == "skip_ocr", str(d))
    check("blank/reason", d["reason"] == "blank_low_text_no_visual", str(d))
    check("blank/no-warnings", d["warnings"] == [], str(d))


def test_error_skips_ocr() -> None:
    d = decide_ocr_route(_page("error"))
    check("error/action", d["action"] == "skip_ocr", str(d))
    check("error/reason", d["reason"] == "classification_error", str(d))


def test_unknown_classification_is_unknown() -> None:
    d = decide_ocr_route(_page("unknown"))
    check("unknown/action", d["action"] == "unknown", str(d))
    check("unknown/reason", d["reason"] == "unknown_classification", str(d))
    # Conservative: unknown must NEVER route to cloud or spend budget.
    check("unknown/not-cloud", d["action"] != "cloud_ocr_candidate", str(d))


def test_unrecognized_classification_coerces_unknown() -> None:
    d = decide_ocr_route(_page("totally_made_up"))
    check("coerce/action", d["action"] == "unknown", str(d))
    check("coerce/reason", d["reason"] == "unknown_classification", str(d))


# --- local availability / cloud gating --------------------------------------


def test_local_unavailable_cloud_off_skips() -> None:
    cfg = {"local_ocr_available": False, "allow_cloud_ocr": False}
    d = decide_ocr_route(_page("likely_scanned"), cfg)
    check("local-off/action", d["action"] == "skip_ocr", str(d))
    check("local-off/reason", d["reason"] == "local_ocr_unavailable", str(d))
    check("local-off/warns-local", "local_ocr_unavailable" in d["warnings"], str(d))
    check("local-off/warns-cloud-disabled", "cloud_ocr_disabled" in d["warnings"], str(d))
    check("local-off/no-cloud-action", d["action"] != "cloud_ocr_candidate", str(d))


def test_cloud_disabled_by_default_no_candidate() -> None:
    # Default config: even with local available, cloud is never volunteered.
    for c in ["likely_scanned", "blank_or_low_text", "mixed", "embedded_text", "unknown"]:
        d = decide_ocr_route(_page(c))
        check(f"cloud-default/{c}", d["action"] != "cloud_ocr_candidate", str(d))


def test_cloud_candidate_only_when_allowed_and_local_unavailable() -> None:
    cfg = {"local_ocr_available": False, "allow_cloud_ocr": True}
    d = decide_ocr_route(_page("likely_scanned"), cfg)
    check("cloud/action", d["action"] == "cloud_ocr_candidate", str(d))
    check("cloud/reason", d["reason"] == "cloud_candidate_local_unavailable", str(d))
    # Advisory only — no provider id (no cloud provider is implemented/configured).
    check("cloud/provider-null", d["provider"] is None, str(d))
    check("cloud/warns-local", "local_ocr_unavailable" in d["warnings"], str(d))


def test_cloud_allowed_but_local_available_prefers_local() -> None:
    # Cost/privacy rule: local OCR before cloud whenever local can serve the page.
    cfg = {"local_ocr_available": True, "allow_cloud_ocr": True}
    d = decide_ocr_route(_page("likely_scanned"), cfg)
    check("cloud-but-local/action", d["action"] == "use_local_ocr", str(d))
    check("cloud-but-local/provider", d["provider"] == LOCAL_OCR_PROVIDER_ID, str(d))


def test_smuggled_truthy_cloud_flag_does_not_enable_cloud() -> None:
    # A non-boolean "truthy" value must NOT flip cloud OCR on.
    cfg = {"local_ocr_available": False, "allow_cloud_ocr": "yes-please"}
    d = decide_ocr_route(_page("likely_scanned"), cfg)
    check("smuggle-flag/no-cloud", d["action"] != "cloud_ocr_candidate", str(d))
    check("smuggle-flag/skips", d["action"] == "skip_ocr", str(d))


# --- budget handling --------------------------------------------------------


def test_budget_exhausted_single_skips() -> None:
    cfg = {"local_ocr_available": True, "page_budget_remaining": 0}
    d = decide_ocr_route(_page("likely_scanned"), cfg)
    check("budget0/action", d["action"] == "skip_ocr", str(d))
    check("budget0/reason", d["reason"] == "ocr_budget_exhausted", str(d))
    check("budget0/warn", "ocr_budget_exhausted" in d["warnings"], str(d))


def test_budget_available_single_ocrs() -> None:
    cfg = {"local_ocr_available": True, "page_budget_remaining": 1}
    d = decide_ocr_route(_page("likely_scanned"), cfg)
    check("budget1/action", d["action"] == "use_local_ocr", str(d))


def test_budget_does_not_block_non_ocr_pages() -> None:
    # Exhausted budget must not change embedded-text / blank decisions.
    cfg = {"page_budget_remaining": 0}
    check("budget/embedded", decide_ocr_route(_page("embedded_text"), cfg)["action"] == "use_embedded_text")
    check("budget/blank", decide_ocr_route(_page("blank_or_low_text"), cfg)["action"] == "skip_ocr")


def test_multipage_budget_consumed_in_order() -> None:
    # 4 scanned pages, budget 2 → first two OCR, rest skip with budget reason.
    cfg = {"local_ocr_available": True, "page_budget_remaining": 2}
    pages = [_page("likely_scanned") for _ in range(4)]
    routes = decide_ocr_routes(pages, cfg)
    check("multi/len", len(routes) == 4, str(routes))
    check("multi/p0", routes[0]["action"] == "use_local_ocr", str(routes[0]))
    check("multi/p1", routes[1]["action"] == "use_local_ocr", str(routes[1]))
    check("multi/p2-skip", routes[2]["action"] == "skip_ocr", str(routes[2]))
    check("multi/p2-reason", routes[2]["reason"] == "ocr_budget_exhausted", str(routes[2]))
    check("multi/p3-skip", routes[3]["action"] == "skip_ocr", str(routes[3]))


def test_multipage_non_ocr_pages_dont_consume_budget() -> None:
    # Interleave embedded-text pages; they must not eat the OCR budget.
    cfg = {"local_ocr_available": True, "page_budget_remaining": 2}
    pages = [
        _page("embedded_text"),   # no consume
        _page("likely_scanned"),  # consume -> 1
        _page("mixed"),           # no consume
        _page("likely_scanned"),  # consume -> 0
        _page("likely_scanned"),  # budget gone -> skip
    ]
    routes = decide_ocr_routes(pages, cfg)
    check("multi-mix/p1-ocr", routes[1]["action"] == "use_local_ocr", str(routes[1]))
    check("multi-mix/p3-ocr", routes[3]["action"] == "use_local_ocr", str(routes[3]))
    check("multi-mix/p4-skip", routes[4]["action"] == "skip_ocr", str(routes[4]))
    check("multi-mix/p4-reason", routes[4]["reason"] == "ocr_budget_exhausted", str(routes[4]))


def test_multipage_uncapped_budget_ocrs_all() -> None:
    cfg = {"local_ocr_available": True}  # no budget -> uncapped
    routes = decide_ocr_routes([_page("likely_scanned") for _ in range(5)], cfg)
    check("uncapped/all-ocr", all(r["action"] == "use_local_ocr" for r in routes), str(routes))


def test_max_ocr_pages_acts_as_budget() -> None:
    cfg = {"local_ocr_available": True, "max_ocr_pages": 1}
    routes = decide_ocr_routes([_page("likely_scanned"), _page("likely_scanned")], cfg)
    check("maxpages/p0-ocr", routes[0]["action"] == "use_local_ocr", str(routes[0]))
    check("maxpages/p1-skip", routes[1]["action"] == "skip_ocr", str(routes[1]))


# --- determinism ------------------------------------------------------------


def test_deterministic_repeat() -> None:
    cfg = {"local_ocr_available": True, "page_budget_remaining": 3}
    pages = [_page(c) for c in
             ["embedded_text", "likely_scanned", "mixed", "likely_scanned",
              "blank_or_low_text", "likely_scanned", "likely_scanned"]]
    first = decide_ocr_routes(pages, cfg)
    for _ in range(5):
        again = decide_ocr_routes(pages, cfg)
        check("determinism/identical", again == first, str(again))


# --- degrade-not-fail / leak-safety -----------------------------------------


def test_malformed_input_degrades_safely() -> None:
    for bad in [None, 42, "string", [], object(), {"classification": object()}]:
        d = decide_ocr_route(bad)
        check(f"degrade/shape::{type(bad).__name__}", _valid_shape(d), str(d))
        # Non-dicts and bad classifications must never route to OCR work.
        check(
            f"degrade/no-ocr::{type(bad).__name__}",
            d["action"] in {"unknown", "skip_ocr"},
            str(d),
        )


def test_malformed_config_degrades_safely() -> None:
    for badcfg in [None, 42, "x", [], {"max_ocr_pages": "lots"},
                   {"page_budget_remaining": -5}, {"allow_cloud_ocr": None}]:
        d = decide_ocr_route(_page("likely_scanned"), badcfg)
        check(f"badcfg/shape::{badcfg}", _valid_shape(d), str(d))
        check(f"badcfg/not-cloud::{badcfg}", d["action"] != "cloud_ocr_candidate", str(d))


def test_smuggled_secrets_and_paths_never_leak() -> None:
    # A hostile page record tries to smuggle a fake action, a host path, an image
    # blob, and a secret. The decision must contain only fixed tokens.
    raw = {
        "classification": "embedded_text",
        "action": "cloud_ocr_candidate",
        "provider": "https://evil.example/ocr?key=sk-leak0123456789abcdef",
        "reason": "/host/secret/lecture.pdf",
        "host_path": "/host/secret/lecture.pdf",
        "image_data": "BASE64DEADBEEF",
        "authorization": "Bearer sk-leak0123456789abcdef",
        "warnings": ["/host/secret", "BASE64DEADBEEF"],
    }
    d = decide_ocr_route(raw)
    check("leak/recomputed-action", d["action"] == "use_embedded_text", str(d))
    check("leak/provider-null", d["provider"] is None, str(d))
    check("leak/reason-vocab", d["reason"] in REASONS, str(d))
    check("leak/warnings-vocab", all(w in WARNINGS for w in d["warnings"]), str(d))
    check("leak/no-secret", KEYLIKE.search(repr(d)) is None, str(d))
    check("leak/no-host-path", "/host" not in repr(d), str(d))
    check("leak/no-image-blob", "BASE64DEADBEEF" not in repr(d), str(d))
    check("leak/no-url", "evil.example" not in repr(d), str(d))


def test_routes_non_list_is_empty() -> None:
    for bad in [None, 42, {"classification": "embedded_text"}, "pages"]:
        check(f"routes-nonlist/{type(bad).__name__}", decide_ocr_routes(bad) == [])


def test_routes_with_malformed_page_in_batch() -> None:
    # A bad page in the middle must not abort the batch or leak.
    pages = [_page("embedded_text"), object(), _page("likely_scanned")]
    routes = decide_ocr_routes(pages, {"local_ocr_available": True})
    check("batch-bad/len", len(routes) == 3, str(routes))
    check("batch-bad/p0", routes[0]["action"] == "use_embedded_text", str(routes[0]))
    check("batch-bad/p1-shape", _valid_shape(routes[1]), str(routes[1]))
    check("batch-bad/p2", routes[2]["action"] == "use_local_ocr", str(routes[2]))


def test_default_config_is_local_first_cloud_off() -> None:
    cfg = default_config()
    check("defaults/cloud-off", cfg["allow_cloud_ocr"] is False, str(cfg))
    check("defaults/local-on", cfg["local_ocr_available"] is True, str(cfg))
    check("defaults/no-cap", cfg["max_ocr_pages"] is None, str(cfg))
    check("defaults/no-budget", cfg["page_budget_remaining"] is None, str(cfg))


def test_every_classification_yields_valid_shape() -> None:
    for c in ["embedded_text", "ocr_fallback", "likely_scanned", "blank_or_low_text",
              "mixed", "unknown", "error", "weird", ""]:
        d = decide_ocr_route(_page(c))
        check(f"shape-all/{c or 'empty'}", _valid_shape(d), str(d))


if __name__ == "__main__":
    test_embedded_text_uses_text()
    test_mixed_uses_text()
    test_ocr_fallback_uses_text()
    test_likely_scanned_uses_local_ocr()
    test_blank_skips_ocr()
    test_error_skips_ocr()
    test_unknown_classification_is_unknown()
    test_unrecognized_classification_coerces_unknown()
    test_local_unavailable_cloud_off_skips()
    test_cloud_disabled_by_default_no_candidate()
    test_cloud_candidate_only_when_allowed_and_local_unavailable()
    test_cloud_allowed_but_local_available_prefers_local()
    test_smuggled_truthy_cloud_flag_does_not_enable_cloud()
    test_budget_exhausted_single_skips()
    test_budget_available_single_ocrs()
    test_budget_does_not_block_non_ocr_pages()
    test_multipage_budget_consumed_in_order()
    test_multipage_non_ocr_pages_dont_consume_budget()
    test_multipage_uncapped_budget_ocrs_all()
    test_max_ocr_pages_acts_as_budget()
    test_deterministic_repeat()
    test_malformed_input_degrades_safely()
    test_malformed_config_degrades_safely()
    test_smuggled_secrets_and_paths_never_leak()
    test_routes_non_list_is_empty()
    test_routes_with_malformed_page_in_batch()
    test_default_config_is_local_first_cloud_off()
    test_every_classification_yields_valid_shape()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"OCR routing-policy tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
