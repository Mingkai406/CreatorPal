import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from creatorpal_agent.backends import CorpusBackend
from creatorpal_agent.contracts import ResearchTask
from creatorpal_agent.experiment import compare, load_cases, run_experiment, select_model
from creatorpal_agent.runtime import ResearchRuntime, run_scripted
from creatorpal_agent.sandbox import AnalyticsSandbox
from creatorpal_agent.skills import SkillRegistry
from creatorpal_agent.state import ResearchState

FIXTURES = Path(__import__("creatorpal_agent").__file__).parent / "fixtures"
CASES = load_cases(FIXTURES / "tasks.test.jsonl")


def runtime(tmp_path, task=None, **kwargs):
    return ResearchRuntime(
        task or CASES[0].task, CorpusBackend(), ResearchState(tmp_path / "state.sqlite"), **kwargs
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.task.id)
@pytest.mark.parametrize("adapter", ["scripted", "offline-adk"])
async def test_task_uses_real_tools_and_validates_numeric_answer(tmp_path, case, adapter):
    result = await run_experiment(
        case.task,
        tmp_path,
        adapter=adapter,
        relevant=case.relevant_communities,
        expected_analysis=case.expected_analysis,
    )
    assert result["completed"] and result["citation_integrity"]
    assert result["report_count"] == 1
    assert result["recall_at_k"] == 1
    if case.expected_analysis is not None:
        assert result["analysis_correct"]
    assert result["usage"] is None
    assert result["estimated_cost_usd"] is None
    assert result["semantic_grounding"] is None
    snapshot = json.loads((tmp_path / "state-snapshot.json").read_text())
    assert snapshot["contract_version"] == 1
    assert snapshot["reports"] and snapshot["evidence"]
    assert (tmp_path / "traces.jsonl").read_text().strip()


def test_skill_loading_is_task_specific_and_format_is_portable(tmp_path):
    from google.adk.skills import load_skill_from_dir

    registry = SkillRegistry()
    for skill in registry.metadata():
        assert "instructions" not in skill
        parsed = load_skill_from_dir(
            Path(__import__("creatorpal_agent").__file__).parent / "skills" / skill["name"]
        )
        assert parsed.frontmatter.name == skill["name"]
    task = ResearchTask(id="simple", query="sourdough bread baking", max_results=1)
    agent = runtime(tmp_path, task)
    assert not agent.state.all("skills")
    assert run_scripted(agent)["status"] == "complete"
    assert set(agent.state.all("skills")) == {"audience-discovery", "evidence-report"}


def test_tools_require_loaded_skills_and_retrieved_scope(tmp_path):
    agent = runtime(tmp_path)
    assert agent.search_communities("plant watering")["status"] == "error"
    agent.load_skill("community-rules")
    assert agent.read_community_rules("unretrieved")["status"] == "error"
    assert not agent.state.all("evidence")


@pytest.mark.parametrize("change", ["task", "corpus"])
def test_resume_rejects_changed_inputs(tmp_path, change):
    agent = runtime(tmp_path)
    if change == "task":
        task = agent.task.model_copy(update={"query": "a different query"})
        with pytest.raises(ValueError, match="different task"):
            runtime(tmp_path, task)
    else:
        backend = CorpusBackend()
        backend.fingerprint = "changed"
        with pytest.raises(ValueError, match="different task"):
            ResearchRuntime(agent.task, backend, agent.state)


@pytest.mark.parametrize(
    "tamper", ["fabricated", "cross-community", "missing-rules", "unknown-analysis", "wrong-task"]
)
def test_report_rejects_invalid_claims(tmp_path, tamper):
    agent = runtime(tmp_path)
    receipt = run_scripted(agent)
    report = agent.state.reports()[0]
    if tamper == "fabricated":
        report["recommendations"][0]["evidence_ids"] = ["invented"]
    elif tamper == "cross-community":
        report["recommendations"][0]["community"] = "AnotherCommunity"
    elif tamper == "missing-rules":
        ev = agent.state.all("evidence")
        rec = report["recommendations"][0]
        rec["evidence_ids"] = [k for k in rec["evidence_ids"] if ev[k]["kind"] == "profile"]
    elif tamper == "unknown-analysis":
        report["analysis_id"] = "invented"
    else:
        report["task_id"] = "wrong-task"
    assert agent.publish_report(report)["status"] == "error"
    assert agent.completed(receipt)
    assert len(agent.state.reports()) == 1


def test_false_receipt_without_durable_report_is_not_completion(tmp_path):
    agent = runtime(tmp_path)
    assert not agent.completed(
        {"status": "complete", "task_id": agent.task.id, "report_sha256": "fabricated"}
    )


def test_atomic_report_commit_is_idempotent_under_contention(tmp_path):
    state = ResearchState(tmp_path / "state.sqlite")
    report = {"task_id": "same", "value": 42}
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: state.commit_report("same", report), range(32)))
    assert sum(created for _, created in outcomes) == 1
    assert sum(e["kind"] == "report_committed" for e in state.events()) == 1
    assert state.reports() == [report]
    with pytest.raises(ValueError, match="another payload"):
        state.commit_report("same", {"value": 43})


