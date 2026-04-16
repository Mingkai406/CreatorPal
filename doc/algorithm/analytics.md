# Analytics Algorithms

This document covers the three algorithms used after retrieval: cross-encoder reranking,
RoBERTa sentiment scoring, and PAL (Program-Aided Language) analytics execution.

---

## Table of Contents

- [1. Cross-Encoder Reranking](#1-cross-encoder-reranking)
- [2. RoBERTa Sentiment Scoring](#2-roberta-sentiment-scoring)
- [3. PAL Analytics Execution](#3-pal-analytics-execution)

---

## 1. Cross-Encoder Reranking

The hybrid retriever returns up to 50 candidates ranked by an approximate fused score.
The cross-encoder reranker re-scores the top candidates with higher precision by
jointly encoding the query and each candidate document.

### Bi-Encoder vs. Cross-Encoder

| Property | Bi-encoder (FAISS stage) | Cross-encoder (rerank stage) |
|---|---|---|
| Encoding | Query and document independently | Query and document concatenated |
| Similarity | Vector dot product | Full attention across both inputs |
| Speed | Fast (pre-computed doc embeddings) | Slow (inference per (query, doc) pair) |
| Precision | Approximate | High |
| Use | First-stage recall over large corpus | Second-stage precision over top-50 |

The bi-encoder must encode documents offline and cannot model query-document
interactions. The cross-encoder processes the pair `[CLS] query [SEP] document [SEP]`
in a single forward pass, allowing every token in the query to attend to every token
in the document. This is more expensive but produces more accurate relevance scores.

### Model

`cross-encoder/ms-marco-MiniLM-L-6-v2` — a 6-layer MiniLM model fine-tuned on
the MS MARCO passage ranking dataset. It outputs a single logit that is treated as
a relevance score (higher = more relevant).

### Procedure

```
pairs  ← [(query, chunk_text) for each candidate in pool]
scores ← cross_encoder.predict(pairs, batch_size=len(pairs))
ranked ← sort_descending(zip(candidates, scores))
top_10 ← ranked[:10]
```

The entire candidate pool is scored in one batch. Single-batch inference is preferred
over streaming because the cross-encoder benefits from padding to a uniform sequence
length across the batch.

### Score Scale

MS-MARCO cross-encoders output unbounded logits. For display purposes scores are
passed through a sigmoid to map them into $(0, 1)$:

$$\text{relevance} = \frac{1}{1 + e^{-\text{logit}}}$$

The resulting value is shown as the "Fit Score" in the UI.

---

## 2. RoBERTa Sentiment Scoring

Each ranked subreddit is assigned a sentiment score summarizing how positive or
negative the community's top posts are. This gives creators a signal about whether
they are walking into a welcoming or skeptical community.

### Model

`cardiffnlp/twitter-roberta-base-sentiment-latest` — a RoBERTa-base model fine-tuned
on Twitter data for three-class sentiment classification: Negative, Neutral, Positive.

### Label-to-Score Mapping

The model outputs a probability distribution over three classes. Let $\hat{c}$ be the
winning class and $p_{\hat{c}}$ its probability:

$$\hat{c} = \operatorname*{argmax}_{c} \operatorname{softmax}(\mathbf{logits})_c$$

$$\text{signed\_score} = \sigma(\hat{c}) \cdot p_{\hat{c}}$$

where the sign function $\sigma$ is:

| $\hat{c}$ | $\sigma(\hat{c})$ |
|-----------|-------------------|
| Positive  | $+1$ |
| Neutral   | $0$ |
| Negative  | $-1$ |

A chunk classified Positive with 90% confidence contributes $+0.90$; one classified
Negative with 60% confidence contributes $-0.60$.

### Per-Subreddit Aggregation

Let $C_r$ be the set of chunks belonging to subreddit $r$. Each chunk is scored
independently and the subreddit sentiment is the mean signed score:

$$\text{sentiment}(r) = \frac{1}{|C_r|} \sum_{c \,\in\, C_r} \text{signed\_score}(c)$$

Mean aggregation is used rather than majority vote because it preserves magnitude:
a community where half the posts are mildly positive and half are strongly negative
will correctly surface as net negative overall.

### Display Thresholds

| Score range | UI label |
|---|---|
| $\geq 0.5$ | Very Positive |
| $[0.1,\; 0.5)$ | Positive |
| $(-0.1,\; 0.1)$ | Mixed |
| $(-0.5,\; -0.1]$ | Negative |
| $< -0.5$ | Very Negative |

---

## 3. PAL Analytics Execution

PAL (Program-Aided Language models) is a technique in which the LLM generates a Python
program to answer an analytical question rather than computing the answer directly in
natural language. The generated code is then executed in a sandboxed environment.

### Why PAL

LLMs are unreliable at multi-step arithmetic and structured data reasoning when
answering directly in text. By delegating computation to a Python interpreter, the
LLM only needs to write correct code — not perform the computation mentally. The
interpreter handles precision and logic.

### Procedure

```
code ← LLM.generate(
    prompt  = "{analytics_question}\n\nWrite Python code using pandas/numpy to answer this.",
    temp    = 0.0
)

result ← sandbox.execute(code)
```

**Temperature 0.0** is used because code generation requires deterministic,
syntactically correct output. Stochastic sampling would increase the rate of syntax
errors and logic mistakes.

### Sandbox Design

Generated code is executed with `RestrictedPython.compile_restricted()`, which rewrites
the AST to block unsafe operations before compilation. The execution environment is
further restricted by a curated `safe_globals` dictionary:

```python
safe_globals = {
    "__builtins__": safe_builtins,   # no exec, eval, open, __import__
    "pd": pandas,
    "np": numpy,
    "math": math,
    "statistics": statistics,
}
```

Blocked by RestrictedPython:
- File I/O (`open`, `write`)
- Module imports outside `safe_globals`
- Attribute access on dunder names (`__class__`, `__bases__`)
- `exec` and `eval`

The sandbox does not enforce CPU or memory limits; the analytics queries in CreatorPal
are bounded by the size of the retrieved corpus slice (~10 subreddits), so runaway
execution is not a practical concern.

### Data Available to Generated Code

The code receives a `data` variable containing the PAL analytics payload as a
Python dict. The LLM is given the schema in the prompt so it can write correct
field access patterns without hallucinating column names.

### Failure Handling

If the generated code raises a `SyntaxError` or `RuntimeError`, the pipeline catches
the exception and returns an empty `pal_results` dict. The rest of the pipeline
continues; PAL analytics are treated as an optional enrichment layer.

---

[cross-encoder-paper]: https://arxiv.org/abs/1901.04085
[roberta-paper]: https://arxiv.org/abs/1907.11692
[pal-paper]: https://arxiv.org/abs/2211.10435
