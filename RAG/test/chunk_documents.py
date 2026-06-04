from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None


DEFAULT_SOURCE_DIR = Path(__file__).resolve().parent / "docs"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "chunks.jsonl"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


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


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"\S+", normalize_whitespace(text))


def iter_source_files(source_dir: Path) -> Iterable[Path]:
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def read_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    if PdfReader is None:
        raise RuntimeError(
            "PDF support requires the 'pypdf' package. Install it before chunking PDF files."
        )

    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((page_number, text))

    return pages


def read_text_document(text_path: Path) -> str:
    return text_path.read_text(encoding="utf-8", errors="ignore")


def split_text_into_chunks(
    text: str,
    chunk_size: int = 5000,
    chunk_overlap: int = 500,
) -> list[str]:
    words = tokenize_words(text)
    if not words:
        return []

    if len(words) <= chunk_size:
        return [normalize_whitespace(text)]

    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start = max(0, end - chunk_overlap)

    return chunks


def build_chunk_records(
    source_dir: Path,
    chunk_size: int = 5000,
    chunk_overlap: int = 500,
) -> list[ChunkRecord]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    records: list[ChunkRecord] = []

    for source_path in iter_source_files(source_dir):
        suffix = source_path.suffix.lower()
        if suffix == ".pdf":
            page_texts = read_pdf_pages(source_path)
            for page_number, page_text in page_texts:
                page_chunks = split_text_into_chunks(
                    page_text,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                total_chunks = len(page_chunks)
                for chunk_index, chunk_text in enumerate(page_chunks, start=1):
                    records.append(
                        ChunkRecord(
                            chunk_id=f"{source_path.stem}:p{page_number}:c{chunk_index}",
                            source_path=str(source_path),
                            source_name=source_path.name,
                            source_type="pdf",
                            page_number=page_number,
                            chunk_index=chunk_index,
                            total_chunks=total_chunks,
                            text=normalize_whitespace(chunk_text),
                            word_count=len(tokenize_words(chunk_text)),
                            char_count=len(chunk_text),
                        )
                    )
        else:
            text = read_text_document(source_path)
            file_chunks = split_text_into_chunks(
                text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            total_chunks = len(file_chunks)
            for chunk_index, chunk_text in enumerate(file_chunks, start=1):
                records.append(
                    ChunkRecord(
                        chunk_id=f"{source_path.stem}:c{chunk_index}",
                        source_path=str(source_path),
                        source_name=source_path.name,
                        source_type=suffix.lstrip("."),
                        page_number=None,
                        chunk_index=chunk_index,
                        total_chunks=total_chunks,
                        text=normalize_whitespace(chunk_text),
                        word_count=len(tokenize_words(chunk_text)),
                        char_count=len(chunk_text),
                    )
                )

    return records


def write_chunk_index(records: list[ChunkRecord], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return output_path


def chunk_documents(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    chunk_size: int = 5000,
    chunk_overlap: int = 500,
) -> list[ChunkRecord]:
    source_path = Path(source_dir)
    output_file = Path(output_path)
    records = build_chunk_records(
        source_path,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    write_chunk_index(records, output_file)
    return records


def build_prompt_context(records: list[ChunkRecord], max_chunks: int = 10) -> str:
    selected = records[:max_chunks]
    lines: list[str] = []
    for rank, record in enumerate(selected, start=1):
        location = record.source_name
        if record.page_number is not None:
            location = f"{location} p.{record.page_number}"
        lines.append(
            f"[{rank}] {record.chunk_id} | {location}\n{record.text}"
        )
    return "\n\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk PDFs and text files into a JSONL index.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Folder that contains PDF and TXT files.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Where to write the chunk index JSONL file.")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Maximum words per chunk.")
    parser.add_argument("--chunk-overlap", type=int, default=500, help="Word overlap between chunks.")
    args = parser.parse_args()

    records = chunk_documents(
        source_dir=args.source_dir,
        output_path=args.output,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print(f"Chunked {len(records)} chunks from {args.source_dir} into {args.output}")


if __name__ == "__main__":
    main()