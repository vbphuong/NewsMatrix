from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


DEFAULT_INDEX_PATH = Path(__file__).resolve().parent / "chunks.jsonl"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}


@dataclass(slots=True)
class ChunkRecord:
    chunk_id: str
    source_path: str
    source_name: str
    source_type: str
    page_number: int | None
    chunk_index: int
    total_chunks: int
    text: str
    word_count: int
    char_count: int


@dataclass(slots=True)
class RetrievalResult:
    record: ChunkRecord
    score: float


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(text))
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def load_chunk_records(index_path: str | Path = DEFAULT_INDEX_PATH) -> list[ChunkRecord]:
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(f"Chunk index not found: {path}")

    records: list[ChunkRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(ChunkRecord(**data))

    return records


class BM25Index:
    def __init__(self, records: Sequence[ChunkRecord], k1: float = 1.5, b: float = 0.75):
        self.records = list(records)
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(record.text) for record in self.records]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0

        self.term_frequencies: list[Counter[str]] = []
        self.document_frequency: Counter[str] = Counter()
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)

        for doc_index, tokens in enumerate(self.doc_tokens):
            frequencies = Counter(tokens)
            self.term_frequencies.append(frequencies)
            for term, frequency in frequencies.items():
                self.document_frequency[term] += 1
                self.postings[term].append((doc_index, frequency))

        self.document_count = len(self.records)
        self.idf = {
            term: math.log(1.0 + (self.document_count - freq + 0.5) / (freq + 0.5))
            for term, freq in self.document_frequency.items()
        }

    def search(self, query: str, top_k: int = 20) -> list[RetrievalResult]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = defaultdict(float)

        for term in set(query_tokens):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for doc_index, term_frequency in self.postings.get(term, []):
                doc_length = self.doc_lengths[doc_index] or 1
                denominator = term_frequency + self.k1 * (1.0 - self.b + self.b * doc_length / self.avg_doc_length)
                scores[doc_index] += idf * (term_frequency * (self.k1 + 1.0)) / denominator

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return [RetrievalResult(record=self.records[index], score=score) for index, score in ranked]


class TfIdfVectorIndex:
    def __init__(self, records: Sequence[ChunkRecord]):
        self.records = list(records)
        self.tokens = [tokenize(record.text) for record in self.records]
        self.document_count = len(self.records)
        self.document_frequency: Counter[str] = Counter()

        for tokens in self.tokens:
            self.document_frequency.update(set(tokens))

        self.vocabulary = {term: index for index, term in enumerate(sorted(self.document_frequency))}
        self.idf = np.zeros(len(self.vocabulary), dtype=np.float32)
        for term, index in self.vocabulary.items():
            self.idf[index] = float(math.log(1.0 + self.document_count / (1.0 + self.document_frequency[term])) + 1.0)

        self.matrix = self._build_matrix()

    def _build_matrix(self) -> np.ndarray:
        if not self.vocabulary:
            return np.zeros((len(self.records), 0), dtype=np.float32)

        matrix = np.zeros((len(self.records), len(self.vocabulary)), dtype=np.float32)
        for row_index, tokens in enumerate(self.tokens):
            counts = Counter(tokens)
            for term, count in counts.items():
                column_index = self.vocabulary.get(term)
                if column_index is None:
                    continue
                matrix[row_index, column_index] = count * self.idf[column_index]

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return matrix / norms

    def search(self, query: str, top_k: int = 20) -> list[RetrievalResult]:
        query_tokens = tokenize(query)
        if not query_tokens or len(self.vocabulary) == 0:
            return []

        query_vector = np.zeros(len(self.vocabulary), dtype=np.float32)
        counts = Counter(query_tokens)
        for term, count in counts.items():
            column_index = self.vocabulary.get(term)
            if column_index is None:
                continue
            query_vector[column_index] = count * self.idf[column_index]

        norm = float(np.linalg.norm(query_vector))
        if norm == 0.0:
            return []

        query_vector /= norm
        scores = self.matrix @ query_vector
        ranked_indices = np.argsort(scores)[::-1]

        results: list[RetrievalResult] = []
        for doc_index in ranked_indices[:top_k]:
            score = float(scores[doc_index])
            if score <= 0.0:
                continue
            results.append(RetrievalResult(record=self.records[int(doc_index)], score=score))
        return results


