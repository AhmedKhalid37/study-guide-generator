"""Ask Your Guide session storage, retrieval, and local-only chat orchestration.

This module is deliberately narrow: it stores chat sessions under a job's
``ask/sessions`` directory, retrieves over the prepared Ask context cache, and
assembles a grounded prompt for the existing local OpenAI-compatible provider.

It never mutates original job artifacts, never creates generation jobs, and never
stores provider configuration, raw prompts, keys, headers, base URLs, or paths in
session files.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pipeline import ask_context, ask_inventory
from pipeline.job_manager import JOBS_DIR, Job
from pipeline.llm_client import LLMProviderError, MissingLLMConfigError, generate_chat_completion
from pipeline.provider_config import build_provider_config, get_local_model_status

SESSION_KIND = "ask_chat_session"
SESSION_VERSION = 1
MAX_QUESTION_CHARS = 4000
MAX_HISTORY_MESSAGES = 40
RECENT_HISTORY_MESSAGES = 6
MAX_RETRIEVED_CHUNKS = 8
MAX_SESSION_SNIPPET_CHARS = 180
TOTAL_CONTEXT_TOKENS = 6000
RESERVE_ANSWER_TOKENS = 1500
RESERVE_SYSTEM_TOKENS = 850
RESERVE_HISTORY_TOKENS = 650
RETRIEVAL_TOKEN_BUDGET = max(
    800, TOTAL_CONTEXT_TOKENS - RESERVE_ANSWER_TOKENS - RESERVE_SYSTEM_TOKENS - RESERVE_HISTORY_TOKENS
)
CHARS_PER_TOKEN = 4

_TERM_RE = re.compile(r"[a-z0-9]{2,}")
_SESSION_ID_RE = re.compile(r"^ask_[a-f0-9]{32}$")
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b")
_AUTH_RE = re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._\-]+")
_URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")
_BRACKET_RE = re.compile(r"\[([^\[\]\n]{1,180})\]")
_CITATION_LIKE_RE = re.compile(r"^(?:Guide\s+\S|Source\s+(?:Page\s+\d+|p\.\s*\d+|\S))", re.IGNORECASE)


class AskSessionError(Exception):
    """HTTP-shaped, user-safe error from the Ask session layer."""

    def __init__(self, status_code: int, detail: str | dict[str, Any]) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _redact_text(value: str) -> str:
    """Defensively mask obvious secrets/provider URLs before persistence/return."""
    text = _SK_RE.sub("[redacted-key]", value)
    text = _AUTH_RE.sub("[redacted-authorization]", text)
    text = _URL_RE.sub("[redacted-url]", text)
    return text


def _terms(text: str) -> Counter[str]:
    return Counter(_TERM_RE.findall(text.lower()))


def _approx_tokens(text_or_chars: str | int) -> int:
    chars = len(text_or_chars) if isinstance(text_or_chars, str) else max(0, text_or_chars)
    return (chars + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _sessions_dir(job: Job) -> Path:
    return job.dir / "ask" / "sessions"


def _session_dir(job: Job, session_id: str) -> Path:
    return _sessions_dir(job) / session_id


def _ensure_fenced(root: Path, path: Path) -> None:
    base = root.resolve()
    target = path.resolve()
    if target != base and not target.is_relative_to(base):
        raise AskSessionError(404, "Ask session not found.")


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}-", suffix=".json")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _history_path(session_path: Path) -> Path:
    return session_path / "history.jsonl"


def _append_history(session_path: Path, records: list[dict[str, Any]]) -> None:
    session_path.mkdir(parents=True, exist_ok=True)
    path = _history_path(session_path)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _read_history(session_path: Path, *, limit: int = MAX_HISTORY_MESSAGES) -> list[dict[str, Any]]:
    path = _history_path(session_path)
    if not path.exists() or not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-max(limit, 0):]:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        safe = {
            "role": role,
            "content": _redact_text(content),
            "created_at": item.get("created_at"),
        }
        if role == "assistant":
            safe["citations"] = _safe_citation_list(item.get("citations"))
            safe["citations_unsupported"] = _safe_citation_list(item.get("citations_unsupported"))
            if isinstance(item.get("citation_validation"), dict):
                validation = item["citation_validation"]
                safe["citation_validation"] = {
                    "ok": validation.get("ok") is not False,
                    "unsupported_count": int(validation.get("unsupported_count") or 0),
                }
        records.append(safe)
    return records


def _read_history_records(session_path: Path) -> list[dict[str, Any]]:
    path = _history_path(session_path)
    if not path.exists() or not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            records.append(item)
    return records


def _safe_citation_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        label = item.strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label[:180])
    return labels[:MAX_RETRIEVED_CHUNKS]


def validate_answer_citations(answer: str, allowed_labels: list[str]) -> tuple[str, dict[str, Any]]:
    """Validate bracket-style citations emitted by the model.

    Only bracket contents that look like Ask citation labels are checked. Other
    bracketed prose, such as ``[optional note]``, is left untouched to avoid false
    failures. Unsupported Ask-looking citations are stripped from the answer and
    reported in machine-readable metadata; they are never converted into trusted
    source chips.
    """
    allowed: list[str] = []
    allowed_set: set[str] = set()
    for label in allowed_labels:
        if not isinstance(label, str):
            continue
        safe = label.strip()
        if not safe or safe in allowed_set:
            continue
        allowed_set.add(safe)
        allowed.append(safe)

    used: list[str] = []
    unsupported: list[str] = []
    unsupported_set: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        raw_label = match.group(1).strip()
        if not _CITATION_LIKE_RE.match(raw_label):
            return match.group(0)
        if raw_label in allowed_set:
            if raw_label not in used:
                used.append(raw_label)
            return match.group(0)
        if raw_label not in unsupported_set:
            unsupported_set.add(raw_label)
            unsupported.append(raw_label)
        return ""

    sanitized = _BRACKET_RE.sub(replace, answer)
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    sanitized = re.sub(r" *\n", "\n", sanitized).strip()
    validation = {
        "ok": not unsupported,
        "unsupported_count": len(unsupported),
    }
    return sanitized, {
        "citations_allowed": allowed,
        "citations_used": used,
        "citations_unsupported": unsupported,
        "citation_validation": validation,
    }


def create_session(job: Job, *, title: str | None = None) -> dict[str, Any]:
    if not job.manifest.exists():
        raise AskSessionError(404, "Job not found.")
    if not ask_inventory.has_generated_guide(job):
        raise AskSessionError(
            409,
            {
                "status": "not_ready",
                "ready": False,
                "reason": "No generated guide (clean.md) is available for this job yet.",
            },
        )

    created = _now()
    session_id = f"ask_{uuid.uuid4().hex}"
    session_path = _session_dir(job, session_id)
    _ensure_fenced(job.dir, session_path)
    metadata = {
        "kind": SESSION_KIND,
        "version": SESSION_VERSION,
        "session_id": session_id,
        "job_id": job.id,
        "created_at": created,
        "updated_at": created,
        "title": _redact_text(title.strip()[:120]) if isinstance(title, str) and title.strip() else None,
        "settings": {
            "provider": "local",
            "retrieval": {
                "max_chunks": MAX_RETRIEVED_CHUNKS,
                "token_budget": RETRIEVAL_TOKEN_BUDGET,
            },
        },
    }
    _atomic_write_json(session_path / "session.json", metadata)
    _history_path(session_path).touch(exist_ok=True)
    return {"session": _public_session(metadata), "history": []}


def _public_session(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": metadata.get("session_id"),
        "job_id": metadata.get("job_id"),
        "created_at": metadata.get("created_at"),
        "updated_at": metadata.get("updated_at"),
        "title": metadata.get("title"),
        "settings": {
            "provider": "local",
            "retrieval": {
                "max_chunks": MAX_RETRIEVED_CHUNKS,
                "token_budget": RETRIEVAL_TOKEN_BUDGET,
            },
        },
    }


def _session_summary(metadata: dict[str, Any], session_path: Path) -> dict[str, Any]:
    session = _public_session(metadata)
    records = _read_history_records(session_path)
    summary = {
        "session_id": session.get("session_id"),
        "job_id": session.get("job_id"),
        "title": session.get("title"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "message_count": len(records),
    }
    for item in reversed(records):
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            snippet = _redact_text(" ".join(content.split()))[:MAX_SESSION_SNIPPET_CHARS]
            if snippet:
                summary["last_message"] = {"role": role, "snippet": snippet}
            break
    return summary


def list_sessions(job: Job) -> dict[str, Any]:
    if not job.manifest.exists():
        raise AskSessionError(404, "Job not found.")
    if not ask_inventory.has_generated_guide(job):
        raise AskSessionError(
            409,
            {
                "status": "not_ready",
                "ready": False,
                "reason": "No generated guide (clean.md) is available for this job yet.",
            },
        )
    sessions_root = _sessions_dir(job)
    _ensure_fenced(job.dir, sessions_root)
    summaries: list[dict[str, Any]] = []
    if sessions_root.exists() and sessions_root.is_dir():
        for session_path in sessions_root.iterdir():
            if not session_path.is_dir() or not _SESSION_ID_RE.match(session_path.name):
                continue
            _ensure_fenced(sessions_root, session_path)
            metadata = _read_json(session_path / "session.json")
            if not metadata or metadata.get("job_id") != job.id:
                continue
            summaries.append(_session_summary(metadata, session_path))
    summaries.sort(
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or item.get("session_id") or ""),
        reverse=True,
    )
    return {"job_id": job.id, "sessions": summaries}


def find_session(session_id: str) -> tuple[Job, Path, dict[str, Any]]:
    if not isinstance(session_id, str) or not _SESSION_ID_RE.match(session_id):
        raise AskSessionError(404, "Ask session not found.")
    if not JOBS_DIR.exists():
        raise AskSessionError(404, "Ask session not found.")
    for job_dir in JOBS_DIR.glob("*/ask/sessions/*"):
        if job_dir.name != session_id:
            continue
        metadata_path = job_dir / "session.json"
        metadata = _read_json(metadata_path)
        if not metadata:
            continue
        job_id = metadata.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            continue
        job = Job(job_id, root=JOBS_DIR)
        _ensure_fenced(job.dir, job_dir)
        if not job.manifest.exists():
            raise AskSessionError(404, "Parent job not found.")
        return job, job_dir, metadata
    raise AskSessionError(404, "Ask session not found.")


def load_session(session_id: str, *, history_limit: int = MAX_HISTORY_MESSAGES) -> dict[str, Any]:
    _job, session_path, metadata = find_session(session_id)
    return {
        "session": _public_session(metadata),
        "history": _read_history(session_path, limit=history_limit),
    }


def clear_history(session_id: str) -> dict[str, Any]:
    _job, session_path, metadata = find_session(session_id)
    now = _now()
    _history_path(session_path).write_text("", encoding="utf-8")
    metadata["updated_at"] = now
    _atomic_write_json(session_path / "session.json", metadata)
    return {"session": _session_summary(metadata, session_path), "history": []}


def delete_session(session_id: str) -> dict[str, Any]:
    job, session_path, _metadata = find_session(session_id)
    sessions_root = _sessions_dir(job)
    _ensure_fenced(sessions_root, session_path)
    if session_path == sessions_root:
        raise AskSessionError(404, "Ask session not found.")
    shutil.rmtree(session_path)
    return {"deleted": True, "session_id": session_id}


def _score_chunks(index: dict[str, Any], query: str) -> list[tuple[float, dict[str, Any]]]:
    query_terms = _terms(query)
    if not query_terms:
        return []
    chunks = index.get("chunks")
    if not isinstance(chunks, list):
        return []
    doc_freq = index.get("doc_freq") if isinstance(index.get("doc_freq"), dict) else {}
    total_docs = max(1, len(chunks))
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        terms = chunk.get("terms")
        if not isinstance(terms, dict):
            continue
        score = 0.0
        for term, qtf in query_terms.items():
            tf = terms.get(term, 0)
            if not isinstance(tf, int) or tf <= 0:
                continue
            df = doc_freq.get(term, 0)
            if not isinstance(df, int):
                df = 0
            idf = math.log((1 + total_docs) / (1 + df)) + 1.0
            score += min(tf, 8) * qtf * idf
        if score > 0:
            scored.append((score, chunk))
    scored.sort(
        key=lambda item: (
            item[0],
            -int(item[1].get("approx_tokens") or 0),
            str(item[1].get("id") or ""),
        ),
        reverse=True,
    )
    return scored


def retrieve_chunks(
    index: dict[str, Any],
    query: str,
    *,
    max_chunks: int = MAX_RETRIEVED_CHUNKS,
    token_budget: int = RETRIEVAL_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = 0
    for score, chunk in _score_chunks(index, query):
        tokens = int(chunk.get("approx_tokens") or _approx_tokens(str(chunk.get("text") or "")))
        if selected and used + tokens > token_budget:
            continue
        if not selected and tokens > token_budget:
            continue
        selected.append({"score": round(score, 4), **chunk})
        used += tokens
        if len(selected) >= max_chunks:
            break
    return selected


def _citation_label(chunk: dict[str, Any]) -> str:
    source_type = chunk.get("source_type")
    label = chunk.get("label")
    if source_type == "source":
        page = chunk.get("page")
        return f"Source Page {page}" if isinstance(page, int) else f"Source {label or chunk.get('id')}"
    return f"Guide {label}" if label else f"Guide {chunk.get('id')}"


def _chunk_metadata(chunk: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("id"),
        "source_type": chunk.get("source_type"),
        "label": label,
        "page": chunk.get("page") if isinstance(chunk.get("page"), int) else None,
        "approx_tokens": chunk.get("approx_tokens"),
        "score": chunk.get("score"),
    }


ANSWER_RULES = """You are Ask Your Guide, a local-only study assistant.
Use only the provided guide/source chunks for factual claims about the user's material.
Cite only the citation labels listed in the context, exactly as written.
Prefer one citation at the end of a paragraph or a short final "Sources used" line; do not cite every sentence.
If the answer is not covered by the provided chunks, say that it is not covered in the guide/source.
Do not invent facts, formulas, page numbers, dates, requirements, or citations.
Clearly distinguish "from your guide/source" from any general knowledge.
If sources conflict, explain the conflict.
If the question is ambiguous, ask one concise clarifying question.
For calculations or formulas, show steps and check the final answer.
For exam advice, mark high-confidence points versus uncertain points."""


def assemble_prompt(
    *,
    question: str,
    retrieved_chunks: list[dict[str, Any]],
    recent_history: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[str], list[dict[str, Any]]]:
    citation_labels: list[str] = []
    metadata: list[dict[str, Any]] = []
    context_blocks: list[str] = []
    for chunk in retrieved_chunks:
        label = _citation_label(chunk)
        if label not in citation_labels:
            citation_labels.append(label)
        metadata.append(_chunk_metadata(chunk, label))
        text = str(chunk.get("text") or "")
        context_blocks.append(f"[{label}]\n{text}")

    recent_lines: list[str] = []
    used_history_tokens = 0
    for item in recent_history[-RECENT_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = str(item.get("content") or "")
        tokens = _approx_tokens(content)
        if used_history_tokens + tokens > RESERVE_HISTORY_TOKENS:
            continue
        used_history_tokens += tokens
        recent_lines.append(f"{role}: {content}")

    system = (
        f"{ANSWER_RULES}\n\n"
        "Available citation labels for this turn:\n"
        + ("\n".join(f"- {label}" for label in citation_labels) if citation_labels else "- none")
    )
    user = (
        "Recent conversation window:\n"
        + ("\n".join(recent_lines) if recent_lines else "(none)")
        + "\n\nRetrieved guide/source chunks:\n"
        + ("\n\n".join(context_blocks) if context_blocks else "(No relevant chunks were retrieved.)")
        + "\n\nUser question:\n"
        + question
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], citation_labels, metadata


def _safe_local_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "local",
        "configured": bool(status.get("configured")),
        "reachable": bool(status.get("reachable")),
        "model": status.get("selected_model") or status.get("default_model"),
        "model_count": status.get("model_count"),
        "base_url_host": status.get("base_url_host"),
        "error": status.get("error") if isinstance(status.get("error"), dict) else None,
    }


def answer_message(
    session_id: str,
    question: str,
    *,
    status_fn: Callable[[], dict[str, Any]] | None = None,
    config_fn: Callable[..., Any] | None = None,
    generate_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    status_fn = status_fn or get_local_model_status
    config_fn = config_fn or build_provider_config
    generate_fn = generate_fn or generate_chat_completion
    if not isinstance(question, str) or not question.strip():
        raise AskSessionError(400, "Message must be a non-empty string.")
    question = _redact_text(question.strip())
    if len(question) > MAX_QUESTION_CHARS:
        raise AskSessionError(400, f"Message is too long; limit is {MAX_QUESTION_CHARS} characters.")

    job, session_path, metadata = find_session(session_id)
    if not job.manifest.exists():
        raise AskSessionError(404, "Parent job not found.")
    if not ask_inventory.has_generated_guide(job):
        raise AskSessionError(
            409,
            {
                "status": "not_ready",
                "ready": False,
                "reason": "No generated guide (clean.md) is available for this job yet.",
            },
        )

    status = status_fn()
    safe_status = _safe_local_status(status if isinstance(status, dict) else {})
    if not safe_status["configured"] or not safe_status["reachable"] or not safe_status.get("model"):
        return {
            "session_id": session_id,
            "status": "local_offline",
            "answer": "",
            "citations": [],
            "citations_allowed": [],
            "citations_used": [],
            "citations_unsupported": [],
            "citation_validation": {"ok": True, "unsupported_count": 0},
            "retrieved_chunks": [],
            "local_model": safe_status,
            "error": {
                "category": (safe_status.get("error") or {}).get("category") or "local_offline",
                "message": (safe_status.get("error") or {}).get("message")
                or "Local model is not configured or reachable.",
            },
        }

    prep = ask_context.prepare_context(job)
    if not prep.get("ready"):
        raise AskSessionError(
            409,
            {
                "status": "not_prepared",
                "ready": False,
                "reason": prep.get("reason") or "Ask context is not prepared.",
            },
        )
    index = ask_context.load_index(job)
    if not index:
        raise AskSessionError(
            409,
            {"status": "not_prepared", "ready": False, "reason": "Ask context index is unavailable."},
        )

    recent_history = _read_history(session_path, limit=RECENT_HISTORY_MESSAGES)
    query = " ".join([item.get("content", "") for item in recent_history[-2:] if item.get("role") == "user"])
    query = f"{query} {question}".strip()
    retrieved = retrieve_chunks(index, query)
    messages, citation_labels, chunk_meta = assemble_prompt(
        question=question, retrieved_chunks=retrieved, recent_history=recent_history
    )

    try:
        config = config_fn(
            "local",
            str(safe_status.get("model") or "Use environment default"),
            max_tokens=RESERVE_ANSWER_TOKENS,
        )
        answer = generate_fn(messages, config)
    except MissingLLMConfigError as exc:
        return {
            "session_id": session_id,
            "status": "local_offline",
            "answer": "",
            "citations": citation_labels,
            "citations_allowed": citation_labels,
            "citations_used": [],
            "citations_unsupported": [],
            "citation_validation": {"ok": True, "unsupported_count": 0},
            "retrieved_chunks": chunk_meta,
            "local_model": safe_status,
            "error": {"category": "provider_config", "message": _redact_text(str(exc))},
        }
    except LLMProviderError as exc:
        return {
            "session_id": session_id,
            "status": "local_offline" if exc.category == "local_offline" else "provider_error",
            "answer": "",
            "citations": citation_labels,
            "citations_allowed": citation_labels,
            "citations_used": [],
            "citations_unsupported": [],
            "citation_validation": {"ok": True, "unsupported_count": 0},
            "retrieved_chunks": chunk_meta,
            "local_model": safe_status,
            "error": {"category": exc.category, "message": _redact_text(str(exc))},
        }

    answer = _redact_text(answer)
    answer, citation_info = validate_answer_citations(answer, citation_labels)
    now = _now()
    _append_history(
        session_path,
        [
            {"role": "user", "content": question, "created_at": now},
            {
                "role": "assistant",
                "content": answer,
                "created_at": now,
                "citations": citation_info["citations_used"],
                "citations_unsupported": citation_info["citations_unsupported"],
                "citation_validation": citation_info["citation_validation"],
            },
        ],
    )
    metadata["updated_at"] = now
    _atomic_write_json(session_path / "session.json", metadata)

    return {
        "session_id": session_id,
        "status": "answered",
        "answer": answer,
        "citations": citation_info["citations_used"],
        **citation_info,
        "retrieved_chunks": chunk_meta,
        "local_model": safe_status,
    }
