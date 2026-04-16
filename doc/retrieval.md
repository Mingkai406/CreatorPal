# Retrieval Stack Reference

This document covers all six components in `src/retrieval/` plus the theme extractor, describing their algorithms, data contracts, configuration parameters, and tuning guidance.

---

## 1. Architecture Overview

The retrieval stack converts a user query into a ranked list of the 10 most relevant subreddits in three phases:

```
Query
  ↓  ThemeExtractor         – extract channel-conditioned topic keywords (optional)
  ↓  QueryRewriter           – generate 3 LLM reformulations for broader recall
  ↓  HybridRetriever         – BM25 (15%) + FAISS (85%) → top-50 candidates
       ↳ HyDEQueryRewriter   – hypothetical document FAISS hits merged in (optional)
  ↓  CrossEncoderReranker    – precision refinement → top-10 results
```

**Why this design?**

A bi-encoder (FAISS) is fast enough to scan millions of vectors but imprecise because it encodes query and document independently. A cross-encoder sees the full `(query, document)` pair and is far more accurate but runs in O(N) inference time. The two-stage approach runs the cheap bi-encoder for broad recall and the expensive cross-encoder only on the top-50 shortlist.

BM25 is included as a complementary keyword signal: dense retrievers can miss communities with distinctive exact-match vocabulary that the embedding model generalizes away from.

---

## 2. Document Representation

Both BM25 and FAISS operate on the same **chunks** — fixed-size sliding-window segments of subreddit profile documents produced by `data/build_faiss_index.py`.

**Chunking parameters (set at index build time):**

| Parameter | Default | Description |
|---|---|---|
| `--window-tokens` | `64` | Window size in bi-encoder tokens |
| `--overlap-tokens` | `16` | Overlap between consecutive windows |

Each chunk is stored as:
- **One row** in the chunk metadata file (`data/processed/subreddit_profile_chunks.json`)
- **One vector** in the FAISS index

Row index `i` in the metadata corresponds to vector id `i` in the index. This alignment is validated at `FaissRetriever` init time: `len(metadata) == index.ntotal` is enforced and raises `ValueError` on mismatch.

**Required metadata columns:**

| Column | Type | Description |
|---|---|---|
| `subreddit` | `str` | Subreddit name without `r/` prefix |
| `chunk_text` | `str` | Raw text of this chunk |

Optional columns (e.g. `subscribers`, `profile_text`) are preserved and forwarded through the entire pipeline without modification.

---

## 3. BM25Retriever

**File:** `src/retrieval/bm25_search.py`  
**Class:** `BM25Retriever`  
**Library:** `rank-bm25` — `BM25Okapi`

### 3.1 Index Construction

At init time, the entire metadata file is loaded into a `pandas.DataFrame`. Every `chunk_text` value is tokenized by lowercasing and splitting on non-alphanumeric characters:

```python
re.findall(r"[a-z0-9]+", text.lower())
```

A `BM25Okapi` index is built over the full token corpus in memory. There is no incremental update path; changing the corpus requires re-instantiating `BM25Retriever` (which happens automatically on each `build_pipeline()` call).

### 3.2 Query Execution

`retrieve(query, top_k)` applies the same tokenizer to the query, calls `bm25.get_scores()` over the full corpus, sorts descending, and returns up to `top_k` results — with an early stop when `score <= 0` (no vocabulary overlap).

**Output schema per result:**

```python
{
    "bm25_id":    int,    # metadata row index (= FAISS vector id)
    "score":      float,  # raw BM25 score (not normalized)
    "subreddit":  str,
    "chunk_text": str,
    **metadata_columns,   # all other columns forwarded as-is
}
```

### 3.3 Behavior Notes

- **Zero-score cutoff:** BM25 returns no result with `score <= 0`. Queries with no vocabulary overlap with the corpus produce an empty list; `HybridRetriever` handles this transparently by relying entirely on the FAISS component.
- **No query expansion:** BM25 operates on the tokenized query as given. Query reformulation happens upstream in `QueryRewriter`.
- **Shared metadata file:** `BM25Retriever` and `FaissRetriever` read from the same metadata file, so their `bm25_id` and `faiss_id` values refer to the same rows and can be used interchangeably as document keys.

