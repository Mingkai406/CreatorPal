import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from creatorpal_agent.backends import LegacyHybridBackend
from creatorpal_agent.contracts import ResearchTask
from creatorpal_agent.experiment import run_experiment


def test_legacy_adapter_calls_existing_retrieval_interfaces(tmp_path, monkeypatch):
    mocks = {}
    for module, cls in [
        ("bm25_search", "BM25Retriever"),
        ("faiss_search", "FaissRetriever"),
        ("hybrid_search", "HybridRetriever"),
        ("reranker", "CrossEncoderReranker"),
    ]:
        stub = types.ModuleType("src.retrieval." + module)
        mocks[cls] = MagicMock()
        setattr(stub, cls, mocks[cls])
        monkeypatch.setitem(sys.modules, stub.__name__, stub)
    index, metadata = tmp_path / "index", tmp_path / "metadata"
    index.write_bytes(b"fixture index fingerprint")
    metadata.write_text("{}")
    settings = SimpleNamespace(
        faiss_index_path=index,
        faiss_metadata_path=metadata,
        embedding_model="embedding",
        reranker_model="reranker",
        hybrid_alpha_keyword=0.15,
        hybrid_alpha_semantic=0.85,
    )
    candidates = [
        {"subreddit": "Example", "chunk_text": "Actual chunk", "rerank_score": 0.8},
        {"subreddit": "Example", "chunk_text": "Second chunk", "rerank_score": 0.7},
    ]
    mocks["HybridRetriever"].return_value.retrieve.return_value = candidates
    mocks["CrossEncoderReranker"].return_value.rerank.return_value = candidates
    backend = LegacyHybridBackend(settings)
    docs = backend.search("original query", limit=3)
    assert len(docs) == 1 and docs[0]["text"] == "Actual chunk"
    assert docs[0]["metrics"] == {"rerank_score": 0.8}
    assert backend.rules("Example") == []
    mocks["HybridRetriever"].return_value.retrieve.assert_called_once_with(
        "original query", top_k=50
    )
    mocks["CrossEncoderReranker"].return_value.rerank.assert_called_once_with(
        query="original query", candidates=candidates, top_k=50
    )


async def test_adk_loop_is_bounded(tmp_path):
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    class Loop(BaseLlm):
        model: str = "offline-loop-double"
        calls: int = 0

        async def generate_content_async(self, llm_request, stream=False):
            self.calls += 1
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name="load_skill", args={"name": "unknown"}
                            )
                        )
                    ],
                )
            )

    model = Loop()
    result = await run_experiment(
        ResearchTask(id="loop", query="find an audience"),
        tmp_path,
        adapter="offline-adk",
        offline_model_factory=lambda: model,
    )
    assert model.calls <= 16
    assert not result["completed"] and result["report_count"] == 0
    assert result["estimated_cost_usd"] is None


async def test_partial_model_usage_does_not_report_a_complete_cost(tmp_path, monkeypatch):
    async def fake_adk(runtime, model, *, usage):
        from creatorpal_agent.runtime import run_scripted

        usage.extend(
            [
                {"input_tokens": 100, "output_tokens": 10, "thinking_tokens": 0},
                {"metadata_missing": True},
            ]
        )
        return run_scripted(runtime)

    monkeypatch.setattr("creatorpal_agent.adk_runner.run_adk", fake_adk)
    result = await run_experiment(
        ResearchTask(id="usage", query="bread baking"),
        tmp_path,
        adapter="adk",
        fast_model="fake",
        pricing={"fake": {"input_per_million": 1, "output_per_million": 2}},
    )
    assert result["completed"] and result["missing_usage_events"] == 1
    assert result["estimated_cost_usd"] is None and not result["usage_complete"]


@pytest.mark.parametrize("rate", [-1, float("nan"), float("inf")])
async def test_invalid_pricing_is_rejected(tmp_path, rate):
    with pytest.raises(ValueError, match="finite nonnegative"):
        await run_experiment(
            ResearchTask(id="pricing", query="bread baking"),
            tmp_path,
            pricing={"model": {"input_per_million": rate, "output_per_million": 1}},
        )
