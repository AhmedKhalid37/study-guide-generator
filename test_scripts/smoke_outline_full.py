"""Full smoke for the outline slice: multipart (attachments) outline path,
custom style + outline, save-to-folder + outline, and artifact regressions.
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

BASE = "http://localhost:8000"


def _json(method, path, body=None):
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except json.JSONDecodeError:
            return exc.code, {}


def _multipart(path, fields, files):
    boundary = f"----smoke{uuid.uuid4().hex}"
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        parts.append(f"{v}\r\n".encode())
    for k, (fname, content) in files.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode())
        parts.append(b"Content-Type: text/plain\r\n\r\n")
        parts.append(content.encode())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"{BASE}{path}", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.status, json.loads(resp.read().decode())


def clean_md(job_id):
    req = urllib.request.Request(f"{BASE}/api/jobs/{job_id}/artifacts/clean.md")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


OUTLINE = {"enabled": True, "sections": [
    {"title": "Zeta Intro", "instructions": "Set the scene."},
    {"title": "Eta Method", "instructions": "Explain the method."},
    {"title": "Theta Wrap", "instructions": "Summarize."},
]}
TITLES = [s["title"] for s in OUTLINE["sections"]]

# 1. Custom style + outline (JSON path)
status, style = _json("POST", "/api/styles", {
    "name": "Outline Smoke Style", "description": "smoke",
    "content": "# {title}\n\nMode: {mode}\nFollow instructions.\n\n{source}",
})
sid = style.get("id")
status, job = _json("POST", "/api/jobs/llm", {
    "source_text": "Topic: simple harmonic motion.", "title": "Custom+Outline",
    "prompt_name": sid, "provider": "deepseek", "model": "deepseek-chat", "outline": OUTLINE,
})
cid = job.get("job_id")
check("custom style + outline -> done", status == 200 and job.get("status") == "done", f"status={status}")
check("custom+outline meta stored", job.get("outline_enabled") is True and job.get("outline_section_count") == 3, "")
md = clean_md(cid)
pos = [md.find(t) for t in TITLES]
check("custom+outline clean.md follows order", all(p != -1 for p in pos) and pos == sorted(pos), f"pos={pos}")

# 2. Attachments + outline via multipart (outline sent as JSON form field)
status, job = _multipart(
    "/api/jobs/llm",
    fields={
        "source_text": "Use the attached note.", "title": "Attach+Outline",
        "prompt_name": "basic_study_guide", "provider": "deepseek", "model": "deepseek-chat",
        "outline": json.dumps(OUTLINE),
    },
    files={"attachments": ("note.txt", "Key fact: the period depends on mass and spring constant.")},
)
aid = job.get("job_id")
check("attachments + outline (multipart) -> done", status == 200 and job.get("status") == "done", f"status={status}")
check("multipart outline parsed + stored", job.get("outline_enabled") is True and job.get("outline_section_count") == 3,
      f"enabled={job.get('outline_enabled')} count={job.get('outline_section_count')}")
check("attachment recorded", (job.get("attachment_summary") or {}).get("count", 0) >= 1, "")
md = clean_md(aid)
pos = [md.find(t) for t in TITLES]
check("attach+outline clean.md follows order", all(p != -1 for p in pos) and pos == sorted(pos), f"pos={pos}")

# 3. Save-to-folder + outline
status, folder = _json("POST", "/api/library/folders", {"name": "Outline Folder", "color": "#34D399"})
fid = folder.get("id")
status, job = _json("POST", "/api/jobs/llm", {
    "source_text": "Topic: vectors.", "title": "Folder+Outline",
    "prompt_name": "basic_study_guide", "provider": "deepseek", "model": "deepseek-chat",
    "folder_id": fid, "outline": OUTLINE,
})
foid = job.get("job_id")
status, lib = _json("GET", f"/api/library?folder_id={fid}")
in_folder = any(j["id"] == foid for j in lib.get("jobs", []))
check("folder + outline: job in folder", in_folder, "")
lj = next((j for j in lib.get("jobs", []) if j["id"] == foid), {})
check("folder + outline: outline summary present", lj.get("outline_enabled") is True, f"{lj.get('outline_enabled')}")

# 4. Artifact regressions for an outline job (pdf/docx/html/md)
for name in ["final.pdf", "final.docx", "final.html", "clean.md"]:
    req = urllib.request.Request(f"{BASE}/api/jobs/{foid}/artifacts/{name}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            ok = resp.status == 200 and len(resp.read()) > 0
    except urllib.error.HTTPError as exc:
        ok = False
    check(f"artifact {name} works on outline job", ok, "")

# 5. Paste + upload still work
status, p = _json("POST", "/api/jobs/paste", {"text": "# Paste regression\n\nBody $x$."})
check("paste still works", status == 200 and p.get("status") == "done", f"status={status}")
status, u = _multipart("/api/jobs/upload-markdown",
                       fields={"theme": "claude_clean", "strict_math": "true"},
                       files={"file": ("u.md", "# Upload regression\n\nBody.")})
check("upload still works", status == 200 and u.get("status") == "done", f"status={status}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
