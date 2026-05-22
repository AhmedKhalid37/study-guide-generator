from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from pipeline.run_markdown_job import MarkdownJobError, run_markdown_job, run_pasted_text_job


def main() -> None:
    st.set_page_config(page_title="Study Guide Generator", layout="centered")
    st.title("Study Guide Generator")

    _init_state()

    mode = st.radio("Mode", ["Upload Markdown", "Paste Text"], horizontal=True)
    theme = st.selectbox("Theme", ["claude_clean"], index=0)
    strict_math = st.checkbox("Strict math validation", value=True)

    if mode == "Upload Markdown":
        _upload_mode(theme=theme, strict_math=strict_math)
    else:
        _paste_mode(theme=theme, strict_math=strict_math)

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
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
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


def _run_job(factory) -> None:
    st.session_state.last_job = None
    st.session_state.last_error = None
    st.session_state.last_failed_job = None

    with st.spinner("Running job..."):
        try:
            st.session_state.last_job = factory()
        except MarkdownJobError as exc:
            st.session_state.last_error = str(exc)
            st.session_state.last_failed_job = exc.job
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
        return

    if job is None:
        return

    st.success("Job completed.")
    st.write(f"Job id: `{job.id}`")
    st.write(f"Job folder: `{job.dir}`")
    st.write(f"clean.md: `{job.clean_md}`")
    st.write(f"final.html: `{job.final_html}`")
    st.write(f"final.pdf: `{job.final_pdf}`")

    _download_button("Download clean.md", job.clean_md, "text/markdown")
    _download_button("Download final.html", job.final_html, "text/html")
    _download_button("Download final.pdf", job.final_pdf, "application/pdf")
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


if __name__ == "__main__":
    main()
