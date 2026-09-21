import copy

import pytest

from creatorpal_agent.backends import CorpusBackend
from creatorpal_agent.contracts import ResearchTask
from creatorpal_agent.runtime import ResearchRuntime
from creatorpal_agent.state import ResearchState


def prepared(path):
    runtime = ResearchRuntime(
        ResearchTask(
            id="numeric", query="Python data analysis", needs_analytics=True, max_results=2
        ),
        CorpusBackend(),
        ResearchState(path / "state.sqlite"),
    )
    runtime.load_skill("audience-discovery")
    docs = runtime.search_communities(runtime.task.query)["evidence"]
    runtime.load_skill("programmatic-analytics")
    analysis = runtime.run_analysis("result = {r['community']: r['engagement_rate'] for r in rows}")
    runtime.load_skill("evidence-report")
    report = {
        "task_id": "numeric",
        "analysis_id": analysis["analysis_id"],
        "recommendations": [
            {"community": d["community"], "rationale": "Profile match", "evidence_ids": [d["id"]]}
            for d in docs
        ],
        "numeric_claims": [
            {"analysis_id": analysis["analysis_id"], "result_key": k, "value": float(v)}
            for k, v in analysis["result"].items()
        ],
    }
    return runtime, report


@pytest.mark.parametrize(
    "mutation",
    [
        "value",
        "scale",
        "reference",
        "key",
        "missing",
        "subset",
        "duplicate",
        "nan",
        "bool",
        "tolerance",
    ],
)
def test_invalid_numbers_never_commit(tmp_path, mutation):
    runtime, original = prepared(tmp_path)
    report = copy.deepcopy(original)
    claim = report["numeric_claims"][0]
    if mutation == "value":
        claim["value"] += 0.01
    elif mutation == "scale":
        claim["scale"] = "percent"
    elif mutation == "reference":
        claim["analysis_id"] = "another-task-analysis"
    elif mutation == "key":
        claim["result_key"] = "invented"
    elif mutation == "missing":
        report["numeric_claims"] = []
    elif mutation == "subset":
        report["numeric_claims"].pop()
    elif mutation == "duplicate":
        report["numeric_claims"].append(claim)
    elif mutation == "nan":
        claim["value"] = float("nan")
    elif mutation == "bool":
        claim["value"] = True
    else:
        claim["tolerance"] = 1000
    assert runtime.publish_report(report)["status"] == "error"
    assert runtime.state.reports() == []
    assert not any(e["kind"] == "report_committed" for e in runtime.state.events())
    assert runtime.publish_report(original)["status"] == "complete"


@pytest.mark.parametrize("scale", ["raw", "percent"])
def test_valid_scale_roundoff_and_idempotent_commit(tmp_path, scale):
    runtime, report = prepared(tmp_path)
    for claim in report["numeric_claims"]:
        claim["scale"] = scale
        claim["value"] *= 100 if scale == "percent" else 1
        claim["value"] += 1e-12
    first = runtime.publish_report(report)
    assert first["status"] == "complete"
    assert runtime.publish_report(report) == first
    assert len(runtime.state.reports()) == 1
