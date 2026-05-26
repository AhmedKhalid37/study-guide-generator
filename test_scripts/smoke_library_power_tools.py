"""Live smoke test for the 'Library power tools and folder visibility' slice.

Verifies: folder metadata on GET /api/jobs and GET /api/jobs/{id}; create folder
(the API path the Builder popover uses) with a preset color; batch move + batch
unfile via /api/library/jobs/move; folder delete leaves jobs intact; and that
paste/upload/LLM generation + library search/filter/sort still work.
"""
import json
import sys
import urllib.request
import urllib.error
import uuid
from urllib.parse import quote

BASE = "http://localhost:8000"


def _req(method, path, *, json_body=None, multipart=None):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        boundary = f"----smoke{uuid.uuid4().hex}"
        parts = []
        for key, value in multipart["fields"].items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            parts.append(f"{value}\r\n".encode())
        for key, (fname, content) in multipart["files"].items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{key}"; filename="{fname}"\r\n'.encode())
            parts.append(b"Content-Type: text/markdown\r\n\r\n")
            parts.append(content.encode() if isinstance(content, str) else content)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def job_in_list(job_id):
    _, listing = _req("GET", "/api/jobs?limit=100")
    for job in listing.get("jobs", []):
        if job.get("id") == job_id:
            return job
    return None


# 1. Create a folder with a preset color (Builder popover uses this exact path)
status, folder = _req("POST", "/api/library/folders", json_body={"name": "Power Tools", "color": "#A855F7"})
check("create folder with color", status == 200 and folder.get("color") == "#A855F7", f"status={status} color={folder.get('color')}")
fid = folder.get("id")

# duplicate-name folders are allowed (unique ids); invalid color must be rejected
status, body = _req("POST", "/api/library/folders", json_body={"name": "Bad", "color": "not a color!!"})
check("invalid color rejected", status == 400, f"status={status} detail={str(body)[:90]}")

# 2. Paste job into the folder, then verify folder metadata on both job endpoints
status, job = _req("POST", "/api/jobs/paste", json_body={"text": "# Meta Probe\n\nInline $x^2$.", "folder_id": fid})
pid = job.get("job_id")
check("paste job created", status == 200 and bool(pid), f"status={status}")

listed = job_in_list(pid) or {}
check(
    "GET /api/jobs has folder metadata",
    listed.get("folder_id") == fid and listed.get("folder_name") == "Power Tools" and listed.get("folder_color") == "#A855F7",
    f"folder_id={listed.get('folder_id')} name={listed.get('folder_name')} color={listed.get('folder_color')}",
)

status, detail = _req("GET", f"/api/jobs/{pid}")
jobmeta = detail.get("job", {})
check(
    "GET /api/jobs/{id} has folder metadata",
    jobmeta.get("folder_id") == fid and jobmeta.get("folder_name") == "Power Tools",
    f"folder_id={jobmeta.get('folder_id')} name={jobmeta.get('folder_name')}",
)

# 3. An unfiled job reports null folder metadata consistently
status, job = _req("POST", "/api/jobs/paste", json_body={"text": "# Unfiled Meta\n\nNothing."})
uid = job.get("job_id")
listed_u = job_in_list(uid) or {}
check(
    "unfiled job has null folder metadata",
    listed_u.get("folder_id") is None and listed_u.get("folder_name") is None,
    f"folder_id={listed_u.get('folder_id')}",
)

# 4. Upload + LLM jobs (unfiled) so we have several jobs to batch-move
status, job = _req("POST", "/api/jobs/upload-markdown", multipart={
    "fields": {"theme": "claude_clean", "strict_math": "true"},
    "files": {"file": ("batch.md", "# Batch Upload\n\nBody $y$.")},
})
up_id = job.get("job_id")
check("upload job created", status == 200 and bool(up_id), f"status={status}")

status, job = _req("POST", "/api/jobs/llm", json_body={
    "source_text": "Two-line summary of Newton's second law.",
    "title": "Batch LLM Guide",
    "mode": "quick",
    "prompt_name": "basic_study_guide",
    "provider": "deepseek",
    "model": "deepseek-chat",
})
llm_id = job.get("job_id")
check("llm job created", status == 200 and bool(llm_id), f"status={status} detail={str(job)[:120]}")

# 5. Batch move multiple jobs into the folder
batch_ids = [uid, up_id, llm_id]
status, body = _req("POST", "/api/library/jobs/move", json_body={"job_ids": batch_ids, "folder_id": fid})
check("batch move ok", status == 200 and body.get("moved") == 3, f"status={status} moved={body.get('moved')}")

_, lib = _req("GET", f"/api/library?folder_id={fid}")
in_folder = {j["id"] for j in lib.get("jobs", [])}
check("batch-moved jobs are in folder", all(j in in_folder for j in batch_ids), f"in_folder count={len(in_folder)}")

# 6. Batch unfile the same jobs
status, body = _req("POST", "/api/library/jobs/move", json_body={"job_ids": batch_ids, "folder_id": "unfiled"})
check("batch unfile ok", status == 200 and body.get("moved") == 3, f"status={status} moved={body.get('moved')}")
_, lib = _req("GET", f"/api/library?folder_id={fid}")
still = {j["id"] for j in lib.get("jobs", [])}
check("batch-unfiled jobs left folder", not any(j in still for j in batch_ids), f"remaining={len(still)}")

# 7. Library search/filter/sort still work
_, s = _req("GET", f"/api/library?q={quote('Batch LLM Guide')}")
check("library search works", any(j.get("id") == llm_id for j in s.get("jobs", [])), f"hits={len(s.get('jobs', []))}")
_, f1 = _req("GET", "/api/library?provider=deepseek&sort=oldest")
check("library filter+sort works", f1.get("sort") == "oldest" and all((j.get("provider") or "").lower() == "deepseek" for j in f1.get("jobs", [])), "")

# 8. Delete folder; jobs survive (the paste job in it becomes unfiled)
status, body = _req("DELETE", f"/api/library/folders/{fid}")
check("delete folder ok", status == 200, f"status={status} reassigned={body.get('reassigned')}")
survivor = job_in_list(pid) or {}
check("job survives folder delete", bool(survivor) and survivor.get("folder_id") is None, f"folder_id={survivor.get('folder_id')}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
