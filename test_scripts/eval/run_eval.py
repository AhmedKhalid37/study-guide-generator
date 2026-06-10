"""GuideForge eval harness CLI (Slice 20 — eval harness Phase 1).

Deterministic, offline-first scoring of guide Markdown against golden specs,
built on the pure correctness modules from Slice 18 (math) and Slice 19 (lint)
plus simple concept / must-not-claim string checks (see ``score_guide.py``).

This is the *measurement spine* only. It does NOT change generation prompts,
provider behavior, ``/api/jobs/llm`` fields, the Builder/JobDetails UI, or job
artifacts, and it adds no embeddings / LLM-judge / retrieval / OCR work.

Spec format: JSON (stdlib only — no PyYAML dependency, matching the project's
dependency-free stance). A loader for ``.yaml``/``.yml`` is offered only if
PyYAML happens to be importable; the committed golden specs are ``.json``.

Modes
-----
Offline (required — no provider keys, no Docker, no LLM calls)::

    python test_scripts/eval/run_eval.py --offline \\
        --spec  test_scripts/eval/golden/sample.json \\
        --guide test_scripts/eval/fixtures/sample_good_guide.md

    python test_scripts/eval/run_eval.py --offline --all
    python test_scripts/eval/run_eval.py --offline --all --output-dir test_scripts/eval/results

Live (optional — submits a tiny source to the local API and scores the result)::

    python test_scripts/eval/run_eval.py --live \\
        --spec test_scripts/eval/golden/sample.json \\
        --base-url http://localhost:8000

The live mode uses only existing API behavior (the no-provider ``/api/jobs/paste``
endpoint), times out cleanly, prints no secrets, and writes results only under the
output directory.

Results are written as JSON under the output dir (default
``test_scripts/eval/results/``) and an appended CSV summary. Each run also reports
a non-blocking regression comparison against the most recent prior result for the
same ``spec_id`` + ``mode``.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from test_scripts.eval.score_guide import SpecError, build_result, validate_spec  # noqa: E402

DEFAULT_GOLDEN_DIR = os.path.join(_HERE, "golden")
DEFAULT_OUTPUT_DIR = os.path.join(_HERE, "results")
DEFAULT_BASE_URL = "http://localhost:8000"
LIVE_TIMEOUT_SECONDS = 120

# Result fields/values that would indicate a leaked credential. Mirrors the
# smoke_release.py leak scan so saved eval results can never carry a secret.
_SECRET_KEY_NAMES = {
    "api_key", "apikey", "secret", "token", "authorization", "password",
    "base_url", "url", "socket_path",
}
_KEYLIKE_RE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")


# ── Spec / guide loading ──────────────────────────────────────────────────────

def load_spec(path: str) -> dict:
    """Load and validate a golden spec (JSON; optional YAML if PyYAML present)."""
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read()
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - env dependent
            raise SpecError(
                f"spec '{path}' is YAML but PyYAML is not installed; use JSON"
            ) from exc
        data = yaml.safe_load(raw)
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SpecError(f"spec '{path}' is not valid JSON: {exc}") from exc
    return validate_spec(data)


def _resolve(path: str) -> str:
    """Resolve a possibly repo-relative path against the repo root."""
    if os.path.isabs(path):
        return path
    here_rel = os.path.join(_HERE, path)
    if os.path.exists(here_rel):
        return here_rel
    return os.path.join(_REPO_ROOT, path)


def read_guide(path: str) -> str:
    with open(_resolve(path), "r", encoding="utf-8") as handle:
        return handle.read()


# ── Secret scrubbing ──────────────────────────────────────────────────────────

def find_secret(node, path: str = "result"):
    """Return the path of the first secret-looking field/value, else ``None``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in _SECRET_KEY_NAMES:
                return f"{path}.{key}"
            hit = find_secret(value, f"{path}.{key}")
            if hit:
                return hit
    elif isinstance(node, list):
        for i, item in enumerate(node):
            hit = find_secret(item, f"{path}[{i}]")
            if hit:
                return hit
    elif isinstance(node, str):
        if _KEYLIKE_RE.search(node):
            return f"{path} (value looks like a credential)"
    return None


def assert_no_secrets(result: dict) -> None:
    leak = find_secret(result)
    if leak is not None:
        raise RuntimeError(f"refusing to write eval result: possible secret at {leak}")


# ── Regression comparison ─────────────────────────────────────────────────────

def _guide_key(guide_path: str | None) -> str:
    """Stable identifier for a guide within a (spec, mode): the path basename."""
    if not guide_path:
        return "guide"
    base = os.path.basename(guide_path.rstrip("/")) or guide_path
    return _safe(os.path.splitext(base)[0])


