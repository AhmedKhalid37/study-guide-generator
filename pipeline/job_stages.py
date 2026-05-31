from __future__ import annotations

# Ordered, coarse-grained progress stages for a generation job.
#
# These are FINER-grained than the job ``status`` field
# (queued/running/done/completed_with_warnings/failed): a job stays in status
# "running" while it advances through these stages. ``status`` remains the source
# of truth for terminal state — ``stage``/``progress`` exists purely so a progress
# UI can poll and show where a still-running job is.
#
# Each stage = {key, label, percent}. ``label`` is the user-facing text.
#
# Not every job hits every stage, and stages are emitted ONLY at pipeline
# boundaries that already exist (we never invent a step just to light up a
# stage). Consequences:
#   - A paste/markdown job has no LLM phase: it goes preparing -> cleaning -> ...
#   - A job without attachments skips "extracting".
#   - Only a job that uses a generator preset hits "loading_preset".
#   - "reading_pages" and "planning" are defined here for completeness / a
#     stable percent ladder, but the current pipeline has no clean boundary to
#     emit them from (page reading happens inside a single atomic extract call;
#     the outline is injected into the source before the job runs, so there is no
#     in-job planning step). They are intentionally NOT emitted.
# Progress is therefore monotonic but may jump over inapplicable stages.

STAGES: list[dict] = [
    {"key": "preparing", "label": "Preparing…", "percent": 5},
    {"key": "extracting", "label": "Extracting text…", "percent": 10},
    {"key": "reading_pages", "label": "Reading pages…", "percent": 15},
    {"key": "planning", "label": "Planning outline…", "percent": 20},
    {"key": "loading_preset", "label": "Loading preset…", "percent": 25},
    {"key": "connecting_model", "label": "Connecting to model…", "percent": 30},
    {"key": "writing", "label": "Writing guide…", "percent": 35},
    {"key": "cleaning", "label": "Cleaning up Markdown…", "percent": 75},
    {"key": "checking_math", "label": "Checking math…", "percent": 82},
    {"key": "rendering", "label": "Rendering PDF…", "percent": 88},
    {"key": "exporting", "label": "Exporting files…", "percent": 95},
    {"key": "complete", "label": "Complete", "percent": 100},
]

_STAGE_BY_KEY: dict[str, dict] = {stage["key"]: stage for stage in STAGES}


def get_stage(key: str) -> dict:
    """Return the stage record for ``key`` (raises KeyError for an unknown key)."""
    try:
        return _STAGE_BY_KEY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown job stage: {key!r}") from exc
