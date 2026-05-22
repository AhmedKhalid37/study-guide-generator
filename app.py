from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import streamlit as st

from pipeline.llm_client import LLMConfig, MissingLLMConfigError, load_env_file
from pipeline.run_llm_job import LLMJobError, run_llm_job
from pipeline.run_markdown_job import MarkdownJobError, run_markdown_job, run_pasted_text_job


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


def _init_state() -> None:
    st.session_state.setdefault("last_job", None)
    st.session_state.setdefault("last_error", None)
    st.session_state.setdefault("last_failed_job", None)


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
    title = st.text_input("Title", value="Generated Study Guide")
    guide_mode = st.selectbox("Mode", ["exam", "theory", "quick", "deep"], index=0)
    model_choice = st.selectbox(
        "Model",
        [
            "Use environment default",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        index=0,
    )
    selected_model = None if model_choice == "Use environment default" else model_choice
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
                theme=theme,
                strict_math=strict_math,
                config=_llm_config_for_model(selected_model),
            )
        )


def _llm_config_for_model(selected_model: str | None) -> LLMConfig:
    config = LLMConfig.from_env()
    if selected_model is None:
        return config
    return LLMConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=selected_model,
        temperature=config.temperature,
    )


def _run_job(factory) -> None:
    st.session_state.last_job = None
    st.session_state.last_error = None
    st.session_state.last_failed_job = None

    with st.spinner("Running job..."):
        try:
            st.session_state.last_job = factory()
        except MissingLLMConfigError:
            st.session_state.last_error = (
                "Missing LLM environment variables. "
                "Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL."
            )
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
            st.write(f"Job folder: `{failed_job.dir}`")
            _show_validation_summary(failed_job)
            _show_render_log(failed_job)
            _download_existing_artifacts(failed_job, include_outputs=False)
        return

    if job is None:
        return

    st.success("Job completed.")
    st.write(f"Job id: `{job.id}`")
    _show_validation_summary(job)

    with st.expander("Job details"):
        st.write(f"Job folder: `{job.dir}`")
        st.write(f"clean.md: `{job.clean_md}`")
        st.write(f"final.html: `{job.final_html}`")
        st.write(f"final.pdf: `{job.final_pdf}`")

    _download_existing_artifacts(job, include_outputs=True)


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


def _show_llm_config_status() -> None:
    load_env_file()
    st.write(f"Base URL: `{'present' if os.getenv('LLM_BASE_URL') else 'missing'}`")
    st.write(f"API key: `{'present' if os.getenv('LLM_API_KEY') else 'missing'}`")
    st.write(f"Default model: `{os.getenv('LLM_MODEL') or 'missing'}`")
    selected = st.session_state.get("selected_llm_model")
    if selected:
        st.write(f"Selected model for this run: `{selected}`")
    else:
        st.write("Selected model for this run: `environment default`")


def _show_validation_summary(job) -> None:
    validation_path = job.logs_dir / "validation.json"
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
    _download_button("Download validation.json", job.logs_dir / "validation.json", "application/json")
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