def _result_glob(output_dir: str, spec_id: str, mode: str, guide_key: str) -> list[str]:
    pattern = os.path.join(output_dir, f"{_safe(spec_id)}__{mode}__{guide_key}__*.json")
    return sorted(glob.glob(pattern))


def compare_to_previous(result: dict, output_dir: str) -> dict | None:
    """Compare *result* to the most recent prior result for the same spec+mode+guide.

    The regression key is (spec_id, mode, guide) so a run is compared against the
    last time *that same guide* was scored — never against a different guide that
    happened to share the spec. Non-blocking and read-only: returns a small delta
    summary or ``None`` when no prior result exists.
    """
    spec_id = result.get("spec_id") or "unknown"
    mode = result.get("mode") or "offline"
    guide_key = _guide_key(result.get("guide_path"))
    prior_paths = _result_glob(output_dir, spec_id, mode, guide_key)
    if not prior_paths:
        return None
    prev_path = prior_paths[-1]
    try:
        with open(prev_path, "r", encoding="utf-8") as handle:
            prev = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    prev_scores = prev.get("scores", {})
    cur_scores = result.get("scores", {})
    prev_overall = prev_scores.get("overall")
    cur_overall = cur_scores.get("overall")
    metric_deltas = {}
    for name in ("concepts", "math", "lint", "must_not_claim", "artifacts"):
        p, c = prev_scores.get(name), cur_scores.get(name)
        if isinstance(p, (int, float)) and isinstance(c, (int, float)):
            metric_deltas[name] = round(c - p, 4)
    delta = None
    if isinstance(prev_overall, (int, float)) and isinstance(cur_overall, (int, float)):
        delta = round(cur_overall - prev_overall, 4)
    return {
        "previous_file": os.path.basename(prev_path),
        "previous_overall": prev_overall,
        "current_overall": cur_overall,
        "overall_delta": delta,
        "metric_deltas": metric_deltas,
    }


# ── Output ────────────────────────────────────────────────────────────────────

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    return _SAFE_RE.sub("-", str(name)).strip("-") or "unknown"


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_result(result: dict, output_dir: str) -> str:
    """Validate-then-write a result JSON file; returns the written path.

    The filename encodes spec, mode, guide, and run timestamp. If that exact name
    already exists (two runs of the same guide within one second), a short counter
    keeps each run's result distinct rather than silently overwriting it.
    """
    assert_no_secrets(result)
    os.makedirs(output_dir, exist_ok=True)
    guide_key = _guide_key(result.get("guide_path"))
    stem = f"{_safe(result.get('spec_id'))}__{result.get('mode')}__{guide_key}__{result['run_id']}"
    path = os.path.join(output_dir, f"{stem}.json")
    counter = 1
    while os.path.exists(path):
        path = os.path.join(output_dir, f"{stem}-{counter}.json")
        counter += 1
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    return path


def append_csv_summary(result: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "summary.csv")
    new = not os.path.exists(path)
    scores = result.get("scores", {})
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow([
                "run_id", "mode", "spec_id", "guide_path",
                "overall", "concepts", "math", "lint", "must_not_claim", "artifacts",
            ])
        writer.writerow([
            result.get("run_id"), result.get("mode"), result.get("spec_id"),
            result.get("guide_path"),
            scores.get("overall"), scores.get("concepts"), scores.get("math"),
            scores.get("lint"), scores.get("must_not_claim"), scores.get("artifacts"),
        ])
    return path


def print_result(result: dict) -> None:
    scores = result.get("scores", {})
    print(f"\n=== {result.get('spec_id')} [{result.get('mode')}] ===")
    print(f"  guide:   {result.get('guide_path')}")
    print(f"  overall: {scores.get('overall')}")
    for name in ("concepts", "math", "lint", "must_not_claim", "artifacts"):
        print(f"    {name:<15} {scores.get(name)}")
    missing = result.get("details", {}).get("missing_concepts") or []
    if missing:
        print(f"  missing concepts: {missing}")
    violations = result.get("details", {}).get("must_not_claim_violations") or []
    if violations:
        print(f"  must-not-claim violations: {[v['phrase'] for v in violations]}")
    reg = result.get("regression")
    if reg:
        print(
            f"  regression vs {reg['previous_file']}: "
            f"{reg['previous_overall']} -> {reg['current_overall']} "
            f"(delta {reg['overall_delta']})"
        )


# ── Live mode ───────────────────────────────────────────────────────────────────

