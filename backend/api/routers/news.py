from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from api.deps import db_dependency, user_dependency
from api.models import Category, Comment, Follow, Like, News, Organization, User
from api.services.news_embedding import update_news_embedding
from api.services.scalability import (
    cache_append_comment,
    cache_get_int,
    cache_get_json,
    cache_replace_comments,
    create_interaction_event,
    create_temporary_comment_id,
    get_cache_set_members,
    get_db_followed_organization_ids,
    get_db_news_comment_count,
    get_db_news_comments,
    get_db_news_like_count,
    get_db_news_like_ids,
    get_db_organization_followers_count,
    get_redis_client,
    invalidate_news_projections,
    prime_cached_id_set,
    prime_news_projection_cache,
    publish_interaction_event,
    redis_key_news_comment_count,
    redis_key_news_comments,
    redis_key_news_like_count,
    redis_key_org_followers_count,
    redis_key_user_followed_orgs,
    redis_key_user_liked_news,
    refresh_news_projection_cache,
    refresh_user_interaction_cache,
)

router = APIRouter(
    prefix="/news",
    tags=["news"],
)


class NewsAuthorResponse(BaseModel):
    user_id: int
    email: str


class NewsCategoryResponse(BaseModel):
    category_id: int
    name: str


class NewsResponse(BaseModel):
    news_id: int
    organization_id: int
    organization_name: str
    title: str
    content: str
    status: str
    published_at: Optional[datetime] = None
    view_count: int
    like_count: int
    comment_count: int
    organization_followers_count: int
    authors: list[NewsAuthorResponse]
    categories: list[NewsCategoryResponse]


class NewsListResponse(BaseModel):
    items: list[NewsResponse]


class NewsWorkspaceResponse(BaseModel):
    has_organization: bool
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    message: str
    items: list[NewsResponse]


class NewsCreateRequest(BaseModel):
    title: str
    content: str
    status: str = "Draft"
    organization_id: Optional[int] = None
    category_ids: list[int] = []


class NewsUpdateRequest(BaseModel):
    title: str
    content: str
    status: str
    category_ids: list[int] = []


class NewsCommentRequest(BaseModel):
    content: str


class NewsCommentResponse(BaseModel):
    comment_id: int
    user_id: int
    user_email: str
    content: str
    created_at: Optional[datetime] = None


class NewsLikeStateResponse(BaseModel):
    news_id: int
    liked: bool
    like_count: int


class NewsInteractionResponse(BaseModel):
    liked_news_ids: list[int]
    followed_organization_ids: list[int]


def require_journalist_or_admin(current_user: user_dependency) -> None:
    if current_user.get("role") not in {"Journalist", "Admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Journalist access required")


def get_news_or_404(db, news_id: int) -> News:
    news = (
        db.query(News)
        .options(
            joinedload(News.organization),
            joinedload(News.authors).joinedload(User.role),
            joinedload(News.categories),
        )
        .filter(News.news_id == news_id)
        .first()
    )
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
    return news


def get_news_metadata(db, news_id: int) -> dict:
    cache = get_redis_client()
    if cache:
        cached_meta = cache.get(f"news:{news_id}:metadata")
        if cached_meta:
            import json
            try:
                return json.loads(cached_meta)
            except Exception:
                pass

    news_row = db.query(News.status, News.organization_id).filter(News.news_id == news_id).first()
    if not news_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")

    metadata = {
        "status": news_row.status,
        "organization_id": news_row.organization_id
    }
    if cache:
        import json
        try:
            cache.set(f"news:{news_id}:metadata", json.dumps(metadata), ex=300)
        except Exception:
            pass
    return metadata


