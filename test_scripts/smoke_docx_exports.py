"""Live smoke test for the DOCX export slice.

Covers: lazy DOCX availability + generation for paste/upload/LLM jobs; the
generated file is a valid .docx (OOXML zip) preserving content incl. LaTeX text;
/api/exports DOCX metadata; ZIP bundles with docx (single, multi pdf+docx+md,
skip-missing, manifest); rerender keeps docx; and PDF/MD/HTML + folder + custom
style regressions.
"""
import io
import json
import sys
import urllib.request
import urllib.error
import uuid
import zipfile

BASE = "http://localhost:8000"

SAMPLE_MD = """# Export A

A paragraph with **bold**, *italic*, and `inline code`.

- first bullet
- second bullet

1. step one
2. step two

Inline math $a+b$ and display:

$$\\int_0^1 x\\,dx = \\tfrac12$$

```python
print("hello")
```

| Col 1 | Col 2 |
| ----- | ----- |
| a     | b     |
"""


def _req(method, path, *, json_body=None, raw=False, multipart=None):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        boundary = f"----smoke{uuid.uuid4().hex}"
        parts = []
        for k, v in multipart["fields"].items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
            parts.append(f"{v}\r\n".encode())
        for k, (fname, content) in multipart["files"].items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode())
            parts.append(b"Content-Type: text/markdown\r\n\r\n")
            parts.append(content.encode() if isinstance(content, str) else content)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read()
            return (resp.status, body, resp.headers) if raw else (resp.status, json.loads(body.decode()))
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if raw:
            return exc.code, body, exc.headers
        try:
            return exc.code, json.loads(body.decode())
        except json.JSONDecodeError:
            return exc.code, {"raw": body.decode(errors="replace")}


results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def fetch_docx(job_id):
    status, body, hdrs = _req("GET", f"/api/jobs/{job_id}/artifacts/final.docx", raw=True)
    return status, body, hdrs.get("Content-Type", "")


def docx_is_valid(body):
    if not zipfile.is_zipfile(io.BytesIO(body)):
        return False, ""
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    if "word/document.xml" not in names:
        return False, ""
    return True, zf.read("word/document.xml").decode("utf-8", errors="replace")


# --- create a paste job from the rich sample ---
_, job = _req("POST", "/api/jobs/paste", json_body={"text": SAMPLE_MD})
pid1 = job.get("job_id")
check("paste job created", bool(pid1), pid1 or "")

# job_response already advertises docx (clean.md exists)
check(
    "job_response advertises final.docx url",
    bool((job.get("artifact_urls") or {}).get("final.docx")),
    f"urls={list((job.get('artifact_urls') or {}).keys())}",
)

# GET /api/jobs/{id} availability + url
_, detail = _req("GET", f"/api/jobs/{pid1}")
avail = detail.get("artifact_availability", {})
check("job detail final_docx available", avail.get("final_docx") is True, f"avail={avail.get('final_docx')}")
check("job detail has docx url", "final.docx" in (detail.get("artifact_urls") or {}), "")

# lazy generation: download docx and validate it
status, body, ctype = fetch_docx(pid1)
ok = status == 200 and ctype.startswith("application/vnd.openxmlformats")
check("download final.docx (lazy gen) ok + mime", ok, f"status={status} ctype={ctype[:40]}")
valid, document_xml = docx_is_valid(body)
check("downloaded docx is valid OOXML", valid, "")
check("docx preserves heading text", "Export A" in document_xml, "")
check("docx preserves LaTeX math as text", "a+b" in document_xml, "")
check("docx preserves code text", "hello" in document_xml, "")

# --- upload job ---
_, up = (None, None)
status, up, hdrs = _req(
    "POST", "/api/jobs/upload-markdown",
    multipart={"fields": {"theme": "claude_clean", "strict_math": "true"},
               "files": {"file": ("u.md", "# Upload Doc\n\nBody with $x^2$.")}},
    raw=True,
)
up = json.loads(up.decode())
upid = up.get("job_id")
check("upload job created", bool(upid), upid or "")
s, b, c = fetch_docx(upid)
v, _ = docx_is_valid(b)
check("upload job docx valid", s == 200 and v, f"status={s}")

# --- LLM job (deepseek configured) ---
status, llm = _req("POST", "/api/jobs/llm", json_body={
    "source_text": "Two-sentence summary of the Pythagorean theorem.",
    "title": "LLM Doc Probe", "mode": "quick", "prompt_name": "basic_study_guide",
    "provider": "deepseek", "model": "deepseek-chat",
})
llmid = llm.get("job_id")
check("llm job created", status == 200 and bool(llmid), f"status={status}")
s, b, c = fetch_docx(llmid)
v, _ = docx_is_valid(b)
check("llm job docx valid", s == 200 and v, f"status={s}")

