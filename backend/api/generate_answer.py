import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel

from database import SessionLocal
from models import Chunk, Document as DocumentRecord

load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_key)
model = ChatOpenAI(
    model="gpt-4o-mini",
    openai_api_key=openai_key
)

media_output_path = "base64.txt"

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
class RetrievedDocument:
    document: Document
    score: float


class QueryVariations(BaseModel):
    queries: list[str]


@dataclass(slots=True)
class IndexedChunk:
    document: Document
    embedding: list[float] | None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(text))
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def parse_chunk_metadata(chunk: Chunk) -> dict:
    metadata = chunk.chunk_metadata or {}
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except json.JSONDecodeError:
            return {"raw_text": metadata}
    return dict(metadata)


def build_chunk_page_content(metadata: dict) -> str:
    enhanced_content = metadata.get("enhanced_content") or ""
    original_content = metadata.get("original_content") or {}

    if isinstance(original_content, str):
        try:
            original_content = json.loads(original_content)
        except json.JSONDecodeError:
            original_content = {"raw_text": original_content}

    raw_text = original_content.get("raw_text", "") if isinstance(original_content, dict) else ""
    tables_html = original_content.get("tables_html", []) if isinstance(original_content, dict) else []

    search_parts = [enhanced_content, raw_text]
    search_parts.extend(str(table) for table in tables_html if table)
    return "\n".join(part for part in search_parts if part).strip()


def load_chunks_from_database() -> list[IndexedChunk]:
    db = SessionLocal()
    try:
        chunk_rows = (
            db.query(Chunk, DocumentRecord.file_name)
            .join(DocumentRecord, Chunk.document_id == DocumentRecord.document_id)
            .order_by(Chunk.created_at.asc(), Chunk.chunk_id.asc())
            .all()
        )

        indexed_chunks: list[IndexedChunk] = []
        for chunk_row, file_name in chunk_rows:
            metadata = parse_chunk_metadata(chunk_row)
            page_content = build_chunk_page_content(metadata)
            page_metadata = {
                "_chunk_id": str(chunk_row.chunk_id),
                "chunk_id": chunk_row.chunk_id,
                "document_id": chunk_row.document_id,
                "source_file": file_name,
                **metadata,
            }
            indexed_chunks.append(
                IndexedChunk(
                    document=Document(page_content=page_content, metadata=page_metadata),
                    embedding=list(chunk_row.embedding) if chunk_row.embedding is not None else None,
                )
            )

        return indexed_chunks
    finally:
        db.close()


class BM25Index:
    def __init__(self, documents: Sequence[Document], k1: float = 1.5, b: float = 0.75):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(document.page_content) for document in self.documents]
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

        self.document_count = len(self.documents)
        self.idf = {
            term: math.log(1.0 + (self.document_count - freq + 0.5) / (freq + 0.5))
            for term, freq in self.document_frequency.items()
        }

    def search(self, query: str, top_k: int = 20) -> list[Document]:
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
        return [self.documents[index] for index, _ in ranked]