def serialize_news(
    news: News,
    like_count: int,
    comment_count: int,
    organization_followers_count: int,
) -> NewsResponse:
    return NewsResponse(
        news_id=news.news_id,
        organization_id=news.organization_id,
        organization_name=news.organization.name if news.organization else "Unknown",
        title=news.title,
        content=news.content,
        status=news.status,
        published_at=news.published_at,
        view_count=news.view_count,
        like_count=like_count,
        comment_count=comment_count,
        organization_followers_count=organization_followers_count,
        authors=[
            NewsAuthorResponse(user_id=author.user_id, email=author.email)
            for author in (news.authors or [])
        ],
        categories=[
            NewsCategoryResponse(category_id=category.category_id, name=category.name)
            for category in (news.categories or [])
        ],
    )


def get_categories_by_ids(db, category_ids: list[int]) -> list[Category]:
    unique_category_ids = sorted(
        {
            category_id
            for category_id in category_ids
            if isinstance(category_id, int) and category_id > 0
        }
    )
    if not unique_category_ids:
        return []

    categories = db.query(Category).filter(Category.category_id.in_(unique_category_ids)).all()
    found_ids = {category.category_id for category in categories}
    missing_ids = [category_id for category_id in unique_category_ids if category_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category IDs: {', '.join(str(category_id) for category_id in missing_ids)}",
        )

    return categories


def get_current_user_organization_id(current_user: user_dependency) -> Optional[int]:
    return current_user.get("organization_id")


def ensure_published_news(news: News) -> None:
    if news.status.lower() != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only published news can be interacted with")


def serialize_comment(comment: Comment) -> NewsCommentResponse:
    return NewsCommentResponse(
        comment_id=comment.comment_id,
        user_id=comment.user_id,
        user_email=comment.user.email if comment.user else "Unknown",
        content=comment.content,
        created_at=comment.created_at,
    )


def fetch_news_metrics(db, news_items: list[News]) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    cache = get_redis_client()
    news_ids = [news.news_id for news in news_items]
    organization_ids = sorted({news.organization_id for news in news_items if news.organization_id})

    like_counts: dict[int, int] = {}
    comment_counts: dict[int, int] = {}
    org_followers_counts: dict[int, int] = {}

    missing_news_ids: list[int] = []
    for news_id in news_ids:
        cached_like_count = cache_get_int(cache, redis_key_news_like_count(news_id))
        cached_comment_count = cache_get_int(cache, redis_key_news_comment_count(news_id))
        if cached_like_count is None or cached_comment_count is None:
            missing_news_ids.append(news_id)
        else:
            like_counts[news_id] = cached_like_count
            comment_counts[news_id] = cached_comment_count

    if missing_news_ids:
        like_rows = (
            db.query(Like.news_id, func.count(Like.like_id).label("like_count"))
            .filter(Like.news_id.in_(missing_news_ids))
            .group_by(Like.news_id)
            .all()
        )
        comment_rows = (
            db.query(Comment.news_id, func.count(Comment.comment_id).label("comment_count"))
            .filter(Comment.news_id.in_(missing_news_ids))
            .group_by(Comment.news_id)
            .all()
        )

        like_map = {news_id: count for news_id, count in like_rows}
        comment_map = {news_id: count for news_id, count in comment_rows}
        for news_id in missing_news_ids:
            like_counts[news_id] = like_map.get(news_id, 0)
            comment_counts[news_id] = comment_map.get(news_id, 0)
            prime_news_projection_cache(
                cache,
                news_id,
                like_count=like_counts[news_id],
                comment_count=comment_counts[news_id],
            )

    missing_org_ids: list[int] = []
    for organization_id in organization_ids:
        cached_followers_count = cache_get_int(cache, redis_key_org_followers_count(organization_id))
        if cached_followers_count is None:
            missing_org_ids.append(organization_id)
        else:
            org_followers_counts[organization_id] = cached_followers_count

    if missing_org_ids:
        follower_rows = (
            db.query(Follow.organization_id, func.count(Follow.follow_id).label("followers_count"))
            .filter(Follow.organization_id.in_(missing_org_ids))
            .group_by(Follow.organization_id)
            .all()
        )
        follower_map = {organization_id: count for organization_id, count in follower_rows}
        for organization_id in missing_org_ids:
            org_followers_counts[organization_id] = follower_map.get(organization_id, 0)
            if cache is not None:
                cache.set(redis_key_org_followers_count(organization_id), org_followers_counts[organization_id], ex=120)

    return like_counts, comment_counts, org_followers_counts


