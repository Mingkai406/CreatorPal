"""Blinded evidence review and task-level policy aggregation; never an LLM judge."""

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

FIELDS = ["item_id", "reviewer", "factual_support", "usefulness", "notes"]
RUBRIC = """# Independent report review

Open items.json and score each report against its supplied evidence and task.
Do not open review-key.json until ratings are locked: it contains policy identities.
Share only items.json, RUBRIC.md and ratings.csv with reviewers.
IDs and presentation order conceal policy/model identity, not task content.

factual_support: 0 = a central claim contradicts or lacks supplied evidence;
1 = central claims supported but some details overreach; 2 = all material claims supported.
usefulness: 0 = does not answer the task; 1 = partly actionable or misses a requirement;
2 = actionable recommendations that address the task and its constraints.
Judge numbers and prose, not merely whether citation IDs exist. Evidence may itself be
incomplete: do not fill gaps with personal knowledge. Explain unsupported claims in notes.

Use reviewer identifiers. Each reviewer contributes one row per item. Concatenate completed
CSVs (one header) for scoring. Default: at least two independent reviewers per item.
Any score disagreement is flagged for adjudication; no automatic quality winner is declared.
Blank ratings are missing, never zero. Failed runs stay in the completion denominator.
No supplied ratings means semantic quality remains unmeasured, even for offline controls.
"""


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(comparison, output, seed=17):
    comparison, output = Path(comparison).resolve(), Path(output)
    results = read(comparison / "comparison.json")
    if not results:
        raise ValueError("Empty comparison")
    identities = [(r["task_id"], r["policy"], r["repeat"]) for r in results]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate run identities")
    dataset = read(comparison / "dataset-manifest.json")
    if type(dataset["repeats"]) is not int or dataset["repeats"] < 1:
        raise ValueError("Invalid repeat count")
    if not dataset.get("task_ids"):
        raise ValueError("Comparison predates task inventory; rerun compare before review")
    expected = {
        (task, policy, repeat)
        for task in dataset["task_ids"]
        for policy in dataset["policies"]
        for repeat in range(dataset["repeats"])
    }
    if set(identities) != expected:
        raise ValueError("Comparison must include every task/policy/repeat, including failures")
    items, keys, hashes = [], [], {}
    shuffled = list(results)
    random.Random(seed).shuffle(shuffled)
    for index, result in enumerate(shuffled):
        folder = comparison / f"{result['task_id']}-{result['policy']}-{result['repeat']}"
        if not folder.resolve().is_relative_to(comparison):
            raise ValueError("Run path escapes comparison")
        run = read(folder / "result.json")
        if {k: v for k, v in result.items() if k != "repeat"} != run:
            raise ValueError("Comparison and per-run result differ")
        for name in ("result.json", "manifest.json", "state-snapshot.json"):
            path = folder / name
            hashes[str(path.relative_to(comparison))] = fingerprint(path)
        if not result["completed"]:
            continue
        snapshot = read(folder / "state-snapshot.json")
        if len(snapshot["reports"]) != 1:
            raise ValueError("Completed run must contain exactly one report")
        item_id = f"item-{index + 1:04d}"
        # Whitelist reviewer content: no model, policy, timing, labels or execution events.
        items.append(
            {
                "item_id": item_id,
                "task": snapshot["task"],
                "report": snapshot["reports"][0],
                "evidence": snapshot["evidence"],
                "analyses": snapshot["analyses"],
            }
        )
        keys.append(
            {
                "item_id": item_id,
                "task_id": result["task_id"],
                "policy": result["policy"],
                "repeat": result["repeat"],
            }
        )
    output.mkdir(parents=True, exist_ok=False)
    write(output / "items.json", items)
    write(output / "review-key.json", {"runs": results, "items": keys})
    (output / "RUBRIC.md").write_text(RUBRIC)
    with (output / "ratings.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows([i["item_id"], "", "", "", ""] for i in items)
    write(
        output / "provenance.json",
        {
            "comparison_sha256": fingerprint(comparison / "comparison.json"),
            "dataset_manifest_sha256": fingerprint(comparison / "dataset-manifest.json"),
            "source_artifacts": hashes,
            "seed": seed,
            "items_sha256": fingerprint(output / "items.json"),
            "key_sha256": fingerprint(output / "review-key.json"),
            "rubric_sha256": fingerprint(output / "RUBRIC.md"),
        },
    )
    return output


def aggregate(pack, ratings, min_reviewers=2):
    pack = Path(pack)
    if min_reviewers < 1:
        raise ValueError("At least one reviewer required")
    provenance = read(pack / "provenance.json")
    for filename, key in (
        ("items.json", "items_sha256"),
        ("review-key.json", "key_sha256"),
        ("RUBRIC.md", "rubric_sha256"),
    ):
        if fingerprint(pack / filename) != provenance[key]:
            raise ValueError("Review packet changed after preparation")
    key = read(pack / "review-key.json")
    by_id = {r["item_id"]: r for r in key["items"]}
    grouped = defaultdict(list)
    seen = set()
    with Path(ratings).open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected rating columns")
        for row in reader:
            if row["item_id"] not in by_id:
                raise ValueError("Unknown review item")
            if all(
                not row[k].strip() for k in ("reviewer", "factual_support", "usefulness", "notes")
            ):
                continue
            reviewer = row["reviewer"].strip()
            if not reviewer or (row["item_id"], reviewer) in seen:
                raise ValueError("Missing reviewer or duplicate rating")
            if any(row[k] not in {"0", "1", "2"} for k in ("factual_support", "usefulness")):
                raise ValueError("Both ratings must be integers 0, 1 or 2")
            seen.add((row["item_id"], reviewer))
            grouped[row["item_id"]].append(
                {
                    "reviewer": reviewer,
                    "factual_support": int(row["factual_support"]),
                    "usefulness": int(row["usefulness"]),
                    "notes": row["notes"],
                }
            )
    reviews, approved = [], {}
    for item_id, identity in by_id.items():
        scores = grouped[item_id]
        enough = len(scores) >= min_reviewers
        disagreement = any(
            len({s[metric] for s in scores}) > 1 for metric in ("factual_support", "usefulness")
        )
        reviews.append(
            {
                **identity,
                "ratings": scores,
                "sufficient_reviewers": enough,
                "needs_adjudication": disagreement,
            }
        )
        if enough and not disagreement:
            approved[(identity["task_id"], identity["policy"], identity["repeat"])] = scores[0]
    tasks = defaultdict(list)
    for run in key["runs"]:
        tasks[(run["policy"], run["task_id"])].append(run)
    task_rows = []
    for (policy, task_id), runs in sorted(tasks.items()):
        complete = [r for r in runs if r["completed"]]
        accepted = [approved.get((task_id, policy, r["repeat"])) for r in complete]
        resolved = all(s is not None for s in accepted)
        row = {
            "policy": policy,
            "task_id": task_id,
            "runs": len(runs),
            "completion_rate": len(complete) / len(runs),
            "quality_review_resolved": resolved,
            "reviewed_completions": sum(s is not None for s in accepted),
        }
        for metric in ("factual_support", "usefulness"):
            # Failed runs contribute zero; successful but unreviewed runs make quality unknown.
            row[metric + "_per_attempt"] = (
                sum(s[metric] for s in accepted) / len(runs) if resolved else None
            )
        costs = [r.get("estimated_cost_usd") for r in runs]
        row["mean_cost_usd"] = statistics.mean(costs) if all(c is not None for c in costs) else None
        task_rows.append(row)
    policies = {}
    for policy in sorted({t["policy"] for t in task_rows}):
        selected = [t for t in task_rows if t["policy"] == policy]
        policies[policy] = {
            metric: statistics.mean([t[metric] for t in selected])
            if all(t[metric] is not None for t in selected)
            else None
            for metric in (
                "completion_rate",
                "factual_support_per_attempt",
                "usefulness_per_attempt",
                "mean_cost_usd",
            )
        }
    return {
        "ratings_sha256": fingerprint(ratings),
        "packet": provenance,
        "adapters": sorted({r["adapter"] for r in key["runs"]}),
        "measurement": "Human ratings of supplied artifacts; offline runs remain offline controls",
        "aggregation": "Average repeats within task, then equal-weight tasks; failures retained",
        "minimum_reviewers": min_reviewers,
        "items": reviews,
        "tasks": task_rows,
        "policies": policies,
        "unresolved_items": sum(
            not r["sufficient_reviewers"] or r["needs_adjudication"] for r in reviews
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("--comparison", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    create.add_argument("--seed", type=int, default=17)
    score = commands.add_parser("score")
    score.add_argument("--pack", type=Path, required=True)
    score.add_argument("--ratings", type=Path, required=True)
    score.add_argument("--min-reviewers", type=int, default=2)
    score.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.command == "prepare":
        print(prepare(a.comparison, a.out, a.seed))
    else:
        result = aggregate(a.pack, a.ratings, a.min_reviewers)
        if a.out.exists():
            p.error("Output already exists")
        write(a.out, result)
        print(f"Unresolved review items: {result['unresolved_items']}")


if __name__ == "__main__":
    main()
