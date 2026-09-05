"""A deterministic model double for ADK integration and fault tests, never an LLM benchmark."""

import json

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types


class OfflineResearchModel(BaseLlm):
    model: str = "offline-research-double"

    async def generate_content_async(self, llm_request, stream=False):
        parts = [p for content in llm_request.contents for p in content.parts or []]
        task = next(json.loads(p.text) for p in parts if p.text and p.text.startswith('{"id":'))
        responses = [p.function_response for p in parts if p.function_response]
        loaded = {
            r.response.get("name")
            for r in responses
            if r.name == "load_skill" and r.response.get("status") == "ok"
        }
        search = next(
            (
                r.response
                for r in reversed(responses)
                if r.name == "search_communities" and r.response.get("status") == "ok"
            ),
            None,
        )
        rule_results = [r.response for r in responses if r.name == "read_community_rules"]
        rules = [d for result in rule_results for d in result.get("evidence", [])]
        analysis = next(
            (
                r.response
                for r in reversed(responses)
                if r.name == "run_analysis" and r.response.get("status") == "ok"
            ),
            None,
        )
        published = next(
            (r.response for r in reversed(responses) if r.name == "publish_report"), None
        )
        call = None
        text = None

        def need(skill, tool, arguments):
            return (tool, arguments) if skill in loaded else ("load_skill", {"name": skill})

        if published:
            text = published
        elif not search:
            if any(r.name == "search_communities" for r in responses):
                text = {"status": "failed", "error_type": "RetrievalFailed"}
            else:
                call = need("audience-discovery", "search_communities", {"query": task["query"]})
        elif not search["evidence"]:
            text = {"status": "failed", "error_type": "NoEvidence"}
        else:
            profiles = search["evidence"]
            missing_rules = [
                d["community"]
                for d in profiles
                if d["community"] not in {r["community"] for r in rules}
            ]
            if task["needs_rules"] and missing_rules:
                call = need(
                    "community-rules", "read_community_rules", {"community": missing_rules[0]}
                )
            elif task["needs_analytics"] and analysis is None:
                if any(r.name == "run_analysis" for r in responses):
                    text = {"status": "failed", "error_type": "AnalysisFailed"}
                else:
                    key = sorted(profiles[0]["metrics"])[0]
                    call = need(
                        "programmatic-analytics",
                        "run_analysis",
                        {"program": f"result = {{r['community']: r[{key!r}] for r in rows}}"},
                    )
            else:
                report = {
                    "task_id": task["id"],
                    "recommendations": [
                        {
                            "community": d["community"],
                            "rationale": "Profile evidence: " + d["text"],
                            "evidence_ids": [d["id"]]
                            + [r["id"] for r in rules if r["community"] == d["community"]],
                            "caveats": [],
                        }
                        for d in profiles
                    ],
                    "analysis_id": analysis["analysis_id"] if analysis else None,
                    "limitations": ["Offline ADK model double; synthetic reference data."],
                }
                call = need("evidence-report", "publish_report", {"report": report})
        if call:
            part = types.Part(function_call=types.FunctionCall(name=call[0], args=call[1]))
        else:
            part = types.Part(text=json.dumps(text))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))