def cosine_similarity(left: Sequence[float] | None, right: Sequence[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(l_value * r_value for l_value, r_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0

    return dot_product / (left_norm * right_norm)


def weighted_rrf(ranked_lists: Sequence[tuple[Sequence[Document], float]], k: int = 60) -> list[RetrievedDocument]:
    score_map: dict[str, float] = defaultdict(float)
    document_map: dict[str, Document] = {}

    for ranked_list, weight in ranked_lists:
        for rank, document in enumerate(ranked_list, start=1):
            document_id = document.metadata.get("_chunk_id") or document.metadata.get("id") or document.page_content
            document_map[document_id] = document
            score_map[document_id] += weight / (k + rank)

    fused = [
        RetrievedDocument(document=document_map[document_id], score=score)
        for document_id, score in score_map.items()
    ]
    fused.sort(key=lambda item: item.score, reverse=True)
    return fused


def expand_query_variants(query: str, max_variants: int = 3) -> list[str]:
    base_query = query.strip()
    if not base_query:
        return []

    prompt = f"""Generate {max_variants} different query variations for information retrieval.

Original query: {base_query}

Return only alternative queries that keep the same intent but use different wording or focus.
Do not repeat the original query."""

    try:
        structured_llm = model.with_structured_output(QueryVariations)
        response = structured_llm.invoke(prompt)
        variants = [variant.strip() for variant in response.queries if variant.strip()]
    except Exception:
        keyword_tokens = tokenize(base_query)
        keyword_phrase = " ".join(keyword_tokens[:8]) if keyword_tokens else base_query
        variants = [
            f"{keyword_phrase} details and evidence",
            f"{keyword_phrase} summary and related context",
            f"what documents mention {keyword_phrase}",
        ]

    unique_variants: list[str] = []
    for variant in [base_query, *variants]:
        normalized = variant.strip()
        if normalized and normalized not in unique_variants:
            unique_variants.append(normalized)
        if len(unique_variants) >= max_variants + 1:
            break

    return unique_variants or [base_query]


class HybridMultiQueryRetriever:
    def __init__(self, indexed_chunks: Sequence[IndexedChunk]):
        self.indexed_chunks = list(indexed_chunks)
        self.documents = [indexed_chunk.document for indexed_chunk in self.indexed_chunks]
        self.embeddings = [indexed_chunk.embedding for indexed_chunk in self.indexed_chunks]
        self.keyword_index = BM25Index(self.documents)

    def search(
        self,
        query: str,
        candidate_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        fusion_k: int = 60,
    ) -> list[RetrievedDocument]:
        query_embedding = embedding_model.embed_query(query)

        vector_candidates: list[tuple[float, Document]] = []
        for document, embedding in zip(self.documents, self.embeddings):
            similarity = cosine_similarity(query_embedding, embedding)
            vector_candidates.append((similarity, document))

        vector_candidates.sort(key=lambda item: item[0], reverse=True)
        vector_docs = [document for similarity, document in vector_candidates[:candidate_k] if similarity > 0]
        keyword_docs = self.keyword_index.search(query, top_k=candidate_k)
        return weighted_rrf(
            [
                (vector_docs, vector_weight),
                (keyword_docs, keyword_weight),
            ],
            k=fusion_k,
        )

    def search_multi_query(
        self,
        query: str,
        max_variants: int = 3,
        candidate_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        query_fusion_k: int = 60,
        retrieval_fusion_k: int = 60,
    ) -> tuple[list[RetrievedDocument], list[str]]:
        query_variations = expand_query_variants(query, max_variants=max_variants)
        per_query_rankings: list[tuple[Sequence[Document], float]] = []

        for variant in query_variations:
            hybrid_results = self.search(
                variant,
                candidate_k=candidate_k,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
                fusion_k=retrieval_fusion_k,
            )
            per_query_rankings.append(([item.document for item in hybrid_results], 1.0))

        fused_results = weighted_rrf(per_query_rankings, k=query_fusion_k)
        return fused_results, query_variations


def format_retrieved_documents(results: Sequence[RetrievedDocument], max_chars: int = 200) -> str:
    lines: list[str] = []
    for rank, result in enumerate(results, start=1):
        document = result.document
        chunk_id = document.metadata.get("_chunk_id", "unknown")
        preview = document.page_content[:max_chars]
        if len(document.page_content) > max_chars:
            preview += "..."
        lines.append(f"[{rank}] {chunk_id} | score={result.score:.4f}\n{preview}")
    return "\n\n".join(lines)


def build_chunk_media_report(chunks: Sequence[Document]) -> str:
    lines: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        lines.append(f"--- Document {index} ---")
        original_content = chunk.metadata.get("original_content")
        if not original_content:
            lines.append("No original_content metadata available.")
            lines.append("")
            continue

        if isinstance(original_content, str):
            try:
                original_data = json.loads(original_content)
            except json.JSONDecodeError:
                original_data = {"raw_text": original_content}
        else:
            original_data = original_content
        tables_html = original_data.get("tables_html", [])
        images_base64 = original_data.get("images_base64", [])

        if tables_html:
            lines.append("TABLES:")
            for table_index, table in enumerate(tables_html, start=1):
                lines.append(f"Table {table_index}: {table}")
        else:
            lines.append("TABLES: none")

        if images_base64:
            lines.append("IMAGE_BASE64:")
            for image_index, image_base64 in enumerate(images_base64, start=1):
                lines.append(f"Image {image_index}: {image_base64}")
        else:
            lines.append("IMAGE_BASE64: none")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_chunk_media_report(chunks: Sequence[Document], output_path: str) -> str:
    report = build_chunk_media_report(chunks)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report)
    return output_path


def chunks_have_media(chunks: Sequence[Document]) -> bool:
    for chunk in chunks:
        original_content = chunk.metadata.get("original_content")
        if not original_content:
            continue

        if isinstance(original_content, str):
            try:
                original_data = json.loads(original_content)
            except json.JSONDecodeError:
                original_data = {"raw_text": original_content}
        else:
            original_data = original_content
        if original_data.get("images_base64") or original_data.get("tables_html"):
            return True

    return False


def generate_final_answer(chunks, query):
    """Generate final answer using multimodal content"""
    
    try:
        # ChatGroq expects plain text content.
        llm = model
        has_media = chunks_have_media(chunks)
        media_instruction = (
            "There is media content available in base64.txt. Do not claim that there are no images if the source chunks contain images or tables."
            if has_media
            else "No image or table content was found in base64.txt. If relevant, you may say you don't have image."
        )
        
        # Build the text prompt
        prompt_text = f"""Based on the following documents, please answer this question: {query}

CONTENT TO ANALYZE:
{media_instruction}
"""
        
        for i, chunk in enumerate(chunks):
            prompt_text += f"--- Document {i+1} ---\n"
            
            original_content = chunk.metadata.get("original_content")
            if original_content:
                if isinstance(original_content, str):
                    try:
                        original_data = json.loads(original_content)
                    except json.JSONDecodeError:
                        original_data = {"raw_text": original_content}
                else:
                    original_data = original_content

                raw_text = original_data.get("raw_text", "")
                if raw_text:
                    prompt_text += f"TEXT:\n{raw_text}\n\n"

                tables_html = original_data.get("tables_html", [])
                if tables_html:
                    prompt_text += "TABLES:\n"
                    for table_index, table in enumerate(tables_html, start=1):
                        prompt_text += f"Table {table_index}:\n{table}\n\n"
            
            prompt_text += "\n"
        
        prompt_text += """
    Please provide a clear, comprehensive answer using the text above. If the documents don't contain sufficient information to answer the question, say "I don't have enough information to answer that question based on the provided documents."

ANSWER:"""

        response = llm.invoke(prompt_text)
        return response.content
        
    except Exception as e:
        print(f"❌ Answer generation failed: {e}")
        return "Sorry, I encountered an error while generating the answer."

def answer_query(query: str, max_results: int = 5) -> dict:
    indexed_chunks = load_chunks_from_database()
    retriever = HybridMultiQueryRetriever(indexed_chunks)
    fused_results, query_variations = retriever.search_multi_query(
        query=query,
        max_variants=3,
        candidate_k=5,
        vector_weight=0.7,
        keyword_weight=0.3,
        query_fusion_k=60,
        retrieval_fusion_k=60,
    )

    chunks = [result.document for result in fused_results[:max_results]]
    answer = generate_final_answer(chunks, query)

    return {
        "query": query,
        "answer": answer,
        "query_variations": query_variations,
        "sources": [
            {
                "chunk_id": result.document.metadata.get("_chunk_id", "unknown"),
                "source_file": result.document.metadata.get("source_file", "unknown"),
                "score": result.score,
                "content": result.document.page_content,
            }
            for result in fused_results[:max_results]
        ],
    }

if __name__ == "__main__":
    query = "Give me some illustration or image about the attention mechanism."
    result = answer_query(query)
    print("Generated Query Variations:")
    for index, variant in enumerate(result["query_variations"], start=1):
        print(f"{index}. {variant}")

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)
    print(result["answer"])

    if result["sources"]:
        write_chunk_media_report([
            Document(
                page_content=item["content"],
                metadata={"_chunk_id": item["chunk_id"], "source_file": item.get("source_file", "unknown")},
            )
            for item in result["sources"]
        ], media_output_path)