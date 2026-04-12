"""Tests for the evaluation modules."""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest

from eval.retrieval_eval import mean_reciprocal_rank, recall_at_k, run_retrieval_evaluation
from eval.generation_eval import load_rubric, summarize_scores


# ---------------------------------------------------------------------------
# recall_at_k
# ---------------------------------------------------------------------------

class TestRecallAtK:
    """Tests for recall_at_k."""

    def test_perfect_recall(self) -> None:
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert recall_at_k(retrieved, relevant, k=3) == pytest.approx(1.0)

    def test_partial_recall(self) -> None:
        retrieved = ["a", "b", "c", "d"]
        relevant = {"a", "c", "e"}
        # top-4 contains a and c -> 2/3
        assert recall_at_k(retrieved, relevant, k=4) == pytest.approx(2.0 / 3.0)

    def test_zero_recall(self) -> None:
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=3) == pytest.approx(0.0)

    def test_k_smaller_than_list(self) -> None:
        retrieved = ["a", "b", "c", "d"]
        relevant = {"c", "d"}
        # top-2 is [a, b] -> 0 hits
        assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(0.0)

    def test_capped_at_one(self) -> None:
        # More hits than relevant items shouldn't exceed 1.0
        retrieved = ["a", "a", "b"]
        relevant = {"a"}
        assert recall_at_k(retrieved, relevant, k=3) <= 1.0

    def test_empty_relevant(self) -> None:
        assert recall_at_k(["a", "b"], set(), k=2) == 0.0


# ---------------------------------------------------------------------------
# mean_reciprocal_rank
# ---------------------------------------------------------------------------

class TestMeanReciprocalRank:
    """Tests for mean_reciprocal_rank (single-query version)."""

    def test_first_position(self) -> None:
        retrieved = ["a", "b", "c"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == pytest.approx(1.0)

    def test_third_position(self) -> None:
        retrieved = ["x", "y", "a"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == pytest.approx(1.0 / 3.0)

    def test_not_found(self) -> None:
        retrieved = ["x", "y", "z"]
        relevant = {"a"}
        assert mean_reciprocal_rank(retrieved, relevant) == pytest.approx(0.0)

    def test_multiple_relevant(self) -> None:
        # Should return reciprocal rank of the *first* relevant item
        retrieved = ["x", "a", "b"]
        relevant = {"a", "b"}
        assert mean_reciprocal_rank(retrieved, relevant) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# run_retrieval_evaluation (end-to-end with temp files)
# ---------------------------------------------------------------------------

class TestRunRetrievalEvaluation:
    """Tests for run_retrieval_evaluation with temporary CSV files."""

    def test_end_to_end(self, tmp_path: Path) -> None:
        gt_path = tmp_path / "gt.csv"
        pred_path = tmp_path / "pred.csv"

        # Ground truth: channel1 -> {sub_a, sub_b}, channel2 -> {sub_c}
        with open(gt_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["channel_id", "subreddit"])
            w.writerow(["channel1", "sub_a"])
            w.writerow(["channel1", "sub_b"])
            w.writerow(["channel2", "sub_c"])

        # Predictions: channel1 retrieves [sub_a, sub_x, sub_b], channel2 retrieves [sub_x, sub_c]
        with open(pred_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["channel_id", "subreddit", "rank"])
            w.writerow(["channel1", "sub_a", 1])
            w.writerow(["channel1", "sub_x", 2])
            w.writerow(["channel1", "sub_b", 3])
            w.writerow(["channel2", "sub_x", 1])
            w.writerow(["channel2", "sub_c", 2])

        metrics = run_retrieval_evaluation(
            ground_truth_path=str(gt_path),
            predictions_path=str(pred_path),
            k_values=[2, 3],
        )

        # channel1 recall@2: 1/2 = 0.5, channel2 recall@2: 1/1 = 1.0 -> avg 0.75
        assert metrics["recall@2"] == pytest.approx(0.75)
        # channel1 recall@3: 2/2 = 1.0, channel2 recall@3: 1/1 = 1.0 -> avg 1.0
        assert metrics["recall@3"] == pytest.approx(1.0)
        # channel1 MRR: 1/1 = 1.0, channel2 MRR: 1/2 = 0.5 -> avg 0.75
        assert metrics["mrr"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# generation_eval
# ---------------------------------------------------------------------------

class TestLoadRubric:
    """Tests for load_rubric."""

    def test_returns_three_dimensions(self) -> None:
        rubric = load_rubric()
        assert len(rubric) == 3

    def test_expected_keys(self) -> None:
        rubric = load_rubric()
        assert set(rubric.keys()) == {"coherence", "grounding", "actionability"}

    def test_values_are_strings(self) -> None:
        rubric = load_rubric()
        for v in rubric.values():
            assert isinstance(v, str)


class TestSummarizeScores:
    """Tests for summarize_scores."""

    def test_single_report(self) -> None:
        scores = [{"coherence": 4, "grounding": 3, "actionability": 5}]
        summary = summarize_scores(scores)
        assert summary["coherence"] == pytest.approx(4.0)
        assert summary["grounding"] == pytest.approx(3.0)
        assert summary["actionability"] == pytest.approx(5.0)

    def test_multiple_reports(self) -> None:
        scores = [
            {"coherence": 4, "grounding": 2, "actionability": 5},
            {"coherence": 2, "grounding": 4, "actionability": 3},
        ]
        summary = summarize_scores(scores)
        assert summary["coherence"] == pytest.approx(3.0)
        assert summary["grounding"] == pytest.approx(3.0)
        assert summary["actionability"] == pytest.approx(4.0)

    def test_empty_list(self) -> None:
        assert summarize_scores([]) == {}
