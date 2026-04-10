"""Program-Aided Language (PAL) package for dynamic analytics execution."""

from __future__ import annotations

from src.pal.executor import PALExecutor


def build_pal_executor() -> PALExecutor:
    """Construct the PAL executor used by the pipeline."""
    raise NotImplementedError("Implement PAL executor factory.")
