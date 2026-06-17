from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import db_dependency, user_dependency
from api.models import Document
from api.services.document_ingestion import ingest_pdf_document, list_documents

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


class DocumentResponse(BaseModel):
    document_id: int
    file_name: str
    file_type: str
    file_path: str
    total_page: int
    total_chunk: int
    created_at: Optional[datetime] = None


class DocumentUploadResponse(DocumentResponse):
    message: str


def require_admin(current_user: user_dependency) -> None:
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def serialize_document(document: Document) -> DocumentResponse:
    return DocumentResponse(
        document_id=document.document_id,
        file_name=document.file_name,
        file_type=document.file_type,
        file_path=document.file_path,
        total_page=document.total_page,
        total_chunk=document.total_chunk,
        created_at=document.created_at,
    )


@router.get("", response_model=list[DocumentResponse])
async def get_documents(current_user: user_dependency, db: db_dependency):
    require_admin(current_user)
    documents = list_documents(db)
    return [serialize_document(document) for document in documents]


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(current_user: user_dependency, db: db_dependency, file: UploadFile = File(...)):
    require_admin(current_user)

    if file.content_type not in {"application/pdf", "application/x-pdf"} and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files can be uploaded")

    document = ingest_pdf_document(db, file)
    response = serialize_document(document)
    return DocumentUploadResponse(message="Document uploaded and processed successfully.", **response.model_dump())