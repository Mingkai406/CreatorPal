"""Program-Aided Language (PAL) package for dynamic analytics execution."""

from __future__ import annotations

from src.pal.executor import PALExecutor


def build_pal_executor(client: "OpenAI", model_name: str) -> PALExecutor:
    """Construct the PAL executor used by the pipeline.

    Args:
        client: OpenAI-compatible API client.
        model_name: Model identifier for code generation.
    """
    return PALExecutor(client=client, model_name=model_name)
