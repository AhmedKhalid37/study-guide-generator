"""End-to-end release smoke test for the Study Guide Generator.

Runs against a live app on :8000 (override with SMOKE_BASE_URL). Exercises the
major user flows and asserts no API keys leak. Provider-dependent flows (LLM,
outline draft, attachments) are SKIPPED cleanly when no provider is configured.

    python test_scripts/smoke_release.py
"""
import io
import json
import os
import re
import sys
import urllib.request
import urllib.error
import uuid
import zipfile

BASE = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")

# Field names that would indicate a leaked credential. Note: a bare "key" is NOT
# included — it's a legitimate non-secret field (e.g. an artifact's availability
# key like "final_pdf"). Actual secret values are also caught by KEYLIKE below.
SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"^(sk-|sk_)[A-Za-z0-9_\-]{16,}$")  # provider key value => likely a credential

results = []  # (name, status) where status in {"PASS","FAIL","SKIP"}


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL"))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def skip(name, detail=""):
    results.append((name, "SKIP"))
    print(f"[SKIP] {name}" + (f" — {detail}" if detail else ""))


def _req(method, path, *, json_body=None, raw=False, multipart=None):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        boundary = f"----rel{uuid.uuid4().hex}"
        parts = []
        for k, v in multipart.get("fields", {}).items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
            parts.append(f"{v}\r\n".encode())
        for k, (fname, content, ctype) in multipart.get("files", {}).items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode())
            parts.append(f"Content-Type: {ctype}\r\n\r\n".encode())
            parts.append(content.encode() if isinstance(content, str) else content)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            body = resp.read()
            if raw:
                return resp.status, body, resp.headers.get("Content-Type", "")
            return resp.status, json.loads(body.decode())
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if raw:
            return exc.code, body, exc.headers.get("Content-Type", "")
        try:
            return exc.code, json.loads(body.decode())
        except json.JSONDecodeError:
            return exc.code, {"raw": body.decode(errors="replace")}


