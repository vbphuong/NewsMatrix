import json
import mimetypes
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from models import Chunk, Document
from multi_model_chunk import create_chunks_by_title, embedding_model, partition_document, summarise_chunks

load_dotenv()

def normalize_supabase_url(raw_url: str) -> str:
    url = raw_url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    if url.endswith("/storage/v1"):
        url = url[: -len("/storage/v1")]
    return url


SUPABASE_URL = normalize_supabase_url(os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL") or "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)
RAW_DATA_BUCKET = os.getenv("SUPABASE_RAW_DATA_BUCKET", "raw_data")


def require_storage_config() -> tuple[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase storage is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
        )

    return SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    stem = Path(name).stem
    suffix = Path(name).suffix.lower() or ".pdf"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-_.") or "document"
    return f"{safe_stem}{suffix}"


def save_upload_to_temp_file(upload_file: UploadFile) -> str:
    suffix = Path(upload_file.filename or "document.pdf").suffix or ".pdf"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(upload_file.file, temp_file)
        return temp_file.name
    finally:
        temp_file.close()


def upload_pdf_to_supabase_storage(file_path: str, object_path: str, content_type: str) -> None:
    supabase_url, service_role_key = require_storage_config()
    encoded_object_path = urllib.parse.quote(object_path, safe="/-_.~")
    request_url = f"{supabase_url}/storage/v1/object/{RAW_DATA_BUCKET}/{encoded_object_path}"

    with open(file_path, "rb") as file_handle:
        request = urllib.request.Request(
            request_url,
            data=file_handle.read(),
            method="POST",
        )

    request.add_header("Authorization", f"Bearer {service_role_key}")
    request.add_header("apikey", service_role_key)
    request.add_header("x-upsert", "true")
    request.add_header("Content-Type", content_type or "application/pdf")

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
    except urllib.error.HTTPError as error:
        error_message = error.read().decode("utf-8", errors="ignore")
        detail = error_message or error.reason or "Failed to upload file to Supabase storage"
        raise HTTPException(status_code=error.code or status.HTTP_502_BAD_GATEWAY, detail=detail) from error
    except urllib.error.URLError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to Supabase storage",
        ) from error


def extract_total_pages(elements) -> int:
    page_numbers = set()
    for element in elements:
        metadata = getattr(element, "metadata", None)
        page_number = getattr(metadata, "page_number", None)
        if isinstance(page_number, int) and page_number > 0:
            page_numbers.add(page_number)
    return max(page_numbers) if page_numbers else 0


def build_chunk_metadata(document_id: int, chunk_index: int, chunk_document) -> dict:
    original_content = chunk_document.metadata.get("original_content", "{}")
    try:
        parsed_original_content = json.loads(original_content) if isinstance(original_content, str) else original_content
    except json.JSONDecodeError:
        parsed_original_content = {"raw_text": original_content}

    return {
        "document_id": document_id,
        "chunk_index": chunk_index,
        "enhanced_content": chunk_document.page_content,
        "original_content": parsed_original_content,
    }


def ingest_pdf_document(db: Session, upload_file: UploadFile) -> Document:
    if not upload_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A PDF file is required")

    filename = sanitize_filename(upload_file.filename)
    inferred_content_type = upload_file.content_type or mimetypes.guess_type(filename)[0] or "application/pdf"
    if inferred_content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files can be uploaded")

    temp_path = save_upload_to_temp_file(upload_file)
    try:
        object_path = f"documents/{uuid4().hex}/{filename}"

        upload_pdf_to_supabase_storage(temp_path, object_path, "application/pdf")

        elements = partition_document(temp_path)
        chunks = create_chunks_by_title(elements)
        summarised_chunks = summarise_chunks(chunks)

        document_record = Document(
            file_name=upload_file.filename,
            file_type="application/pdf",
            file_path=object_path,
            total_page=extract_total_pages(elements),
            total_chunk=len(summarised_chunks),
        )

        db.add(document_record)
        db.flush()

        if summarised_chunks:
            embeddings = embedding_model.embed_documents([chunk.page_content for chunk in summarised_chunks])
            for chunk_index, (chunk_document, embedding) in enumerate(zip(summarised_chunks, embeddings), start=1):
                db.add(
                    Chunk(
                        document_id=document_record.document_id,
                        embedding=embedding,
                        chunk_index=chunk_index,
                        chunk_metadata=build_chunk_metadata(document_record.document_id, chunk_index, chunk_document),
                    )
                )

        db.commit()
        db.refresh(document_record)
        return document_record
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process uploaded document: {error}",
        ) from error
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def list_documents(db: Session, limit: int = 100) -> list[Document]:
    return (
        db.query(Document)
        .order_by(Document.created_at.desc(), Document.document_id.desc())
        .limit(limit)
        .all()
    )