---

## 4. FaissRetriever

**File:** `src/retrieval/faiss_search.py`  
**Class:** `FaissRetriever`  
**Libraries:** `faiss-cpu`, `sentence-transformers`

### 4.1 Index Type and Similarity Metric

The index is a `faiss.IndexFlatIP` (inner-product). At build time, embeddings are L2-normalized before insertion:

```
normalize(v) = v / ‖v‖₂
```

Because L2-normalized vectors satisfy `‖a‖ = ‖b‖ = 1`, their inner product equals cosine similarity:

```
IP(normalize(a), normalize(b)) = cosine_similarity(a, b)
```

`FaissRetriever.encode_query()` applies the same L2 normalization at query time via `faiss.normalize_L2()`, ensuring a consistent similarity metric throughout.

### 4.2 Bi-Encoder Model

| Setting | Default | Env Var |
|---|---|---|
| Model | `sentence-transformers/all-mpnet-base-v2` | `EMBEDDING_MODEL` |
| Embedding dim | 768 | — |

**Critical constraint:** the model used at query time must be identical to the model used during index build. Changing `EMBEDDING_MODEL` requires rebuilding the FAISS index from scratch (`data/run_pipeline.sh` after deleting the stale `.faiss` file).

### 4.3 Query Execution

`retrieve(query, top_k)` encodes and normalizes the query, calls `index.search(vec, top_k)`, and maps returned FAISS ids to metadata rows.

**Output schema per result:**

```python
{
    "faiss_id":   int,    # FAISS vector id (= metadata row index)
    "score":      float,  # cosine similarity in [−1, 1]; typically positive
    "subreddit":  str,
    "chunk_text": str,
    **metadata_columns,
}
```

FAISS returns `id = -1` for padding slots when fewer than `top_k` vectors exist; these are filtered out.

---

## 5. HybridRetriever

**File:** `src/retrieval/hybrid_search.py`  
**Class:** `HybridRetriever`

### 5.1 Fusion Algorithm

`retrieve(query, top_k)` implements the following five-step procedure:

**Step 1 — Over-fetch.**  
Both retrievers are called with `pool_size = top_k * 2` to give the fusion step a wider candidate pool. This compensates for documents that rank in the top-k for one retriever but not the other.

**Step 2 — Score collection.**  
BM25 scores are indexed by `bm25_id`; FAISS scores by `faiss_id`. Both ids map to the same metadata row index, so they share the same key space.

**Step 3 — Min-max normalization.**  
Each score set is independently normalized to `[0, 1]`:

```
normalized(s) = (s − min_scores) / (max_scores − min_scores)
```

When all scores in a set are equal (degenerate case), every score is mapped to `1.0`. Normalization is required because BM25 and cosine similarity operate on different numerical ranges and cannot be compared directly.

**Step 4 — Weighted linear fusion.**  
For each document id in the union of both result sets:

```
fused_score = α_semantic × faiss_normalized + α_keyword × bm25_normalized
```

Documents present in only one retriever receive `0.0` for the absent component.

**Step 5 — Sort and truncate.**  
Results are sorted by `fused_score` descending; the top `top_k` are returned.

### 5.2 Weight Configuration

| Parameter | Env Var | Default | Meaning |
|---|---|---|---|
| `alpha_semantic` | `HYBRID_ALPHA_SEMANTIC` | `0.85` | FAISS (semantic) weight |
| `alpha_keyword` | `HYBRID_ALPHA_KEYWORD` | `0.15` | BM25 (keyword) weight |

Weights must sum to `1.0` — enforced in `__init__()` with a `ValueError`.

The 85/15 split favors semantic similarity as the dominant signal for community matching, while BM25 provides a tie-breaking advantage for subreddits with distinctive vocabulary that directly overlaps the query. Increasing `HYBRID_ALPHA_KEYWORD` toward 0.3 benefits recall for niche technical topics; decreasing it toward 0.05 benefits open-ended conceptual queries.

