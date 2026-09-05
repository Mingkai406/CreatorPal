import asyncio
import csv
import importlib.metadata
import json
import math
import time
import uuid
from pathlib import Path

from .backends import CorpusBackend
from .contracts import EvaluationCase
from .runtime import InterruptedTask, ResearchRuntime, run_scripted
from .sandbox import AnalyticsSandbox
from .state import ResearchState, digest
from .telemetry import make_provider

POLICIES = ("eager-fast", "progressive-fast", "progressive-routed")


def select_model(task, policy, fast, strong):
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    if policy == "progressive-routed" and task.needs_analytics:
        return strong, "explicit_numeric_analysis"
    return fast, "default_fast"


def score(runtime, receipt, relevant=None, expected_analysis=None):
    reports = runtime.state.reports()
    predictions = [r["community"] for r in reports[0]["recommendations"]] if reports else []
    metrics = {
        "completed": runtime.completed(receipt),
        "report_count": len(reports),
        "citation_integrity": runtime.completed(),
        "semantic_grounding": None,
        "human_review_required": True,
    }
    if relevant is not None:
        truth = set(relevant)
        metrics["recall_at_k"] = len(set(predictions) & truth) / len(truth) if truth else None
        metrics["reciprocal_rank"] = next(
            (1 / (i + 1) for i, p in enumerate(predictions) if p in truth), 0
        )
        dcg = sum(1 / math.log2(i + 2) for i, p in enumerate(predictions) if p in truth)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(len(truth), runtime.task.max_results)))
        metrics["ndcg_at_k"] = dcg / ideal if ideal else None
    if expected_analysis is not None:
        analysis = runtime.state.get("analysis", reports[0].get("analysis_id")) if reports else None
        actual = analysis.get("result") if analysis else None
        metrics["analysis_correct"] = (
            isinstance(actual, dict)
            and actual.keys() == expected_analysis.keys()
            and all(
                type(actual[k]) in {int, float} and math.isclose(actual[k], value, rel_tol=1e-7)
                for k, value in expected_analysis.items()
            )
        )
    return metrics


async def run_experiment(
    task,
    directory,
    *,
    backend=None,
    adapter="scripted",
    policy="progressive-fast",
    fast_model=None,
    strong_model=None,
    hook=None,
    relevant=None,
    sandbox_backend="restricted",
    pricing=None,
    state_path=None,
    offline_model_factory=None,
    expected_analysis=None,
):
    if pricing is not None:
        for rates in pricing.values():
            for key in ("input_per_million", "output_per_million"):
                value = rates[key]
                if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
                    raise ValueError("Pricing rates must be finite nonnegative numbers")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    backend = backend or CorpusBackend()
    state = ResearchState(state_path or directory / "state.sqlite")
    selected, reason = select_model(task, policy, fast_model, strong_model)
    runtime = ResearchRuntime(
        task,
        backend,
        state,
        skill_mode=("eager" if policy == "eager-fast" else "progressive"),
        hook=hook,
        sandbox=AnalyticsSandbox(sandbox_backend),
    )
    provider = make_provider(directory / "traces.jsonl")
    runtime.tracer = provider.get_tracer("experiment")
    start = time.perf_counter()
    usage, attempted_models = [], []
    response = {"status": "failed"}
    usage_complete = True
    try:
        with runtime.tracer.start_as_current_span("creatorpal.experiment"):
            state.event("model_selected", model=selected, reason=reason, adapter=adapter)
            for attempt in range(2):
                try:
                    if adapter == "scripted":
                        response = run_scripted(runtime)
                    else:
                        from .adk_runner import run_adk

                        if adapter == "offline-adk":
                            from .offline_model import OfflineResearchModel

                            model = (
                                offline_model_factory()
                                if offline_model_factory
                                else OfflineResearchModel()
                            )
                            model_id = model.model
                        elif adapter == "adk":
                            if not selected:
                                raise ValueError("A live model identifier is required")
                            model, model_id = selected, selected
                        else:
                            raise ValueError("Unknown adapter")
                        invocation_usage = []
                        attempted_models.append(model_id)
                        try:
                            response = await run_adk(runtime, model, usage=invocation_usage)
                        finally:
                            usage += [{"model": model_id, **row} for row in invocation_usage]
                    if runtime.completed(response):
                        break
                    if policy == "progressive-routed" and selected != strong_model and strong_model:
                        selected = strong_model
                        state.event("model_escalated", model=selected, reason="invalid_completion")
                        continue
                    break
                except InterruptedTask:
                    usage_complete = False
                    state.event("task_interrupted", attempt=attempt)
                    continue
                except Exception as exc:
                    usage_complete = False
                    state.event("adapter_error", error_type=type(exc).__name__)
                    response = {"status": "failed", "error_type": type(exc).__name__}
                    if policy == "progressive-routed" and selected != strong_model and strong_model:
                        selected = strong_model
                        state.event("model_escalated", model=selected, reason="provider_error")
                        continue
                    break
    finally:
        provider.shutdown()
    missing_usage_events = sum(bool(row.get("metadata_missing")) for row in usage)
    usage_complete = usage_complete and missing_usage_events == 0
    usage = [row for row in usage if not row.get("metadata_missing")]
    cost = None
    if pricing and usage and usage_complete and all(row["model"] in pricing for row in usage):
        cost = sum(
            (
                row["input_tokens"] * pricing[row["model"]]["input_per_million"]
                + (row["output_tokens"] + row["thinking_tokens"])
                * pricing[row["model"]]["output_per_million"]
            )
            / 1_000_000
            for row in usage
        )
    result = {
        "task_id": task.id,
        "policy": policy,
        "adapter": adapter,
        "backend": backend.kind,
        "selected_model": selected,
        "attempted_models": attempted_models,
        **score(runtime, response, relevant, expected_analysis),
        "receipt": response,
        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        "usage": usage or None,
        "missing_usage_events": missing_usage_events,
        "usage_complete": usage_complete if usage else None,
        "estimated_cost_usd": cost,
        "cost_method": "User-supplied flat rates, without cache discounts"
        if cost is not None
        else None,
        "skill_instruction_chars_loaded": sum(
            len(s["instructions"]) for s in state.all("skills").values()
        ),
        "events": state.events(),
    }
    manifest = {
        "task": task.model_dump(),
        "corpus_sha256": backend.fingerprint,
        "skill_sha256": runtime.registry.fingerprint,
        "policy": policy,
        "adapter": adapter,
        "fast_model": fast_model,
        "strong_model": strong_model,
        "sandbox": sandbox_backend,
        "limits": {"llm_calls_per_invocation": 16, "invocations": 2, "tool_attempts": 30},
        "package_version": importlib.metadata.version("creatorpal-agent"),
        "adk_version": importlib.metadata.version("google-adk") if adapter != "scripted" else None,
        "pricing": pricing,
        "measurement": "Live inference"
        if adapter == "adk"
        else "Offline control; not measured LLM capability",
    }
    manifest["configuration_sha256"] = digest(manifest)
    snapshot = {
        "contract_version": 1,
        "task": task.model_dump(),
        "evidence": state.all("evidence"),
        "analyses": state.all("analysis"),
        "reports": state.reports(),
        "events": state.events(),
    }
    for name, value in [
        ("result.json", result),
        ("manifest.json", manifest),
        ("reports.json", state.reports()),
        ("state-snapshot.json", snapshot),
    ]:
        (directory / name).write_text(json.dumps(value, indent=2) + "\n")
    return result