def serialize_news_collection(db, news_items: list[News]) -> list[NewsResponse]:
    like_counts, comment_counts, org_followers_counts = fetch_news_metrics(db, news_items)
    return [
        serialize_news(
            news,
            like_counts.get(news.news_id, 0),
            comment_counts.get(news.news_id, 0),
            org_followers_counts.get(news.organization_id, 0) if news.organization_id else 0,
        )
        for news in news_items
    ]


@router.get("", response_model=NewsListResponse)
async def list_news(db: db_dependency):
    news_items = (
        db.query(News)
        .options(
            joinedload(News.organization),
            joinedload(News.authors),
            joinedload(News.categories),
        )
        .order_by(News.news_id.desc())
        .all()
    )
    return NewsListResponse(items=serialize_news_collection(db, news_items))


@router.get("/interactions/me", response_model=NewsInteractionResponse)
async def get_my_news_interactions(current_user: user_dependency, db: db_dependency):
    user_id = current_user.get("id")
    cache = get_redis_client()

    liked_news_ids = get_cache_set_members(cache, redis_key_user_liked_news(user_id))
    if not liked_news_ids:
        liked_news_ids = get_db_news_like_ids(db, user_id)
        prime_cached_id_set(cache, redis_key_user_liked_news(user_id), liked_news_ids)

    followed_organization_ids = get_cache_set_members(cache, redis_key_user_followed_orgs(user_id))
    if not followed_organization_ids:
        followed_organization_ids = get_db_followed_organization_ids(db, user_id)
        prime_cached_id_set(cache, redis_key_user_followed_orgs(user_id), followed_organization_ids)

    return NewsInteractionResponse(
        liked_news_ids=liked_news_ids,
        followed_organization_ids=followed_organization_ids,
    )


@router.get("/workspace", response_model=NewsWorkspaceResponse)
async def get_workspace_news(current_user: user_dependency, db: db_dependency):
    require_journalist_or_admin(current_user)

    organization_id = get_current_user_organization_id(current_user)
    if not organization_id:
        return NewsWorkspaceResponse(
            has_organization=False,
            message="You are not assigned to any organization yet.",
            items=[],
        )

    organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()
    if not organization:
        return NewsWorkspaceResponse(
            has_organization=False,
            message="Your organization could not be found.",
            items=[],
        )

    news_items = (
        db.query(News)
        .options(
            joinedload(News.organization),
            joinedload(News.authors),
            joinedload(News.categories),
        )
        .filter(News.organization_id == organization_id)
        .order_by(News.news_id.desc())
        .all()
    )

    return NewsWorkspaceResponse(
        has_organization=True,
        organization_id=organization.organization_id,
        organization_name=organization.name,
        message=f"News in {organization.name}",
        items=serialize_news_collection(db, news_items),
    )


@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(news_id: int, db: db_dependency):
    news = get_news_or_404(db, news_id)
    like_count, comment_count, organization_followers_counts = fetch_news_metrics(db, [news])
    return serialize_news(
        news,
        like_count.get(news.news_id, 0),
        comment_count.get(news.news_id, 0),
        organization_followers_counts.get(news.organization_id, 0) if news.organization_id else 0,
    )


