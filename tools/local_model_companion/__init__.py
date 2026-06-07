"""Host-side Local Model Manager companion prototype.

The HTTP companion remains scan-only. Phase 2G1 adds private process-control
internals for fake-executable tests only; no start/stop HTTP API is exposed.
"""

__all__ = ["companion", "config", "model_library", "process_manager", "profiles"]
