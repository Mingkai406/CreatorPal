# Retrieval Algorithms

This document covers the four algorithms that build and search the subreddit corpus:
sliding-window chunking, BM25 keyword retrieval, bi-encoder dense retrieval, and hybrid score fusion.

---

## Table of Contents

- [1. Sliding-Window Chunking](#1-sliding-window-chunking)
- [2. BM25 Keyword Retrieval](#2-bm25-keyword-retrieval)
- [3. Bi-Encoder Dense Retrieval](#3-bi-encoder-dense-retrieval)
- [4. Hybrid Score Fusion](#4-hybrid-score-fusion)

---

## 1. Sliding-Window Chunking

Before indexing, each subreddit profile is split into overlapping token windows so that
long profiles do not exceed the encoder's context limit and boundary information is not lost.

**Parameters**

| Parameter      | Value |
|----------------|-------|
| Window size    | 64 tokens |
| Stride         | 48 tokens (overlap = 16) |
| Tokenizer      | whitespace split on lowercased text |

**Algorithm**

```
tokens  ← tokenize(profile_text)
chunks  ← []
i       ← 0
while i < len(tokens):
    chunk ← tokens[i : i + window_size]
    chunks.append(join(chunk))
    i ← i + stride
return chunks
```

Each chunk is stored with its parent subreddit name so retrieval results can be
aggregated back to the subreddit level.

The overlap of 16 tokens ensures that a sentence spanning a window boundary appears
in at least one chunk in full, preventing precision loss at boundaries.

---

## 2. BM25 Keyword Retrieval

BM25 (Best Match 25) is a probabilistic ranking function that scores documents by
term frequency saturation and document-length normalization. It is used as the
keyword signal in the hybrid retriever.

### Tokenizer

```python
tokens = re.findall(r"[a-z0-9]+", text.lower())
```

This strips punctuation and normalizes case before indexing and at query time.

### Scoring Formula

For query $Q$ containing terms $q_1, \ldots, q_n$ and document $d$:

$$\text{score}(Q, d) = \sum_{i=1}^{n} \text{IDF}(q_i) \cdot \frac{f(q_i,\, d) \cdot (k_1 + 1)}{f(q_i,\, d) + k_1 \cdot \left(1 - b + b \cdot \dfrac{|d|}{\text{avgdl}}\right)}$$

Where the IDF term is:

$$\text{IDF}(q_i) = \log\!\left(\frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} + 1\right)$$

Symbol definitions:

| Symbol | Meaning |
|--------|---------|
| $f(q_i, d)$ | Term frequency of $q_i$ in document $d$ |
| $\|d\|$ | Length of $d$ in tokens |
| $\text{avgdl}$ | Average document length across the corpus |
| $N$ | Total number of documents in the corpus |
| $n(q_i)$ | Number of documents containing $q_i$ |
| $k_1$ | Saturation parameter — default $1.5$ |
| $b$ | Length normalization parameter — default $0.75$ |

The $+1$ inside the IDF logarithm prevents negative scores for near-universal terms.

**Implementation:** `rank_bm25.BM25Okapi` initialized over all chunk texts at startup.
The index is held in memory; no persistence is required because it is rebuilt from the
NDJSON profile file on each application start.

---

## 3. Bi-Encoder Dense Retrieval

Dense retrieval encodes both the query and each chunk into a shared vector space and
retrieves the nearest neighbors by cosine similarity. FAISS is used as the
nearest-neighbor index.

### Embedding Model

`all-mpnet-base-v2` (Sentence-Transformers) — 768-dimensional output, trained on
1 billion sentence pairs to maximize semantic similarity alignment.

### Cosine Similarity via Inner Product

Cosine similarity between two vectors $\mathbf{u}$ and $\mathbf{v}$ is:

$$\cos(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \cdot \|\mathbf{v}\|}$$

If both vectors are pre-normalized to unit length ($\|\mathbf{u}\| = \|\mathbf{v}\| = 1$):

$$\cos(\mathbf{u}, \mathbf{v}) = \mathbf{u} \cdot \mathbf{v}$$

This lets FAISS `IndexFlatIP` (inner product index) compute cosine similarity directly
without an explicit division at query time.

### Index Construction

```
for each chunk c in corpus:
    e_c ← encode(c)           # shape (768,)
    e_c ← e_c / ‖e_c‖         # L2 normalize to unit length
    add e_c to IndexFlatIP

store chunk_to_subreddit mapping alongside index
```

### Query Execution

```
e_q ← encode(query)
e_q ← e_q / ‖e_q‖
(scores, indices) ← index.search(e_q, top_k=50)
results ← [(chunk_metadata[i], scores[i]) for i in indices]
```

FAISS `IndexFlatIP` performs an exact brute-force inner product scan. At corpus sizes
of ~10 000 chunks this is fast enough that an approximate index (IVF, HNSW) is not
required.

---

## 4. Hybrid Score Fusion

Hybrid fusion combines BM25 and FAISS scores into a single ranked list. The two
retrievers operate over different score scales, so min-max normalization is applied
before the weighted combination.

### Step 1 — Independent Retrieval

Both retrievers run against the same query independently and return their top-50
candidates. Candidates are keyed by subreddit name.

### Step 2 — Min-Max Normalization

For a score list $S = \{s_1, s_2, \ldots, s_n\}$:

$$\hat{s}_i = \frac{s_i - \min(S)}{\max(S) - \min(S) + \varepsilon}$$

$\varepsilon = 10^{-9}$ prevents division by zero when all scores are equal.
Normalization is applied separately to BM25 scores and FAISS scores before any fusion.

### Step 3 — Weighted Linear Combination

$$\text{score}_\text{fused}(d) = \alpha_\text{sem} \cdot \hat{s}_\text{FAISS}(d) + \alpha_\text{kw} \cdot \hat{s}_\text{BM25}(d)$$

| Weight | Value | Signal |
|--------|-------|--------|
| $\alpha_\text{sem}$ | 0.85 | FAISS semantic similarity |
| $\alpha_\text{kw}$ | 0.15 | BM25 keyword match |

Documents present in only one retriever receive $\hat{s} = 0$ for the missing signal,
not a penalty.

### Step 4 — Sort and Truncate

The fused scores are sorted descending. The top-50 candidates are passed to the
cross-encoder reranker.

### Weight Selection Rationale

The 85/15 split reflects the empirical observation that semantic matching is the
stronger signal for community-topic alignment (a subreddit about Rust systems
programming and a query about "memory management in C++" share meaning but few
exact words). BM25 retains a 15% share to capture exact-match recall for
domain-specific terminology (library names, technical acronyms) that embeddings
can under-weight.

---

[bm25-paper]: https://dl.acm.org/doi/10.1561/1500000019
[sbert-paper]: https://arxiv.org/abs/1908.10084
[faiss-paper]: https://arxiv.org/abs/1702.08734
