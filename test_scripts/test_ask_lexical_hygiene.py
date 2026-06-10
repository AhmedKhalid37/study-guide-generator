#!/usr/bin/env python3
"""Focused tests for Slice 25B Ask lexical retrieval hygiene.

These are pure, deterministic unit checks for ``pipeline.ask_lexical`` plus a
small integration check that the hygiene actually flows through the real Ask
index build (``ask_context``) and query scorer (``ask_sessions``). No server,
model, provider, or Docker is involved.

What they prove:
  * stopwords ("the", "it", "on", ...) are dropped from term maps;
  * conservative plural folding is applied ("inputs"->"input") while doubled-s
    and short tokens are preserved ("loss", "is");
  * domain/technical tokens survive ("l2", "f1", "sigmoid", "dropout");
  * the index side and the query side use the *same* tokenisation (a query term
    can match an indexed term) — the invariant that makes retrieval work;
  * the recorded paraphrase weakness improves: with hygiene the Overfitting
    section is ranked #1 for the paraphrase fixture (was rank 5 at the 25A
    baseline), while the blocking keyword cases do not regress.

    python test_scripts/test_ask_lexical_hygiene.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import ask_context, ask_sessions  # noqa: E402
from pipeline.ask_lexical import STOPWORDS, lexical_terms, normalize_token  # noqa: E402
from pipeline.job_manager import Job  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ask_retrieval"

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def test_stopwords_filtered() -> None:
    terms = lexical_terms("How does the model learn from it on the data")
    for stop in ("how", "does", "the", "it", "on", "from"):
        check(f"stopword dropped: {stop!r}", stop not in terms)
    # Content words survive (and "data" is not treated as a stopword).
    check("content word kept: 'model'", "model" in terms)
    check("content word kept: 'data'", "data" in terms)
    check("content word kept: 'learn'", "learn" in terms)


def test_plural_normalization() -> None:
    # Regular +s plurals fold to the same stem as their singular (the symmetry
    # that lets a query term match an indexed term).
    check("'inputs' -> 'input'", normalize_token("inputs") == "input")
    check("'examples' -> 'example'", normalize_token("examples") == "example")
    check("'weights' -> 'weight'", normalize_token("weights") == "weight")
    check("'metrics' -> 'metric'", normalize_token("metrics") == "metric")
    check("'example' unchanged (already singular)", normalize_token("example") == "example")
    # Doubled-s and short tokens must be preserved.
    check("'loss' preserved (doubled ss)", normalize_token("loss") == "loss")
    check("'class' preserved (doubled ss)", normalize_token("class") == "class")
    check("'is' preserved (too short)", normalize_token("is") == "is")
    # No verb-tense stemming (intentional): these stay intact.
    check("'training' not stemmed", normalize_token("training") == "training")
    check("'based' not stemmed", normalize_token("based") == "based")


def test_technical_tokens_survive() -> None:
    terms = lexical_terms("L2 regularization and dropout improve the F1 sigmoid")
    for tok in ("l2", "regularization", "dropout", "f1", "sigmoid"):
        check(f"technical token kept: {tok!r}", tok in terms)


def test_index_and_query_use_same_tokeniser() -> None:
    # ask_context (index side) and ask_sessions (query side) must agree.
    text = "Backpropagation computes the gradients using the chain rules"
    check(
        "ask_context._term_freqs == ask_lexical.lexical_terms",
        ask_context._term_freqs(text) == lexical_terms(text),
    )
    check(
        "ask_sessions._terms == ask_lexical.lexical_terms",
        dict(ask_sessions._terms(text)) == lexical_terms(text),
    )


def _build_fixture_index(tmp: Path) -> dict:
    guide = (FIXTURE_DIR / "guide.md").read_text(encoding="utf-8")
    source = (FIXTURE_DIR / "source.txt").read_text(encoding="utf-8")
    job = Job("ask-lexical-fixture", root=tmp)
    job.dir.mkdir(parents=True, exist_ok=True)
    job.clean_md.write_text(guide, encoding="utf-8")
    job.extracted_txt.write_text(source, encoding="utf-8")
    result = ask_context.prepare_context(job)
    if not result.get("ready"):
        raise RuntimeError("fixture did not prepare an Ask context index")
    index = ask_context.load_index(job)
    if not isinstance(index, dict) or not index.get("chunks"):
        raise RuntimeError("prepared Ask context index is empty")
    return index


def _rank_of(index: dict, query: str, label: str) -> int | None:
    ranked = ask_sessions._score_chunks(index, query)
    for position, (_score, chunk) in enumerate(ranked, start=1):
        if chunk.get("source_type") == "guide" and chunk.get("label") == label:
            return position
    return None


def test_index_doc_freq_is_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        index = _build_fixture_index(Path(td))
    doc_freq = index.get("doc_freq") or {}
    # The historically dominant noise term must no longer be indexed at all.
    check("'the' absent from doc_freq", "the" not in doc_freq)
    check("'it' absent from doc_freq", "it" not in doc_freq)
    # Indexed chunk terms are also clean.
    leaked = sorted({t for c in index["chunks"] for t in c["terms"] if t in STOPWORDS})
    check("no stopword leaked into chunk terms", not leaked, detail=str(leaked))


def test_retrieval_quality() -> None:
    queries = json.loads((FIXTURE_DIR / "queries.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        index = _build_fixture_index(Path(td))

    # Blocking keyword cases: the section keyword overlap must keep them at #1.
    blocking_expectations = {
        "How does backpropagation compute the gradient using the chain rule?": "Backpropagation",
        "What is the sigmoid logistic function used for in logistic regression?": "Logistic Regression and the Sigmoid Function",
        "How do L2 regularization and dropout reduce overfitting?": "Overfitting and Regularization",
        "What do precision and recall mean in a confusion matrix?": "Confusion Matrix and Evaluation Metrics",
    }
    for query, label in blocking_expectations.items():
        rank = _rank_of(index, query, label)
        check(f"blocking keyword stays #1: {label!r}", rank == 1, detail=f"rank={rank}")

    # The recorded paraphrase weakness improves to rank 1 with hygiene (was 5).
    paraphrase = next(c for c in queries["cases"] if c["id"] == "overfitting-paraphrase")
    rank = _rank_of(index, paraphrase["query"], "Overfitting and Regularization")
    check(
        "paraphrase improves to rank 1 (25A baseline was 5)",
        rank == 1,
        detail=f"rank={rank}",
    )


def main() -> int:
    test_stopwords_filtered()
    test_plural_normalization()
    test_technical_tokens_survive()
    test_index_and_query_use_same_tokeniser()
    test_index_doc_freq_is_clean()
    test_retrieval_quality()

    passed = sum(1 for _, ok in results if ok)
    failed = len(results) - passed
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
