"""Live smoke test for the 'Save generated guides to a folder' slice.

Runs against the container on :8000. Verifies that paste/upload/LLM jobs created
with a folder_id land in that folder, that invalid folders are rejected, and that
deleting a folder leaves the jobs intact (just unfiled).
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

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
            parts.append(
                f'Content-Disposition: form-data; name="{key}"; filename="{fname}"\r\n'.encode()
            )
            parts.append(b"Content-Type: text/markdown\r\n\r\n")
            parts.append(content if isinstance(content, bytes) else content.encode())
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
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# 1. Create a folder
status, folder = _req("POST", "/api/library/folders", json_body={"name": "Smoke Folder", "color": "#22D3EE"})
check("create folder", status == 200 and "id" in folder, f"status={status} id={folder.get('id')}")
folder_id = folder.get("id")


def folder_of(job_id):
    _, lib = _req("GET", "/api/library")
    for job in lib.get("jobs", []):
        if job.get("id") == job_id:
            return job.get("folder_id")
    return "MISSING"


# 2. Paste job into folder
status, job = _req("POST", "/api/jobs/paste", json_body={
    "text": "# Smoke Paste\n\nInline $a^2+b^2=c^2$ and a sentence.",
    "folder_id": folder_id,
})
paste_id = job.get("job_id")
check("paste job created", status == 200 and bool(paste_id), f"status={status}")
check("paste job assigned to folder", folder_of(paste_id) == folder_id, f"folder={folder_of(paste_id)}")

# 3. Upload-markdown job into folder
status, job = _req("POST", "/api/jobs/upload-markdown", multipart={
    "fields": {"theme": "claude_clean", "strict_math": "true", "folder_id": folder_id},
    "files": {"file": ("smoke.md", "# Smoke Upload\n\nA short markdown body with $x$.")},
})
upload_id = job.get("job_id")
check("upload job created", status == 200 and bool(upload_id), f"status={status}")
check("upload job assigned to folder", folder_of(upload_id) == folder_id, f"folder={folder_of(upload_id)}")

# 4. LLM job into folder (providers are configured)
status, job = _req("POST", "/api/jobs/llm", json_body={
    "source_text": "Summarize the Pythagorean theorem in two bullet points.",
    "title": "Smoke LLM Guide",
    "mode": "quick",
    "prompt_name": "basic_study_guide",
    "provider": "deepseek",
    "model": "deepseek-chat",
    "folder_id": folder_id,
})
llm_id = job.get("job_id")
check("llm job created", status == 200 and bool(llm_id), f"status={status} detail={str(job)[:160]}")
if llm_id:
    check("llm job assigned to folder", folder_of(llm_id) == folder_id, f"folder={folder_of(llm_id)}")

# 5. Unfiled job (no folder_id) stays unfiled
status, job = _req("POST", "/api/jobs/paste", json_body={"text": "# Unfiled Smoke\n\nNo folder here."})
unfiled_id = job.get("job_id")
check("unfiled paste created", status == 200 and bool(unfiled_id), f"status={status}")
check("unfiled job is unfiled", folder_of(unfiled_id) == "unfiled", f"folder={folder_of(unfiled_id)}")

# 6. Reject invalid / nonexistent folder
status, body = _req("POST", "/api/jobs/paste", json_body={"text": "x", "folder_id": "does-not-exist"})
check("nonexistent folder rejected", status == 404, f"status={status} detail={str(body)[:120]}")

status, body = _req("POST", "/api/jobs/paste", json_body={"text": "x", "folder_id": "all"})
check("virtual 'all' rejected", status == 400, f"status={status} detail={str(body)[:120]}")

# 7. Deleting the folder leaves jobs intact (they become unfiled)
status, body = _req("DELETE", f"/api/library/folders/{folder_id}")
check("delete folder ok", status == 200, f"status={status} reassigned={body.get('reassigned')}")
# jobs still exist
_, jdetail = _req("GET", f"/api/jobs/{paste_id}")
check("paste job survives folder delete", bool(jdetail.get("job")), f"status pulled job={bool(jdetail.get('job'))}")
check("paste job now unfiled", folder_of(paste_id) == "unfiled", f"folder={folder_of(paste_id)}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok, _ in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