### 5.3 Output Schema per Result

```python
{
    "hybrid_score": float,  # fused score — primary sort key
    "faiss_score":  float,  # normalized FAISS component
    "bm25_score":   float,  # normalized BM25 component
    "subreddit":    str,
    "chunk_text":   str,
    **metadata_columns,     # from whichever retriever contributed (FAISS preferred)
}
```

---

## 6. QueryRewriter

**File:** `src/retrieval/query_rewriter.py`  
**Class:** `QueryRewriter`

### 6.1 Purpose

A single query phrasing under-specifies user intent and misses subreddits that use different vocabulary for the same concept. The rewriter generates diverse reformulations that emphasize synonyms, related topics, and sub-topic specificity to broaden recall.

### 6.2 Rewrite Generation

`rewrite(user_query, channel_themes)` makes one LLM call (`temperature=0.7`, `max_tokens=256`) requesting `num_rewrites` (default 3) alternative formulations. The original query is always prepended as `rewrites[0]`:

```
return [user_query, rewrite_1, rewrite_2, rewrite_3]
```

The system prompt instructs the LLM to vary emphasis across synonyms, related topics, and specificity levels — not to rephrase the same query with minor word changes.

When `channel_themes` is provided, they are appended to the user message to condition reformulations toward the creator's topical domain.

### 6.3 Retrieval with Deduplication

`retrieve_with_rewrites(user_query, retriever, channel_themes, top_k)` runs the retriever for all four queries and deduplicates by `(subreddit, chunk_text[:80])`. The merged result set is sorted by the first score key found in `{"hybrid_score", "score", "rerank_score"}` and capped at `top_k`.

The `retriever` argument is duck-typed — any object with a `retrieve(query, top_k) -> list[dict]` interface is accepted.

---

## 7. HyDEQueryRewriter

**File:** `src/retrieval/hyde.py`  
**Class:** `HyDEQueryRewriter`

### 7.1 Motivation

Standard bi-encoder retrieval encodes a short keyword query and compares it against dense subreddit profile embeddings. The query and documents live in different parts of the embedding space: a query like *"gaming tutorials"* is a request, while a subreddit profile is a description — even when topically aligned, their embeddings are not nearest neighbors.

**HyDE (Hypothetical Document Embeddings)** generates a pseudo-document in the same linguistic register as real subreddit profiles. Because the generated text is a *description* rather than a query, it is embedded much closer to matching documents in the vector space.

### 7.2 Pseudo-Document Generation

`generate_hypothetical_subreddit_description(user_query, channel_themes)` sends one LLM call (`temperature=0.7`, `max_tokens=200`) that produces an 80–120 word subreddit profile:

- Focus, typical content topics, audience interests, and engagement style are all described.
- No subreddit name is included — the model writes as if describing a community, not naming one.
- `channel_themes` are included in the user message to anchor the generated description.

### 7.3 Retrieval and Merging

`retrieve(user_query, channel_themes, faiss_retriever, top_k)` passes the generated pseudo-document directly to `faiss_retriever.retrieve()`. HyDE never calls BM25 — BM25 cannot meaningfully compare a generated text against its keyword index.

Hits are tagged with `hyde_score = score` to allow callers to distinguish HyDE candidates from hybrid candidates. Deduplication in `pipeline.py` is append-only: novel HyDE hits are added to the existing candidate list; no existing candidate is replaced or modified.

### 7.4 Failure Characteristics

Both the LLM call and the `retrieve()` invocation are wrapped in a try-except in `pipeline.py`. If the LLM is unavailable or returns an empty response, no error surfaces to the user — the pipeline continues with only the hybrid candidates.

---

## 8. CrossEncoderReranker

**File:** `src/retrieval/reranker.py`  
**Class:** `CrossEncoderReranker`

### 8.1 Cross-Encoder vs. Bi-Encoder

