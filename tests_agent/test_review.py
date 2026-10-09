import csv
import json

import pytest

from creatorpal_agent.experiment import compare
from creatorpal_agent.review import FIELDS, aggregate, prepare


@pytest.fixture
async def packet(tmp_path):
    root, _ = await compare(tmp_path / "runs")
    return prepare(root, tmp_path / "review")


@pytest.mark.asyncio
async def test_blank_ratings_are_unknown_and_identity_is_hidden(packet):
    items = json.loads((packet / "items.json").read_text())
    assert len(items) == 12
    assert all(set(i) == {"item_id", "task", "report", "evidence", "analyses"} for i in items)
    result = aggregate(packet, packet / "ratings.csv")
    assert result["unresolved_items"] == 12
    assert all(p["factual_support_per_attempt"] is None for p in result["policies"].values())
    assert all(p["mean_cost_usd"] is None for p in result["policies"].values())


@pytest.mark.asyncio
async def test_review_agreement_conflicts_duplicates_and_tampering(packet):
    ids = [i["item_id"] for i in json.loads((packet / "items.json").read_text())]
    ratings = packet / "completed.csv"
    rows = [[item, reviewer, 2, 1, "test fixture only"] for item in ids for reviewer in ("a", "b")]

    def save():
        with ratings.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
            w.writerows(rows)

    save()
    result = aggregate(packet, ratings)
    assert result["unresolved_items"] == 0
    assert all(p["factual_support_per_attempt"] == 2 for p in result["policies"].values())
    rows[0][2] = 0
    save()
    assert aggregate(packet, ratings)["unresolved_items"] == 1
    rows.append(rows[0])
    save()
    with pytest.raises(ValueError, match="duplicate"):
        aggregate(packet, ratings)
    (packet / "items.json").write_text("[]")
    with pytest.raises(ValueError, match="changed"):
        aggregate(packet, ratings)


@pytest.mark.asyncio
async def test_failed_runs_stay_in_denominator_and_missing_runs_fail(tmp_path):
    root, results = await compare(tmp_path / "runs")
    failed = results[0]
    failed["completed"] = False
    folder = root / f"{failed['task_id']}-{failed['policy']}-{failed['repeat']}"
    (folder / "result.json").write_text(
        json.dumps({k: v for k, v in failed.items() if k != "repeat"})
    )
    (root / "comparison.json").write_text(json.dumps(results))
    packet = prepare(root, tmp_path / "review")
    report = aggregate(packet, packet / "ratings.csv")
    task = next(
        t
        for t in report["tasks"]
        if t["task_id"] == failed["task_id"] and t["policy"] == failed["policy"]
    )
    assert task["completion_rate"] == 0
    assert task["factual_support_per_attempt"] == 0
    (root / "comparison.json").write_text(json.dumps(results[1:]))
    with pytest.raises(ValueError, match="every task"):
        prepare(root, tmp_path / "incomplete")

    (root / "comparison.json").write_text(
        json.dumps([r for r in results if r["task_id"] != failed["task_id"]])
    )
    with pytest.raises(ValueError, match="every task"):
        prepare(root, tmp_path / "missing-task")