def load_cases(path, split="test"):
    cases = [
        EvaluationCase.model_validate(json.loads(line))
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]
    if len({case.task.id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    if any(case.split != split for case in cases):
        raise ValueError("Dataset contains another split")
    return cases


async def compare(
    output,
    *,
    cases_path=None,
    repeats=1,
    adapter="scripted",
    backend=None,
    fast_model=None,
    strong_model=None,
    pricing=None,
):
    if repeats < 1:
        raise ValueError("Repeats must be positive")
    path = cases_path or Path(__file__).parent / "fixtures" / "tasks.test.jsonl"
    cases = load_cases(path)
    root = Path(output) / ("comparison-" + uuid.uuid4().hex[:12])
    root.mkdir(parents=True)
    results = []
    for case in cases:
        for policy in POLICIES:
            for repeat in range(repeats):
                result = await run_experiment(
                    case.task,
                    root / f"{case.task.id}-{policy}-{repeat}",
                    backend=backend,
                    adapter=adapter,
                    policy=policy,
                    fast_model=fast_model,
                    strong_model=strong_model,
                    relevant=case.relevant_communities,
                    pricing=pricing,
                    expected_analysis=case.expected_analysis,
                )
                result["repeat"] = repeat
                results.append(result)
    manifest = {
        "dataset_sha256": digest([case.model_dump() for case in cases]),
        "split": "test",
        "repeats": repeats,
        "policies": list(POLICIES),
        "label_boundary": "Only task fields enter the runtime; labels stay in the scorer.",
        "adapter": adapter,
        "provenance": sorted({c.provenance for c in cases}),
    }
    (root / "comparison.json").write_text(json.dumps(results, indent=2) + "\n")
    (root / "dataset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = [
        "# CreatorPal policy comparison",
        "",
        f"Adapter: `{adapter}`. Repeats: {repeats}.",
        "",
        "Offline controls test implementation, not model quality. Citation integrity checks IDs "
        "and source/community relationships; semantic grounding requires separate human review.",
        "",
        "| Task | Policy | Complete | Recall@K | Loaded skill chars | Duration ms |",
        "|---|---|---|---:|---:|---:|",
    ]
    for r in results:
        rows.append(
            f"| {r['task_id']} | {r['policy']} | {r['completed']} | {r['recall_at_k']} | "
            f"{r['skill_instruction_chars_loaded']} | {r['duration_ms']} |"
        )
    (root / "report.md").write_text("\n".join(rows) + "\n")
    with (root / "human-review.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "task_id",
                "policy",
                "repeat",
                "factual_support_0_to_2",
                "usefulness_0_to_2",
                "reviewer",
                "notes",
            ]
        )
        for result in results:
            writer.writerow([result["task_id"], result["policy"], result["repeat"], "", "", "", ""])

    return root, results


def compare_sync(output, **kwargs):
    return asyncio.run(compare(output, **kwargs))
