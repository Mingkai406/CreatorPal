"""Generation package for final RAG-conditioned audience strategy reports."""

from __future__ import annotations

from src.generator.augmented_gen import AugmentedGenerator


def build_generator() -> AugmentedGenerator:
    """Construct the final report generator used by the pipeline."""
    raise NotImplementedError("Implement report generator factory.")
