"""Reproduce 180 deterministic ADK integration trials without credentials or model calls."""

import argparse
import asyncio
import hashlib
import json
import platform
from pathlib import Path

from .experiment import compare, load_cases


def make_cases():
    bases = load_cases(Path(__file__).parent / "fixtures" / "tasks.test.jsonl")
    expected = {
        "test-plants": {"DemoUrbanGardens": 0.12, "DemoPlantCare": 0.08},
        "test-python": {"DemoPythonLearning": 0.07, "DemoDataProjects": 0.09},
        "test-bread": {"DemoBreadBaking": 0.15},
        "test-camera": {"DemoCameraPractice": 0.05},
    }
    cases = []
    variants = [
        (False, False, None),
        (True, False, None),
        (False, True, None),
        (True, True, None),
        (True, True, 1),
    ]
    for base in bases:
        for i, (rules, analytics, limit) in enumerate(variants):
            row = base.model_dump()
            row["task"].update(
                id=f"{base.task.id}-v{i + 1}",
                needs_rules=rules,
                needs_analytics=analytics,
                max_results=limit or base.task.max_results,
            )
            # Single-result variants use the known first ranked fixture community.
            truth = list(expected[base.task.id])[: row["task"]["max_results"]]
            row["relevant_communities"] = truth
            row["expected_analysis"] = (
                {k: expected[base.task.id][k] for k in truth} if analytics else None
            )
            row["provenance"] = (
                "Synthetic integration matrix: four topics x five tool-requirement variants. "
                "Repeated trials check determinism, not independent model-quality samples."
            )
            cases.append(row)
    return cases


async def benchmark(output):
    output.mkdir(parents=True, exist_ok=True)
    cases = make_cases()
    dataset = output / "cases.jsonl"
    dataset.write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in cases))
    root, results = await compare(
        output / "raw", cases_path=dataset, repeats=3, adapter="offline-adk"
    )
    evidence = []
    for row in results:
        directory = root / f"{row['task_id']}-{row['policy']}-{row['repeat']}"
        snapshot = json.loads((directory / "state-snapshot.json").read_text())
        evidence.append(
            {
                "task_id": row["task_id"],
                "policy": row["policy"],
                "repeat": row["repeat"],
                "receipt": row["receipt"],
                "snapshot": snapshot,
            }
        )
    compact = output / "evidence.jsonl"
    compact.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in evidence))
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    hashes = {}
    for row in results:
        hashes.setdefault((row["task_id"], row["policy"]), set()).add(
            row["receipt"].get("report_sha256")
        )
    summary = {
        "adapter": "offline-adk",
        "model": "deterministic model double",
        "tasks": 20,
        "policies": 3,
        "repeats": 3,
        "trials": len(results),
        "completed": sum(r["completed"] for r in results),
        "numeric_trials": sum("analysis_correct" in r for r in results),
        "analysis_correct": sum(r.get("analysis_correct", False) for r in results),
        "numeric_consistency_passed": sum(r["numeric_consistency"] for r in results),
        "repeat_groups_identical": sum(len(v) == 1 and None not in v for v in hashes.values()),
        "token_savings": None,
        "model_quality": None,
        "python": platform.python_version(),
        "artifacts_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [dataset, compact, output / "results.json"]
        },
        "scope": "Real ADK Runner and tools; synthetic corpus; no live model inference.",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "report.md").write_text(
        "# 180-trial deterministic integration benchmark\n\n"
        "Four research topics × five tool-requirement variants "
        "× three policies × three repeats.\n\n"
        f"| Check | Result |\n|---|---:|\n| Completed workflows | {summary['completed']}/180 |\n"
        f"| Correct analytics | {summary['analysis_correct']}/{summary['numeric_trials']} |\n"
        f"| Publication consistency | {summary['numeric_consistency_passed']}/180 |\n"
        f"| Identical report hashes across repeats | {summary['repeat_groups_identical']}/60 |\n\n"
        "[Summary](summary.json) · [Per-trial results](results.json) · "
        "[State and receipts](evidence.jsonl) · [Task matrix](cases.jsonl)\n\n"
        "The deterministic model double drives real ADK tools and SQLite commits. "
        "Non-analytics tasks pass the numeric gate without claims. Repeats test stable execution; "
        "they are not independent model-quality samples. All policies use the same model double; "
        "this does not measure live routing quality, token savings or inference cost. "
        "Raw runs additionally retain traces and databases in the CI artifact.\n"
    )
    assert len(results) == 180 and summary["completed"] == 180
    assert summary["analysis_correct"] == summary["numeric_trials"] == 108
    assert summary["numeric_consistency_passed"] == 180
    assert summary["repeat_groups_identical"] == 60
    assert all(r["usage"] is None for r in results)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("runs/benchmark-180"))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(benchmark(args.output)), indent=2))


if __name__ == "__main__":
    main()