def _http_json(method: str, url: str, *, body: dict | None = None, timeout: int = LIVE_TIMEOUT_SECONDS):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def _http_text(url: str, *, timeout: int = LIVE_TIMEOUT_SECONDS) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def run_live(spec: dict, base_url: str) -> dict:
    """Submit the spec's source to the local API (no provider) and score the guide.

    Uses ``/api/jobs/paste`` so it never needs a provider key. Only the API host
    is recorded in the result (never the full URL). Raises on any HTTP failure so
    the caller can report it cleanly.
    """
    base = base_url.rstrip("/")
    host = urllib.parse.urlparse(base).netloc or "local"
    source_path = spec.get("source_path")
    if not source_path:
        raise SpecError("live mode requires the spec to define 'source_path'")
    source_text = read_guide(source_path)

    status, paste = _http_json("POST", f"{base}/api/jobs/paste", body={
        "text": source_text, "title": spec.get("title") or spec.get("id"),
    })
    if status != 200 or paste.get("status") != "done":
        raise RuntimeError(f"live paste failed (status={status}, job={paste.get('status')})")
    job_id = paste.get("job_id")

    art_status, guide_text = _http_text(f"{base}/api/jobs/{job_id}/artifacts/clean.md")
    if art_status != 200:
        raise RuntimeError(f"could not fetch clean.md (status={art_status})")

    # Cheap artifact-presence probe (HEAD-like GET, body discarded).
    artifacts = {}
    for name, artifact in (("markdown", "clean.md"), ("html", "final.html"), ("pdf", "final.pdf")):
        try:
            s, _ = _http_text(f"{base}/api/jobs/{job_id}/artifacts/{artifact}", timeout=30)
            artifacts[name] = s == 200
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            artifacts[name] = False

    result = build_result(
        spec, guide_text, guide_path=f"live:{host}/job/{job_id}",
        mode="live", artifacts=artifacts,
    )
    return result


# ── Offline mode ─────────────────────────────────────────────────────────────

def run_offline_one(spec: dict, guide_path: str) -> dict:
    guide_text = read_guide(guide_path)
    return build_result(spec, guide_text, guide_path=guide_path, mode="offline")


def _spec_guides(spec: dict) -> list[str]:
    """Offline guides for ``--all``: the spec's ``offline_guides``, else its source."""
    guides = spec.get("offline_guides")
    if guides:
        return list(guides)
    src = spec.get("source_path")
    return [src] if src else []


def _all_spec_paths(golden_dir: str) -> list[str]:
    paths = sorted(glob.glob(os.path.join(golden_dir, "*.json")))
    paths += sorted(glob.glob(os.path.join(golden_dir, "*.yaml")))
    paths += sorted(glob.glob(os.path.join(golden_dir, "*.yml")))
    return paths


# ── Finalize + persist a single result ─────────────────────────────────────────

def finalize(result: dict, output_dir: str) -> dict:
    result["run_id"] = _timestamp()
    reg = compare_to_previous(result, output_dir)
    if reg is not None:
        result["regression"] = reg
    path = write_result(result, output_dir)
    append_csv_summary(result, output_dir)
    print_result(result)
    print(f"  written: {os.path.relpath(path, _REPO_ROOT)}")
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="GuideForge deterministic eval harness")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="score guide files (default)")
    mode.add_argument("--live", action="store_true", help="generate via local API, then score")
    parser.add_argument("--spec", help="path to a golden spec (.json)")
    parser.add_argument("--guide", help="path to a guide Markdown file (offline single-run)")
    parser.add_argument("--all", action="store_true", help="run every golden spec (offline)")
    parser.add_argument("--golden-dir", default=DEFAULT_GOLDEN_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="live mode API base URL")
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    results: list[dict] = []

    try:
        if args.live:
            if not args.spec:
                parser.error("--live requires --spec")
            spec = load_spec(args.spec)
            try:
                result = run_live(spec, args.base_url)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, RuntimeError) as exc:
                print(f"[live] failed: {exc}", file=sys.stderr)
                return 2
            results.append(finalize(result, output_dir))

        elif args.all:
            for spec_path in _all_spec_paths(args.golden_dir):
                spec = load_spec(spec_path)
                for guide_path in _spec_guides(spec):
                    results.append(finalize(run_offline_one(spec, guide_path), output_dir))

        else:  # default offline single-run
            if not args.spec or not args.guide:
                parser.error("offline mode requires --spec and --guide (or use --all)")
            spec = load_spec(args.spec)
            results.append(finalize(run_offline_one(spec, args.guide), output_dir))
    except SpecError as exc:
        print(f"[spec] {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    if not results:
        print("[warn] no results produced (no specs/guides found)", file=sys.stderr)
        return 1
    print(f"\nScored {len(results)} guide(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
