#!/usr/bin/env python3
"""Ask retrieval relevance harness — Slice 25A baseline (no optimization).

Measures the *current* local-only lexical (tf-idf) Ask retrieval behaviour
before any LanceDB / embeddings / reranking / context-compression work. This is
a BASELINE: it records strengths and weaknesses honestly and never changes how
retrieval works.

What it exercises (the real pipeline, no server / model / provider / Docker):

  1. ``pipeline.ask_context.prepare_context`` builds the deterministic chunk +
     lexical index from a small synthetic guide + extracted-source fixture,
     written into a TEMP job directory (never the real ``jobs/`` tree).
  2. ``pipeline.ask_context.load_index`` reads that index back.
  3. ``pipeline.ask_sessions._score_chunks`` / ``retrieve_chunks`` rank chunks
     for each fixture query — the exact functions Ask uses at chat time.

Metrics (JSON-serializable, deterministic):

  * ``hit_at_k``  — does an expected concept/source marker appear in the top-k?
  * ``rank``      — 1-indexed rank of the first expected hit (or null).
  * ``reciprocal_rank`` and the aggregate ``mrr``.
  * ``hit_rate_at_k`` over blocking cases.
  * ``missing``   — blocking cases with no expected hit in top-k.
  * ``known_weaknesses`` — paraphrase cases reported but NON-blocking.

Pass/fail: the harness fails only if a *blocking* case (``known_weakness:false``)
misses its expected hit in the top-k. Known-weakness cases are reported either
way so a future retrieval-optimization slice can measure improvement against
this recorded baseline.

Run:  ``python test_scripts/test_ask_retrieval_relevance.py``
Add ``--json`` to print the full deterministic report.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Make the repo root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import ask_context  # noqa: E402
from pipeline import ask_sessions  # noqa: E402
from pipeline.job_manager import Job  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ask_retrieval"

PASS = 0
FAIL = 0


def check(name: str, ok: bool) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _load_fixture() -> tuple[str, str, dict]:
    guide = (FIXTURE_DIR / "guide.md").read_text(encoding="utf-8")
    source = (FIXTURE_DIR / "source.txt").read_text(encoding="utf-8")
    queries = json.loads((FIXTURE_DIR / "queries.json").read_text(encoding="utf-8"))
    return guide, source, queries


def _build_index(tmp: Path, guide: str, source: str) -> dict:
    """Prepare the real Ask context index inside a throwaway job directory."""
    job = Job("ask-retrieval-fixture", root=tmp)
    job.dir.mkdir(parents=True, exist_ok=True)
    job.clean_md.write_text(guide, encoding="utf-8")
    job.extracted_txt.write_text(source, encoding="utf-8")
    result = ask_context.prepare_context(job)
    if not result.get("ready"):
        raise RuntimeError("fixture guide did not prepare an Ask context index")
    index = ask_context.load_index(job)
    if not isinstance(index, dict) or not index.get("chunks"):
        raise RuntimeError("prepared Ask context index is empty")
    return index


def _chunk_matches(chunk: dict, expect: dict) -> bool:
    """True if a chunk satisfies an expected concept/source-marker target."""
    if chunk.get("source_type") != expect.get("source_type"):
        return False
    if expect.get("source_type") == "source":
        return chunk.get("page") in set(expect.get("pages") or [])
    return chunk.get("label") in set(expect.get("labels") or [])


def _score_case(index: dict, case: dict, top_k: int) -> dict:
    """Rank one query and compute its baseline metrics (no retrieval changes)."""
    query = case["query"]
    expect = case["expect"]

    # Full deterministic ranking (score desc, then tokens, then id) — the exact
    # ordering Ask uses; we read it to find the first expected hit's rank.
    ranked = ask_sessions._score_chunks(index, query)
    rank = None
    for position, (_score, chunk) in enumerate(ranked, start=1):
        if _chunk_matches(chunk, expect):
            rank = position
            break
    reciprocal_rank = round(1.0 / rank, 4) if rank else 0.0
    hit_at_k = rank is not None and rank <= top_k

    # Also exercise the real budgeted public retrieval and record what it would
    # actually hand to the model, so the baseline reflects production behaviour.
    retrieved = ask_sessions.retrieve_chunks(index, query, max_chunks=top_k)
    retrieved_targets = [
        {
            "id": c.get("id"),
            "source_type": c.get("source_type"),
            "label": c.get("label"),
            "page": c.get("page") if isinstance(c.get("page"), int) else None,
        }
        for c in retrieved
    ]
    retrieved_hit = any(_chunk_matches(c, expect) for c in retrieved)

    return {
        "id": case["id"],
        "query": query,
        "expect": expect,
        "known_weakness": bool(case.get("known_weakness")),
        "rank": rank,
        "hit_at_k": hit_at_k,
        "reciprocal_rank": reciprocal_rank,
        "retrieved_hit": retrieved_hit,
        "retrieved_top": retrieved_targets,
    }


def build_report(index: dict, queries: dict) -> dict:
    top_k = int(queries.get("top_k", 5))
    cases = [_score_case(index, case, top_k) for case in queries.get("cases", [])]

    blocking = [c for c in cases if not c["known_weakness"]]
    weaknesses = [c for c in cases if c["known_weakness"]]

    blocking_hits = [c for c in blocking if c["hit_at_k"]]
    hit_rate = round(len(blocking_hits) / len(blocking), 4) if blocking else 0.0
    rr_values = [c["reciprocal_rank"] for c in blocking]
    mrr = round(sum(rr_values) / len(rr_values), 4) if rr_values else 0.0
    missing = [c["id"] for c in blocking if not c["hit_at_k"]]

    return {
        "harness": "ask_retrieval_relevance",
        "version": 1,
        "retrieval": "local-only lexical tf-idf (ask_context + ask_sessions)",
        "top_k": top_k,
        "index_stats": {
            "guide_chunk_count": index.get("guide_chunk_count"),
            "source_chunk_count": index.get("source_chunk_count"),
            "total_chunk_count": index.get("total_chunk_count"),
        },
        "metrics": {
            "blocking_case_count": len(blocking),
            "hit_rate_at_k": hit_rate,
            "mrr": mrr,
            "missing": missing,
        },
        "cases": cases,
        "known_weaknesses": [
            {"id": c["id"], "hit_at_k": c["hit_at_k"], "rank": c["rank"]}
            for c in weaknesses
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask retrieval relevance baseline harness")
    parser.add_argument("--json", action="store_true", help="print the full deterministic JSON report")
    args = parser.parse_args()

    guide, source, queries = _load_fixture()
    with tempfile.TemporaryDirectory() as td:
        index = _build_index(Path(td), guide, source)
    report = build_report(index, queries)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))

    # Sanity: the fixture must produce both guide and source chunks.
    check("index has guide chunks", (report["index_stats"]["guide_chunk_count"] or 0) > 0)
    check("index has source chunks", (report["index_stats"]["source_chunk_count"] or 0) > 0)

    # Blocking cases must retrieve their expected concept/source marker in top-k.
    for case in report["cases"]:
        if case["known_weakness"]:
            continue
        check(
            f"blocking hit@{report['top_k']}: {case['id']} (rank={case['rank']})",
            case["hit_at_k"],
        )

    # The budgeted public retrieval must agree with the ranking for blocking hits.
    for case in report["cases"]:
        if case["known_weakness"] or not case["hit_at_k"]:
            continue
        check(f"public retrieve agrees: {case['id']}", case["retrieved_hit"])

    # Report (do not fail on) known weaknesses so the baseline is honest.
    for case in report["known_weaknesses"]:
        status = "hit" if case["hit_at_k"] else "MISS (known weakness, non-blocking)"
        print(f"[INFO] known-weakness {case['id']}: {status} (rank={case['rank']})")

    m = report["metrics"]
    print(
        f"\nbaseline: hit_rate@{report['top_k']}={m['hit_rate_at_k']} "
        f"mrr={m['mrr']} missing={m['missing']}"
    )
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
