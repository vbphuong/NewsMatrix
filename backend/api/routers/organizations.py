from datetime import datetime, timezone
from math import ceil
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from api.deps import db_dependency, user_dependency
from api.models import Follow, Organization, Role, User
from api.services.scalability import (
    cache_get_int,
    create_interaction_event,
    get_cache_set_members,
    get_db_followed_organization_ids,
    get_db_organization_followers_count,
    get_redis_client,
    invalidate_organization_projections,
    prime_cached_id_set,
    prime_organization_projection_cache,
    publish_interaction_event,
    redis_key_org_followers_count,
    redis_key_user_followed_orgs,
)

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
)


class OrganizationRequest(BaseModel):
    name: str
    description: Optional[str] = None
    daily_post_limit: int = 5
    current_edit_limit: int = 0


class OrganizationResponse(BaseModel):
    organization_id: int
    name: str
    description: Optional[str] = None
    daily_post_limit: int
    current_edit_limit: int
    followers_count: int


class JournalistResponse(BaseModel):
    user_id: int
    email: str
    organization_id: Optional[int] = None


class JournalistPaginationResponse(BaseModel):
    items: list[JournalistResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class JournalistAddRequest(BaseModel):
    journalist_id: int


class OrganizationFollowStateResponse(BaseModel):
    organization_id: int
    following: bool
    followers_count: int


class OrganizationFollowingResponse(BaseModel):
    organization_ids: list[int]


def require_admin(current_user: user_dependency) -> None:
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def get_organization_or_404(db, organization_id: int) -> Organization:
    organization = (
        db.query(Organization)
        .filter(Organization.organization_id == organization_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


def get_journalist_or_404(db, journalist_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.user_id == journalist_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role_name = user.role.role_name if user.role else None
    if role_name != "Journalist":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only journalists can be assigned")

    return user


def serialize_organization(org: Organization, followers_count: int) -> OrganizationResponse:
    return OrganizationResponse(
        organization_id=org.organization_id,
        name=org.name,
        description=org.description,
        daily_post_limit=org.daily_post_limit,
        current_edit_limit=org.current_edit_limit,
        followers_count=followers_count,
    )


def fetch_organization_followers_counts(db, organizations: list[Organization]) -> dict[int, int]:
    cache = get_redis_client()
    organization_ids = [organization.organization_id for organization in organizations]
    followers_counts: dict[int, int] = {}

    missing_organization_ids: list[int] = []
    for organization_id in organization_ids:
        cached_followers_count = cache_get_int(cache, redis_key_org_followers_count(organization_id))
        if cached_followers_count is None:
            missing_organization_ids.append(organization_id)
        else:
            followers_counts[organization_id] = cached_followers_count

    if missing_organization_ids:
        follower_rows = (
            db.query(Follow.organization_id, func.count(Follow.follow_id).label("followers_count"))
            .filter(Follow.organization_id.in_(missing_organization_ids))
            .group_by(Follow.organization_id)
            .all()
        )
        follower_map = {organization_id: count for organization_id, count in follower_rows}
        for organization_id in missing_organization_ids:
            followers_counts[organization_id] = follower_map.get(organization_id, 0)
            prime_organization_projection_cache(cache, organization_id, followers_counts[organization_id])

    return followers_counts


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(db: db_dependency):
    organizations = (
        db.query(Organization)
        .order_by(Organization.organization_id.desc())
        .all()
    )
    followers_counts = fetch_organization_followers_counts(db, organizations)
    return [serialize_organization(org, followers_counts.get(org.organization_id, 0)) for org in organizations]


@router.get("/following/me", response_model=OrganizationFollowingResponse)
async def list_following_organizations(current_user: user_dependency, db: db_dependency):
    user_id = current_user.get("id")
    cache = get_redis_client()
    organization_ids = get_cache_set_members(cache, redis_key_user_followed_orgs(user_id))
    if not organization_ids:
        organization_ids = get_db_followed_organization_ids(db, user_id)
        prime_cached_id_set(cache, redis_key_user_followed_orgs(user_id), organization_ids)
    return OrganizationFollowingResponse(organization_ids=organization_ids)


@router.get("/journalists/pool", response_model=list[JournalistResponse])
async def list_journalist_pool(current_user: user_dependency, db: db_dependency):
    require_admin(current_user)

    journalists = (
        db.query(User)
        .join(Role, User.role_id == Role.role_id)
        .filter(Role.role_name == "Journalist")
        .order_by(User.email.asc())
        .all()
    )

    return [
        JournalistResponse(
            user_id=journalist.user_id,
            email=journalist.email,
            organization_id=journalist.organization_id,
        )
        for journalist in journalists
    ]


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(organization_id: int, db: db_dependency):
    organization = get_organization_or_404(db, organization_id)
    followers_count = fetch_organization_followers_counts(db, [organization]).get(organization.organization_id, 0)
    return serialize_organization(organization, followers_count)


@router.get("/{organization_id}/journalists", response_model=JournalistPaginationResponse)
async def get_organization_journalists(
    organization_id: int,
    db: db_dependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=50),
):
    get_organization_or_404(db, organization_id)

    base_query = (
        db.query(User)
        .join(Role, User.role_id == Role.role_id)
        .filter(User.organization_id == organization_id, Role.role_name == "Journalist")
    )

    total = base_query.with_entities(func.count(User.user_id)).scalar() or 0
    total_pages = max(1, ceil(total / page_size)) if total > 0 else 1

    journalists = (
        base_query
        .order_by(User.email.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        JournalistResponse(
            user_id=journalist.user_id,
            email=journalist.email,
            organization_id=journalist.organization_id,
        )
        for journalist in journalists
    ]

    return JournalistPaginationResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(payload: OrganizationRequest, current_user: user_dependency, db: db_dependency):
    require_admin(current_user)

    organization = Organization(
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        daily_post_limit=payload.daily_post_limit,
        current_edit_limit=payload.current_edit_limit,
        updated_at=datetime.now(timezone.utc),
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)
    followers_count = fetch_organization_followers_counts(db, [organization]).get(organization.organization_id, 0)
    return serialize_organization(organization, followers_count)


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: int,
    payload: OrganizationRequest,
    current_user: user_dependency,
    db: db_dependency,
):
    require_admin(current_user)
    organization = get_organization_or_404(db, organization_id)

    organization.name = payload.name.strip()
    organization.description = (payload.description or "").strip() or None
    organization.daily_post_limit = payload.daily_post_limit
    organization.current_edit_limit = payload.current_edit_limit
    organization.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(organization)
    followers_count = fetch_organization_followers_counts(db, [organization]).get(organization.organization_id, 0)
    return serialize_organization(organization, followers_count)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(organization_id: int, current_user: user_dependency, db: db_dependency):
    require_admin(current_user)
    organization = get_organization_or_404(db, organization_id)

    db.delete(organization)
    db.commit()
    return None


@router.post("/{organization_id}/follow", response_model=OrganizationFollowStateResponse)
async def follow_organization(organization_id: int, current_user: user_dependency, db: db_dependency):
    organization = get_organization_or_404(db, organization_id)
    user_id = current_user.get("id")
    event = create_interaction_event("follow", user_id=user_id, organization_id=organization_id)
    cache = get_redis_client()

    if publish_interaction_event(event):
        followers_count = cache_get_int(cache, redis_key_org_followers_count(organization_id))
        if followers_count is None:
            followers_count = get_db_organization_followers_count(db, organization_id)
            prime_organization_projection_cache(cache, organization_id, followers_count)
        return OrganizationFollowStateResponse(
            organization_id=organization.organization_id,
            following=True,
            followers_count=followers_count,
        )

    existing_follow = (
        db.query(Follow)
        .filter(Follow.organization_id == organization_id, Follow.user_id == user_id)
        .first()
    )

    if not existing_follow:
        db.add(Follow(organization_id=organization_id, user_id=user_id))
        db.commit()

    followers_count = get_db_organization_followers_count(db, organization_id)
    prime_organization_projection_cache(cache, organization_id, followers_count)
    invalidate_organization_projections(cache, organization_id)
    return OrganizationFollowStateResponse(
        organization_id=organization.organization_id,
        following=True,
        followers_count=followers_count,
    )


@router.delete("/{organization_id}/follow", response_model=OrganizationFollowStateResponse)
async def unfollow_organization(organization_id: int, current_user: user_dependency, db: db_dependency):
    organization = get_organization_or_404(db, organization_id)
    user_id = current_user.get("id")
    event = create_interaction_event("unfollow", user_id=user_id, organization_id=organization_id)
    cache = get_redis_client()

    if publish_interaction_event(event):
        followers_count = cache_get_int(cache, redis_key_org_followers_count(organization_id))
        if followers_count is None:
            followers_count = get_db_organization_followers_count(db, organization_id)
            prime_organization_projection_cache(cache, organization_id, followers_count)
        return OrganizationFollowStateResponse(
            organization_id=organization.organization_id,
            following=False,
            followers_count=followers_count,
        )

    existing_follow = (
        db.query(Follow)
        .filter(Follow.organization_id == organization_id, Follow.user_id == user_id)
        .first()
    )

    if existing_follow:
        db.delete(existing_follow)
        db.commit()

    followers_count = get_db_organization_followers_count(db, organization_id)
    prime_organization_projection_cache(cache, organization_id, followers_count)
    invalidate_organization_projections(cache, organization_id)
    return OrganizationFollowStateResponse(
        organization_id=organization.organization_id,
        following=False,
        followers_count=followers_count,
    )


@router.post("/{organization_id}/journalists", response_model=JournalistResponse)
async def add_journalist_to_organization(
    organization_id: int,
    payload: JournalistAddRequest,
    current_user: user_dependency,
    db: db_dependency,
):
    require_admin(current_user)
    get_organization_or_404(db, organization_id)
    journalist = get_journalist_or_404(db, payload.journalist_id)

    journalist.organization_id = organization_id
    journalist.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(journalist)

    return JournalistResponse(
        user_id=journalist.user_id,
        email=journalist.email,
        organization_id=journalist.organization_id,
    )


@router.delete("/{organization_id}/journalists/{journalist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_journalist_from_organization(
    organization_id: int,
    journalist_id: int,
    current_user: user_dependency,
    db: db_dependency,
):
    require_admin(current_user)
    get_organization_or_404(db, organization_id)
    journalist = get_journalist_or_404(db, journalist_id)

    if journalist.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Journalist is not in this organization")

    journalist.organization_id = None
    journalist.updated_at = datetime.now(timezone.utc)
    db.commit()
    return None
