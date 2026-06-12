"""Slice 53 — True Anki ``.apkg`` export for existing quiz / flashcard data.

This module turns the *already generated* quiz / flashcard items that live in a
job's ``quizzes/<n>.json`` artifact into a real, importable Anki ``.apkg``
package, so the operator can study generated material inside Anki.

Design / safety notes
=====================
* **Stdlib only.** An ``.apkg`` is a ZIP that contains a SQLite database
  (``collection.anki2``, schema 11 — the long-stable, universally importable
  format) plus a ``media`` JSON map. We build it with ``sqlite3`` + ``zipfile``
  + ``json`` + ``hashlib`` only. No third-party dependency (no ``genanki``), no
  network, no model/provider call, no image/media, no LaTeX rendering.
* **Deterministic.** Deck/model/note/card identifiers and creation/mod
  timestamps are fixed constants or derived deterministically from the
  ``job_id`` / ``quiz_n`` / card index — never from wall-clock time and never
  random. Re-exporting the same quiz yields a byte-stable structure, and stable
  note GUIDs let Anki *update* rather than duplicate cards on re-import.
* **No leaks.** The package contains only the user's own ``Front`` / ``Back``
  study text (HTML-escaped). It never embeds: provider keys, headers, tokens,
  socket paths, local/host filesystem paths, executable paths, model/``mmproj``
  paths, raw argv, raw OCR dumps, raw provider/model payloads, image bytes, data
  URIs, base64 image data, artifact URLs, or internal job-directory metadata.
  The deck name is a sanitized guide title only.
* **Basic 2-field card model** (``Front`` / ``Back``). No images, audio, media,
  or LaTeX work in this slice.

The module is pure: callers pass in plain quiz items and get back ``bytes``.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from typing import Any

# ---------------------------------------------------------------------------
# Deterministic constants
# ---------------------------------------------------------------------------

# Fixed app-level identity for the single shared "GuideForge Basic" note model.
# Stable across every export so Anki re-uses one model instead of accumulating a
# new model per import. These are arbitrary but constant; they are NOT derived
# from any private card text.
MODEL_ID = 1010101010
MODEL_NAME = "GuideForge Basic"

# Deck-config id 1 ("Default") is referenced by every deck.
DEFAULT_DCONF_ID = 1

# Fixed timestamps (seconds / milliseconds). Using constants — never the wall
# clock — keeps exports deterministic. 1600000000 = 2020-09-13 (an arbitrary
# fixed epoch second); the millisecond variants reuse it.
_FIXED_CRT = 1600000000          # collection creation (seconds)
_FIXED_MOD_MS = 1600000000000    # modification / schema time (milliseconds)

# Anki id space: derived deck ids are mapped into a safe positive range that
# avoids the reserved Default deck id (1) and stays well inside 53-bit ints.
_ID_FLOOR = 1 << 31
_ID_CEIL = 1 << 50

# Anki field separator (0x1f) joins note fields in the ``flds`` column.
_FLD_SEP = "\x1f"

# Closed status vocabulary for skipped cards (diagnostic only; never embedded in
# the package). Kept small and stable so callers/tests can assert on it.
SKIP_EMPTY = "skipped_empty"
SKIP_MALFORMED = "skipped_malformed"


# ---------------------------------------------------------------------------
# Card text extraction (mirrors api.server._render_quiz_export front/back rules)
# ---------------------------------------------------------------------------

def _front_text(item: dict[str, Any]) -> str:
    """Question prompt; for MCQ, list the options so the card is self-testable."""
    question = str(item.get("question") or "").strip()
    if item.get("type") == "mcq" and isinstance(item.get("options"), list):
        opts = [str(o).strip() for o in item["options"] if str(o).strip()]
        if opts:
            return question + "\n" + "\n".join(opts)
    return question


def _back_text(item: dict[str, Any]) -> str:
    """Answer; for MCQ resolve the answer letter to its full option text."""
    ans = str(item.get("answer") or "").strip()
    if item.get("type") == "mcq" and isinstance(item.get("options"), list):
        letter = ans.upper()
        opts = [str(o) for o in item["options"]]
        match = next((o for o in opts if o.upper().startswith(f"{letter}.")), ans)
        return str(match).strip()
    return ans


def _to_field_html(text: str) -> str:
    """HTML-escape user text and turn newlines into <br> for safe Anki rendering.

    Anki interprets field content as HTML; escaping prevents stray ``<``/``&`` in
    user study text from being mis-parsed, and keeps the field free of any markup
    we did not put there.
    """
    return html.escape(text).replace("\n", "<br>")


def normalize_cards(items: Any) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Return (cards, skipped_counts).

    ``cards`` is a list of ``(front_html, back_html)`` pairs for well-formed
    items; malformed / empty items are dropped safely. ``skipped_counts`` maps a
    closed status vocabulary to counts (diagnostic only).
    """
    cards: list[tuple[str, str]] = []
    skipped = {SKIP_EMPTY: 0, SKIP_MALFORMED: 0}
    if not isinstance(items, list):
        return cards, skipped
    for item in items:
        if not isinstance(item, dict):
            skipped[SKIP_MALFORMED] += 1
            continue
        front = _front_text(item)
        back = _back_text(item)
        if not front.strip() or not back.strip():
            skipped[SKIP_EMPTY] += 1
            continue
        cards.append((_to_field_html(front), _to_field_html(back)))
    return cards, skipped


