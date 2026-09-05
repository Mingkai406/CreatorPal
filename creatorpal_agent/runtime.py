"""The tool contract is shared by ADK, deterministic controls, and external fault injectors."""

import time

from opentelemetry import trace
from pydantic import ValidationError

from .contracts import Evidence, ResearchReport
from .sandbox import AnalyticsSandbox
from .skills import SkillRegistry
from .state import digest


class RetryableToolError(Exception):
    pass


class InterruptedTask(Exception):
    pass


class ToolExecutionError(Exception):
    """A nonretryable execution error with a non-sensitive error category."""


class ToolHook:
    """An external test adapter can inject faults without modifying business tools."""

    def before(self, name, arguments, state):
        pass

    def after(self, name, arguments, result, state):
        return result


class ResearchRuntime:
    def __init__(
        self,
        task,
        backend,
        state,
        *,
        skill_mode="progressive",
        sandbox=None,
        hook=None,
        tracer=None,
        max_tool_calls=30,
    ):
        if skill_mode not in {"progressive", "eager"}:
            raise ValueError("Unknown skill loading mode")
        self.task, self.backend, self.state = task, backend, state
        self.registry = SkillRegistry()
        self.sandbox = sandbox or AnalyticsSandbox()
        self.hook = hook or ToolHook()
        self.tracer = tracer or trace.get_tracer("creatorpal")
        self.skill_mode, self.max_tool_calls = skill_mode, max_tool_calls
        state.bind(
            {
                "task": task.model_dump(),
                "corpus": backend.fingerprint,
                "skills": self.registry.fingerprint,
                "sandbox": self.sandbox.backend,
                "contract": 1,
            }
        )
        if skill_mode == "eager":
            for skill in self.registry.metadata():
                self.load_skill(skill["name"])

    def load_skill(self, name: str) -> dict:
        """Load one named skill's instructions before using its corresponding tools."""
        try:
            skill = self.registry.load(name)
        except ValueError:
            return {"status": "error", "error_type": "UnknownSkill"}
        if self.state.get("skills", name) is None:
            self.state.put("skills", name, skill)
            self.state.event(
                "skill_loaded",
                name=name,
                sha256=skill["sha256"],
                instruction_chars=len(skill["instructions"]),
            )
        return {"status": "ok", **skill}

    def _require(self, skill):
        if self.state.get("skills", skill) is None:
            raise ValueError(f"Load skill {skill} before calling this tool")

    def _invoke(self, name, arguments, action, validator=None):
        used = sum(e["kind"] == "tool_attempt" for e in self.state.events())
        if used >= self.max_tool_calls:
            return {"status": "error", "error_type": "ToolBudgetExceeded"}
        with self.tracer.start_as_current_span(
            f"creatorpal.tool.{name}", record_exception=False, set_status_on_exception=False
        ) as span:
            for attempt in range(1, 3):
                if used + attempt > self.max_tool_calls:
                    return {"status": "error", "error_type": "ToolBudgetExceeded"}
                self.state.event("tool_attempt", tool=name, attempt=attempt)
                try:
                    self.hook.before(name, arguments, self.state)
                    result = action()
                    result = self.hook.after(name, arguments, result, self.state)
                    if validator and not validator(result):
                        raise RetryableToolError("InvalidToolResponse")
                    span.set_attribute("creatorpal.status", result.get("status", "unknown"))
                    return result
                except RetryableToolError as exc:
                    self.state.event("retryable_failure", tool=name, error_type=type(exc).__name__)
                    if attempt == 2:
                        return {"status": "error", "error_type": "RetryBudgetExceeded"}
                    time.sleep(0.001)
                except ToolExecutionError as exc:
                    self.state.event("execution_failure", tool=name, error_type=str(exc))
                    return {"status": "error", "error_type": str(exc)}
                except (ValueError, ValidationError, KeyError, TypeError) as exc:
                    self.state.event("validation_failure", tool=name, error_type=type(exc).__name__)
                    return {
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "hint": "Check skill, task, evidence IDs, and tool argument schema",
                    }
            raise AssertionError("unreachable")

    def search_communities(self, query: str) -> dict:
        """Find relevant communities; return source IDs, text, timestamps and numeric metrics."""

        def action():
            self._require("audience-discovery")
            if not 3 <= len(query) <= 3000:
                raise ValueError("Query size")
            key = digest([query, self.task.max_results])
            cached = self.state.get("search", key)
            if cached is not None:
                return cached
            evidence = [
                Evidence.model_validate(d).model_dump()
                for d in self.backend.search(query, self.task.max_results)[: self.task.max_results]
            ]
            for doc in evidence:
                if doc["kind"] != "profile":
                    raise ValueError("Search returned non-profile evidence")
                self.state.put("evidence", doc["id"], doc)
            result = {"status": "ok", "evidence": evidence, "backend": self.backend.kind}
            self.state.put("search", key, result)
            return result

        def valid(result):
            try:
                if not isinstance(result, dict) or result.get("status") != "ok":
                    return False
                return isinstance(result.get("evidence"), list) and all(
                    Evidence.model_validate(d).kind == "profile" for d in result["evidence"]
                )
            except (ValidationError, ValueError, TypeError):
                return False

        return self._invoke("search_communities", {"query": query}, action, valid)

    def read_community_rules(self, community: str) -> dict:
        """Read supplied rules snapshots for a retrieved community; these are not live policies."""

        def action():
            self._require("community-rules")
            evidence = self.state.all("evidence")
            if community not in {d["community"] for d in evidence.values()}:
                raise ValueError("Retrieve the community first")
            documents = [
                Evidence.model_validate(d).model_dump() for d in self.backend.rules(community)
            ]
            for doc in documents:
                if doc["kind"] != "rules" or doc["community"] != community:
                    raise ValueError("Rules do not match community")
                self.state.put("evidence", doc["id"], doc)
            return {"status": "ok" if documents else "unavailable", "evidence": documents}

        return self._invoke("read_community_rules", {"community": community}, action)

    def run_analysis(self, program: str) -> dict:
        """Run restricted Python over retrieved metrics as rows; assign the answer to result."""

        def action():
            self._require("programmatic-analytics")
            rows = [
                {**d["metrics"], "community": d["community"], "evidence_id": d["id"]}
                for d in self.state.all("evidence").values()
                if d["kind"] == "profile" and d["metrics"]
            ]
            if not rows:
                raise ValueError("No retrieved numeric data")
            analysis_id = digest([program, rows])[:24]
            cached = self.state.get("analysis", analysis_id)
            if cached:
                return {"status": "ok", "analysis_id": analysis_id, "result": cached["result"]}
            result = self.sandbox.execute(program, rows)
            if result.get("status") != "ok":
                self.state.event("analysis_failed", error_type=result.get("error_type"))
                return result
            self.state.put(
                "analysis",
                analysis_id,
                {
                    "program": program,
                    "rows": rows,
                    "result": result["result"],
                    "sandbox": self.sandbox.backend,
                },
            )
            return {"status": "ok", "analysis_id": analysis_id, "result": result["result"]}

        return self._invoke("run_analysis", {"program_sha256": digest(program)}, action)

    def publish_report(self, report: dict) -> dict:
        """Validate and durably commit a ResearchReport; return a receipt only after commit."""

        def action():
            self._require("evidence-report")
            parsed = ResearchReport.model_validate(report)
            if not self.validate_report(parsed):
                raise ValueError("Report references or required analysis are invalid")
            actual, _ = self.state.commit_report(self.task.id, parsed.model_dump())
            return {"status": "complete", "task_id": self.task.id, "report_sha256": digest(actual)}

        return self._invoke(
            "publish_report",
            {"report_sha256": digest(report)},
            action,
            lambda r: (
                isinstance(r, dict)
                and r.get("status") == "complete"
                and r.get("task_id") == self.task.id
                and isinstance(r.get("report_sha256"), str)
            ),
        )

    def validate_report(self, report):
        if report.task_id != self.task.id or len(report.recommendations) > self.task.max_results:
            return False
        evidence = self.state.all("evidence")
        seen = set()
        for rec in report.recommendations:
            if rec.community in seen:
                return False
            seen.add(rec.community)
            docs = [evidence.get(key) for key in rec.evidence_ids]
            if any(d is None or d["community"] != rec.community for d in docs):
                return False
            kinds = {d["kind"] for d in docs}
            if "profile" not in kinds or (self.task.needs_rules and "rules" not in kinds):
                return False
        if self.task.needs_analytics and not report.analysis_id:
            return False
        if report.analysis_id and self.state.get("analysis", report.analysis_id) is None:
            return False
        return True

    def completed(self, receipt=None):
        reports = self.state.reports()
        if len(reports) != 1:
            return False
        if not self.validate_report(ResearchReport.model_validate(reports[0])):
            return False
        return receipt is None or (
            isinstance(receipt, dict)
            and receipt.get("status") == "complete"
            and receipt.get("task_id") == self.task.id
            and receipt.get("report_sha256") == digest(reports[0])
        )

    def resumed_receipt(self):
        if self.completed():
            return {
                "status": "complete",
                "task_id": self.task.id,
                "report_sha256": digest(self.state.reports()[0]),
            }
        return None

    def tools(self):
        return [
            self.load_skill,
            self.search_communities,
            self.read_community_rules,
            self.run_analysis,
            self.publish_report,
        ]


