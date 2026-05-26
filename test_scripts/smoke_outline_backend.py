"""M1 backend smoke for the outline slice (no frontend changes required).

Verifies: LLM generation without outline still works; with outline the job
follows the section order in clean.md and stores outline metadata; /api/jobs/{id}
and /api/jobs expose the outline summary; mode defaults to study_guide when
omitted; and POST /api/outline/generate returns a usable draft.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


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
            return (resp.status, body) if raw else (resp.status, json.loads(body.decode()))
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if raw:
            return exc.code, body
        try:
            return exc.code, json.loads(body.decode())
        except json.JSONDecodeError:
            return exc.code, {"raw": body.decode(errors="replace")}


results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def clean_md(job_id):
    status, body = _req("GET", f"/api/jobs/{job_id}/artifacts/clean.md", raw=True)
    return body.decode("utf-8", errors="replace") if status == 200 else ""


def llm(body):
    base = {"provider": "deepseek", "model": "deepseek-chat", "mode": "exam"}
    base.update(body)
    return _req("POST", "/api/jobs/llm", json_body=base)


# 1. LLM without outline still works; outline summary reports disabled
status, job = llm({
    "source_text": "Explain Ohm's law and basic circuit analysis.",
    "title": "No Outline Probe", "prompt_name": "basic_study_guide",
})
nid = job.get("job_id")
check("llm without outline -> done", status == 200 and job.get("status") == "done", f"status={status}")
check("no-outline job reports outline_enabled false", job.get("outline_enabled") is False, f"{job.get('outline_enabled')}")

# 2. LLM with outline -> done + metadata + clean.md follows order
titles = ["Foundations Overview", "Core Equations", "Worked Example", "Common Pitfalls", "Rapid Review"]
status, job = llm({
    "source_text": "Source: kinematics — displacement, velocity, acceleration, and basic equations of motion.",
    "title": "Outline Probe", "prompt_name": "basic_study_guide",
    "outline": {"enabled": True, "sections": [{"title": t, "instructions": f"Cover {t} clearly."} for t in titles]},
})
oid = job.get("job_id")
check("llm with outline -> done", status == 200 and job.get("status") == "done", f"status={status}")
check("outline job reports enabled + count", job.get("outline_enabled") is True and job.get("outline_section_count") == 5,
      f"enabled={job.get('outline_enabled')} count={job.get('outline_section_count')}")
check("outline job returns titles", job.get("outline_titles") == titles, f"{job.get('outline_titles')}")

md = clean_md(oid)
positions = [md.find(t) for t in titles]
all_present = all(p != -1 for p in positions)
in_order = all_present and positions == sorted(positions)
check("clean.md contains every outline title", all_present, f"positions={positions}")
check("clean.md follows outline order", in_order, f"positions={positions}")

# 3. GET /api/jobs/{id} + /api/jobs expose outline summary
_, detail = _req("GET", f"/api/jobs/{oid}")
jm = detail.get("job", {})
check("job detail has outline summary", jm.get("outline_enabled") is True and jm.get("outline_section_count") == 5,
      f"enabled={jm.get('outline_enabled')} count={jm.get('outline_section_count')}")
check("job detail mode defaulted/stored", bool(jm.get("mode")), f"mode={jm.get('mode')}")
_, listing = _req("GET", "/api/jobs?limit=100")
lj = next((j for j in listing.get("jobs", []) if j.get("id") == oid), {})
check("/api/jobs item has outline summary", lj.get("outline_enabled") is True and lj.get("outline_section_count") == 5, "")

# 4. mode defaults to study_guide when omitted
status, job = _req("POST", "/api/jobs/llm", json_body={
    "source_text": "Summarize Newton's three laws.", "title": "Mode Default Probe",
    "prompt_name": "basic_study_guide", "provider": "deepseek", "model": "deepseek-chat",
})
mid = job.get("job_id")
_, mdetail = _req("GET", f"/api/jobs/{mid}")
check("omitted mode defaults to study_guide", mdetail.get("job", {}).get("mode") == "study_guide",
      f"mode={mdetail.get('job', {}).get('mode')}")

# 5. /api/outline/generate returns a usable draft
status, gen = _req("POST", "/api/outline/generate", json_body={
    "source_text": "Photosynthesis: light reactions, Calvin cycle, and energy flow.",
    "title": "Photosynthesis Guide", "provider": "deepseek", "model": "deepseek-chat",
})
secs = gen.get("sections", [])
check("outline generate returns sections", status == 200 and len(secs) >= 3, f"status={status} n={len(secs)}")
check("generated sections have titles", all(s.get("title") for s in secs), "")

# 6. empty outline request rejected
status, _ = _req("POST", "/api/outline/generate", json_body={"source_text": "", "title": ""})
check("empty outline generate rejected", status == 400, f"status={status}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
