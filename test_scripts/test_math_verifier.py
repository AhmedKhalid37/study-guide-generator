"""Unit tests for pipeline/math_verifier.py (Slice 18 pure core).

Plain-Python assertion style (matches the rest of test_scripts/). Run with:

    python test_scripts/test_math_verifier.py

Covers good / mismatch / unparseable claim verdicts, Markdown safety (fenced and
inline code, math wrappers), normalization, tolerance/rounding behavior, the
safety guards (length, unknown function, no execution), fixture files, and the
JSON-serializable report shape.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.math_verifier import (
    MathVerificationReport,
    verify_math_claims,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "math_verifier")

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


def _single(text: str):
    """Verify a one-claim snippet and return its single ClaimResult."""
    report = verify_math_claims(text)
    return report, (report.claims[0] if report.claims else None)


def _status(text: str) -> str:
    _, claim = _single(text)
    return claim.status if claim else "<no-claim>"


# ── Good claims ─────────────────────────────────────────────────────────────

def test_good_claims() -> None:
    cases = [
        "2 + 3 = 5",
        "3 × 4 = 12",
        "10 / 4 = 2.5",
        "sqrt(16) = 4",
        "exp(0) = 1",
        "1 / 3 ≈ 0.333",
        "exp(1.43) / (1 + exp(1.43)) ≈ 0.806",
    ]
    for case in cases:
        check(f"good/{case}", _status(case) == "ok", f"got {_status(case)}")


def test_good_extras() -> None:
    check("good/unicode-minus", _status("5 − 3 = 2") == "ok")
    check("good/cdot", _status(r"3 \cdot 4 = 12") == "ok")
    check("good/division-sign", _status("12 ÷ 4 = 3") == "ok")
    check("good/power-caret", _status("2^10 = 1024") == "ok")
    check("good/sqrt-unicode", _status("√(16) = 4") == "ok")
    check("good/frac", _status(r"\frac{1}{4} = 0.25") == "ok")
    check("good/pi", _status("pi ≈ 3.14159") == "ok")
    check("good/e-power", _status("e^1.43 / (1 + e^1.43) ≈ 0.806") == "ok")
    check("good/log-natural", _status("log(1) = 0") == "ok")
    # rounded value tighter than rel tolerance, handled by rounding tolerance
    check("good/round-0.806", _status("0.8057 ≈ 0.806") == "ok")


# ── Mismatch claims ─────────────────────────────────────────────────────────

def test_mismatch_claims() -> None:
    check("mismatch/2+3=6", _status("2 + 3 = 6") == "mismatch")
    check("mismatch/10/4=3", _status("10 / 4 = 3") == "mismatch")
    check("mismatch/corrupted-round", _status("1 / 3 ≈ 0.350") == "mismatch")
    check("mismatch/sqrt", _status("sqrt(16) = 5") == "mismatch")


# ── Unparseable claims (never mismatch) ─────────────────────────────────────

def test_unparseable_claims() -> None:
    check("unparseable/force", _status("force = mass × acceleration") == "unparseable")
    check("unparseable/units", _status("5 kg = 5000") == "unparseable")
    check("unparseable/variable", _status("x + 2 = 5") == "unparseable")
    check("unparseable/symbolic", _status("a^2 + b^2 = c^2") == "unparseable")
    # no relation / pure prose → no claim extracted at all
    rep, _ = _single("This sentence approximately doubles the value.")
    check("unparseable/prose-no-claim", rep.summary["total"] == 0)
    rep2, _ = _single("Name = Alice")
    check("unparseable/non-math-equals", rep2.summary["total"] == 0)


# ── Markdown safety ─────────────────────────────────────────────────────────

def test_code_block_ignored() -> None:
    text = (
        "Before: 2 + 3 = 5\n"
        "```\n"
        "2 + 3 = 6\n"
        "```\n"
        "After: 4 + 4 = 8\n"
    )
    report = verify_math_claims(text)
    texts = [c.text for c in report.claims]
    check("code/fence-excluded", all("6" not in t for t in texts), str(texts))
    check("code/total-is-2", report.summary["total"] == 2, str(report.summary))
    check("code/both-ok", report.summary["ok"] == 2)


def test_inline_code_ignored() -> None:
    report = verify_math_claims("An example `2 + 3 = 6` is shown.")
    check("code/inline-excluded", report.summary["total"] == 0, str(report.summary))


def test_math_wrappers() -> None:
    check("wrap/inline-dollar", _status("$2 + 2 = 4$") == "ok")
    check("wrap/display-dollar", _status("$$2 + 2 = 4$$") == "ok")
    check("wrap/paren", _status(r"\(2 + 2 = 4\)") == "ok")
    check("wrap/bracket", _status(r"\[2 + 2 = 4\]") == "ok")


# ── Tolerance / line numbers / chained ──────────────────────────────────────

def test_line_numbers() -> None:
    text = "intro\n\n2 + 3 = 5\n"
    _, claim = _single(text)
    check("line/number", claim is not None and claim.line == 3,
          str(claim.line if claim else None))


def test_chained_claim() -> None:
    # expr = intermediate ≈ final ; both adjacent numeric pairs verified ok
    report = verify_math_claims("1 / 4 = 0.25 ≈ 0.3")
    statuses = [c.status for c in report.claims]
    check("chain/two-claims", len(report.claims) == 2, str(statuses))
    check("chain/first-ok", statuses and statuses[0] == "ok", str(statuses))


# ── Safety guards ───────────────────────────────────────────────────────────

def test_long_expression_rejected() -> None:
    long_expr = " + ".join(["1"] * 300)  # well over MAX_EXPR_LEN
    _, claim = _single(f"{long_expr} = 300")
    check("safety/long-expr", claim is not None and claim.status == "unparseable",
          str(claim.status if claim else None))
    check("safety/long-expr-reason",
          claim is not None and claim.reason in {"expression_too_long", "too_many_tokens", "expression_too_complex"},
          str(claim.reason if claim else None))


def test_unknown_function_rejected() -> None:
    _, claim = _single("foo(2) = 4")
    check("safety/unknown-fn", claim is not None and claim.status == "unparseable")
    check("safety/unknown-fn-reason",
          claim is not None and claim.reason == "unknown_function",
          str(claim.reason if claim else None))


def test_malicious_not_executed() -> None:
    # Attribute access / string literal / dunder calls must never execute and
    # must downgrade to unparseable.
    for payload in (
        "__import__('os').system('echo pwned') = 0",
        "(1).__class__ = 0",
        "open('x') = 0",
    ):
        status = _status(payload)
        check(f"safety/no-exec [{payload[:24]}...]", status == "unparseable",
              f"got {status}")


def test_no_negative_power_blowup() -> None:
    # Huge exponent rejected, never computed.
    _, claim = _single("2 ** 100000 = 1")
    check("safety/pow-guard", claim is not None and claim.status == "unparseable",
          str(claim.status if claim else None))


def test_division_by_zero() -> None:
    check("safety/div-zero", _status("1 / 0 = 0") == "unparseable")


# ── Report shape / JSON ─────────────────────────────────────────────────────

def test_report_serializable() -> None:
    report = verify_math_claims("2 + 3 = 5\n2 + 3 = 6\nx + 1 = 2\n",
                                source_name="example.md")
    check("report/type", isinstance(report, MathVerificationReport))
    check("report/version", report.to_dict()["version"] == 1)
    check("report/source", report.to_dict()["source_name"] == "example.md")
    check("report/summary-total", report.summary["total"] == 3)
    check("report/summary-counts",
          report.summary["ok"] == 1 and report.summary["mismatch"] == 1
          and report.summary["unparseable"] == 1, str(report.summary))
    # Round-trips through JSON without error and preserves the claim count.
    blob = report.to_json(indent=2)
    parsed = json.loads(blob)
    check("report/json-roundtrip", len(parsed["claims"]) == 3)
    first = parsed["claims"][0]
    for key in ("id", "line", "text", "expression", "claimed", "computed",
                "status", "reason", "tolerance_abs", "tolerance_rel"):
        check(f"report/claim-key-{key}", key in first)
    check("report/claim-id-format", first["id"] == "claim_0001")


# ── Fixtures ────────────────────────────────────────────────────────────────

def _load(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as handle:
        return handle.read()


def test_fixture_good() -> None:
    report = verify_math_claims(_load("good_claims.md"), source_name="good_claims.md")
    check("fixture/good-no-mismatch", report.summary["mismatch"] == 0, str(report.summary))
    check("fixture/good-has-ok", report.summary["ok"] >= 7, str(report.summary))


def test_fixture_mismatch() -> None:
    report = verify_math_claims(_load("mismatch_claims.md"))
    check("fixture/mismatch-count", report.summary["mismatch"] == 3, str(report.summary))
    check("fixture/mismatch-no-false-ok", report.summary["ok"] == 0, str(report.summary))


def test_fixture_unparseable() -> None:
    report = verify_math_claims(_load("unparseable_claims.md"))
    check("fixture/unparseable-no-mismatch", report.summary["mismatch"] == 0, str(report.summary))
    check("fixture/unparseable-some", report.summary["unparseable"] >= 4, str(report.summary))


def test_fixture_code_block() -> None:
    report = verify_math_claims(_load("code_block.md"))
    texts = [c.text for c in report.claims]
    check("fixture/code-no-9", all("9" not in t for t in texts), str(texts))
    check("fixture/code-no-6", all("= 6" not in t for t in texts), str(texts))
    check("fixture/code-real-claim-ok", report.summary["ok"] == 1, str(report.summary))
    check("fixture/code-no-mismatch", report.summary["mismatch"] == 0, str(report.summary))


if __name__ == "__main__":
    test_good_claims()
    test_good_extras()
    test_mismatch_claims()
    test_unparseable_claims()
    test_code_block_ignored()
    test_inline_code_ignored()
    test_math_wrappers()
    test_line_numbers()
    test_chained_claim()
    test_long_expression_rejected()
    test_unknown_function_rejected()
    test_malicious_not_executed()
    test_no_negative_power_blowup()
    test_division_by_zero()
    test_report_serializable()
    test_fixture_good()
    test_fixture_mismatch()
    test_fixture_unparseable()
    test_fixture_code_block()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Math verifier tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
