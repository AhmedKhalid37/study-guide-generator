"""Focused tests for the present-input target reconstructor (Slice 176E).

Synthetic, public-safe positioned tokens only — no raw source / OCR / table / guide
text, no formulas, no real source values, no fixture values, no answer strings. The
full chain is exercised: spatial grid reconstruction → integer class-count rows →
weighted-Gini ``inputs`` → **masked** recompute through the REAL verifier (answer
never supplied). Anti-laundering (Gini answer decimals refused), the hand-located /
spot-check provenance guard, the closed-vocab contract, and total degradation on
malformed input are all asserted.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.quality_safety_present_input_target_reconstructor import (  # noqa: E402
    ARTIFACT_NAME,
    BLOCKED_BY_TOKENS,
    INPUT_PRESENCE_CLAIM_BASES,
    INPUT_PRESENCE_CONFIRMED,
    MASKED_RECOMPUTE_STATUSES,
    NEXT_STEPS,
    SELECTED_REGION_ORIGINS,
    SOURCE_CONFIRMATION_STATUSES,
    STATUSES,
    reconstruct_present_input_target,
)

_PASS = 0
_FAIL = 0


def check(label, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        print(f"  FAIL: {label}")


def _row_tokens(rows, y_step=10.0, x_step=20.0):
    """Build public-safe positioned {x,y,text} tokens from a list-of-rows grid."""
    tokens = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            tokens.append({"x": x_step * c, "y": y_step * r, "text": str(text)})
    return tokens


# ── A clean weighted-Gini class-count region parses cold + masked recompute passes ──

def test_class_counts_parse_and_masked_recompute_passes():
    # Two child nodes, each a row of integer class counts (public-safe, invented).
    tokens = _row_tokens([["3", "1"], ["1", "5"]])
    out = reconstruct_present_input_target(
        target_id="gini_chest_pain",
        target_family="weighted_gini",
        positioned_tokens=tokens,
        selected_region_origin="discovered_from_extraction",
    )
    rec = out["record"]
    check("parsed status", rec["status"] == "parsed")
    check("row_cell parsed", rec["row_cell_extraction_status"] == "parsed_from_extraction_output")
    check("record created", rec["source_input_record_status"] == "created")
    check("origin parsed", rec["source_input_origin"] == "parsed_from_extraction_output")
    check("machine consumable", rec["machine_consumable_for_recompute"] is True)
    check("masked recompute passed", rec["masked_recompute_status"] == "passed")
    check("confirmed true", rec["input_presence_confirmed_against_source"] == "true")
    check("claim basis source-confirmed", rec["input_presence_claim_basis"] == "source_confirmed_this_slice")
    check("confirmation rows", rec["source_confirmation_status"] == "computation_input_rows_confirmed")
    check("next wire", rec["next_step"] == "wire_parsed_rows_into_recompute")
    check("no hand-located", rec["parser_received_hand_located_region"] is False)
    check("no spot-check hint", rec["parser_received_spot_check_region_hint"] is False)
    check("recompute_input present", isinstance(out["recompute_input"], dict))
    check("recompute_input is gini", out["recompute_input"]["method"] == "weighted_gini")
    check("recompute_input groups", "groups" in out["recompute_input"]["inputs"])


def test_verifier_independently_recomputes_masked_gini():
    from pipeline.quality_safety_recompute_verifier import recompute_quality_safety_fact

    tokens = _row_tokens([["3", "1"], ["1", "5"]])
    out = reconstruct_present_input_target(
        target_id="gini_chest_pain",
        target_family="weighted_gini",
        positioned_tokens=tokens,
    )
    ri = out["recompute_input"]
    fact = {
        "id": "masked",
        "type": "numeric",
        "value": None,  # answer MASKED
        "provenance": "unverified",
        "computation": {"method": ri["method"], "inputs": ri["inputs"]},
    }
    res = recompute_quality_safety_fact(fact)
    check("verifier recomputes finite gini", isinstance(res.get("recomputed_value"), (int, float)))
    check("recomputed in unit interval", 0.0 <= res["recomputed_value"] <= 1.0)


# ── Anti-laundering: Gini answer decimals are refused as inputs ───────────────

def test_answer_decimals_refused():
    # Only unit-interval decimals present (the Gini values = answers), no counts.
    tokens = _row_tokens([["0.48", "0.32"], ["0.20", "0.50"]])
    out = reconstruct_present_input_target(
        target_id="gini_chest_pain",
        target_family="weighted_gini",
        positioned_tokens=tokens,
    )
    rec = out["record"]
    check("answer-only not created", rec["source_input_record_status"] == "not_created")
    check("answer-only not machine consumable", rec["machine_consumable_for_recompute"] is False)
    check("answer-only blocked source_input_mapping", rec["blocked_by"] == "source_input_mapping")
    check("answer-only warning", "answer_matrix_not_input" in rec["warnings"])
    check("answer-only confirmation", rec["source_confirmation_status"] == "answer_output_only_confirmed")
    check("answer-only confirmed false", rec["input_presence_confirmed_against_source"] == "false")
    check("answer-only claim basis prior", rec["input_presence_claim_basis"] == "prior_closed_evidence")
    check("answer-only next choose-different", rec["next_step"] == "choose_different_input_present_target")
    check("answer-only no recompute_input", out["recompute_input"] is None)


# ── Provenance guard: hand-located / spot-check region refused ────────────────

def test_hand_located_region_refused():
    tokens = _row_tokens([["3", "1"], ["1", "5"]])
    out = reconstruct_present_input_target(
        target_id="gini_weight_gt_176",
        target_family="weighted_gini",
        positioned_tokens=tokens,
        parser_received_hand_located_region=True,
    )
    rec = out["record"]
    check("hand-located not created", rec["source_input_record_status"] == "not_created")
    check("hand-located blocked privacy", rec["blocked_by"] == "privacy_boundary")
    check("hand-located flag true", rec["parser_received_hand_located_region"] is True)
    check("hand-located region origin", rec["selected_region_origin"] == "hand_located_spot_check")
    check("hand-located warning", "hand_located_region_refused" in rec["warnings"])
    check("hand-located no recompute_input", out["recompute_input"] is None)


def test_spot_check_hint_refused():
    tokens = _row_tokens([["3", "1"], ["1", "5"]])
    out = reconstruct_present_input_target(
        target_id="gini_weight_gt_176",
        target_family="weighted_gini",
        positioned_tokens=tokens,
        parser_received_spot_check_region_hint=True,
    )
    rec = out["record"]
    check("spot-check not created", rec["source_input_record_status"] == "not_created")
    check("spot-check blocked privacy", rec["blocked_by"] == "privacy_boundary")
    check("spot-check flag true", rec["parser_received_spot_check_region_hint"] is True)
    check("spot-check warning", "spot_check_hint_refused" in rec["warnings"])


# ── Degrade paths ────────────────────────────────────────────────────────────

def test_no_region_blocks():
    out = reconstruct_present_input_target(
        target_id="gini_chest_pain",
        target_family="weighted_gini",
        positioned_tokens=None,
    )
    rec = out["record"]
    check("no region not created", rec["source_input_record_status"] == "not_created")
    check("no region blocked detection", rec["blocked_by"] == "target_region_detection")
    check("no region confirmation", rec["source_confirmation_status"] == "no_input_region_found")
    check("no region warning", "region_input_unavailable" in rec["warnings"])
    check("no region next improve", rec["next_step"] == "improve_input_region_evidence")


def test_no_input_columns_blocks():
    # A single integer per row (no >=2-count group) and no decimals → no input region.
    tokens = _row_tokens([["7"], ["9"]])
    out = reconstruct_present_input_target(
        target_id="gini_chest_pain",
        target_family="weighted_gini",
        positioned_tokens=tokens,
    )
    rec = out["record"]
    check("no-columns not created", rec["source_input_record_status"] == "not_created")
    check("no-columns confirmation", rec["source_confirmation_status"] == "no_input_region_found")
    check("no-columns warning", "no_input_columns_found" in rec["warnings"])


def test_unsupported_family_blocks():
    out = reconstruct_present_input_target(
        target_id="total_error_stump_1",
        target_family="total_error",
        positioned_tokens=_row_tokens([["3", "1"]]),
    )
    rec = out["record"]
    check("unsupported family blocked", rec["blocked_by"] == "unsupported_method")
    check("unsupported warning", "unsupported_target_family" in rec["warnings"])
    check("unsupported not created", rec["source_input_record_status"] == "not_created")


def test_totality_on_malformed():
    for bad in [None, 42, "x", [], [{"no": "coords"}], [{"x": 1, "y": 1}]]:
        out = reconstruct_present_input_target(
            target_id="gini_chest_pain", target_family="weighted_gini", positioned_tokens=bad
        )
        check(f"malformed {bad!r} does not raise", isinstance(out, dict))
        check(f"malformed {bad!r} closed status", out["record"]["status"] in STATUSES)


# ── Closed-vocab contract + no raw values committed ──────────────────────────

def test_closed_vocab_contract():
    tokens = _row_tokens([["3", "1"], ["1", "5"]])
    rec = reconstruct_present_input_target(
        target_id="gini_chest_pain", target_family="weighted_gini", positioned_tokens=tokens
    )["record"]
    check("artifact name", rec["artifact_name"] == ARTIFACT_NAME)
    check("status closed", rec["status"] in STATUSES)
    check("region origin closed", rec["selected_region_origin"] in SELECTED_REGION_ORIGINS)
    check("masked closed", rec["masked_recompute_status"] in MASKED_RECOMPUTE_STATUSES)
    check("claim basis closed", rec["input_presence_claim_basis"] in INPUT_PRESENCE_CLAIM_BASES)
    check("confirmed closed", rec["input_presence_confirmed_against_source"] in INPUT_PRESENCE_CONFIRMED)
    check("confirmation closed", rec["source_confirmation_status"] in SOURCE_CONFIRMATION_STATUSES)
    check("blocked_by closed", rec["blocked_by"] in BLOCKED_BY_TOKENS)
    check("next_step closed", rec["next_step"] in NEXT_STEPS)
    for flag in (
        "hand_authored_rows", "fixture_derived", "answer_string_derived",
        "guide_candidate_derived", "raw_values_committed", "raw_ocr_committed",
    ):
        check(f"provenance flag {flag} false", rec[flag] is False)


def test_committed_record_has_no_raw_float_values():
    # The closed record must contain only closed tokens / ints / bools — no float.
    tokens = _row_tokens([["3", "1"], ["1", "5"]])
    rec = reconstruct_present_input_target(
        target_id="gini_chest_pain", target_family="weighted_gini", positioned_tokens=tokens
    )["record"]
    blob = json.dumps(rec)
    check("no decimal-point float in record", "." not in blob.replace("0.0", "") or "0." not in
          json.dumps([v for v in rec.values() if isinstance(v, float)]))
    check("record json round-trips", json.loads(blob) == rec)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    total = _PASS + _FAIL
    print(f"\n{_PASS}/{total} checks passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