def weighted_rrf(
    ranked_lists: Sequence[tuple[Sequence[RetrievalResult], float]],
    k: int = 60,
) -> list[RetrievalResult]:
    score_map: dict[str, float] = defaultdict(float)
    record_map: dict[str, ChunkRecord] = {}

    for ranked_list, weight in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            record_map[result.record.chunk_id] = result.record
            score_map[result.record.chunk_id] += weight / (k + rank)

    fused = [RetrievalResult(record=record_map[chunk_id], score=score) for chunk_id, score in score_map.items()]
    fused.sort(key=lambda item: item.score, reverse=True)
    return fused


def expand_query_variants(query: str, max_variants: int = 3) -> list[str]:
    base_query = query.strip()
    if not base_query:
        return []

    keyword_tokens = tokenize(base_query)
    keyword_phrase = " ".join(keyword_tokens[:8]) if keyword_tokens else base_query

    variants = [
        base_query,
        f"{keyword_phrase} details and evidence",
        f"{keyword_phrase} summary and related context",
        f"what documents mention {keyword_phrase}",
    ]

    unique_variants: list[str] = []
    for variant in variants:
        normalized = variant.strip()
        if normalized and normalized not in unique_variants:
            unique_variants.append(normalized)
        if len(unique_variants) >= max_variants:
            break

    return unique_variants or [base_query]


def retrieve_top_chunks(
    query: str,
    records: Sequence[ChunkRecord],
    query_variants: Sequence[str] | None = None,
    top_k: int = 15,
    candidate_k: int = 20,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    fusion_k: int = 60,
) -> list[RetrievalResult]:
    if not records:
        return []

    vector_index = TfIdfVectorIndex(records)
    keyword_index = BM25Index(records)
    variants = list(query_variants) if query_variants else expand_query_variants(query)
    if not variants:
        variants = [query]

    per_query_rankings: list[tuple[Sequence[RetrievalResult], float]] = []

    for variant in variants:
        vector_results = vector_index.search(variant, top_k=candidate_k)
        keyword_results = keyword_index.search(variant, top_k=candidate_k)
        query_fused = weighted_rrf(
            [
                (vector_results, vector_weight),
                (keyword_results, keyword_weight),
            ],
            k=fusion_k,
        )
        per_query_rankings.append((query_fused, 1.0))

    fused_results = weighted_rrf(per_query_rankings, k=fusion_k)
    return fused_results[:top_k]


def format_chunks_for_llm(results: Sequence[RetrievalResult], max_chars: int = 2000) -> str:
    lines: list[str] = []
    for rank, result in enumerate(results, start=1):
        record = result.record
        location = record.source_name
        if record.page_number is not None:
            location = f"{location} p.{record.page_number}"

        chunk_text = record.text[:max_chars]
        if len(record.text) > max_chars:
            chunk_text += "..."

        lines.append(
            f"[{rank}] {record.chunk_id} | score={result.score:.4f} | {location}\n{chunk_text}"
        )

    return "\n\n".join(lines)


def retrieve_context(
    query: str,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    query_variants: Sequence[str] | None = None,
    top_k: int = 15,
    candidate_k: int = 20,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    fusion_k: int = 60,
) -> tuple[list[RetrievalResult], str]:
    records = load_chunk_records(index_path)
    results = retrieve_top_chunks(
        query=query,
        records=records,
        query_variants=query_variants,
        top_k=top_k,
        candidate_k=candidate_k,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
        fusion_k=fusion_k,
    )
    return results, format_chunks_for_llm(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve top chunks from a chunk index using hybrid search + RRF.")
    parser.add_argument("query", help="User question to retrieve context for.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX_PATH), help="Path to chunks.jsonl.")
    parser.add_argument("--top-k", type=int, default=15, help="How many chunks to keep after fusion.")
    parser.add_argument("--candidate-k", type=int, default=20, help="How many candidates to pull from each retriever.")
    parser.add_argument("--query-variant", action="append", default=[], help="Optional extra query variants. Repeatable.")
    args = parser.parse_args()

    variants = args.query_variant or None
    results, context = retrieve_context(
        query=args.query,
        index_path=args.index,
        query_variants=variants,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
    )

    print(context)
    print()
    print(f"Returned {len(results)} chunks for the query.")


if __name__ == "__main__":
    main()