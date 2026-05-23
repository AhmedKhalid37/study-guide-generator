from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import streamlit as st

from pipeline.job_manager import JOBS_DIR, Job
from pipeline.llm_client import LLMConfig, MissingLLMConfigError, load_env_file
from pipeline.run_llm_job import LLMJobError, run_llm_job
from pipeline.run_markdown_job import MarkdownJobError, run_markdown_job, run_pasted_text_job


DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]
QWEN_MODELS = [
    "qwen3.7-max",
    "qwen3.6-plus",
    "qwen3-max",
    "qwen3.6-max-preview",
    "qwen-plus",
    "qwen-max",
]


def main() -> None:
    st.set_page_config(page_title="Study Guide Generator", layout="centered")
    st.title("Study Guide Generator")
    _sidebar_help()

    _init_state()

    mode = st.radio(
        "Mode",
        ["Upload Markdown", "Paste Text", "Generate with LLM"],
        horizontal=True,
    )
    theme = st.selectbox("Theme", ["claude_clean"], index=0)
    strict_math = st.checkbox("Strict math validation", value=True)

    if mode == "Upload Markdown":
        _upload_mode(theme=theme, strict_math=strict_math)
    elif mode == "Paste Text":
        _paste_mode(theme=theme, strict_math=strict_math)
    else:
        _llm_mode(theme=theme, strict_math=strict_math)

    _show_result()
    _show_selected_history_job()


def _init_state() -> None:
    st.session_state.setdefault("last_job", None)
    st.session_state.setdefault("last_error", None)
    st.session_state.setdefault("last_failed_job", None)
    st.session_state.setdefault("selected_history_job_id", None)


def _upload_mode(*, theme: str, strict_math: bool) -> None:
    uploaded = st.file_uploader("Markdown file", type=["md", "markdown"])
    if st.button("Convert to PDF", type="primary", disabled=uploaded is None):
        if uploaded is None:
            st.warning("Upload a Markdown file first.")
            return

        suffix = Path(uploaded.name).suffix or ".md"
        prefix = _safe_temp_prefix(uploaded.name)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=prefix) as tmp:
            tmp.write(uploaded.getbuffer())
            temp_path = Path(tmp.name)

        _run_job(lambda: run_markdown_job(temp_path, theme=theme, strict_math=strict_math))


def _paste_mode(*, theme: str, strict_math: bool) -> None:
    text = st.text_area("Markdown or text", height=360)
    if st.button("Convert pasted text to PDF", type="primary", disabled=not text.strip()):
        if not text.strip():
            st.warning("Paste Markdown or text first.")
            return
        _run_job(lambda: run_pasted_text_job(text, theme=theme, strict_math=strict_math))


def _llm_mode(*, theme: str, strict_math: bool) -> None:
    load_env_file()
    title = st.text_input("Title", value="Generated Study Guide")
    guide_mode = st.selectbox("Mode", ["exam", "theory", "quick", "deep"], index=0)
    style_label = st.selectbox(
        "Style",
        [
            "Basic study guide",
            "Baby-step explanation",
            "Exam cram",
            "MCQ training",
            "Final solution",
            "Claude-style study guide",
            "Master-level longform guide",
        ],
        index=0,
    )
    prompt_name = _prompt_name_for_style(style_label)
    provider = st.selectbox("Provider", ["DeepSeek", "Qwen"], index=0)
    model_options = DEEPSEEK_MODELS if provider == "DeepSeek" else QWEN_MODELS
    model_choice = st.selectbox(
        f"{provider} model",
        ["Use environment default", *model_options, "Custom model ID"],
        index=0 if provider == "DeepSeek" else 1,
    )
    custom_model = st.text_input(
        "Custom model ID",
        value="",
        placeholder="Enter a provider-specific model ID",
        disabled=model_choice != "Custom model ID",
    )
    qwen_thinking_enabled = True
    if provider == "Qwen":
        qwen_thinking_enabled = st.checkbox("Enable thinking mode", value=True)
    selected_model = custom_model.strip() if model_choice == "Custom model ID" else model_choice
    st.session_state.selected_llm_provider = provider
    st.session_state.selected_llm_model = selected_model

    uploaded = st.file_uploader("Optional source file", type=["txt", "md", "markdown"])
    text = st.text_area("Source text", height=360)

    if uploaded is not None and text.strip():
        st.caption("Using uploaded source file and ignoring pasted source text.")

    has_source = uploaded is not None or bool(text.strip())
    if st.button("Generate Study Guide PDF", type="primary", disabled=not has_source):
        if uploaded is not None:
            source_text = uploaded.getvalue().decode("utf-8", errors="replace")
        else:
            source_text = text

        if not source_text.strip():
            st.warning("Provide source text or upload a source file first.")
            return

        _run_job(
            lambda: run_llm_job(
                source_text,
                title=title,
                mode=guide_mode,
                prompt_name=prompt_name,
                theme=theme,
                strict_math=strict_math,
                config=build_provider_config(
                    provider,
                    model_choice,
                    custom_model,
                    qwen_thinking_enabled=qwen_thinking_enabled,
                ),
            )
        )


