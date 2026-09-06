# Testing CreatorPal

Run these commands from the repository root. Start with offline checks, then test one live task before paying for a comparison. The agent CLI and the original Streamlit pipeline have separate entry points.

## 1. Verify the implementation without a provider

```sh
uv sync --locked --extra adk --extra dev
uv run pytest -q tests_agent
uv run creatorpal-agent run --adapter offline-adk --task examples/agent/task.json --output runs/smoke
uv run creatorpal-agent compare --adapter offline-adk --output runs/offline
```

Expected results for the checked-in version:

- 39 tests pass; the Docker test skips unless explicitly enabled below.
- The single task returns `completed: true` and a report receipt. Its artifacts are under `runs/smoke/audience-demo-<id>/`.
- The comparison completes 12 runs: four synthetic tasks times three policies. Numeric tasks have `analysis_correct: true` in `comparison.json`.

The ADK Runner and business tools execute normally. The model is a deterministic test double, so these checks verify implementation, not model quality. ADK may log missing token metadata for the double; token/cost fields are intentionally unavailable.

To test the container boundary, start Docker first:

```sh
docker build -f Dockerfile.analytics -t creatorpal-analytics .
CREATORPAL_DOCKER_TEST=1 uv run pytest -q tests_agent/test_research.py -k docker
uv run creatorpal-agent run --adapter offline-adk --sandbox docker \
  --task examples/agent/task.json --output runs/docker
```

The selected Docker test should pass. The run should complete using a non-root container with no network, no host mounts and a read-only filesystem. GitHub's Agent CI also builds the wheel, installs it outside the checkout, runs both comparison controls and executes the Docker test.

The original PAL/sentiment tests require the original application dependencies, including model libraries. In that environment use `python -m pytest -q tests/test_pal.py tests/test_sentiment.py`; executing the test files as plain scripts does not run pytest test cases. `uv sync` for the lightweight agent does not install all legacy dependencies. With the model files already cached, set `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` to prevent downloads during that regression check.

## 2. Test one real model on a known task

