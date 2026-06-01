"""Live smoke test for the 'Library bulk actions (backend)' slice.

Verifies the three new bulk endpoints — POST /api/jobs/bulk/delete,
POST /api/jobs/bulk/restore, POST /api/jobs/bulk/move — including:
  * partial-success contract (ok / skipped / error + ok_count/fail_count),
  * bulk soft-delete routes through the trash (jobs/.trash/), never hard-delete,
  * bulk restore brings jobs back out of the trash,
  * bulk move reuses the existing folder model (folder_id), unknown folder 404s,
  * path-traversal / malformed ids are rejected as errors and never crash.

Reuses paste jobs (no LLM/provider needed) so it is fast and deterministic.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def _req(method, path, *, json_body=None):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
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


def status_of(body, jid):
    for r in body.get("results", []):
        if r.get("id") == jid:
            return r.get("status")
    return None


def job_in_active(job_id):
    _, listing = _req("GET", "/api/jobs?limit=200")
    return any(j.get("id") == job_id for j in listing.get("jobs", []))


def job_in_trash(job_id):
    _, listing = _req("GET", "/api/jobs/trash")
    return any(j.get("id") == job_id for j in listing.get("jobs", []))


# Create two throwaway paste jobs via the normal API path.
status, j = _req("POST", "/api/jobs/paste", json_body={"text": "# Bulk One\n\nBody $a$."})
j1 = j.get("job_id")
check("paste job 1 created", status == 200 and bool(j1), f"status={status}")

status, j = _req("POST", "/api/jobs/paste", json_body={"text": "# Bulk Two\n\nBody $b$."})
j2 = j.get("job_id")
check("paste job 2 created", status == 200 and bool(j2), f"status={status}")

BOGUS = "no_such_job_id_xyz"

# 1. Bulk delete: two valid ids + one bogus id (partial success)
status, body = _req("POST", "/api/jobs/bulk/delete", json_body={"ids": [j1, j2, BOGUS]})
check(
    "bulk delete partial success",
    status == 200
    and status_of(body, j1) == "ok"
    and status_of(body, j2) == "ok"
    and status_of(body, BOGUS) == "error"
    and body.get("ok_count") == 2
    and body.get("fail_count") == 1,
    f"status={status} body={json.dumps(body)[:160]}",
)
check(
    "deleted jobs left active list",
    not job_in_active(j1) and not job_in_active(j2),
    "",
)
check(
    "deleted jobs are in trash (.trash)",
    job_in_trash(j1) and job_in_trash(j2),
    "",
)

# 2. Re-delete an already-trashed id -> skipped
status, body = _req("POST", "/api/jobs/bulk/delete", json_body={"ids": [j1]})
check("re-delete already-trashed is skipped", status == 200 and status_of(body, j1) == "skipped", f"body={json.dumps(body)[:120]}")

# 3. Bulk restore the two valid ids
status, body = _req("POST", "/api/jobs/bulk/restore", json_body={"ids": [j1, j2]})
check(
    "bulk restore ok",
    status == 200 and status_of(body, j1) == "ok" and status_of(body, j2) == "ok" and body.get("ok_count") == 2,
    f"body={json.dumps(body)[:160]}",
)
check("restored jobs back in active list", job_in_active(j1) and job_in_active(j2), "")
check("restored jobs gone from trash", not job_in_trash(j1) and not job_in_trash(j2), "")

# 4. Restore an id that is not trashed (already active) -> skipped
status, body = _req("POST", "/api/jobs/bulk/restore", json_body={"ids": [j1]})
check("restore non-trashed is skipped", status == 200 and status_of(body, j1) == "skipped", f"body={json.dumps(body)[:120]}")

# 5. Bulk move into a folder
status, folder = _req("POST", "/api/library/folders", json_body={"name": "Bulk Move", "color": "#22C55E"})
fid = folder.get("id")
check("create destination folder", status == 200 and bool(fid), f"status={status}")

status, body = _req("POST", "/api/jobs/bulk/move", json_body={"ids": [j1, j2], "folder_id": fid})
check(
    "bulk move ok",
    status == 200 and status_of(body, j1) == "ok" and status_of(body, j2) == "ok" and body.get("ok_count") == 2,
    f"body={json.dumps(body)[:160]}",
)
_, lib = _req("GET", f"/api/library?folder_id={fid}")
in_folder = {jj["id"] for jj in lib.get("jobs", [])}
check("bulk-moved jobs are in folder", j1 in in_folder and j2 in in_folder, f"in_folder={len(in_folder)}")

# 6. Bulk move with a bad id + good id -> partial success
status, body = _req("POST", "/api/jobs/bulk/move", json_body={"ids": [j1, BOGUS], "folder_id": "unfiled"})
check(
    "bulk move partial (unfile + bad id)",
    status == 200 and status_of(body, j1) == "ok" and status_of(body, BOGUS) == "error",
    f"body={json.dumps(body)[:160]}",
)

# 7. Bulk move to an unknown folder -> whole request 404 (matches single-item)
status, body = _req("POST", "/api/jobs/bulk/move", json_body={"ids": [j1], "folder_id": "definitely_not_a_folder"})
check("bulk move unknown folder 404s", status == 404, f"status={status} detail={str(body)[:90]}")

# 8. Path-traversal / malformed ids must be rejected as errors, never crash,
#    and never escape the jobs tree (the guard turns them into clean errors).
trav_ids = ["../../etc/passwd", "..", "a/b", ""]
status, body = _req("POST", "/api/jobs/bulk/delete", json_body={"ids": trav_ids})
# empty id is dropped by dedupe; the rest must all be 'error' and none 'ok'.
reported = {r["id"]: r["status"] for r in body.get("results", [])}
check(
    "traversal ids rejected as errors, none ok",
    status == 200
    and body.get("ok_count") == 0
    and all(s == "error" for s in reported.values())
    and reported,
    f"reported={reported}",
)

# Cleanup: unfile then delete the folder; jobs survive.
_req("POST", "/api/jobs/bulk/move", json_body={"ids": [j1, j2], "folder_id": "unfiled"})
_req("DELETE", f"/api/library/folders/{fid}")

print("\n--- SUMMARY ---")
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
