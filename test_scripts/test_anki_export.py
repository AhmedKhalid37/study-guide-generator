#!/usr/bin/env python3
"""Focused tests for Slice 53: true Anki ``.apkg`` export.

Run with:

    python test_scripts/test_anki_export.py

The core builder (``pipeline.anki_export``) is stdlib-only (sqlite3 + zipfile +
json + hashlib), so the bulk of this suite runs anywhere — no FastAPI, no
PyMuPDF/Tesseract, no provider/model/network, no genanki. A final section drives
the ``api.server`` quiz-export route directly to confirm the ``apkg`` format and
that existing CSV/anki_tsv/quizlet exports still work; that section is SKIPPED
automatically when FastAPI is not importable in host Python (run in Docker for
full coverage).

Slice 53 adds a real Anki package from already-generated quiz/flashcard items
using a deterministic deck/model scheme. It embeds only the user's own
Front/Back study text (HTML-escaped) — never paths, tokens, payloads, OCR dumps,
image bytes, data URIs, base64, model/mmproj/executable/socket paths, artifact
URLs, or internal job metadata. No images/media in the deck.
"""
from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import anki_export  # noqa: E402

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\)")
URLLIKE = re.compile(r"https?://")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


def skip(name: str, detail: str = "") -> None:
    print(f"[SKIP] {name}" + (f" - {detail}" if detail else ""))


def _open_db(apkg_bytes: bytes):
    """Return (table_names, col_row_dict, notes, cards) from an apkg's sqlite db."""
    tmp = tempfile.mkdtemp(prefix="gf_apkg_test_")
    db_path = os.path.join(tmp, "collection.anki2")
    with zipfile.ZipFile(io.BytesIO(apkg_bytes)) as zf:
        names = set(zf.namelist())
        with open(db_path, "wb") as fh:
            fh.write(zf.read("collection.anki2"))
        media = zf.read("media").decode("utf-8")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    col = dict(con.execute("SELECT * FROM col").fetchone())
    notes = [dict(r) for r in con.execute("SELECT * FROM notes")]
    cards = [dict(r) for r in con.execute("SELECT * FROM cards")]
    con.close()
    try:
        os.remove(db_path)
        os.rmdir(tmp)
    except OSError:
        pass
    return names, tables, col, notes, cards, media


SAMPLE_ITEMS = [
    {"type": "flashcards", "question": "What is mitosis?",
     "answer": "Cell division producing two identical daughter cells.",
     "topic": "Cell Biology", "difficulty": "medium"},
    {"type": "mcq", "question": "Which organelle makes ATP?",
     "options": ["A. Nucleus", "B. Mitochondrion", "C. Ribosome", "D. Golgi"],
     "answer": "B", "topic": "Cell Biology", "difficulty": "easy"},
    {"type": "true_false", "question": "DNA is double-stranded.",
     "answer": "True", "topic": "Genetics", "difficulty": "easy"},
]


