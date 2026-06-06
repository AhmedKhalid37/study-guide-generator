"""Host-side Local Model Manager companion prototype.

Phase 2B is scanning-only: approved GGUF roots, safe metadata, and an optional
Unix socket API. It does not start, stop, or manage model server processes.
"""

__all__ = ["companion", "config", "model_library"]