def test_restart_after_process_dies_after_commit(tmp_path):
    script = """
import os, sys
from pathlib import Path
from creatorpal_agent.backends import CorpusBackend
from creatorpal_agent.contracts import ResearchTask
from creatorpal_agent.runtime import ResearchRuntime, run_scripted
from creatorpal_agent.state import ResearchState
state = ResearchState(Path(sys.argv[1]))
original_commit = state.commit_report
def crash_after_transaction(task_id, report):
    result = original_commit(task_id, report)
    if state.once('crash'):
        os._exit(75)
    return result
state.commit_report = crash_after_transaction
agent = ResearchRuntime(ResearchTask(id='restart', query='sourdough bread baking', max_results=1),
                        CorpusBackend(), state)
assert run_scripted(agent)['status'] == 'complete'
assert len(state.reports()) == 1
assert sum(e['kind'] == 'report_committed' for e in state.events()) == 1
"""
    cmd = [sys.executable, "-c", script, str(tmp_path / "restart.sqlite")]
    assert subprocess.run(cmd, timeout=15).returncode == 75
    assert subprocess.run(cmd, timeout=15).returncode == 0


@pytest.mark.parametrize(
    "program",
    [
        "import os\nresult = 1",
        "result = rows.__class__",
        'result = open("/etc/passwd")',
        "result = __builtins__",
        "result = 2 ** 10000",
        "while True: pass",
        'result = float("nan")',
        'result = "a" * 40000',
    ],
)
def test_analytics_rejects_unsafe_or_unbounded_output(program):
    assert AnalyticsSandbox().execute(program, [{"value": 1}])["status"] == "error"


def test_analytics_executes_program_and_has_deadline():
    sandbox = AnalyticsSandbox()
    assert sandbox.execute(
        "result = sum(r['value'] for r in rows)", [{"value": 2}, {"value": 3}]
    ) == {"status": "ok", "result": 5}
    result = AnalyticsSandbox(timeout_seconds=0.1).execute(
        "result = sum(i for i in range(1000000000))", []
    )
    assert result == {"status": "error", "error_type": "Timeout"}


@pytest.mark.skipif(os.environ.get("CREATORPAL_DOCKER_TEST") != "1", reason="Requires built image")
def test_docker_analytics_computes_without_host_access():
    sandbox = AnalyticsSandbox("docker", timeout_seconds=15)
    assert sandbox.execute('result = sum(r["x"] for r in rows)', [{"x": 4}]) == {
        "status": "ok",
        "result": 4,
    }
    assert sandbox.execute('result = open("/etc/passwd")', [])["status"] == "error"


def test_policies_route_only_from_task_requirements():
    numeric = next(c.task for c in CASES if c.task.needs_analytics)
    assert select_model(numeric, "progressive-routed", "fast", "strong") == (
        "strong",
        "explicit_numeric_analysis",
    )
    assert select_model(numeric, "progressive-fast", "fast", "strong")[0] == "fast"
    assert select_model(CASES[0].task, "progressive-routed", "fast", "strong")[0] == "fast"


async def test_invalid_completion_escalates_and_accounts_for_both_models(tmp_path, monkeypatch):
    calls = []

    async def fake_adk(agent, model, *, usage):
        calls.append(model)
        usage.append(
            {"input_tokens": 100, "output_tokens": 20, "thinking_tokens": 5, "cached_tokens": 0}
        )
        return {"status": "complete"} if model == "fast" else run_scripted(agent)

    monkeypatch.setattr("creatorpal_agent.adk_runner.run_adk", fake_adk)
    result = await run_experiment(
        CASES[0].task,
        tmp_path,
        adapter="adk",
        policy="progressive-routed",
        fast_model="fast",
        strong_model="strong",
        pricing={
            "fast": {"input_per_million": 1, "output_per_million": 2},
            "strong": {"input_per_million": 3, "output_per_million": 6},
        },
    )
    assert calls == ["fast", "strong"]
    assert result["completed"]
    assert result["estimated_cost_usd"] == pytest.approx(0.0006)


async def test_comparison_preserves_label_boundary_and_numeric_grading(tmp_path):
    root, results = await compare(tmp_path)
    assert len(results) == 12 and all(r["completed"] for r in results)
    assert all(r.get("analysis_correct", True) for r in results)
    manifest = json.loads((root / "dataset-manifest.json").read_text())
    assert manifest["split"] == "test"
    for file in root.glob("*/manifest.json"):
        assert "relevant_communities" not in json.loads(file.read_text())["task"]
    progressive = [
        r for r in results if r["task_id"] == "test-bread" and r["policy"] == "progressive-fast"
    ][0]
    eager = [r for r in results if r["task_id"] == "test-bread" and r["policy"] == "eager-fast"][0]
    assert progressive["skill_instruction_chars_loaded"] < eager["skill_instruction_chars_loaded"]


def test_dataset_rejects_mixed_splits_and_duplicate_ids(tmp_path):
    row = CASES[0].model_dump()
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row))
    with pytest.raises(ValueError, match="unique"):
        load_cases(path)
    row["split"] = "dev"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="another split"):
        load_cases(path)
