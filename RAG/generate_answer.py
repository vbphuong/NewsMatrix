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
from langchain_chroma import Chroma
from pydantic import BaseModel

load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_key)
model = ChatOpenAI(
    model="gpt-4o-mini",
    openai_api_key=openai_key
)

persistent_directory = "dbv2/chroma_db"
media_output_path = "base64.txt"

db = Chroma(
    persist_directory=persistent_directory,
    embedding_function=embedding_model,
    collection_metadata={"hnsw:space": "cosine"}
)

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


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(text))
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def load_documents_from_store() -> list[Document]:
    """Load all documents from the Chroma collection into memory."""

    try:
        raw = db.get(include=["documents", "metadatas"])
    except Exception:
        raw = db._collection.get(include=["documents", "metadatas"])  # pragma: no cover

    documents = raw.get("documents", []) or []
    metadatas = raw.get("metadatas", []) or []
    ids = raw.get("ids", []) or []

    loaded_documents: list[Document] = []
    for index, text in enumerate(documents):
        metadata = dict(metadatas[index] or {}) if index < len(metadatas) else {}
        if index < len(ids):
            metadata.setdefault("_chunk_id", ids[index])
        loaded_documents.append(Document(page_content=text or "", metadata=metadata))

    return loaded_documents


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
    def __init__(self, documents: Sequence[Document]):
        self.documents = list(documents)
        self.keyword_index = BM25Index(self.documents)

    def search(
        self,
        query: str,
        candidate_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        fusion_k: int = 60,
    ) -> list[RetrievedDocument]:
        vector_docs = db.similarity_search(query, k=candidate_k)
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
        if "original_content" not in chunk.metadata:
            lines.append("No original_content metadata available.")
            lines.append("")
            continue

        original_data = json.loads(chunk.metadata["original_content"])
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

        original_data = json.loads(original_content)
        if original_data.get("images_base64") or original_data.get("tables_html"):
            return True

    return False


documents = load_documents_from_store()
retriever = HybridMultiQueryRetriever(documents)

# Query the vector store
query = "Give me some illustration or image about the attention mechanism."

fused_results, query_variations = retriever.search_multi_query(
    query=query,
    max_variants=3,
    candidate_k=5,
    vector_weight=0.7,
    keyword_weight=0.3,
    query_fusion_k=60,
    retrieval_fusion_k=60,
)

chunks = [result.document for result in fused_results[:5]]

print("Generated Query Variations:")
for index, variant in enumerate(query_variations, start=1):
    print(f"{index}. {variant}")

print("\n" + "=" * 60)
print("FUSED RETRIEVAL RESULTS")
print("=" * 60)
print(format_retrieved_documents(fused_results[:10]))

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
            
            if "original_content" in chunk.metadata:
                original_data = json.loads(chunk.metadata["original_content"])
                
                # Add raw text
                raw_text = original_data.get("raw_text", "")
                if raw_text:
                    prompt_text += f"TEXT:\n{raw_text}\n\n"
            
            prompt_text += "\n"
        
        prompt_text += """
    Please provide a clear, comprehensive answer using the text above. If the documents don't contain sufficient information to answer the question, say "I don't have enough information to answer that question based on the provided documents."

ANSWER:"""

        response = llm.invoke(prompt_text)
        return response.content
        
    except Exception as e:
        print(f"❌ Answer generation failed: {e}")
        return "Sorry, I encountered an error while generating the answer."

# Usage
final_answer = generate_final_answer(chunks, query)
print(final_answer)

write_chunk_media_report(chunks, media_output_path)