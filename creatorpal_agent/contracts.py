from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ResearchTask(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    query: str = Field(min_length=3, max_length=3000)
    needs_rules: bool = False
    needs_analytics: bool = False
    max_results: int = Field(default=3, ge=1, le=10)


class Evidence(Contract):
    id: str
    community: str
    kind: Literal["profile", "rules"] = "profile"
    text: str = Field(max_length=6000)
    source_url: str
    collected_at: str
    metrics: dict[str, float] = Field(default_factory=dict)


class Recommendation(Contract):
    community: str
    rationale: str = Field(min_length=5, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    caveats: list[str] = Field(default_factory=list, max_length=10)


class ResearchReport(Contract):
    task_id: str
    recommendations: list[Recommendation] = Field(min_length=1, max_length=10)
    analysis_id: str | None = None
    limitations: list[str] = Field(default_factory=list, max_length=20)


class EvaluationCase(Contract):
    task: ResearchTask
    relevant_communities: list[str]
    expected_analysis: dict[str, float] | None = None
    split: Literal["dev", "test"]
    provenance: str
