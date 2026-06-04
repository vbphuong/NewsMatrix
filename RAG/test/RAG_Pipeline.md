# RAG Architecture Design

## Overview

This system implements an **Advanced Hybrid RAG (Retrieval-Augmented Generation)** architecture that combines:

* Multi-Query Retrieval
* Hybrid Search (Vector + Keyword)
* Reciprocal Rank Fusion (RRF)
* Large Language Model (LLM) Generation

The objective is to improve retrieval quality before providing context to the LLM.

---

# 1. Ingestion Pipeline

The ingestion pipeline transforms raw documents into searchable vector representations.

```text
Source Documents
      ↓
Chunking (~5000 tokens)
      ↓
Embedding Model
      ↓
Vector Database (Supabase PostgreSQL)
```

## 1.1 Document Chunking

Source documents are divided into smaller chunks of approximately 5,000 tokens.

Example:

```text
Annual Report
├── Chunk 1
├── Chunk 2
├── Chunk 3
└── ...
```

Chunking enables efficient retrieval and reduces context size for the LLM.

---

## 1.2 Embedding Generation

Each chunk is converted into a dense vector representation using an embedding model.

Example:

```text
Chunk 1 → [number, number, number, number,...]
Chunk 2 → [number, number, number, number,...]
```

These embeddings capture the semantic meaning of the text.

---

## 1.3 Storage

The chunk content, metadata, and embeddings are stored in:

* PostgreSQL
* Supabase Vector Extension

This enables efficient semantic similarity search during retrieval.

---

# 2. Retrieval Pipeline

The retrieval workflow begins when a user submits a question.

```text
User Query
      ↓
Hybrid Search
      ↓
Top Retrieved Chunks
      ↓
LLM
      ↓
Final Answer
```

However, the Hybrid Search stage contains several advanced retrieval mechanisms.

---

# 3. Multi-Query Expansion

Instead of searching with a single query, the system generates multiple variations of the user's question.

```text
Original Query
      ↓
Query 1
Query 2
Query 3
Query 4
```

Example:

User query:

> Tesla revenue growth in 2024

Generated queries:

```text
Query 1:
Tesla revenue growth 2024

Query 2:
Tesla annual revenue increase

Query 3:
Tesla sales growth fiscal year 2024

Query 4:
Revenue trend Tesla 2024
```

## Purpose

Multi-query expansion improves retrieval recall by:

* Capturing different phrasings
* Handling synonym usage
* Reducing dependency on a single wording

---

# 4. Hybrid Search

For each generated query, the system performs two retrieval strategies simultaneously.

## 4.1 Vector Search

Vector search retrieves semantically similar chunks.

```text
Embedding(Query)
        ↓
Cosine Similarity
        ↓
Top Chunks
```

Example results:

```text
Chunk 5
Chunk 17
Chunk 22
...
```

### Advantages

* Understands semantic meaning
* Handles paraphrasing effectively
* Retrieves conceptually related information

---

## 4.2 Keyword Search

Keyword search retrieves documents using lexical matching.

Possible implementations:

* BM25
* PostgreSQL Full Text Search

Example results:

```text
Chunk 3
Chunk 22
Chunk 30
...
```

### Advantages

* Preserves exact terminology
* Works well for names, numbers, and technical keywords

---

# 5. Reciprocal Rank Fusion (RRF)

Results from Vector Search and Keyword Search are merged using Reciprocal Rank Fusion (RRF).

## Formula

[
Score(d)=\sum \frac{1}{k+rank}
]

Where:

* `d` = document/chunk
* `rank` = position in a ranked list
* `k` = smoothing constant

---

## Example

### Vector Search

```text
1. Chunk A
2. Chunk B
3. Chunk C
```

### Keyword Search

```text
1. Chunk B
2. Chunk D
3. Chunk A
```

### RRF Output

```text
1. Chunk B
2. Chunk A
3. Chunk D
4. Chunk C
```

## Purpose

RRF rewards chunks that consistently rank highly across multiple retrieval methods.

---

# 6. Two-Level RRF Fusion

The architecture applies RRF twice.

---

## 6.1 First-Level Fusion

For each query:

```text
Vector Search
      +
Keyword Search
      ↓
      RRF
      ↓
Top ~20 Chunks
```

Result:

```text
Query 1 → Top 20 Chunks
Query 2 → Top 20 Chunks
Query 3 → Top 20 Chunks
Query 4 → Top 20 Chunks
```

This produces a ranked retrieval result for every query variation.

---

## 6.2 Second-Level Fusion

Results from all generated queries are combined again using RRF.

```text
20 Chunks
20 Chunks
20 Chunks
20 Chunks
      ↓
      RRF
      ↓
Top ~15 Chunks
```

## Purpose

The second fusion stage:

* Removes redundancy
* Promotes consistently relevant chunks
* Improves retrieval robustness

---

# 7. Context Construction

After the final RRF stage, the system selects the highest-ranked chunks.

```text
Top 15 Chunks
```

These chunks are assembled into the final prompt:

```text
Retrieved Context

Chunk 1
Chunk 2
...
Chunk 15

Conversation History

Current User Question
```

---

# 8. LLM Generation

The LLM receives:

```text
Retrieved Chunks
+
Conversation History
+
Current User Question
```

The model then generates the final response.

```text
Answer
```

---

# Advantages of This Architecture

## 1. Hybrid Retrieval

Combines:

* Semantic Search
* Keyword Search

Benefits:

* Better recall
* Better precision
* Reduced retrieval failure

---

## 2. Multi-Query Expansion

Transforms one question into multiple search formulations.

Benefits:

* Improved coverage
* Better handling of user phrasing variations

---

## 3. Dual RRF Fusion

Two-stage ranking improves result quality by combining:

1. Multiple retrieval methods
2. Multiple query formulations

Benefits:

* Higher retrieval robustness
* Better ranking consistency

---

## 4. Context Compression

The system may generate over 100 candidate chunks:

```text
4 Queries
×
20–30 Chunks
≈ 80–120 Candidates
```

But only passes:

```text
Top ~15 Chunks
```

to the LLM.

Benefits:

* Lower token cost
* Less noise
* Improved answer quality

---

# Final Architecture Summary

```text
Document
    ↓
Chunking
    ↓
Embedding
    ↓
Vector Database

User Query
    ↓
Multi-Query Expansion
    ↓
Hybrid Search
    ├── Vector Search
    └── Keyword Search
    ↓
RRF Fusion (Level 1)
    ↓
Per-Query Results
    ↓
RRF Fusion (Level 2)
    ↓
Top 15 Chunks
    ↓
Prompt Construction
    ↓
LLM
    ↓
Answer
```

This architecture is significantly more powerful than a basic RAG pipeline:

```text
Query
   ↓
Vector Search
   ↓
Top-K Chunks
   ↓
LLM
```

because it leverages multiple query formulations, hybrid retrieval mechanisms, and ranking fusion strategies to maximize retrieval accuracy before generation.
