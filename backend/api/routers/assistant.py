from fastapi import APIRouter
from pydantic import BaseModel

from deps import user_dependency
from generate_answer import answer_query

router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
)


class AssistantChatRequest(BaseModel):
    message: str


class AssistantSourceResponse(BaseModel):
    chunk_id: str
    score: float
    content: str


class AssistantChatResponse(BaseModel):
    query: str
    answer: str
    query_variations: list[str]
    sources: list[AssistantSourceResponse]


@router.post("/chat", response_model=AssistantChatResponse)
async def chat_with_chunks(current_user: user_dependency, request: AssistantChatRequest):
    result = answer_query(request.message.strip())
    return AssistantChatResponse(
        query=result["query"],
        answer=result["answer"],
        query_variations=result["query_variations"],
        sources=[AssistantSourceResponse(**source) for source in result["sources"]],
    )