"""Smoke test for Phase A: Quiz / Flashcards Generator.

Tests:
  1. POST /api/jobs/{id}/quiz — MCQ + flashcards
  2. GET  /api/jobs/{id}/quizzes — list returns the new quiz
  3. GET  /api/jobs/{id}/quizzes/{n} — full quiz load (items present)
  4. Export formats: csv, anki_tsv, quizlet — correct structure
  5. Input validation — bad question_type, bad count, bad difficulty, bad focus

Run against a live server (default http://localhost:8000):
    python test_scripts/smoke_quiz.py

Override server:
    SMOKE_BASE_URL=http://localhost:9000 python test_scripts/smoke_quiz.py
"""

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")

results = []


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL"))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def skip(name, detail=""):
    results.append((name, "SKIP"))
    print(f"[SKIP] {name}" + (f" — {detail}" if detail else ""))


def _req(method, path, *, json_body=None, raw=False):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read()
            if raw:
                return resp.status, body, {}
            return resp.status, json.loads(body), {}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body), {}
        except Exception:
            return exc.code, body.decode(errors="replace"), {}


def _download(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {}


def _find_done_job():
    status, data, _ = _req("GET", "/api/jobs")
    if status != 200:
        return None
    for job in (data.get("jobs") or []):
        if job.get("status") == "done" and job.get("artifact_availability", {}).get("clean_md"):
            return job["id"]
    return None


# ── Find a suitable job ───────────────────────────────────────────────────────
print("=" * 60)
print("Phase A: Quiz / Flashcards smoke test")
print("=" * 60)

status, data, _ = _req("GET", "/api/health")
if status != 200 or not data.get("ok"):
    print("ERROR: server not healthy — aborting")
    sys.exit(1)

# Check provider availability
status, opts, _ = _req("GET", "/api/options")
configured = [p for p in (opts.get("providers_v2") or []) if p.get("configured")]
if not configured:
    skip("ALL QUIZ TESTS", "No LLM provider configured — cannot generate quiz")
    print("\n[RESULT] SKIPPED (no provider)")
    sys.exit(0)

job_id = _find_done_job()
if not job_id:
    skip("ALL QUIZ TESTS", "No done job with clean.md found")
    print("\n[RESULT] SKIPPED (no done job)")
    sys.exit(0)

print(f"Using job: {job_id}")
print()

# ── Test 1: Generate MCQ + flashcards ────────────────────────────────────────
status, quiz, _ = _req("POST", f"/api/jobs/{job_id}/quiz", json_body={
    "question_types": ["mcq", "flashcards"],
    "count": 10,
    "difficulty": "medium",
    "focus": "all",
})
ok_gen = (
    status == 200
    and isinstance(quiz.get("items"), list)
    and len(quiz["items"]) > 0
    and isinstance(quiz.get("n"), int)
)
check("POST /quiz — returns items list", ok_gen, f"status={status} items={len(quiz.get('items', []))}")

if not ok_gen:
    print("Quiz generation failed — cannot continue tests")
    print(f"  Response: {str(quiz)[:400]}")
    # Print final summary and exit
    total = len(results)
    passed = sum(1 for _, s in results if s == "PASS")
    skipped = sum(1 for _, s in results if s == "SKIP")
    failed = total - passed - skipped
    print(f"\n{'='*60}\nRESULT: {passed}/{total-skipped} passed, {skipped} skipped, {failed} failed\n{'='*60}")
    sys.exit(1 if failed else 0)

quiz_n = quiz["n"]
items = quiz["items"]

# Validate item structure
has_type = all("type" in item for item in items)
has_question = all("question" in item and item["question"] for item in items)
has_answer = all("answer" in item and item["answer"] for item in items)
has_topic = all("topic" in item for item in items)
check("Quiz items have required fields (type/question/answer/topic)", has_type and has_question and has_answer and has_topic)

mcq_items = [i for i in items if i["type"] == "mcq"]
flash_items = [i for i in items if i["type"] == "flashcards"]
check("Quiz contains MCQ items", len(mcq_items) > 0, f"{len(mcq_items)} mcq")
check("Quiz contains flashcard items", len(flash_items) > 0, f"{len(flash_items)} flashcards")

if mcq_items:
    mcq = mcq_items[0]
    has_options = isinstance(mcq.get("options"), list) and len(mcq["options"]) == 4
    answer_is_letter = mcq.get("answer", "").upper() in {"A", "B", "C", "D"}
    check("MCQ has 4 options", has_options, f"options={mcq.get('options')}")
    check("MCQ answer is a letter (A/B/C/D)", answer_is_letter, f"answer={mcq.get('answer')!r}")

# ── Test 2: GET /quizzes list ─────────────────────────────────────────────────
status, list_data, _ = _req("GET", f"/api/jobs/{job_id}/quizzes")
ok_list = (
    status == 200
    and isinstance(list_data.get("quizzes"), list)
    and any(q["n"] == quiz_n for q in list_data["quizzes"])
)
check("GET /quizzes — lists the new quiz", ok_list, f"found={any(q['n']==quiz_n for q in list_data.get('quizzes',[]))}")

# ── Test 3: GET /quizzes/{n} ─────────────────────────────────────────────────
status, full_quiz, _ = _req("GET", f"/api/jobs/{job_id}/quizzes/{quiz_n}")
ok_get = (
    status == 200
    and full_quiz.get("n") == quiz_n
    and isinstance(full_quiz.get("items"), list)
    and len(full_quiz["items"]) > 0
)
check("GET /quizzes/{n} — full quiz with items", ok_get, f"items={len(full_quiz.get('items', []))}")

# ── Test 4: Export formats ────────────────────────────────────────────────────

# CSV
status_csv, body_csv, hdrs_csv = _download(f"/api/jobs/{job_id}/quizzes/{quiz_n}/export?format=csv")
if status_csv == 200:
    try:
        reader = csv.reader(io.StringIO(body_csv.decode("utf-8")))
        rows = list(reader)
        header_ok = rows[0] == ["Front", "Back", "Topic", "Difficulty"]
        data_rows = rows[1:]
        data_ok = len(data_rows) > 0 and all(len(r) == 4 for r in data_rows)
        check("CSV export — header correct", header_ok, f"header={rows[0]}")
        check("CSV export — data rows present (4 columns each)", data_ok, f"rows={len(data_rows)}")
    except Exception as exc:
        check("CSV export — parse", False, str(exc))
else:
    check("CSV export — 200 OK", False, f"status={status_csv}")

# Anki TSV
status_tsv, body_tsv, _ = _download(f"/api/jobs/{job_id}/quizzes/{quiz_n}/export?format=anki_tsv")
if status_tsv == 200:
    text_tsv = body_tsv.decode("utf-8")
    lines = [l for l in text_tsv.splitlines() if l.strip()]
    tsv_ok = len(lines) > 0 and all("\t" in l for l in lines)
    no_header = lines[0].split("\t")[0].lower() not in {"front", "question"}
    check("Anki TSV — tab-separated, no header", tsv_ok and no_header, f"lines={len(lines)} first={lines[0][:50] if lines else ''!r}")
else:
    check("Anki TSV export — 200 OK", False, f"status={status_tsv}")

# Quizlet
status_q, body_q, _ = _download(f"/api/jobs/{job_id}/quizzes/{quiz_n}/export?format=quizlet")
if status_q == 200:
    text_q = body_q.decode("utf-8")
    lines_q = [l for l in text_q.splitlines() if l.strip()]
    quizlet_ok = len(lines_q) > 0 and all("\t" in l for l in lines_q)
    check("Quizlet export — tab-separated term/definition", quizlet_ok, f"lines={len(lines_q)}")
else:
    check("Quizlet export — 200 OK", False, f"status={status_q}")

# ── Test 5: Input validation ──────────────────────────────────────────────────
# Bad question type
status_bad, _, _ = _req("POST", f"/api/jobs/{job_id}/quiz", json_body={
    "question_types": ["banana"],
    "count": 10,
    "difficulty": "medium",
    "focus": "all",
})
check("Validation — bad question_type → 400", status_bad == 400, f"status={status_bad}")

# Bad count
status_bad2, _, _ = _req("POST", f"/api/jobs/{job_id}/quiz", json_body={
    "question_types": ["mcq"],
    "count": 7,
    "difficulty": "medium",
    "focus": "all",
})
check("Validation — bad count (7) → 400", status_bad2 == 400, f"status={status_bad2}")

# Bad difficulty
status_bad3, _, _ = _req("POST", f"/api/jobs/{job_id}/quiz", json_body={
    "question_types": ["mcq"],
    "count": 10,
    "difficulty": "extreme",
    "focus": "all",
})
check("Validation — bad difficulty → 400", status_bad3 == 400, f"status={status_bad3}")

# Bad export format
status_bad4, _, _ = _download(f"/api/jobs/{job_id}/quizzes/{quiz_n}/export?format=docx")
check("Validation — bad export format → 400", status_bad4 == 400, f"status={status_bad4}")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
total = len(results)
passed = sum(1 for _, s in results if s == "PASS")
skipped_count = sum(1 for _, s in results if s == "SKIP")
failed = total - passed - skipped_count
print("=" * 60)
print(f"RESULT: {passed}/{total - skipped_count} passed, {skipped_count} skipped, {failed} failed")
print("=" * 60)
sys.exit(1 if failed else 0)