@router.post("", response_model=NewsResponse, status_code=status.HTTP_201_CREATED)
async def create_news(payload: NewsCreateRequest, current_user: user_dependency, db: db_dependency):
    require_journalist_or_admin(current_user)

    organization_id = payload.organization_id or get_current_user_organization_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You need to belong to an organization to create news")

    organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if current_user.get("role") == "Journalist" and current_user.get("organization_id") != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only create news in your own organization")

    author = db.query(User).filter(User.user_id == current_user.get("id")).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

    normalized_status = payload.status.strip() or "Draft"

    news = News(
        organization_id=organization_id,
        title=payload.title.strip(),
        content=payload.content.strip(),
        status=normalized_status,
        published_at=datetime.now(timezone.utc) if normalized_status.lower() == "published" else None,
    )
    news.authors.append(author)
    news.categories = get_categories_by_ids(db, payload.category_ids)

    db.add(news)
    db.commit()
    db.refresh(news)
    cache = get_redis_client()
    invalidate_news_projections(cache, news.news_id, news.organization_id)

    # Generate embedding for RAG when news is published
    if normalized_status.lower() == "published":
        try:
            update_news_embedding(db, news.news_id)
        except Exception as e:
            print(f"⚠️ Failed to generate embedding for news #{news.news_id}: {e}")

    like_count_dict, comment_count_dict, org_followers_dict = fetch_news_metrics(db, [news])
    return serialize_news(
        news,
        like_count_dict.get(news.news_id, 0),
        comment_count_dict.get(news.news_id, 0),
        org_followers_dict.get(news.organization_id, 0) if news.organization_id else 0,
    )


@router.put("/{news_id}", response_model=NewsResponse)
async def update_news(news_id: int, payload: NewsUpdateRequest, current_user: user_dependency, db: db_dependency):
    require_journalist_or_admin(current_user)
    news = get_news_or_404(db, news_id)

    if current_user.get("role") == "Journalist" and news.organization_id != current_user.get("organization_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update news in your own organization")

    normalized_status = payload.status.strip() or "Draft"

    news.title = payload.title.strip()
    news.content = payload.content.strip()
    news.status = normalized_status
    news.published_at = datetime.now(timezone.utc) if normalized_status.lower() == "published" else news.published_at
    news.categories = get_categories_by_ids(db, payload.category_ids)

    db.commit()
    db.refresh(news)
    cache = get_redis_client()
    invalidate_news_projections(cache, news_id, news.organization_id)

    # Generate/update embedding for RAG when news is published
    if normalized_status.lower() == "published":
        try:
            update_news_embedding(db, news_id)
        except Exception as e:
            print(f"⚠️ Failed to generate embedding for news #{news_id}: {e}")

    like_count_dict, comment_count_dict, org_followers_dict = fetch_news_metrics(db, [news])
    return serialize_news(
        news,
        like_count_dict.get(news.news_id, 0),
        comment_count_dict.get(news.news_id, 0),
        org_followers_dict.get(news.organization_id, 0) if news.organization_id else 0,
    )


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(news_id: int, current_user: user_dependency, db: db_dependency):
    require_journalist_or_admin(current_user)
    news = get_news_or_404(db, news_id)

    if current_user.get("role") == "Journalist" and news.organization_id != current_user.get("organization_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete news in your own organization")

    org_id = news.organization_id
    db.delete(news)
    db.commit()
    cache = get_redis_client()
    invalidate_news_projections(cache, news_id, org_id)
    return None


@router.post("/{news_id}/like", response_model=NewsLikeStateResponse)
async def like_news(news_id: int, current_user: user_dependency, db: db_dependency):
    news_meta = get_news_metadata(db, news_id)
    if news_meta["status"].lower() != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only published news can be interacted with")

    user_id = current_user.get("id")
    event = create_interaction_event("like", user_id=user_id, news_id=news_id)
    cache = get_redis_client()

    if publish_interaction_event(event):
        like_count = cache_get_int(cache, redis_key_news_like_count(news_id))
        if like_count is None:
            like_count = get_db_news_like_count(db, news_id)
            prime_news_projection_cache(cache, news_id, like_count=like_count)
        return NewsLikeStateResponse(news_id=news_id, liked=True, like_count=like_count)

    existing_like = db.query(Like).filter(Like.news_id == news_id, Like.user_id == user_id).first()
    if not existing_like:
        db.add(Like(news_id=news_id, user_id=user_id))
        db.commit()

    like_count = get_db_news_like_count(db, news_id)
    refresh_news_projection_cache(db, cache, news_id, news_meta["organization_id"])
    invalidate_news_projections(cache, news_id, news_meta["organization_id"])
    return NewsLikeStateResponse(news_id=news_id, liked=True, like_count=like_count)


