"""Live smoke test for the Exports Center slice.

Verifies: GET /api/exports shape (artifact availability + urls + folder/style);
batch ZIP bundle for one and many jobs; skip-missing-artifact handling; that the
zip contains manifest.json + expected files; the rerender endpoint; and that
paste/upload/LLM generation still work.
"""
import io
import json
import sys
import urllib.request
import urllib.error
import uuid
import zipfile

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
            if raw:
                return resp.status, body, resp.headers
            return resp.status, json.loads(body.decode())
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


def paste(text, folder_id=None):
    body = {"text": text}
    if folder_id:
        body["folder_id"] = folder_id
    _, job = _req("POST", "/api/jobs/paste", json_body=body)
    return job.get("job_id")


# Make two fresh paste jobs (both produce pdf + clean.md + html + validation)
pid1 = paste("# Export A\n\nInline $a+b$ and a line.")
pid2 = paste("# Export B\n\nDisplay $$\\int_0^1 x\\,dx = \\tfrac12$$.")
check("two paste jobs created", bool(pid1 and pid2), f"{pid1}, {pid2}")

# 1. GET /api/exports shape
status, exports = _req("GET", "/api/exports")
jobs = {j["id"]: j for j in exports.get("jobs", [])}
ja = jobs.get(pid1, {})
has_shape = (
    status == 200
    and isinstance(exports.get("folders"), list)
    and exports.get("artifact_types")
    and "artifact_availability" in ja
    and "artifact_urls" in ja
    and "folder_id" in ja
)
check("GET /api/exports shape", has_shape, f"artifact_types={exports.get('artifact_types')}")
check(
    "export job exposes pdf availability + url",
    bool(ja.get("artifact_availability", {}).get("final_pdf")) and "final.pdf" in (ja.get("artifact_urls") or {}),
    f"avail={ja.get('artifact_availability', {}).get('final_pdf')}",
)
check(
    "no filesystem paths leaked",
    not any(k in ja for k in ("source_path", "input_path", "raw_md", "clean_md", "final_pdf")),
    "",
)

# 2. Bundle a single job (PDF only)
status, body, hdrs = _req("POST", "/api/exports/bundle", json_body={"job_ids": [pid1], "artifacts": ["pdf"]}, raw=True)
ctype = hdrs.get("Content-Type", "")
is_zip = status == 200 and zipfile.is_zipfile(io.BytesIO(body))
check("single-job PDF bundle returns zip", is_zip, f"status={status} ctype={ctype}")
if is_zip:
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    manifest = json.loads(zf.read("manifest.json"))
    check("zip has manifest.json", "manifest.json" in names, "")
    check("zip contains one pdf", sum(1 for n in names if n.endswith("final.pdf")) == 1, f"names={names}")
    check("manifest files_included == 1", manifest.get("files_included") == 1, f"manifest={manifest.get('files_included')}")

# 3. Bundle multiple jobs, PDF + Markdown
status, body, hdrs = _req(
    "POST", "/api/exports/bundle",
    json_body={"job_ids": [pid1, pid2], "artifacts": ["pdf", "markdown"]}, raw=True,
)
check("multi-job pdf+md bundle ok", status == 200, f"status={status}")
if status == 200:
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    pdfs = sum(1 for n in names if n.endswith("final.pdf"))
    mds = sum(1 for n in names if n.endswith("clean.md"))
    check("multi bundle has 2 pdf + 2 md", pdfs == 2 and mds == 2, f"pdf={pdfs} md={mds} names={names}")
    manifest = json.loads(zf.read("manifest.json"))
    check("manifest lists both jobs", len(manifest.get("jobs", [])) == 2, f"jobs={len(manifest.get('jobs', []))}")

# 4. Skip-missing: mix a real job with an unknown id -> unknown is skipped, real included
status, body, hdrs = _req(
    "POST", "/api/exports/bundle",
    json_body={"job_ids": [pid1, "nonexistent-job-xyz"], "artifacts": ["pdf"]}, raw=True,
)
check("bundle with one unknown job still ok", status == 200, f"status={status}")
if status == 200:
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(body)).read("manifest.json"))
    by_id = {e.get("job_id"): e for e in manifest.get("jobs", [])}
    real = by_id.get(pid1, {})
    missing = by_id.get("nonexistent-job-xyz", {})
    check(
        "manifest records included + skipped",
        "pdf" in real.get("included", []) and missing.get("found") is False and "pdf" in missing.get("skipped", []),
        f"real={real.get('included')} missing_found={missing.get('found')}",
    )

# 5. Bundle where nothing is available (only an unknown job) -> clear 404
status, body = _req("POST", "/api/exports/bundle", json_body={"job_ids": ["nonexistent-job-xyz"], "artifacts": ["pdf"]})
check("no-available-artifact bundle returns 404", status == 404, f"status={status} detail={str(body)[:90]}")

# 6. Validation guards
status, body = _req("POST", "/api/exports/bundle", json_body={"job_ids": [pid1], "artifacts": ["exe"]})
check("invalid artifact type rejected", status == 400, f"status={status}")
status, body = _req("POST", "/api/exports/bundle", json_body={"job_ids": [], "artifacts": ["pdf"]})
check("empty job_ids rejected", status == 400, f"status={status}")

# 7. Rerender endpoint regenerates pdf/html and keeps status done
status, body = _req("POST", f"/api/jobs/{pid2}/rerender", json_body={})
check("rerender ok", status == 200 and body.get("status") == "done", f"status={status} jobstatus={body.get('status')}")
check("rerender keeps pdf artifact", bool((body.get("artifact_urls") or {}).get("final.pdf")), "")

# 8. Generation regressions: upload + LLM still work
import uuid as _uuid  # noqa
boundary = f"----smoke{uuid.uuid4().hex}"
parts = []
for k, v in {"theme": "claude_clean", "strict_math": "true"}.items():
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
    parts.append(f"{v}\r\n".encode())
parts.append(f"--{boundary}\r\n".encode())
parts.append('Content-Disposition: form-data; name="file"; filename="up.md"\r\n'.encode())
parts.append(b"Content-Type: text/markdown\r\n\r\n# Upload regression\n\nBody $z$.\r\n")
parts.append(f"--{boundary}--\r\n".encode())
req = urllib.request.Request(
    f"{BASE}/api/jobs/upload-markdown",
    data=b"".join(parts),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    up = json.loads(resp.read().decode())
check("upload generation still works", up.get("status") == "done", f"status={up.get('status')}")

status, llm = _req("POST", "/api/jobs/llm", json_body={
    "source_text": "One-line summary of Ohm's law.",
    "title": "Exports LLM Probe",
    "mode": "quick",
    "prompt_name": "basic_study_guide",
    "provider": "deepseek",
    "model": "deepseek-chat",
})
check("llm generation still works", status == 200 and llm.get("status") == "done", f"status={status} jobstatus={llm.get('status')}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