# --- a second paste job for multi-bundle ---
_, job2 = _req("POST", "/api/jobs/paste", json_body={"text": "# Export B\n\nShort body $y$."})
pid2 = job2.get("job_id")

# --- /api/exports includes docx metadata + artifact_types ---
_, exports = _req("GET", "/api/exports")
check("exports artifact_types includes docx", "docx" in (exports.get("artifact_types") or []), f"{exports.get('artifact_types')}")
ex_jobs = {j["id"]: j for j in exports.get("jobs", [])}
exj = ex_jobs.get(pid1, {})
check(
    "exports job has docx availability + url",
    exj.get("artifact_availability", {}).get("final_docx") and "final.docx" in (exj.get("artifact_urls") or {}),
    "",
)

# --- bundle single job docx ---
status, body, hdrs = _req("POST", "/api/exports/bundle", json_body={"job_ids": [pid1], "artifacts": ["docx"]}, raw=True)
ok = status == 200 and zipfile.is_zipfile(io.BytesIO(body))
check("single docx bundle returns zip", ok, f"status={status}")
if ok:
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    manifest = json.loads(zf.read("manifest.json"))
    check("bundle contains one .docx", sum(1 for n in names if n.endswith("final.docx")) == 1, f"names={names}")
    check("manifest records docx included", "docx" in manifest["jobs"][0].get("included", []), f"{manifest['jobs'][0]}")

# --- bundle multi: pdf + docx + markdown ---
status, body, hdrs = _req(
    "POST", "/api/exports/bundle",
    json_body={"job_ids": [pid1, pid2], "artifacts": ["pdf", "docx", "markdown"]}, raw=True,
)
check("multi pdf+docx+md bundle ok", status == 200, f"status={status}")
if status == 200:
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    pdfs = sum(1 for n in names if n.endswith("final.pdf"))
    docxs = sum(1 for n in names if n.endswith("final.docx"))
    mds = sum(1 for n in names if n.endswith("clean.md"))
    check("multi bundle has 2 pdf + 2 docx + 2 md", pdfs == 2 and docxs == 2 and mds == 2, f"pdf={pdfs} docx={docxs} md={mds}")

# --- skip-missing docx (unknown job) ---
status, body, hdrs = _req(
    "POST", "/api/exports/bundle",
    json_body={"job_ids": [pid1, "nonexistent-job"], "artifacts": ["docx"]}, raw=True,
)
check("bundle with unknown job still ok", status == 200, f"status={status}")
if status == 200:
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(body)).read("manifest.json"))
    by_id = {e.get("job_id"): e for e in manifest.get("jobs", [])}
    miss = by_id.get("nonexistent-job", {})
    check("manifest marks unknown job docx skipped", miss.get("found") is False and "docx" in miss.get("skipped", []), f"{miss}")

# --- rerender keeps docx in sync ---
status, rr = _req("POST", f"/api/jobs/{pid1}/rerender", json_body={})
check("rerender ok", status == 200 and rr.get("status") == "done", f"status={status}")
s, b, c = fetch_docx(pid1)
v, _ = docx_is_valid(b)
check("docx still valid after rerender", s == 200 and v, f"status={s}")

# --- regressions: pdf/md/html artifacts ---
for name, expect_ctype in [("final.pdf", "application/pdf"), ("clean.md", "text/markdown"), ("final.html", "text/html")]:
    s, b, h = _req("GET", f"/api/jobs/{pid1}/artifacts/{name}", raw=True)
    check(f"artifact {name} still downloads", s == 200 and len(b) > 0, f"status={s}")

# --- regression: library folder assignment ---
_, folder = _req("POST", "/api/library/folders", json_body={"name": "Docx Smoke", "color": "#60A5FA"})
fid = folder.get("id")
_, fjob = _req("POST", "/api/jobs/paste", json_body={"text": "# Folder probe\n\nx", "folder_id": fid})
_, lib = _req("GET", f"/api/library?folder_id={fid}")
check("folder assignment still works", any(j["id"] == fjob.get("job_id") for j in lib.get("jobs", [])), "")

# --- regression: custom style LLM generation ---
status, style = _req("POST", "/api/styles", json_body={
    "name": "Smoke Outline Style",
    "description": "smoke",
    "content": "# {title}\n\nMode: {mode}\nMake a concise outline.\n\n{source}",
})
sid = style.get("id")
check("custom style created", status == 200 and bool(sid), f"status={status} id={sid}")
status, cjob = _req("POST", "/api/jobs/llm", json_body={
    "source_text": "Summarize Newton's laws.", "title": "Custom Style Probe", "mode": "quick",
    "prompt_name": sid, "provider": "deepseek", "model": "deepseek-chat",
})
check("custom-style LLM generation works", status == 200 and cjob.get("status") == "done", f"status={status} jobstatus={cjob.get('status')}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
