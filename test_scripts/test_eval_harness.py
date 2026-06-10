"""Unit tests for the Slice 20 eval harness (test_scripts/eval/).

Plain-Python assertion style (matches the rest of test_scripts/). Run with:

    python test_scripts/test_eval_harness.py

Covers spec loading/validation, the four deterministic offline metrics (concept
coverage, must-not-claim, math via the Slice 18 verifier, lint via the Slice 19
linter), overall scoring on clean / bad-math / bad-structure fixtures, the JSON
result shape, previous-run regression comparison, and a guarantee that no
provider key or secret-like field is ever written into a result.

Offline only — no provider keys, no Docker, no LLM calls, no network.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from test_scripts.eval import run_eval, score_guide

FIXTURE_DIR = os.path.join(_HERE, "eval", "fixtures")
GOLDEN_DIR = os.path.join(_HERE, "eval", "golden")
SAMPLE_SPEC = os.path.join(GOLDEN_DIR, "sample.json")

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def _load_guide(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as handle:
        return handle.read()


# ── Spec loading / validation ──────────────────────────────────────────────────

def test_load_valid_spec() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    check("spec/loads", spec.get("id") == "sample_nn_part3", str(spec.get("id")))
    check("spec/has-sections", "Overview" in (spec.get("expected_sections") or []))
    check("spec/has-concepts", "backpropagation" in (spec.get("required_concepts") or []))
    check("spec/has-source-page-anchors", spec.get("source_page_anchors") == [1, 2])


def test_invalid_spec_rejected() -> None:
    bad_cases = [
        ("not-a-dict", ["just a string"]),
        ("missing-id", {"title": "no id here"}),
        ("bad-sections", {"id": "x", "expected_sections": "Overview"}),
        ("bad-concepts", {"id": "x", "required_concepts": [1, 2, 3]}),
        ("bad-page-anchors", {"id": "x", "source_page_anchors": ["1"]}),
    ]
    for label, payload in bad_cases:
        try:
            score_guide.validate_spec(payload)
            ok = False
        except score_guide.SpecError:
            ok = True
        check(f"spec/reject-{label}", ok)


def test_invalid_json_spec_reported() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        handle.write("{ not valid json ")
        path = handle.name
    try:
        run_eval.load_spec(path)
        ok = False
    except score_guide.SpecError:
        ok = True
    finally:
        os.unlink(path)
    check("spec/reject-bad-json", ok)


# ── Concept matching ────────────────────────────────────────────────────────────

def test_concept_matching() -> None:
    text = "The activation function and gradient descent are covered, with examples."
    score, missing = score_guide.score_concepts(
        text, ["activation function", "gradient descent", "backpropagation"]
    )
    check("concepts/partial-score", abs(score - (2 / 3)) < 1e-9, str(score))
    check("concepts/missing-list", missing == ["backpropagation"], str(missing))


def test_concept_normalization() -> None:
    # Punctuation/casing differences must still match.
    text = "We discuss the Activation-Function in detail."
    score, missing = score_guide.score_concepts(text, ["activation function"])
    check("concepts/normalized-match", score == 1.0 and missing == [], str((score, missing)))


def test_concept_none_required() -> None:
    score, missing = score_guide.score_concepts("anything", None)
    check("concepts/none-required", score == 1.0 and missing == [])


# ── Must-not-claim detection ─────────────────────────────────────────────────────

def test_must_not_claim_detected() -> None:
    text = "It is false that Softmax outputs can be negative, but here it is stated."
    score, violations = score_guide.score_must_not_claim(
        text, ["softmax outputs can be negative"]
    )
    check("mnc/violation-score", score == 0.0, str(score))
    check("mnc/violation-listed", len(violations) == 1, str(violations))
    check("mnc/violation-phrase", violations and "softmax" in violations[0]["phrase"].lower())


def test_must_not_claim_clean() -> None:
    text = "Softmax outputs are non-negative and sum to one."
    score, violations = score_guide.score_must_not_claim(
        text, ["softmax outputs can be negative"]
    )
    check("mnc/clean-score", score == 1.0 and violations == [], str((score, violations)))


# ── Math verifier integration (Slice 18) ─────────────────────────────────────────

def test_math_integration_good() -> None:
    score, summary = score_guide.score_math(_load_guide("sample_good_guide.md"))
    check("math/good-no-mismatch", summary.get("mismatch", 0) == 0, str(summary))
    check("math/good-high-score", score >= 0.75, str(score))


def test_math_integration_bad() -> None:
    score, summary = score_guide.score_math(_load_guide("sample_bad_math_guide.md"))
    check("math/bad-has-mismatch", summary.get("mismatch", 0) >= 2, str(summary))
    check("math/bad-low-score", score < 0.5, str(score))


# ── Guide lint integration (Slice 19) ────────────────────────────────────────────

def test_lint_integration_clean() -> None:
    score, summary, top = score_guide.score_lint(
        _load_guide("sample_good_guide.md"),
        ["Overview", "Key Concepts", "Worked Examples", "Practice Questions"],
    )
    check("lint/clean-no-error", summary.get("error", 0) == 0, str(summary))
    check("lint/clean-high-score", score >= 0.95, str(score))


def test_lint_integration_bad_structure() -> None:
    score, summary, top = score_guide.score_lint(
        _load_guide("sample_bad_structure_guide.md"),
        ["Overview", "Key Concepts", "Worked Examples", "Practice Questions"],
    )
    check("lint/bad-has-findings", summary.get("total", 0) >= 3, str(summary))
    check("lint/bad-lower-score", score < 0.8, str(score))
    check("lint/top-findings-capped", len(top) <= score_guide.MAX_TOP_FINDINGS)


def test_lint_integration_page_citation_plausibility() -> None:
    good = "## Overview\n\nA valid cited definition (p. 2).\n"
    score, summary, top = score_guide.score_lint(
        good,
        ["Overview"],
        available_source_pages=[1, 2],
    )
    check("lint/citation-valid-no-warning", summary.get("warning", 0) == 0, str(summary))
    bad = "## Overview\n\nAn impossible cited definition (pp. 2-4).\n"
    score, summary, top = score_guide.score_lint(
        bad,
        ["Overview"],
        available_source_pages=[1, 2],
    )
    check("lint/citation-invalid-warning", summary.get("warning", 0) == 1, str(summary))
    check(
        "lint/citation-invalid-top-finding",
        top and top[0]["rule"] == "page_citation_range",
        str(top),
    )


# ── Overall scoring on the three fixtures ─────────────────────────────────────────

def test_score_clean_guide() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    result = score_guide.build_result(
        spec, _load_guide("sample_good_guide.md"),
        guide_path="sample_good_guide.md", mode="offline",
    )
    s = result["scores"]
    check("clean/overall-high", s["overall"] >= 0.9, str(s))
    check("clean/concepts-full", s["concepts"] == 1.0, str(s))
    check("clean/no-violations", result["details"]["must_not_claim_violations"] == [])
    check("clean/artifacts-null-offline", s["artifacts"] is None)


def test_score_bad_math_guide() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    result = score_guide.build_result(
        spec, _load_guide("sample_bad_math_guide.md"),
        guide_path="sample_bad_math_guide.md", mode="offline",
    )
    s = result["scores"]
    check("badmath/math-low", s["math"] < 0.5, str(s))
    check("badmath/overall-below-clean", s["overall"] < 0.9, str(s))


def test_score_bad_structure_guide() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    result = score_guide.build_result(
        spec, _load_guide("sample_bad_structure_guide.md"),
        guide_path="sample_bad_structure_guide.md", mode="offline",
    )
    s = result["scores"]
    check("badstruct/lint-low", s["lint"] < 0.8, str(s))
    missing = result["details"]["lint_summary"]
    check("badstruct/lint-summary-shape",
          set(missing) == {"total", "error", "warning", "info"}, str(missing))


def test_clean_beats_bad() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    good = score_guide.build_result(spec, _load_guide("sample_good_guide.md"), mode="offline")
    bad_m = score_guide.build_result(spec, _load_guide("sample_bad_math_guide.md"), mode="offline")
    bad_s = score_guide.build_result(spec, _load_guide("sample_bad_structure_guide.md"), mode="offline")
    check("ordering/good>bad_math", good["scores"]["overall"] > bad_m["scores"]["overall"])
    check("ordering/good>bad_struct", good["scores"]["overall"] > bad_s["scores"]["overall"])


# ── Artifact scoring (live-mode metric, exercised directly) ──────────────────────

def test_artifact_scoring() -> None:
    score, detail = score_guide.score_artifacts({"markdown": True, "html": True, "pdf": False})
    check("artifacts/fraction", abs(score - (2 / 3)) < 1e-9, str(score))
    check("artifacts/detail", detail and detail["present"] == 2 and detail["expected"] == 3)
    none_score, none_detail = score_guide.score_artifacts(None)
    check("artifacts/offline-null", none_score is None and none_detail is None)


def test_overall_renormalizes_without_artifacts() -> None:
    # With artifacts None, overall must be the weighted mean of the other four.
    scores = {"concepts": 1.0, "math": 1.0, "lint": 1.0, "must_not_claim": 1.0, "artifacts": None}
    check("overall/renorm-all-ones", abs(score_guide.compute_overall(scores) - 1.0) < 1e-9)
    scores2 = {"concepts": 0.0, "math": 0.0, "lint": 0.0, "must_not_claim": 0.0, "artifacts": None}
    check("overall/renorm-all-zero", score_guide.compute_overall(scores2) == 0.0)


# ── JSON result shape ────────────────────────────────────────────────────────────

def test_result_shape() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    result = score_guide.build_result(
        spec, _load_guide("sample_good_guide.md"),
        guide_path="sample_good_guide.md", mode="offline",
    )
    check("json/version", result.get("version") == 1)
    check("json/spec-id", result.get("spec_id") == "sample_nn_part3")
    score_keys = {"overall", "concepts", "math", "lint", "must_not_claim", "artifacts"}
    check("json/score-keys", set(result["scores"]) == score_keys, str(result["scores"].keys()))
    detail_keys = {
        "missing_concepts", "must_not_claim_violations", "math_summary",
        "lint_summary", "lint_top_findings", "artifacts",
    }
    check("json/detail-keys", set(result["details"]) == detail_keys, str(result["details"].keys()))
    # Round-trips through JSON cleanly.
    parsed = json.loads(json.dumps(result))
    check("json/roundtrip", parsed == result)


# ── Previous-run comparison ──────────────────────────────────────────────────────

def test_previous_run_comparison() -> None:
    out = tempfile.mkdtemp(prefix="eval_test_")
    try:
        spec = run_eval.load_spec(SAMPLE_SPEC)
        # First run of the good guide → no prior, no regression block.
        r1 = score_guide.build_result(
            spec, _load_guide("sample_good_guide.md"),
            guide_path="sample_good_guide.md", mode="offline",
        )
        run_eval.finalize(r1, out)
        check("regression/first-run-none", "regression" not in r1)

        # Second run of the SAME guide → regression block comparing to the first.
        r2 = score_guide.build_result(
            spec, _load_guide("sample_good_guide.md"),
            guide_path="sample_good_guide.md", mode="offline",
        )
        run_eval.finalize(r2, out)
        reg = r2.get("regression")
        check("regression/second-run-present", reg is not None, str(reg))
        check("regression/zero-delta-same-guide", reg and reg["overall_delta"] == 0.0, str(reg))

        # A DIFFERENT guide for the same spec must NOT compare against the good guide.
        r3 = score_guide.build_result(
            spec, _load_guide("sample_bad_math_guide.md"),
            guide_path="sample_bad_math_guide.md", mode="offline",
        )
        run_eval.finalize(r3, out)
        check("regression/different-guide-isolated", "regression" not in r3, str(r3.get("regression")))

        # Files actually landed.
        written = [f for f in os.listdir(out) if f.endswith(".json")]
        check("regression/files-written", len(written) == 3, str(written))
        check("regression/csv-written", os.path.exists(os.path.join(out, "summary.csv")))
    finally:
        shutil.rmtree(out, ignore_errors=True)


# ── No secret leakage in saved results ────────────────────────────────────────────

def test_no_secret_in_result() -> None:
    spec = run_eval.load_spec(SAMPLE_SPEC)
    result = score_guide.build_result(
        spec, _load_guide("sample_good_guide.md"),
        guide_path="sample_good_guide.md", mode="offline",
    )
    result["run_id"] = "2026-01-01T00-00-00Z"
    check("secrets/clean-result-ok", run_eval.find_secret(result) is None,
          str(run_eval.find_secret(result)))

    # A planted credential-looking value must be caught and block the write.
    poisoned = dict(result)
    poisoned["details"] = dict(result["details"])
    poisoned["details"]["leak"] = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    out = tempfile.mkdtemp(prefix="eval_secret_")
    try:
        try:
            run_eval.write_result(poisoned, out)
            blocked = False
        except RuntimeError:
            blocked = True
        check("secrets/planted-blocked", blocked)
    finally:
        shutil.rmtree(out, ignore_errors=True)

    # An api_key *field name* (even with a placeholder value) must also be caught.
    poisoned2 = dict(result)
    poisoned2["api_key"] = "placeholder"
    check("secrets/key-field-name-caught", run_eval.find_secret(poisoned2) is not None)


# ── Full offline CLI run (--all) writes valid, secret-free results ────────────────

def test_cli_all_offline() -> None:
    out = tempfile.mkdtemp(prefix="eval_cli_")
    try:
        rc = run_eval.main(["--offline", "--all", "--output-dir", out])
        check("cli/all-exit-zero", rc == 0, str(rc))
        files = [f for f in os.listdir(out) if f.endswith(".json")]
        check("cli/all-wrote-three", len(files) == 3, str(files))
        for fname in files:
            with open(os.path.join(out, fname), encoding="utf-8") as handle:
                data = json.load(handle)
            check(f"cli/secret-free::{fname}", run_eval.find_secret(data) is None)
    finally:
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    test_load_valid_spec()
    test_invalid_spec_rejected()
    test_invalid_json_spec_reported()
    test_concept_matching()
    test_concept_normalization()
    test_concept_none_required()
    test_must_not_claim_detected()
    test_must_not_claim_clean()
    test_math_integration_good()
    test_math_integration_bad()
    test_lint_integration_clean()
    test_lint_integration_bad_structure()
    test_lint_integration_page_citation_plausibility()
    test_score_clean_guide()
    test_score_bad_math_guide()
    test_score_bad_structure_guide()
    test_clean_beats_bad()
    test_artifact_scoring()
    test_overall_renormalizes_without_artifacts()
    test_result_shape()
    test_previous_run_comparison()
    test_no_secret_in_result()
    test_cli_all_offline()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Eval harness tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