def main() -> int:
    # --- 1. Builds a valid, non-empty .apkg from synthetic flashcards ----------
    pkg = anki_export.build_apkg(SAMPLE_ITEMS, job_id="job-abc", quiz_n=1, title="Bio 101")
    check("build.returns_bytes", isinstance(pkg, bytes) and len(pkg) > 0,
          f"len={len(pkg) if isinstance(pkg, bytes) else 'n/a'}")
    check("build.is_zip", pkg[:2] == b"PK", "expected ZIP local-file signature")

    names, tables, col, notes, cards, media = _open_db(pkg)
    check("zip.has_collection", "collection.anki2" in names)
    check("zip.has_media", "media" in names)
    check("zip.media_empty_map", media == "{}", f"media={media!r}")
    check("zip.no_media_files",
          not any(n not in ("collection.anki2", "media") for n in names),
          f"unexpected entries: {names - {'collection.anki2', 'media'}}")

    # --- 2. Schema-11 collection structure ------------------------------------
    for t in ("col", "notes", "cards", "revlog", "graves"):
        check(f"schema.table_{t}", t in tables)
    check("schema.ver_11", col.get("ver") == 11, f"ver={col.get('ver')}")

    # one note + one card per well-formed item (all 3 sample items are valid)
    check("content.note_count", len(notes) == 3, f"notes={len(notes)}")
    check("content.card_count", len(cards) == 3, f"cards={len(cards)}")

    # fields joined by 0x1f into Front + Back (note ids are content-independent,
    # so match by content rather than row order).
    check("content.field_separator", all("\x1f" in n["flds"] for n in notes))
    fronts = [n["flds"].split("\x1f", 1)[0] for n in notes]
    backs = [n["flds"].split("\x1f", 1)[1] for n in notes]
    check("content.front_text", any("mitosis" in f.lower() for f in fronts))
    check("content.back_text", any("daughter cells" in b.lower() for b in backs))

    # mcq: options listed on front, full correct option resolved on back
    mcq_idx = next((i for i, f in enumerate(fronts) if "organelle" in f.lower()), None)
    check("content.mcq_found", mcq_idx is not None)
    if mcq_idx is not None:
        check("content.mcq_options_on_front", "Mitochondrion" in fronts[mcq_idx])
        check("content.mcq_answer_resolved", "Mitochondrion" in backs[mcq_idx],
              f"back={backs[mcq_idx]!r}")

    # --- 3. Deterministic deck/model ids across repeated exports --------------
    pkg2 = anki_export.build_apkg(SAMPLE_ITEMS, job_id="job-abc", quiz_n=1, title="Bio 101")
    check("determinism.byte_identical", pkg == pkg2, "re-export should be byte-stable")

    _, _, col_a, notes_a, cards_a, _ = _open_db(pkg)
    decks_a = json.loads(col_a["decks"])
    models_a = json.loads(col_a["models"])
    check("determinism.model_id_constant", str(anki_export.MODEL_ID) in models_a)
    expected_deck = str(anki_export.deck_id_for("job-abc", 1))
    check("determinism.deck_id_stable", expected_deck in decks_a,
          f"decks={list(decks_a)}")
    check("determinism.default_deck_present", "1" in decks_a)
    # different job -> different deck id (no churn collisions)
    pkg_other = anki_export.build_apkg(SAMPLE_ITEMS, job_id="job-xyz", quiz_n=1, title="Bio 101")
    _, _, col_o, _, _, _ = _open_db(pkg_other)
    decks_o = json.loads(col_o["decks"])
    check("determinism.per_job_deck",
          set(decks_o) != set(decks_a),
          "distinct jobs should yield distinct deck ids")
    # stable note GUIDs across re-export (so Anki updates, not duplicates)
    guids_a = [n["guid"] for n in notes_a]
    _, _, _, notes_b, _, _ = _open_db(pkg2)
    guids_b = [n["guid"] for n in notes_b]
    check("determinism.guids_stable", guids_a == guids_b and len(set(guids_a)) == 3)

    # --- 4. Malformed / empty cards skipped safely ----------------------------
    messy = [
        {"type": "flashcards", "question": "Good Q", "answer": "Good A"},
        {"type": "flashcards", "question": "", "answer": "missing front"},
        {"type": "flashcards", "question": "missing back", "answer": "   "},
        "not-a-dict",
        {"type": "flashcards"},  # no question/answer
        None,
    ]
    cards_list, skipped = anki_export.normalize_cards(messy)
    check("malformed.kept_one", len(cards_list) == 1, f"kept={len(cards_list)}")
    check("malformed.counts_closed_vocab",
          set(skipped) == {anki_export.SKIP_EMPTY, anki_export.SKIP_MALFORMED})
    check("malformed.empty_counted", skipped[anki_export.SKIP_EMPTY] == 3,
          f"empty={skipped[anki_export.SKIP_EMPTY]}")
    check("malformed.malformed_counted", skipped[anki_export.SKIP_MALFORMED] == 2,
          f"malformed={skipped[anki_export.SKIP_MALFORMED]}")
    messy_pkg = anki_export.build_apkg(messy, job_id="job-m", quiz_n=2, title="X")
    _, _, _, messy_notes, _, _ = _open_db(messy_pkg)
    check("malformed.build_skips", len(messy_notes) == 1)

    # --- 5. No cards -> valid empty-deck package (no exception, matches route) -
    empty_pkg = anki_export.build_apkg([], job_id="job-e", quiz_n=3, title="Empty")
    check("empty.returns_valid_zip", isinstance(empty_pkg, bytes) and empty_pkg[:2] == b"PK")
    _, _, _, empty_notes, empty_cards, _ = _open_db(empty_pkg)
    check("empty.no_notes", len(empty_notes) == 0)
    check("empty.no_cards", len(empty_cards) == 0)

    # --- 6. No-leak scan: internal ids / paths never embedded in the package --
    # The job_id is a path-shaped internal value; it must only seed derived
    # numeric ids/guids/filename and must NEVER appear inside the package, and
    # the package's structural JSON must carry no path/token/url/data-uri.
    leak_items = [{"type": "flashcards", "question": "normal study q",
                   "answer": "normal study a"}]
    leak_pkg = anki_export.build_apkg(
        leak_items, job_id="/home/secret/job-id-7f3a", quiz_n=9, title="Plain Title",
    )
    _, _, leak_col, leak_notes, _, leak_media = _open_db(leak_pkg)
    scan_blob = json.dumps(leak_col) + leak_media + json.dumps(leak_notes)
    check("noleak.no_keys", not KEYLIKE.search(scan_blob))
    check("noleak.no_paths", not PATHLIKE.search(scan_blob),
          "filesystem path leaked into package")
    check("noleak.no_urls", not URLLIKE.search(scan_blob))
    check("noleak.no_datauri", not DATAURI.search(scan_blob))
    check("noleak.no_socket", not SOCKETLIKE.search(scan_blob))
    # The job_id is used only to derive numeric ids/guids/filename, never embedded.
    check("noleak.job_id_not_embedded", "/home/secret/job-id-7f3a" not in scan_blob)
    # filename is path-safe (no directory components, no raw job path)
    fname = anki_export.apkg_filename("/home/secret/job-id", 9)
    check("noleak.filename_safe",
          "/" not in fname and "\\" not in fname and fname.endswith(".apkg"),
          f"filename={fname}")
    # deck name sanitized: subdeck-prefixed, no path/token characters
    deck_name = anki_export.deck_name_for("Guide /etc/passwd ::token")
    check("noleak.deck_name_prefixed", deck_name.startswith("GuideForge::"))
    check("noleak.deck_name_no_slash", "/" not in deck_name, f"deck={deck_name}")

    # --- 7. Module is stdlib-only (no third-party/genanki/network imports) ----
    src = Path(anki_export.__file__).read_text(encoding="utf-8")
    import_lines = [ln.strip() for ln in src.splitlines()
                    if ln.strip().startswith(("import ", "from "))]
    joined_imports = "\n".join(import_lines)
    check("deps.no_genanki", "genanki" not in joined_imports,
          "module must not import genanki")
    check("deps.no_network",
          not re.search(r"\b(requests|urllib|socket|httpx|http\.client)\b", joined_imports),
          f"network import found: {joined_imports}")
    check("deps.no_image_libs",
          not re.search(r"\b(PIL|fitz|pytesseract|cv2)\b", joined_imports))

    # --- 8. Route-level checks (CSV preserved + apkg format) -------------------
    try:
        from fastapi import HTTPException  # noqa: F401

        from api import server
    except Exception as exc:  # pragma: no cover - host without FastAPI
        skip("route.*", f"FastAPI unavailable: {exc}")
        return _summary()

    check("route.apkg_in_valid_formats", "apkg" in server.VALID_EXPORT_FORMATS)
    for legacy in ("csv", "anki_tsv", "quizlet"):
        check(f"route.legacy_format_{legacy}", legacy in server.VALID_EXPORT_FORMATS)

    # CSV-shaped export still works through the existing renderer.
    csv_bytes, csv_media, csv_ext = server._render_quiz_export(SAMPLE_ITEMS, "csv")
    check("route.csv_still_works",
          csv_ext == "csv" and csv_media.startswith("text/csv")
          and b"Front,Back,Topic,Difficulty" in csv_bytes)
    tsv_bytes, _, tsv_ext = server._render_quiz_export(SAMPLE_ITEMS, "anki_tsv")
    check("route.anki_tsv_still_works", tsv_ext == "tsv" and b"\t" in tsv_bytes)

    # Drive the export route for apkg + csv against a temp-dir Job.
    tmp_root = Path(tempfile.mkdtemp(prefix="gf_apkg_route_"))
    job_dir = tmp_root / "job-route"
    (job_dir / "quizzes").mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({"title": "Route Guide"}), encoding="utf-8")
    (job_dir / "quizzes" / "1.json").write_text(
        json.dumps({"n": 1, "items": SAMPLE_ITEMS}), encoding="utf-8")

    class _StubJob:
        id = "job-route"
        quizzes_dir = job_dir / "quizzes"

        def read_manifest(self):
            return {"title": "Route Guide"}

    orig_get_job = server._get_job
    orig_is_job_path = server._is_job_path
    server._get_job = lambda jid: _StubJob()
    server._is_job_path = lambda job, path: True
    try:
        resp = server.export_quiz("job-route", 1, format="apkg")
        check("route.apkg_status", resp.status_code == 200, f"status={resp.status_code}")
        check("route.apkg_content_type",
              resp.media_type == "application/octet-stream",
              f"media_type={resp.media_type}")
        cd = resp.headers.get("content-disposition", "")
        check("route.apkg_disposition",
              "attachment" in cd and ".apkg" in cd, f"cd={cd}")
        check("route.apkg_body_is_zip", resp.body[:2] == b"PK" and len(resp.body) > 0)
        _, _, _, route_notes, _, _ = _open_db(resp.body)
        check("route.apkg_has_cards", len(route_notes) == 3)

        csv_resp = server.export_quiz("job-route", 1, format="csv")
        check("route.csv_status", csv_resp.status_code == 200)
        check("route.csv_disposition",
              ".csv" in csv_resp.headers.get("content-disposition", ""))

        # bad format still rejected
        try:
            server.export_quiz("job-route", 1, format="bogus")
            check("route.bad_format_rejected", False, "expected HTTPException")
        except HTTPException as exc:
            check("route.bad_format_rejected", exc.status_code == 400)
    finally:
        server._get_job = orig_get_job
        server._is_job_path = orig_is_job_path

    return _summary()


def _summary() -> int:
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
