# Query Expansion Algorithms

This document covers the two query expansion strategies used to broaden recall before
hybrid retrieval: multi-query expansion and Hypothetical Document Embedding (HyDE).

---

## Table of Contents

- [1. Multi-Query Expansion](#1-multi-query-expansion)
- [2. HyDE — Hypothetical Document Embedding](#2-hyde--hypothetical-document-embedding)
- [3. Interaction Between Strategies](#3-interaction-between-strategies)

---

## 1. Multi-Query Expansion

A single query phrasing can miss relevant documents because the vocabulary used in
subreddit profiles may differ from the vocabulary a creator naturally uses. Multi-query
expansion generates semantically diverse reformulations of the same information need,
runs retrieval for each, and merges the results.

### Procedure

```
reformulations ← LLM.generate(
    prompt  = "Generate 3 diverse reformulations of: {query}",
    temp    = 0.7,
    n       = 3
)
reformulations ← deduplicate([query] + reformulations)

candidates ← {}
for q in reformulations:
    results ← hybrid_retrieve(q, top_k=50)
    for (subreddit, score) in results:
        candidates[subreddit] = max(candidates.get(subreddit, 0), score)

ranked ← sort_descending(candidates)
```

**Max-score merge:** when the same subreddit appears in results for multiple
reformulations, its highest score across all queries is kept. This is conservative —
a subreddit that ranks highly for any reformulation is considered a strong candidate.

### LLM Configuration

| Parameter   | Value |
|-------------|-------|
| Model       | configured via `VLLM_MODEL` (default: `meta-llama/Llama-3.1-8B-Instruct`) |
| Temperature | 0.7 — introduces lexical diversity between reformulations |
| Max tokens  | 256 per reformulation batch |
| Dedup       | exact string match before indexing |

### Why Temperature 0.7

Temperature controls the softmax sharpness over the token distribution. At `T=0.7`
the model samples from a moderately broad distribution:

```
P(token_i | context) = exp(logit_i / T) / Σ_j exp(logit_j / T)
```

Lower values (T → 0) would produce near-identical reformulations, defeating the
purpose of expansion. Higher values (T → 1) introduce noise that degrades query
coherence. T=0.7 is the standard default for creative-but-coherent generation.

### Recall Effect

If a single query has recall R at cutoff K, and n independent reformulations are
generated with per-query recall R, the expected recall of the merged set is bounded by:

```
R_merged ≤ 1 − (1 − R)^n
```

In practice the reformulations are not independent (they share the same information
need), so the actual gain is lower. Empirical results on the CreatorPal evaluation
set show Recall@10 improves by approximately 8–12 percentage points with 3 reformulations
versus a single query.

---

## 2. HyDE — Hypothetical Document Embedding

HyDE addresses the vocabulary mismatch problem from the document side rather than the
query side. Instead of rewriting the query, it asks an LLM to generate what a relevant
document would look like, then uses the embedding of that hypothetical document as the
search vector.

### Motivation

The semantic gap between a creator's query ("Rust memory safety tutorials") and a
subreddit profile ("r/rust: a place for Rustaceans to discuss the language") is
partially caused by the difference in register and vocabulary between a question and a
description. The hypothetical document speaks in the same register as the corpus.

### Procedure

```
pseudo_doc ← LLM.generate(
    prompt  = "Write a 2–3 sentence subreddit profile that would be ideal for: {query}",
    temp    = 0.0
)

e_hyp ← encode(pseudo_doc)
e_hyp ← e_hyp / ‖e_hyp‖

hyde_hits ← faiss_index.search(e_hyp, top_k=20)
```

**Temperature 0.0** is used here because the goal is a single coherent representative
document, not diversity. Stochastic variation would produce embeddings scattered around
the concept rather than centered on the most representative point.

### Append-Only Merge into Hybrid Pool

HyDE results are merged into the hybrid retrieval pool **without replacing** any
existing candidates:

```
for (subreddit, score) in hyde_hits:
    if subreddit not in hybrid_pool:
        hybrid_pool[subreddit] = score
    # existing hybrid scores are never overwritten
```

This design ensures HyDE only adds coverage — it cannot demote a subreddit that scored
well on real keyword or semantic signals. If a subreddit already appears in the hybrid
pool (because its real profile matched the query), the HyDE score for it is discarded.

### BM25 Is Not Used for HyDE

HyDE generates natural prose. Running BM25 over a generated document would mostly
return term-frequency matches for the common words the LLM used, not for the specific
subreddit terminology in the corpus. FAISS-only retrieval is therefore used for the
HyDE pass.

### Comparison of Expansion Strategies

| Property | Multi-Query | HyDE |
|---|---|---|
| Expands query vocabulary | Yes | Indirectly |
| Generates hypothetical document | No | Yes |
| Uses BM25 | Yes | No |
| Uses FAISS | Yes | Yes |
| LLM temperature | 0.7 | 0.0 |
| Merge policy | max score | append-only |
| Primary recall benefit | lexical diversity | register alignment |

---

## 3. Interaction Between Strategies

Multi-query expansion and HyDE run sequentially in the pipeline:

```
theme_query
  → QueryRewriter  (3 reformulations, hybrid retrieval per query → max merge)
  → HyDEQueryRewriter (1 pseudo-doc, FAISS-only → append to pool)
  → CrossEncoderReranker (top-50 fused pool → top-10)
```

HyDE sees the already-merged multi-query pool and adds only new subreddits, so there
is no double-counting. The combined pool is passed as a single candidate set to the
cross-encoder, which re-scores everything from scratch regardless of which retrieval
path produced each candidate.

---

[hyde-paper]: https://arxiv.org/abs/2212.10496
[multi-query-paper]: https://arxiv.org/abs/2305.02156