@router.delete("/{news_id}/like", response_model=NewsLikeStateResponse)
async def unlike_news(news_id: int, current_user: user_dependency, db: db_dependency):
    news_meta = get_news_metadata(db, news_id)
    if news_meta["status"].lower() != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only published news can be interacted with")

    user_id = current_user.get("id")
    event = create_interaction_event("unlike", user_id=user_id, news_id=news_id)
    cache = get_redis_client()

    if publish_interaction_event(event):
        like_count = cache_get_int(cache, redis_key_news_like_count(news_id))
        if like_count is None:
            like_count = get_db_news_like_count(db, news_id)
            prime_news_projection_cache(cache, news_id, like_count=like_count)
        return NewsLikeStateResponse(news_id=news_id, liked=False, like_count=like_count)

    existing_like = db.query(Like).filter(Like.news_id == news_id, Like.user_id == user_id).first()
    if existing_like:
        db.delete(existing_like)
        db.commit()

    like_count = get_db_news_like_count(db, news_id)
    refresh_news_projection_cache(db, cache, news_id, news_meta["organization_id"])
    invalidate_news_projections(cache, news_id, news_meta["organization_id"])
    return NewsLikeStateResponse(news_id=news_id, liked=False, like_count=like_count)


@router.get("/{news_id}/comments", response_model=list[NewsCommentResponse])
async def list_news_comments(news_id: int, db: db_dependency):
    news_meta = get_news_metadata(db, news_id)
    if news_meta["status"].lower() != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only published news can be interacted with")

    cache = get_redis_client()
    cached_comments = cache_get_json(cache, redis_key_news_comments(news_id))
    if cached_comments is not None:
        return [NewsCommentResponse(**comment) for comment in cached_comments]

    comments = get_db_news_comments(db, news_id)
    cache_replace_comments(cache, news_id, comments)
    return [NewsCommentResponse(**comment) for comment in comments]


@router.post("/{news_id}/comments", response_model=NewsCommentResponse, status_code=status.HTTP_201_CREATED)
async def create_news_comment(news_id: int, payload: NewsCommentRequest, current_user: user_dependency, db: db_dependency):
    news_meta = get_news_metadata(db, news_id)
    if news_meta["status"].lower() != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only published news can be interacted with")

    comment_content = payload.content.strip()
    if not comment_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment content is required")

    user_id = current_user.get("id")
    user_email = current_user.get("username", "Unknown")
    temporary_comment_id = create_temporary_comment_id()
    event = create_interaction_event(
        "comment",
        user_id=user_id,
        news_id=news_id,
        content=comment_content,
        user_email=user_email,
    )
    event["comment_id"] = temporary_comment_id
    cache = get_redis_client()

    if publish_interaction_event(event):
        created_at = datetime.now(timezone.utc)
        response = NewsCommentResponse(
            comment_id=temporary_comment_id,
            user_id=user_id,
            user_email=user_email,
            content=comment_content,
            created_at=created_at,
        )
        cache_append_comment(cache, news_id, response.model_dump())
        return response

    comment = Comment(news_id=news_id, user_id=user_id, content=comment_content)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    hydrated_comment = db.query(Comment).options(joinedload(Comment.user)).filter(Comment.comment_id == comment.comment_id).first()
    serialized_comment = serialize_comment(hydrated_comment)
    cache_append_comment(cache, news_id, serialized_comment.model_dump())
    refresh_news_projection_cache(db, cache, news_id, news_meta["organization_id"])
    return serialized_comment