| Property | Bi-encoder (FAISS) | Cross-encoder (reranker) |
|---|---|---|
| Input | Query and doc encoded separately | `[query; doc]` concatenated as one input |
| Attention | No cross-attention between query and doc | Full self-attention across both |
| Accuracy | Moderate | High |
| Throughput | O(1) after index build | O(N) per query |
| Use case | Broad recall over millions of vectors | Precision refinement over top-k shortlist |

### 8.2 Model and Scoring

| Setting | Default | Env Var |
|---|---|---|
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `RERANKER_MODEL` |

The model is fine-tuned on MS-MARCO passage ranking. It outputs a single logit per `(query, chunk_text)` pair, interpreted directly as a relevance score. There is no normalization step; scores are only used for relative ranking.

`score_pairs(query, candidates)` calls `model.predict(pairs, convert_to_numpy=True)` in a single batch over all candidates. `rerank(query, candidates, top_k)` sorts descending and returns the top `top_k` entries with a new `rerank_score` field appended.

### 8.3 Chunk-Level Ranking

The reranker operates at the **chunk level**, not the subreddit level. Multiple chunks from the same subreddit may appear in the top-10 ranked results. The pipeline does not deduplicate by subreddit after reranking; if this behavior is undesirable, add a post-reranking deduplication step in `pipeline.py` before output assembly.

---

## 9. ThemeExtractor

**File:** `src/retrieval/theme_extractor.py`  
**Class:** `ThemeExtractor`

`extract_themes(channel_payload, max_themes=20)` sends one LLM call (`temperature=0.3`, `max_tokens=256`) with a prompt constructed from:

- Channel title and description (truncated to 500 characters)
- Up to 20 recent video titles
- Up to 30 audience comment samples (first 5 comments from each of the first 10 videos)

The LLM returns a newline-separated list of 2–5 word topic phrases. Low temperature (0.3) is intentional: themes are factual extractions rather than creative variations.

Themes serve two downstream roles:

1. **Query conditioning (Step 3):** appended to the retrieval query as `"Topics: t1, t2, ..."`.
2. **LLM context (Steps 4, 4b):** passed to `QueryRewriter` and `HyDEQueryRewriter` to anchor reformulations to the creator's domain.

---

## 10. Tuning Guide

### Retrieval Quality

| Parameter | Default | Effect of increasing |
|---|---|---|
| `HYBRID_ALPHA_SEMANTIC` | `0.85` | Stronger semantic bias; better for broad conceptual queries |
| `HYBRID_ALPHA_KEYWORD` | `0.15` | Stronger keyword bias; better for niche topics with distinctive vocabulary |
| `RETRIEVAL_TOP_K` | `50` | Larger candidate pool for the reranker; higher latency, marginally higher recall |
| `RERANK_TOP_K` | `10` | More results returned to the frontend |

### Model Swapping

**Changing the embedding model:**
1. Set `EMBEDDING_MODEL` in `.env`.
2. Delete `data/processed/subreddit_profiles.faiss`.
3. Re-run `bash data/run_pipeline.sh` to rebuild the index.

The query-time encoder and the index-build-time encoder must always be the same model. Mismatches produce silently wrong results (no error, but the cosine scores are meaningless).

**Changing the reranker:**
1. Set `RERANKER_MODEL` in `.env`. No index rebuild required.

**Changing the LLM:**
1. Set `VLLM_MODEL` in `.env`. Affects all four LLM-backed components: theme extractor, query rewriter, HyDE, and report generator. No index rebuild required.

### Latency Breakdown

End-to-end latency is dominated by:

| Stage | Driver | Approximate share |
|---|---|---|
| LLM calls (4 sequential) | Network + inference time | 60–80% |
| Cross-encoder reranking | CPU inference over `RETRIEVAL_TOP_K` pairs | 10–30% |
| FAISS search | Exact scan over all vectors | < 5% |

To reduce latency:
- Lower `RETRIEVAL_TOP_K` (smaller reranker batch).
- Disable HyDE by raising `NotImplementedError` in `HyDEQueryRewriter.__init__()` (removes one LLM call).
- Run vLLM on GPU (largest single improvement for LLM-heavy paths).
