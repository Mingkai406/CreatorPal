# Independent semantic review

Citation integrity verifies identifiers and source relationships. It does not establish that
all prose follows from evidence. The review workflow supplies the task, report, evidence and
computed analysis to independent reviewers while withholding policy, model, latency, labels
and execution events from the review packet.

## Prepare and score

First run a new comparison with the CLI. Older comparisons without a task inventory must
be rerun before preparing a review packet. For live inference, provide authenticated model
IDs and optional pricing through its `--adapter adk`, `--fast-model`, `--strong-model` and
`--pricing` options. The built-in four-task dataset is a synthetic demonstration; replace it
with independently authored held-out cases for a meaningful quality study.

```sh
# Runnable without model credentials; this does NOT measure live model quality.
creatorpal-agent compare --adapter offline-adk --repeats 3 --output runs/study
# Replace comparison-ID with the directory printed above.
python -m creatorpal_agent.review prepare \
  --comparison runs/study/comparison-ID --out runs/review
# Share only items.json, RUBRIC.md and ratings.csv with reviewers.
# Concatenate the independently completed CSVs into completed-ratings.csv.
python -m creatorpal_agent.review score \
  --pack runs/review --ratings completed-ratings.csv --out runs/review/summary.json
```

The coordinator retains `review-key.json`. It maps anonymous item IDs to policies and repeats;
reviewers should not receive it. Random presentation order is reproducible with `--seed`.
This is presentation blinding, not a claim that the outputs themselves cannot reveal a policy.

## Scoring rules

- Score factual support and usefulness separately on a defined 0–2 rubric; cite problematic
  claims in notes. A numeric gate pass is not an automatic semantic-support score.
- Require two reviewer IDs per item by default. Duplicate ratings, unknown items and invalid
  scores fail validation. Every disagreement is flagged for adjudication and keeps that item's
  final quality score unresolved. Preserve original ratings before creating an adjudicated CSV.
- Blank ratings are missing, not zero. No human review means no semantic-quality result.
- Average repeats within each task, then equally weight tasks. Failed attempts remain in the
  denominator and receive zero utility/support per attempt; unreviewed successful attempts
  keep the quality estimate unknown. This composite is not a success-only quality score.
- Unknown costs remain unknown. Offline controls never acquire inferred token costs.
- Fingerprint source results, snapshots, manifests and the review packet. Reject modified
  packets and incomplete task/policy/repeat grids rather than silently dropping failed runs.

## Verified in this change

An actual 12-run offline ADK comparison produced a 12-item review packet. Scoring its untouched
blank ratings returned **12 unresolved items** and **null semantic-quality and cost estimates**,
as intended. The reference status in `examples/agent/independent-review/status.json` records
that boundary. Tests exercise agreement, disagreement, missing ratings, duplicate reviewers,
artifact modification, incomplete comparisons, and the treatment of failed attempts.

Live-model quality, human agreement, and cost improvements have **not** been measured by this
change. The feature makes those evaluations executable and auditable without inventing results.