def build_provider_config(
    provider: str,
    model_choice: str,
    custom_model: str | None = None,
    *,
    qwen_thinking_enabled: bool = True,
) -> LLMConfig:
    load_env_file()
    temperature = _llm_temperature_from_env()

    if provider == "DeepSeek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise MissingLLMConfigError("Missing DEEPSEEK_API_KEY.")
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=os.getenv("DEEPSEEK_MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("DEEPSEEK_MODEL_FLASH")
            or DEEPSEEK_MODELS[0],
        )
        return LLMConfig(
            base_url=os.getenv("DEEPSEEK_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or DEEPSEEK_BASE_URL,
            api_key=api_key,
            model=model,
            temperature=temperature,
            provider="deepseek",
        )

    if provider == "Qwen":
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key:
            raise MissingLLMConfigError("Missing DASHSCOPE_API_KEY or QWEN_API_KEY.")
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0],
        )
        return LLMConfig(
            base_url=os.getenv("DASHSCOPE_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or QWEN_BASE_URL,
            api_key=api_key,
            model=model,
            temperature=temperature,
            provider="qwen",
            extra_body={"enable_thinking": qwen_thinking_enabled},
        )

    raise MissingLLMConfigError(f"Unsupported LLM provider: {provider}")


def _selected_model(model_choice: str, custom_model: str | None, *, fallback: str) -> str:
    if model_choice == "Use environment default":
        return fallback
    if model_choice == "Custom model ID":
        model = (custom_model or "").strip()
        if not model:
            return fallback
        return model
    return model_choice


def _llm_temperature_from_env() -> float:
    temperature_raw = os.getenv("LLM_TEMPERATURE", "0.2")
    try:
        return float(temperature_raw)
    except ValueError as exc:
        raise MissingLLMConfigError(
            f"LLM_TEMPERATURE must be a number, got: {temperature_raw}"
        ) from exc


def _prompt_name_for_style(style_label: str) -> str:
    return {
        "Basic study guide": "basic_study_guide",
        "Baby-step explanation": "baby_steps",
        "Exam cram": "exam_cram",
        "MCQ training": "mcq_training",
        "Final solution": "final_solution",
        "Claude-style study guide": "claude_study_guide",
        "Master-level longform guide": "master_longform",
    }[style_label]


def _run_job(factory) -> None:
    st.session_state.last_job = None
    st.session_state.last_error = None
    st.session_state.last_failed_job = None

    with st.spinner("Running job..."):
        try:
            st.session_state.last_job = factory()
        except MissingLLMConfigError as exc:
            st.session_state.last_error = str(exc)
        except (MarkdownJobError, LLMJobError) as exc:
            st.session_state.last_error = str(exc)
            st.session_state.last_failed_job = getattr(exc, "job", None)
        except Exception as exc:
            st.session_state.last_error = str(exc)


def _show_result() -> None:
    error = st.session_state.last_error
    failed_job = st.session_state.last_failed_job
    job = st.session_state.last_job

    if error:
        st.error(error)
        if failed_job is not None:
            _show_job_artifacts(failed_job, include_outputs=False)
        return

    if job is None:
        return

    st.success("Job completed.")
    st.write(f"Job id: `{job.id}`")
    _show_job_artifacts(job, include_outputs=True)


def _show_job_artifacts(job: Job, *, include_outputs: bool) -> None:
    _show_validation_summary(job)

    with st.expander("Job details"):
        st.write(f"Job folder: `{job.dir}`")
        st.write(f"clean.md: `{job.clean_md}`")
        st.write(f"final.html: `{job.final_html}`")
        st.write(f"final.pdf: `{job.final_pdf}`")

    _download_existing_artifacts(job, include_outputs=include_outputs)


def _sidebar_help() -> None:
    with st.sidebar:
        st.header("Help")
        st.markdown(
            """
**Upload Markdown** converts an existing `.md` or `.markdown` file into a
sanitized study-guide PDF.

**Paste Text** converts pasted Markdown or plain text through the same backend
pipeline.

**Generate with LLM** sends source text to the configured OpenAI-compatible LLM,
then sanitizes, validates, and renders the generated Markdown.

**Strict math validation** stops the job when KaTeX cannot parse a formula.
Turn it off only when you want a PDF even with visibly marked math errors.

Jobs are saved under `jobs/<job_id>/` with inputs, logs, Markdown, HTML, PDF,
and `job.json`.
"""
        )
        st.header("LLM Config")
        _show_llm_config_status()
        _show_recent_jobs_panel()


def scan_recent_jobs(limit: int = 10) -> list[dict]:
    jobs = []
    if not JOBS_DIR.exists():
        return jobs

    for manifest_path in JOBS_DIR.glob("*/job.json"):
        data = _read_json(manifest_path)
        if data is None:
            continue
        job_id = str(data.get("id") or manifest_path.parent.name)
        data["_job_id"] = job_id
        data["_job_dir"] = str(manifest_path.parent)
        jobs.append(data)

    jobs.sort(
        key=lambda item: str(item.get("created_at") or item.get("_job_id") or ""),
        reverse=True,
    )
    return jobs[:limit]


def _show_recent_jobs_panel() -> None:
    st.header("Recent Jobs")
    jobs = scan_recent_jobs()
    if not jobs:
        st.caption("No jobs found.")
        st.session_state.selected_history_job_id = None
        return

    job_by_id = {job["_job_id"]: job for job in jobs}
    options = [""] + list(job_by_id)
    selected = st.selectbox(
        "Open previous job",
        options,
        format_func=lambda job_id: (
            "Select a job" if not job_id else _job_option_label(job_by_id[job_id])
        ),
    )
    st.session_state.selected_history_job_id = selected or None

    with st.expander("Latest 10", expanded=False):
        for job in jobs:
            st.markdown(f"**{job.get('_job_id', 'unknown')}**")
            st.caption(_job_summary(job))


def _job_option_label(job: dict) -> str:
    status = job.get("status") or "unknown"
    title = job.get("title") or "Untitled"
    created_at = job.get("created_at") or "unknown time"
    return f"{created_at} | {status} | {title} | {job.get('_job_id', 'unknown')}"


def _job_summary(job: dict) -> str:
    provider = job.get("provider")
    model = job.get("model")
    provider_model = " / ".join(str(value) for value in (provider, model) if value)
    if not provider_model:
        provider_model = "provider/model unavailable"
    return (
        f"status: {job.get('status') or 'unknown'} | "
        f"provider/model: {provider_model} | "
        f"title: {job.get('title') or 'Untitled'} | "
        f"created_at: {job.get('created_at') or 'unknown'}"
    )


def _show_selected_history_job() -> None:
    job_id = st.session_state.get("selected_history_job_id")
    if not job_id:
        return

    job = Job(job_id)
    manifest = job.read_manifest()
    st.divider()
    st.subheader("Previous Job")
    st.write(f"Job id: `{job.id}`")
    st.write(f"Status: `{manifest.get('status') or 'unknown'}`")
    if manifest.get("title"):
        st.write(f"Title: `{manifest['title']}`")
    if manifest.get("provider") or manifest.get("model"):
        provider_model = f"{manifest.get('provider') or 'unknown'} / {manifest.get('model') or 'unknown'}"
        st.write(f"Provider/model: `{provider_model}`")
    if manifest.get("created_at"):
        st.write(f"Created at: `{manifest['created_at']}`")
    _show_job_artifacts(job, include_outputs=True)


def _show_llm_config_status() -> None:
    load_env_file()
    deepseek_base = (
        "present" if os.getenv("DEEPSEEK_BASE_URL") or os.getenv("LLM_BASE_URL") else "default"
    )
    deepseek_key = (
        "present" if os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY") else "missing"
    )
    qwen_base = (
        "present" if os.getenv("DASHSCOPE_BASE_URL") or os.getenv("QWEN_BASE_URL") else "default"
    )
    qwen_key = (
        "present" if os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") else "missing"
    )
    st.write(f"DeepSeek base URL: `{deepseek_base}`")
    st.write(f"DeepSeek API key: `{deepseek_key}`")
    st.write(f"DashScope/Qwen base URL: `{qwen_base}`")
    st.write(f"DashScope/Qwen API key: `{qwen_key}`")
    st.write(f"LLM temperature: `{os.getenv('LLM_TEMPERATURE') or '0.2'}`")
    provider = st.session_state.get("selected_llm_provider")
    if provider:
        st.write(f"Selected provider for this run: `{provider}`")
    selected = st.session_state.get("selected_llm_model")
    if selected:
        st.write(f"Selected model for this run: `{selected}`")
    else:
        st.write("Selected model for this run: `environment default`")


def _validation_json_path(job: Job) -> Path:
    manifest = job.read_manifest()
    manifest_path = manifest.get("validation_json")
    candidates = [
        Path(manifest_path) if manifest_path else None,
        job.logs_dir / "validation.json",
        job.validation_json,
    ]
    for path in candidates:
        if path is not None and path.exists():
            return path
    return job.logs_dir / "validation.json"


def _show_validation_summary(job: Job) -> None:
    validation_path = _validation_json_path(job)
    data = _read_json(validation_path)
    if data is None:
        st.caption(f"Validation summary unavailable: {validation_path}")
        return

    ok = bool(data.get("ok"))
    errors = data.get("errors") or []
    status = "passed" if ok else "failed"
    st.write(
        "Validation "
        f"{status}: display math blocks `{data.get('displayBlocks', 0)}`, "
        f"inline math `{data.get('inlineFormulas', 0)}`, "
        f"errors `{len(errors)}`"
    )

    if errors:
        with st.expander("Validation errors"):
            for index, error in enumerate(errors, start=1):
                expr = error.get("expr", "")
                message = error.get("message") or error.get("error", "")
                mode = "display" if error.get("display_mode") or error.get("displayMode") else "inline"
                st.markdown(f"**{index}. {mode}**")
                st.code(expr)
                st.write(message)


def _show_render_log(job) -> None:
    if not job.render_log.exists():
        return
    with st.expander("Render log"):
        st.code(job.render_log.read_text(encoding="utf-8", errors="replace"))


def _download_existing_artifacts(job, *, include_outputs: bool) -> None:
    if include_outputs:
        _download_button("Download clean.md", job.clean_md, "text/markdown")
        _download_button("Download final.html", job.final_html, "text/html")
        _download_button("Download final.pdf", job.final_pdf, "application/pdf")
    else:
        _download_button("Download clean.md", job.clean_md, "text/markdown")
    _download_button("Download validation.json", _validation_json_path(job), "application/json")
    _download_button("Download render.log", job.render_log, "text/plain")


def _download_button(label: str, path: Path, mime: str) -> None:
    if not path.exists():
        st.caption(f"Missing artifact: {path}")
        return
    st.download_button(
        label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime,
    )


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _safe_temp_prefix(filename: str) -> str:
    stem = Path(filename).stem or "upload"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-") or "upload"
    return f"{safe[:40]}_"


if __name__ == "__main__":
    main()