def find_leak(node, path="root"):
    """Return a description of the first key/credential-looking leak, else None."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key}"
            hit = find_leak(value, f"{path}.{key}")
            if hit:
                return hit
    elif isinstance(node, list):
        for i, item in enumerate(node):
            hit = find_leak(item, f"{path}[{i}]")
            if hit:
                return hit
    elif isinstance(node, str):
        if node.startswith("sk-") or KEYLIKE.match(node):
            return f"{path} (value looks like a credential)"
    return None


def artifact_ok(job_id, name):
    status, body, _ = _req("GET", f"/api/jobs/{job_id}/artifacts/{name}", raw=True)
    return status == 200 and len(body) > 0


# ── 1. core endpoints + leak scan ───────────────────────────────────────────
status, health = _req("GET", "/api/health")
check("GET /api/health", status == 200 and health.get("ok") is True, f"status={status}")

status, options = _req("GET", "/api/options")
check("GET /api/options", status == 200 and "provider_details" in options, f"status={status}")
leak = find_leak(options)
check("no key leakage in /api/options", leak is None, leak or "")

status, styles = _req("GET", "/api/styles")
check("GET /api/styles", status == 200 and ("builtin" in styles or "custom" in styles), f"status={status}")
leak = find_leak(styles)
check("no key leakage in /api/styles", leak is None, leak or "")

status, library = _req("GET", "/api/library")
check("GET /api/library", status == 200 and "folders" in library and "jobs" in library, f"status={status}")

status, exports = _req("GET", "/api/exports")
check("GET /api/exports", status == 200 and "artifact_types" in exports, f"status={status}")

configured = [p for p in (options.get("provider_details") or []) if p.get("configured")]
provider = configured[0] if configured else None
model = (provider or {}).get("default_model") or ((provider or {}).get("available_models") or [None])[0]

# ── 2. paste → all artifacts ─────────────────────────────────────────────────
status, paste = _req("POST", "/api/jobs/paste", json_body={"text": "# Release Paste\n\nInline $a^2+b^2=c^2$ and text."})
pid = paste.get("job_id")
check("paste → done", status == 200 and paste.get("status") == "done", f"status={status}")
check("paste artifacts (PDF/HTML/MD/DOCX)",
      all(artifact_ok(pid, n) for n in ["final.pdf", "final.html", "clean.md", "final.docx"]), "")

# ── 3. upload markdown → all artifacts ───────────────────────────────────────
status, up = _req("POST", "/api/jobs/upload-markdown", multipart={
    "fields": {"theme": "claude_clean", "strict_math": "true"},
    "files": {"file": ("rel.md", "# Release Upload\n\nA body with $x$.", "text/markdown")},
})
uid = up.get("job_id")
check("upload → done", status == 200 and up.get("status") == "done", f"status={status}")
check("upload artifacts (PDF/HTML/MD/DOCX)",
      all(artifact_ok(uid, n) for n in ["final.pdf", "final.html", "clean.md", "final.docx"]), "")

# ── 4. job details metadata ──────────────────────────────────────────────────
status, detail = _req("GET", f"/api/jobs/{pid}")
jm = detail.get("job", {})
check("job details metadata", status == 200 and bool(jm.get("id")) and "artifact_availability" in detail
      and "outline_enabled" in jm, "")
check("no key leakage in job details", find_leak(detail) is None, "")

# ── 5. save-to-folder + library move/batch ───────────────────────────────────
status, folder = _req("POST", "/api/library/folders", json_body={"name": "Release Smoke", "color": "#60A5FA"})
fid = folder.get("id")
check("create folder", status == 200 and bool(fid), f"status={status}")

status, fjob = _req("POST", "/api/jobs/paste", json_body={"text": "# Filed\n\nx", "folder_id": fid})
filed_id = fjob.get("job_id")
_, lib = _req("GET", f"/api/library?folder_id={fid}")
check("save-to-folder", any(j["id"] == filed_id for j in lib.get("jobs", [])), "")

status, mv = _req("POST", f"/api/library/jobs/{pid}/move", json_body={"folder_id": fid})
check("single move", status == 200, f"status={status}")
status, batch = _req("POST", "/api/library/jobs/move", json_body={"job_ids": [pid, filed_id], "folder_id": "unfiled"})
check("batch move (to unfiled)", status == 200 and batch.get("moved") == 2, f"moved={batch.get('moved')}")

# ── 6. exports ZIP bundle ────────────────────────────────────────────────────
status, body, ctype = _req("POST", "/api/exports/bundle",
                           json_body={"job_ids": [pid, uid], "artifacts": ["pdf", "docx", "markdown"]}, raw=True)
ok_zip = status == 200 and zipfile.is_zipfile(io.BytesIO(body))
check("exports ZIP bundle", ok_zip, f"status={status}")
if ok_zip:
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    check("ZIP has manifest.json", "manifest.json" in names, "")
    check("ZIP contains pdf+docx+md",
          any(n.endswith("final.pdf") for n in names) and any(n.endswith("final.docx") for n in names)
          and any(n.endswith("clean.md") for n in names), f"names={names[:6]}")

# ── 7. custom style create / (use) / delete ──────────────────────────────────
status, style = _req("POST", "/api/styles", json_body={
    "name": "Release Smoke Style", "description": "smoke",
    "content": "# {title}\n\nMode: {mode}\nWrite clearly.\n\n{source}",
})
sid = style.get("id")
check("custom style create", status == 200 and bool(sid), f"status={status}")

# ── 8. rerender (works on the paste job; no provider needed) ─────────────────
status, rr = _req("POST", f"/api/jobs/{pid}/rerender", json_body={})
check("rerender endpoint", status == 200 and rr.get("status") == "done", f"status={status}")

# ── 9. provider-dependent flows (skip cleanly if unconfigured) ───────────────
if provider and model:
    pname = provider.get("id")
    status, llm = _req("POST", "/api/jobs/llm", json_body={
        "source_text": "Summarize the Pythagorean theorem.", "title": "Release LLM",
        "prompt_name": "basic_study_guide", "provider": pname, "model": model,
    })
    llm_id = llm.get("job_id")
    check("LLM generation → done", status == 200 and llm.get("status") == "done", f"status={status}")

    status, custom = _req("POST", "/api/jobs/llm", json_body={
        "source_text": "Summarize Ohm's law.", "title": "Release Custom Style",
        "prompt_name": sid or "basic_study_guide", "provider": pname, "model": model,
    })
    check("custom-style LLM use", status == 200 and custom.get("status") == "done", f"status={status}")

    status, att = _req("POST", "/api/jobs/llm", multipart={
        "fields": {"source_text": "Use the attached note.", "title": "Release Attach",
                   "prompt_name": "basic_study_guide", "provider": pname, "model": model},
        "files": {"attachments": ("note.txt", "Key fact: V = I * R.", "text/plain")},
    })
    check("attachment (.txt) generation",
          status == 200 and att.get("status") == "done" and (att.get("attachment_summary") or {}).get("count", 0) >= 1,
          f"status={status}")

    status, gen = _req("POST", "/api/outline/generate", json_body={
        "source_text": "Photosynthesis basics.", "title": "Outline", "provider": pname, "model": model})
    secs = gen.get("sections", [])
    check("outline generation", status == 200 and len(secs) >= 3, f"n={len(secs)}")

    titles = ["Alpha", "Bravo", "Charlie"]
    status, oj = _req("POST", "/api/jobs/llm", json_body={
        "source_text": "Topic: vectors.", "title": "Release Outline Use",
        "prompt_name": "basic_study_guide", "provider": pname, "model": model,
        "outline": {"enabled": True, "sections": [{"title": t, "instructions": ""} for t in titles]},
    })
    oid = oj.get("job_id")
    ok_done = status == 200 and oj.get("status") == "done" and oj.get("outline_enabled") is True
    md = ""
    if oid:
        s, b, _ = _req("GET", f"/api/jobs/{oid}/artifacts/clean.md", raw=True)
        md = b.decode("utf-8", errors="replace") if s == 200 else ""
    pos = [md.find(t) for t in titles]
    check("outline use → followed in order", ok_done and all(p != -1 for p in pos) and pos == sorted(pos), f"pos={pos}")
else:
    for name in ["LLM generation → done", "custom-style LLM use", "attachment (.txt) generation",
                 "outline generation", "outline use → followed in order"]:
        skip(name, "no provider configured")

# ── 10. cleanup the smoke style ──────────────────────────────────────────────
if sid:
    status, _ = _req("DELETE", f"/api/styles/{sid}")
    check("custom style delete", status == 200, f"status={status}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, s in results if s == "PASS")
failed = sum(1 for _, s in results if s == "FAIL")
skipped = sum(1 for _, s in results if s == "SKIP")
print(f"{passed} passed, {failed} failed, {skipped} skipped")
sys.exit(1 if failed else 0)