# ---------------------------------------------------------------------------
# Deterministic id / name / filename helpers
# ---------------------------------------------------------------------------

def _stable_int(*parts: str) -> int:
    """Deterministic positive int in the safe Anki id range from string parts.

    Derived from a namespaced SHA-256 of internal identifiers (job id, quiz
    number, index) — never from private card text — then folded into
    ``[_ID_FLOOR, _ID_CEIL)``.
    """
    seed = "guideforge\x1f" + "\x1f".join(parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    raw = int(digest[:14], 16)
    return _ID_FLOOR + (raw % (_ID_CEIL - _ID_FLOOR))


def deck_id_for(job_id: str, quiz_n: int) -> int:
    """Stable deck id for a given job + quiz number."""
    return _stable_int("deck", str(job_id), str(quiz_n))


def _note_guid(job_id: str, quiz_n: int, index: int) -> str:
    """Stable, content-independent note GUID (index-based, so re-exports update).

    A short base36 string derived from internal ids only. Anki uses the GUID to
    match notes across re-imports; index-based means the same quiz position maps
    to the same note rather than creating duplicates.
    """
    digest = hashlib.sha256(
        f"guideforge-note\x1f{job_id}\x1f{quiz_n}\x1f{index}".encode("utf-8")
    ).hexdigest()
    n = int(digest[:16], 16)
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    while n:
        n, rem = divmod(n, 36)
        out.append(alphabet[rem])
    return "".join(reversed(out)) or "0"


_DECK_NAME_SAFE = re.compile(r"[^0-9A-Za-z _.\-]")


def deck_name_for(title: str | None) -> str:
    """Sanitized deck name: ``GuideForge::<clean title>``.

    The title comes from the guide manifest only; ``::`` is Anki's subdeck
    separator. Strips characters that could carry markup/paths and bounds length.
    """
    clean = (title or "").strip()
    # Collapse Anki's subdeck separator and any control/odd chars out of the leaf.
    clean = clean.replace("::", " ")
    clean = _DECK_NAME_SAFE.sub(" ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        clean = "Study Guide"
    return f"GuideForge::{clean[:80]}"


_FNAME_SAFE = re.compile(r"[^0-9A-Za-z_.\-]")


def apkg_filename(job_id: str, quiz_n: int) -> str:
    """Deterministic, path-safe download filename (no directory components)."""
    safe_job = _FNAME_SAFE.sub("_", str(job_id))[:64] or "job"
    return f"quiz-{safe_job}-{quiz_n}.apkg"


# ---------------------------------------------------------------------------
# Anki collection JSON blobs (schema 11)
# ---------------------------------------------------------------------------

_CARD_CSS = (
    ".card {\n"
    " font-family: arial;\n"
    " font-size: 20px;\n"
    " text-align: center;\n"
    " color: black;\n"
    " background-color: white;\n"
    "}\n"
)


def _model_json() -> dict[str, Any]:
    return {
        str(MODEL_ID): {
            "id": MODEL_ID,
            "name": MODEL_NAME,
            "type": 0,
            "mod": _FIXED_CRT,
            "usn": -1,
            "sortf": 0,
            "did": 1,
            "tmpls": [
                {
                    "name": "Card 1",
                    "ord": 0,
                    "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}",
                    "did": None,
                    "bqfmt": "",
                    "bafmt": "",
                }
            ],
            "flds": [
                {"name": "Front", "ord": 0, "sticky": False, "rtl": False,
                 "font": "Arial", "size": 20, "media": []},
                {"name": "Back", "ord": 1, "sticky": False, "rtl": False,
                 "font": "Arial", "size": 20, "media": []},
            ],
            "css": _CARD_CSS,
            "latexPre": "",
            "latexPost": "",
            "req": [[0, "any", [0]]],
            "tags": [],
            "vers": [],
        }
    }


def _decks_json(deck_id: int, deck_name: str) -> dict[str, Any]:
    def _deck(did: int, name: str, *, default: bool) -> dict[str, Any]:
        return {
            "id": did,
            "name": name,
            "mod": _FIXED_CRT,
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "collapsed": default,
            "browserCollapsed": default,
            "desc": "",
            "dyn": 0,
            "conf": DEFAULT_DCONF_ID,
            "extendNew": 0,
            "extendRev": 50,
        }

    decks = {"1": _deck(1, "Default", default=True)}
    if deck_id != 1:
        decks[str(deck_id)] = _deck(deck_id, deck_name, default=False)
    return decks


def _dconf_json() -> dict[str, Any]:
    return {
        str(DEFAULT_DCONF_ID): {
            "id": DEFAULT_DCONF_ID,
            "name": "Default",
            "mod": 0,
            "usn": 0,
            "maxTaken": 60,
            "autoplay": True,
            "timer": 0,
            "replayq": True,
            "new": {"bury": False, "delays": [1, 10], "initialFactor": 2500,
                    "ints": [1, 4, 0], "order": 1, "perDay": 20, "separate": True},
            "rev": {"bury": False, "ease4": 1.3, "fuzz": 0.05, "ivlFct": 1,
                    "maxIvl": 36500, "minSpace": 1, "perDay": 200, "hardFactor": 1.2},
            "lapse": {"delays": [10], "leechAction": 0, "leechFails": 8,
                      "minInt": 1, "mult": 0},
            "dyn": False,
        }
    }


def _conf_json() -> dict[str, Any]:
    return {
        "nextPos": 1,
        "estTimes": True,
        "activeDecks": [1],
        "sortType": "noteFld",
        "timeLim": 0,
        "sortBackwards": False,
        "addToCur": True,
        "curDeck": 1,
        "newBury": True,
        "newSpread": 0,
        "dueCounts": True,
        "curModel": str(MODEL_ID),
        "collapseTime": 1200,
    }


_SCHEMA_SQL = """
CREATE TABLE col (
    id integer primary key, crt integer not null, mod integer not null,
    scm integer not null, ver integer not null, dty integer not null,
    usn integer not null, ls integer not null, conf text not null,
    models text not null, decks text not null, dconf text not null,
    tags text not null
);
CREATE TABLE notes (
    id integer primary key, guid text not null, mid integer not null,
    mod integer not null, usn integer not null, tags text not null,
    flds text not null, sfld integer not null, csum integer not null,
    flags integer not null, data text not null
);
CREATE TABLE cards (
    id integer primary key, nid integer not null, did integer not null,
    ord integer not null, mod integer not null, usn integer not null,
    type integer not null, queue integer not null, due integer not null,
    ivl integer not null, factor integer not null, reps integer not null,
    lapses integer not null, left integer not null, odue integer not null,
    odid integer not null, flags integer not null, data text not null
);
CREATE TABLE revlog (
    id integer primary key, cid integer not null, usn integer not null,
    ease integer not null, ivl integer not null, lastIvl integer not null,
    factor integer not null, time integer not null, type integer not null
);
CREATE TABLE graves (
    usn integer not null, oid integer not null, type integer not null
);
CREATE INDEX ix_notes_usn on notes (usn);
CREATE INDEX ix_cards_usn on cards (usn);
CREATE INDEX ix_revlog_usn on revlog (usn);
CREATE INDEX ix_cards_nid on cards (nid);
CREATE INDEX ix_cards_sched on cards (did, queue, due);
CREATE INDEX ix_revlog_cid on revlog (cid);
CREATE INDEX ix_notes_csum on notes (csum);
"""


def _field_checksum(first_field_html: str) -> int:
    """Anki ``csum``: int of the first 8 sha1 hex digits of the first field.

    This is the format-required internal duplicate-detection checksum (a one-way
    digest, not reversible). Anki strips HTML before hashing; we approximate by
    removing tags so the checksum matches Anki's own recomputation closely.
    """
    plain = re.sub(r"<[^>]+>", "", first_field_html)
    return int(hashlib.sha1(plain.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_apkg(
    items: Any,
    *,
    job_id: str,
    quiz_n: int,
    title: str | None = None,
) -> bytes:
    """Build a deterministic Anki ``.apkg`` package from quiz/flashcard items.

    Malformed / empty items are skipped. With zero surviving cards this still
    returns a valid empty deck package (matching the existing export route's
    "empty export, not an error" behaviour). Returns the raw ``.apkg`` bytes.
    """
    cards, _skipped = normalize_cards(items)
    deck_id = deck_id_for(job_id, quiz_n)
    deck_name = deck_name_for(title)

    tmp_dir = tempfile.mkdtemp(prefix="gf_apkg_")
    db_path = os.path.join(tmp_dir, "collection.anki2")
    try:
        con = sqlite3.connect(db_path)
        try:
            con.executescript(_SCHEMA_SQL)
            con.execute(
                "INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, "
                "conf, models, decks, dconf, tags) "
                "VALUES (1, ?, ?, ?, 11, 0, 0, 0, ?, ?, ?, ?, ?)",
                (
                    _FIXED_CRT,
                    _FIXED_MOD_MS,
                    _FIXED_MOD_MS,
                    json.dumps(_conf_json()),
                    json.dumps(_model_json()),
                    json.dumps(_decks_json(deck_id, deck_name)),
                    json.dumps(_dconf_json()),
                    "{}",
                ),
            )

            for index, (front_html, back_html) in enumerate(cards):
                note_id = _stable_int("note", str(job_id), str(quiz_n), str(index))
                card_id = _stable_int("card", str(job_id), str(quiz_n), str(index))
                guid = _note_guid(job_id, quiz_n, index)
                flds = front_html + _FLD_SEP + back_html
                sfld = re.sub(r"<[^>]+>", "", front_html)
                con.execute(
                    "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, "
                    "sfld, csum, flags, data) "
                    "VALUES (?, ?, ?, ?, -1, '', ?, ?, ?, 0, '')",
                    (note_id, guid, MODEL_ID, _FIXED_CRT, flds, sfld,
                     _field_checksum(front_html)),
                )
                con.execute(
                    "INSERT INTO cards (id, nid, did, ord, mod, usn, type, "
                    "queue, due, ivl, factor, reps, lapses, left, odue, odid, "
                    "flags, data) "
                    "VALUES (?, ?, ?, 0, ?, -1, 0, 0, ?, 0, 0, 0, 0, 0, 0, 0, 0, '')",
                    (card_id, note_id, deck_id, _FIXED_CRT, index + 1),
                )
            con.commit()
        finally:
            con.close()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, "collection.anki2")
            # Empty media map: no images/audio/media in this slice.
            zf.writestr("media", "{}")
        return buf.getvalue()
    finally:
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass
