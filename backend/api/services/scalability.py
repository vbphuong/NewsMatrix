from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from dotenv import load_dotenv

from database import SessionLocal
from models import Comment, Follow, Like, News, Organization

load_dotenv(override=True)

try:
    import pika
except ImportError:  # pragma: no cover - optional dependency
    pika = None

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "120"))
COMMENT_CACHE_TTL_SECONDS = int(os.getenv("COMMENT_CACHE_TTL_SECONDS", "300"))
RABBITMQ_QUEUE_NAME = os.getenv("RABBITMQ_QUEUE_NAME", "news_interactions")


@dataclass(slots=True)
class InteractionEvent:
    event_type: str
    user_id: int
    news_id: Optional[int] = None
    organization_id: Optional[int] = None
    content: Optional[str] = None
    user_email: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "user_id": self.user_id,
            "news_id": self.news_id,
            "organization_id": self.organization_id,
            "content": self.content,
            "user_email": self.user_email,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }


@lru_cache(maxsize=1)
def get_redis_client():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url or redis is None:
        return None

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def redis_key_news_like_count(news_id: int) -> str:
    return f"news:{news_id}:like_count"


def redis_key_news_comment_count(news_id: int) -> str:
    return f"news:{news_id}:comment_count"


def redis_key_org_followers_count(organization_id: int) -> str:
    return f"organization:{organization_id}:followers_count"


def redis_key_user_liked_news(user_id: int) -> str:
    return f"user:{user_id}:liked_news_ids"


def redis_key_user_followed_orgs(user_id: int) -> str:
    return f"user:{user_id}:followed_organization_ids"


def redis_key_news_comments(news_id: int) -> str:
    return f"news:{news_id}:comments"


def redis_key_news_detail(news_id: int) -> str:
    return f"news:{news_id}:detail"


def redis_key_news_list() -> str:
    return "news:list"


def redis_key_organization_detail(organization_id: int) -> str:
    return f"organization:{organization_id}:detail"


def redis_key_organization_list() -> str:
    return "organization:list"


def cache_get_int(cache, key: str) -> Optional[int]:
    if cache is None:
        return None
    value = cache.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def cache_set_int(cache, key: str, value: int, ttl: int = CACHE_TTL_SECONDS) -> None:
    if cache is None:
        return
    cache.set(key, int(value), ex=ttl)


def cache_increment_int(cache, key: str, amount: int = 1, ttl: int = CACHE_TTL_SECONDS) -> None:
    if cache is None:
        return
    current = cache_get_int(cache, key)
    if current is None:
        current = 0
    cache.set(key, max(current + amount, 0), ex=ttl)


def cache_decrement_int(cache, key: str, amount: int = 1, ttl: int = CACHE_TTL_SECONDS) -> None:
    cache_increment_int(cache, key, -amount, ttl=ttl)


def cache_get_json(cache, key: str) -> Any:
    if cache is None:
        return None
    payload = cache.get(key)
    if payload is None:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def cache_set_json(cache, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> None:
    if cache is None:
        return
    cache.set(key, json.dumps(value, default=str), ex=ttl)


def cache_delete_keys(cache, *keys: str) -> None:
    if cache is None or not keys:
        return
    cache.delete(*keys)


def cache_replace_comments(cache, news_id: int, comments: list[dict[str, Any]], ttl: int = COMMENT_CACHE_TTL_SECONDS) -> None:
    cache_set_json(cache, redis_key_news_comments(news_id), comments, ttl=ttl)


def cache_append_comment(cache, news_id: int, comment: dict[str, Any], ttl: int = COMMENT_CACHE_TTL_SECONDS) -> None:
    if cache is None:
        return
    comments = cache_get_json(cache, redis_key_news_comments(news_id)) or []
    comments.append(comment)
    cache_replace_comments(cache, news_id, comments, ttl=ttl)


def prime_news_projection_cache(
    cache,
    news_id: int,
    like_count: Optional[int] = None,
    comment_count: Optional[int] = None,
) -> None:
    if cache is None:
        return
    if like_count is not None:
        cache_set_int(cache, redis_key_news_like_count(news_id), like_count)
    if comment_count is not None:
        cache_set_int(cache, redis_key_news_comment_count(news_id), comment_count)


def prime_organization_projection_cache(cache, organization_id: int, followers_count: int) -> None:
    cache_set_int(cache, redis_key_org_followers_count(organization_id), followers_count)


def invalidate_news_projections(cache, news_id: int, organization_id: Optional[int] = None) -> None:
    if cache is None:
        return
    keys = [
        redis_key_news_detail(news_id),
        redis_key_news_comments(news_id),
        redis_key_news_list(),
    ]
    if organization_id is not None:
        keys.append(redis_key_organization_detail(organization_id))
        keys.append(redis_key_organization_list())
    cache_delete_keys(cache, *keys)


def invalidate_organization_projections(cache, organization_id: int) -> None:
    if cache is None:
        return
    cache_delete_keys(
        cache,
        redis_key_organization_detail(organization_id),
        redis_key_organization_list(),
        redis_key_news_list(),
    )


def invalidate_user_interaction_projections(cache, user_id: int) -> None:
    if cache is None:
        return
    cache_delete_keys(
        cache,
        redis_key_user_liked_news(user_id),
        redis_key_user_followed_orgs(user_id),
    )


def project_event_to_cache(cache, event: dict[str, Any]) -> None:
    if cache is None:
        return

    event_type = event.get("event_type")
    user_id = event.get("user_id")
    news_id = event.get("news_id")
    organization_id = event.get("organization_id")

    if event_type == "like" and news_id is not None and user_id is not None:
        cache_increment_int(cache, redis_key_news_like_count(news_id))
        cache.sadd(redis_key_user_liked_news(user_id), str(news_id))
        cache.expire(redis_key_user_liked_news(user_id), CACHE_TTL_SECONDS)
        invalidate_news_projections(cache, news_id)
    elif event_type == "unlike" and news_id is not None and user_id is not None:
        cache_decrement_int(cache, redis_key_news_like_count(news_id))
        cache.srem(redis_key_user_liked_news(user_id), str(news_id))
        cache.expire(redis_key_user_liked_news(user_id), CACHE_TTL_SECONDS)
        invalidate_news_projections(cache, news_id)
    elif event_type == "comment" and news_id is not None:
        cache_increment_int(cache, redis_key_news_comment_count(news_id))
        cache_delete_keys(cache, redis_key_news_detail(news_id), redis_key_news_list())
    elif event_type == "follow" and organization_id is not None and user_id is not None:
        cache_increment_int(cache, redis_key_org_followers_count(organization_id))
        cache.sadd(redis_key_user_followed_orgs(user_id), str(organization_id))
        cache.expire(redis_key_user_followed_orgs(user_id), CACHE_TTL_SECONDS)
        invalidate_organization_projections(cache, organization_id)
    elif event_type == "unfollow" and organization_id is not None and user_id is not None:
        cache_decrement_int(cache, redis_key_org_followers_count(organization_id))
        cache.srem(redis_key_user_followed_orgs(user_id), str(organization_id))
        cache.expire(redis_key_user_followed_orgs(user_id), CACHE_TTL_SECONDS)
        invalidate_organization_projections(cache, organization_id)


def publish_interaction_event(event: dict[str, Any]) -> bool:
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url or pika is None:
        return False

    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        try:
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE_NAME, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=RABBITMQ_QUEUE_NAME,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            return True
        finally:
            connection.close()
    except Exception:
        return False


def create_interaction_event(
    event_type: str,
    user_id: int,
    news_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    content: Optional[str] = None,
    user_email: Optional[str] = None,
) -> dict[str, Any]:
    return InteractionEvent(
        event_type=event_type,
        user_id=user_id,
        news_id=news_id,
        organization_id=organization_id,
        content=content,
        user_email=user_email,
    ).to_dict()


def create_temporary_comment_id() -> int:
    return -int(time.time_ns() % 10**12)


def apply_interaction_event(db, event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("event_type")
    user_id = event.get("user_id")
    news_id = event.get("news_id")
    organization_id = event.get("organization_id")
    content = event.get("content")

    if event_type == "like" and news_id is not None and user_id is not None:
        existing_like = db.query(Like).filter(Like.news_id == news_id, Like.user_id == user_id).first()
        if not existing_like:
            db.add(Like(news_id=news_id, user_id=user_id))
            db.commit()
            return {"applied": True, "event_type": event_type, "news_id": news_id, "user_id": user_id}
        return {"applied": False, "event_type": event_type, "news_id": news_id, "user_id": user_id}

    if event_type == "unlike" and news_id is not None and user_id is not None:
        existing_like = db.query(Like).filter(Like.news_id == news_id, Like.user_id == user_id).first()
        if existing_like:
            db.delete(existing_like)
            db.commit()
            return {"applied": True, "event_type": event_type, "news_id": news_id, "user_id": user_id}
        return {"applied": False, "event_type": event_type, "news_id": news_id, "user_id": user_id}

    if event_type == "follow" and organization_id is not None and user_id is not None:
        existing_follow = (
            db.query(Follow)
            .filter(Follow.organization_id == organization_id, Follow.user_id == user_id)
            .first()
        )
        if not existing_follow:
            db.add(Follow(organization_id=organization_id, user_id=user_id))
            db.commit()
            return {"applied": True, "event_type": event_type, "organization_id": organization_id, "user_id": user_id}
        return {"applied": False, "event_type": event_type, "organization_id": organization_id, "user_id": user_id}

    if event_type == "unfollow" and organization_id is not None and user_id is not None:
        existing_follow = (
            db.query(Follow)
            .filter(Follow.organization_id == organization_id, Follow.user_id == user_id)
            .first()
        )
        if existing_follow:
            db.delete(existing_follow)
            db.commit()
            return {"applied": True, "event_type": event_type, "organization_id": organization_id, "user_id": user_id}
        return {"applied": False, "event_type": event_type, "organization_id": organization_id, "user_id": user_id}

    if event_type == "comment" and news_id is not None and user_id is not None:
        comment = Comment(news_id=news_id, user_id=user_id, content=content or "")
        db.add(comment)
        db.commit()
        db.refresh(comment)
        return {
            "applied": True,
            "comment_id": comment.comment_id,
            "user_id": comment.user_id,
            "news_id": comment.news_id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
        }

    return {"applied": False}


def refresh_news_projection_cache(db, cache, news_id: int, organization_id: Optional[int] = None) -> None:
    like_count = get_db_news_like_count(db, news_id)
    comment_count = get_db_news_comment_count(db, news_id)
    prime_news_projection_cache(cache, news_id, like_count=like_count, comment_count=comment_count)
    if organization_id is not None:
        organization_followers_count = get_db_organization_followers_count(db, organization_id)
        prime_organization_projection_cache(cache, organization_id, organization_followers_count)


def refresh_user_interaction_cache(db, cache, user_id: int) -> None:
    prime_cached_id_set(cache, redis_key_user_liked_news(user_id), get_db_news_like_ids(db, user_id))
    prime_cached_id_set(cache, redis_key_user_followed_orgs(user_id), get_db_followed_organization_ids(db, user_id))


def build_comment_response(
    comment_id: int,
    user_id: int,
    user_email: str,
    content: str,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "comment_id": comment_id,
        "user_id": user_id,
        "user_email": user_email,
        "content": content,
        "created_at": created_at,
    }


def get_cache_set_members(cache, key: str) -> list[int]:
    if cache is None:
        return []
    members = cache.smembers(key)
    if not members:
        return []
    result: list[int] = []
    for member in members:
        try:
            result.append(int(member))
        except (TypeError, ValueError):
            continue
    return result


def prime_cached_id_set(cache, key: str, values: list[int], ttl: int = CACHE_TTL_SECONDS) -> None:
    if cache is None:
        return
    if not values:
        cache.delete(key)
        return
    cache.delete(key)
    cache.sadd(key, *[str(value) for value in values])
    cache.expire(key, ttl)


def get_db_news_like_ids(db, user_id: int) -> list[int]:
    return [like.news_id for like in db.query(Like).filter(Like.user_id == user_id).all()]


def get_db_followed_organization_ids(db, user_id: int) -> list[int]:
    return [follow.organization_id for follow in db.query(Follow).filter(Follow.user_id == user_id).all()]


def get_db_news_comment_count(db, news_id: int) -> int:
    return db.query(Comment).filter(Comment.news_id == news_id).count()


def get_db_news_like_count(db, news_id: int) -> int:
    return db.query(Like).filter(Like.news_id == news_id).count()


def get_db_organization_followers_count(db, organization_id: int) -> int:
    return db.query(Follow).filter(Follow.organization_id == organization_id).count()


def get_db_news_comments(db, news_id: int) -> list[dict[str, Any]]:
    comments = (
        db.query(Comment)
        .join(Comment.user)
        .filter(Comment.news_id == news_id)
        .order_by(Comment.created_at.asc(), Comment.comment_id.asc())
        .all()
    )
    return [
        {
            "comment_id": comment.comment_id,
            "user_id": comment.user_id,
            "user_email": comment.user.email if comment.user else "Unknown",
            "content": comment.content,
            "created_at": comment.created_at,
        }
        for comment in comments
    ]


def get_db_comment_by_id(db, comment_id: int) -> Optional[Comment]:
    return db.query(Comment).filter(Comment.comment_id == comment_id).first()


def get_db_news_summary(db, news_id: int) -> Optional[News]:
    return db.query(News).filter(News.news_id == news_id).first()


def get_db_organization_summary(db, organization_id: int) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.organization_id == organization_id).first()