def run_scripted(runtime):
    """Offline control over real tools; never presented as model inference."""
    if runtime.completed():
        return runtime.resumed_receipt()
    runtime.load_skill("audience-discovery")
    search = runtime.search_communities(runtime.task.query)
    if search.get("status") != "ok" or not search["evidence"]:
        return {"status": "failed", "error_type": "NoEvidence"}
    profiles = search["evidence"]
    if runtime.task.needs_rules:
        runtime.load_skill("community-rules")
        for doc in profiles:
            runtime.read_community_rules(doc["community"])
    analysis_id = None
    if runtime.task.needs_analytics:
        runtime.load_skill("programmatic-analytics")
        key = sorted(profiles[0]["metrics"])[0]
        result = runtime.run_analysis(f"result = {{r['community']: r[{key!r}] for r in rows}}")
        if result.get("status") != "ok":
            return result
        analysis_id = result["analysis_id"]
    runtime.load_skill("evidence-report")
    evidence = runtime.state.all("evidence")
    return runtime.publish_report(
        {
            "task_id": runtime.task.id,
            "analysis_id": analysis_id,
            "recommendations": [
                {
                    "community": d["community"],
                    "rationale": "Retrieved profile: " + d["text"],
                    "evidence_ids": [
                        key for key, item in evidence.items() if item["community"] == d["community"]
                    ],
                    "caveats": [],
                }
                for d in profiles
            ],
            "limitations": ["Deterministic reference control; no model inference."],
        }
    )
