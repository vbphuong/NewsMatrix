import base64
import os
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import db_dependency, user_dependency
from api.generate_answer import answer_query
from api.services.news_embedding import backfill_news_embeddings

load_dotenv()

router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
CHAT_IMAGES_BUCKET = os.getenv("SUPABASE_CHAT_IMAGES_BUCKET", "chat-images")


def _normalize_supabase_url(raw_url: str) -> str:
    url = raw_url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    if url.endswith("/storage/v1"):
        url = url[: -len("/storage/v1")]
    return url


SUPABASE_URL = _normalize_supabase_url(os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL") or "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)


def _upload_image_to_supabase(image_bytes: bytes, object_path: str, content_type: str) -> str:
    """Upload image bytes to Supabase Storage and return the public URL."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase storage is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
        )

    encoded_path = urllib.parse.quote(object_path, safe="/-_.~")
    request_url = f"{SUPABASE_URL}/storage/v1/object/{CHAT_IMAGES_BUCKET}/{encoded_path}"

    req = urllib.request.Request(request_url, data=image_bytes, method="POST")
    req.add_header("Authorization", f"Bearer {SUPABASE_SERVICE_ROLE_KEY}")
    req.add_header("apikey", SUPABASE_SERVICE_ROLE_KEY)
    req.add_header("x-upsert", "true")
    req.add_header("Content-Type", content_type or "image/jpeg")

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            response.read()
    except urllib.error.HTTPError as error:
        error_message = error.read().decode("utf-8", errors="ignore")
        detail = error_message or error.reason or "Failed to upload image to Supabase storage"
        raise HTTPException(status_code=error.code or status.HTTP_502_BAD_GATEWAY, detail=detail) from error
    except urllib.error.URLError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to Supabase storage",
        ) from error

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{CHAT_IMAGES_BUCKET}/{encoded_path}"
    return public_url


class AssistantSourceResponse(BaseModel):
    chunk_id: str
    score: float
    content: str


class AssistantChatResponse(BaseModel):
    query: str
    answer: str
    image_url: str | None = None
    query_variations: list[str]
    sources: list[AssistantSourceResponse]


@router.post("/chat", response_model=AssistantChatResponse)
async def chat_with_chunks(
    current_user: user_dependency,
    message: str = Form(...),
    image: UploadFile | None = File(None),
):
    image_base64 = None
    image_url = None

    if image and image.filename:
        # Validate content type
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image type: {image.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )

        # Read and validate size
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB.",
            )

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Upload to Supabase Storage
        ext = os.path.splitext(image.filename or "image.jpg")[1] or ".jpg"
        object_path = f"chat/{uuid4().hex}{ext}"
        image_url = _upload_image_to_supabase(image_bytes, object_path, image.content_type)

    result = answer_query(message.strip(), image_base64=image_base64, image_content_type=image.content_type if image else "image/jpeg")

    return AssistantChatResponse(
        query=result["query"],
        answer=result["answer"],
        image_url=image_url,
        query_variations=result["query_variations"],
        sources=[AssistantSourceResponse(**source) for source in result["sources"]],
    )


@router.post("/backfill-news-embeddings")
async def backfill_news_embeddings_endpoint(
    current_user: user_dependency,
    db: db_dependency,
):
    """Generate embeddings for all published news articles that don't have one yet. Admin only."""
    if current_user.get("role") != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can trigger the news embedding backfill.",
        )

    result = backfill_news_embeddings(db)
    return result
