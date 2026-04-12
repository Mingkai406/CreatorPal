"""Human-evaluation framework for generated strategy reports."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def load_rubric() -> dict[str, str]:
    """Load rubric dimensions for 1-5 generation scoring.

    Returns:
        Dict mapping dimension name to its evaluation question.
    """
    return {
        "coherence": "Is the report logically structured and easy to follow?",
        "grounding": "Are recommendations backed by retrieved subreddit data?",
        "actionability": "Can the creator act on these recommendations?",
    }


def collect_single_rating(report: str, dimension: str, description: str) -> int:
    """Print the report and dimension, prompt user for a 1-5 rating.

    Args:
        report: The generated report text to evaluate.
        dimension: Name of the evaluation dimension.
        description: Evaluation question for this dimension.

    Returns:
        Integer rating between 1 and 5.
    """
    print("\n" + "=" * 60)
    print("REPORT:")
    print(report)
    print("=" * 60)
    print(f"\nDimension: {dimension}")
    print(f"Question:  {description}")

    while True:
        raw = input("Rating (1-5): ").strip()
        try:
            rating = int(raw)
            if 1 <= rating <= 5:
                return rating
            print("Please enter a number between 1 and 5.")
        except ValueError:
            print("Invalid input. Please enter a number between 1 and 5.")


def evaluate_report(report: str) -> dict[str, int]:
    """Collect human ratings for a single report across all rubric dimensions.

    Args:
        report: The generated report text to evaluate.

    Returns:
        Dict mapping each dimension to its integer rating.
    """
    rubric = load_rubric()
    scores: dict[str, int] = {}
    for dimension, description in rubric.items():
        scores[dimension] = collect_single_rating(report, dimension, description)
    return scores


def summarize_scores(all_scores: list[dict[str, int]]) -> dict[str, float]:
    """Compute average score per dimension across all evaluated reports.

    Args:
        all_scores: List of per-report score dicts.

    Returns:
        Dict mapping each dimension to its average score.
    """
    if not all_scores:
        return {}
    dimensions = all_scores[0].keys()
    return {
        dim: float(np.mean([s[dim] for s in all_scores]))
        for dim in dimensions
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for generation evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate generated strategy reports.")
    parser.add_argument(
        "--reports-dir",
        required=True,
        help="Directory containing generated report .txt files.",
    )
    return parser.parse_args()


def main() -> None:
    """Run generation evaluation from the command line."""
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    report_files = sorted(reports_dir.glob("*.txt"))

    if not report_files:
        print(f"No .txt report files found in {reports_dir}")
        return

    all_scores: list[dict[str, int]] = []
    for path in report_files:
        print(f"\n>>> Evaluating: {path.name}")
        report = path.read_text()
        scores = evaluate_report(report)
        all_scores.append(scores)
        print(f"    Scores: {scores}")

    summary = summarize_scores(all_scores)
    print("\nGeneration Evaluation Summary")
    print("-" * 30)
    for dim, avg in summary.items():
        print(f"  {dim}: {avg:.2f}")


if __name__ == "__main__":
    main()