Configure Gemini API credentials in the shell environment, or configure your supported Google Cloud authentication. See the [official ADK Gemini authentication guide](https://adk.dev/agents/models/google-gemini/#gemini-model-authentication). The reference-backend CLI does not automatically load a repository `.env`; its process must receive the credentials as environment variables. Do not paste keys into task files or commits.

Set `FAST_MODEL` to a model ID actually available in that environment. Prefer a specific model version for comparisons. An OpenAI-compatible vLLM URL alone is not accepted by the new CLI; the older Streamlit/vLLM pipeline remains separate.

```sh
export FAST_MODEL='your-accessible-model-id'
uv run creatorpal-agent run --adapter adk --fast-model "$FAST_MODEL" \
  --task examples/agent/task.json --output runs/live-smoke
```

Inspect `result.json`, `reports.json`, `state-snapshot.json` and `manifest.json` in the generated task directory. Check:

1. The task completes with one report and a receipt matching that report.
2. Each recommended community cites its retrieved profile and rules.
3. The analysis result uses the retrieved `engagement_rate` values; it does not invent another metric or data source.
4. The actual model and configuration are recorded; provider token usage is present when returned. A null cost is expected until you supply a pricing file.
5. Read the report beside the evidence: source IDs alone cannot verify that every sentence is supported.

This first task uses synthetic data deliberately, so tool behavior is easy to inspect. Passing it is an integration smoke test, not a real-world quality result. If it fails, inspect `receipt.error_type` and ordered `events` in `result.json` before increasing the run count. A 401/403 points to access configuration; a 429 points to provider limits; `NoValidCompletion`, an invalid citation or missing analysis needs a tool/prompt/output investigation. Keep failed trials in the evaluation record.

## 3. Compare skills and model-routing policies

After the single-task test, set a second accessible model ID and run the small matrix once:

```sh
export STRONG_MODEL='your-accessible-stronger-model-id'
uv run creatorpal-agent compare --adapter adk \
  --fast-model "$FAST_MODEL" --strong-model "$STRONG_MODEL" \
  --repeats 1 --output runs/live-pilot
```

This requests 12 tasks through the models, with potentially multiple calls per task. Each task has a maximum of two ADK invocations with up to 16 model calls each. A routed task may select the stronger model immediately or escalate once. The pilot is billable and still uses the demonstration data.

Then freeze real tasks and their evidence corpus before tuning against results. A practical first study is 20 distinct tasks, three policies and three repeats (180 task runs). This is a proposed starting size, not a guarantee of statistical power. Include discovery-only, rules-required and numeric-analysis tasks. Use separate development tasks to change prompts or Skills; do not repeatedly tune on the frozen test set.

Each line in the test JSONL must follow `EvaluationCase` from `creatorpal_agent/contracts.py`, for example:

```json
{"task":{"id":"audience-001","query":"Find relevant communities using the supplied evidence","needs_rules":false,"needs_analytics":false,"max_results":2},"relevant_communities":["ActualCommunity"],"split":"test","provenance":"Human-labeled task against frozen corpus version 1"}
```

Use unique IDs, `split: "test"`, actual relevant community labels and documented provenance. For numeric tasks, add `expected_analysis`, a mapping from community names to expected numeric values. The current numeric scorer handles this mapping format; arbitrary analytical output shapes need their own scorer. Evidence JSON follows `Evidence` in the same contracts file, with collection dates, source URLs and the numeric fields the task asks about.

```sh
uv run creatorpal-agent compare --adapter adk \
  --fast-model "$FAST_MODEL" --strong-model "$STRONG_MODEL" \
  --cases /path/to/frozen-test-cases.jsonl --corpus /path/to/evidence-corpus.json \
  --repeats 3 --output runs/live-study
```

These comparisons use the supplied file-backed lexical search. To evaluate the original BM25/FAISS/cross-encoder backend, configure its real indexes, install the `retrieval` extra and explicitly pass `--backend legacy`, plus `--rules-corpus` for rule tasks. The legacy adapter exposes ranking scores, not engagement metrics; choose tasks and numeric targets supported by the actual data. See the [backend setup](README.md#use-the-original-retrieval-backend).

## 4. Decide whether the change helped

Start with `report.md`, then use the full metrics in `comparison.json`:

| Question | Evidence to inspect |
|---|---|
| Did work finish correctly? | Completion flag, one committed report, matching receipt, trace/events |
| Did it find relevant communities? | Recall@K, reciprocal rank and NDCG@K against the frozen labels |
| Were numeric answers correct? | `analysis_correct` and the saved program, rows and result |
| Did progressive loading reduce model input? | Real `usage` input tokens; loaded character counts alone are insufficient |
| Did stronger-model routing help? | Per-task quality, failures, latency and usage across all three policies |
| Is the prose supported and useful? | Human review beside the actual source evidence |

Fill `human-review.csv` using a predefined rubric. For factual support: 0 = material unsupported/contradictory claims, 1 = partially supported or missing caveats, 2 = material claims supported. For usefulness: 0 = unusable, 1 = useful with substantial revision, 2 = actionable within the task's scope. Record reviewer and notes; keep policy/model information out of the review copy if doing blinded review. A second reviewer can independently rate a subset and resolve disagreements.

Keep the same task set and corpus across policies. Summarize repeats per task before comparing policies; report failures and variation, not just the best run. Define acceptable quality and cost thresholds before inspecting results. Completion is necessary but does not imply semantic correctness. The original fixed pipeline is not one of these three policies, so improvement over that pipeline requires an additional matched baseline experiment.

For cost estimates, supply `--pricing /path/to/pricing.json`. Keys must exactly match model IDs, with numeric nonnegative `input_per_million` and `output_per_million` rates from your provider's applicable pricing. Incomplete usage produces a null estimate; do not treat null as zero. The current estimate uses flat rates and does not include cache discounts or all provider billing variations.

Save the Git commit, `dataset-manifest.json`, per-run manifests, all results and reviewer decisions together. Re-run the offline suite after any code or Skill change. Use a new comparison directory and fresh task state for each model experiment.

## 5. Check faults and restart behavior

Use the [separate Harness test guide](https://github.com/Mingkai406/agent-reliability-harness/blob/main/docs/testing.md) for external fault injection. CreatorPal's own `test_restart_after_process_dies_after_commit` terminates a child process immediately after its commit transaction, then starts a new process against the same state and verifies one report and one commit event.

For manual artifact recovery, repeat a `run` command with the same task/corpus/sandbox and `--state /path/to/the/original/state.sqlite`. A committed task reuses its receipt; a different task or corpus is rejected. This is an artifact recovery check, not a fresh model-quality trial.
