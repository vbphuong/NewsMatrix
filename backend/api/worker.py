from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv

from api.database import SessionLocal
from api.models import News
from api.services.scalability import (
    RABBITMQ_QUEUE_NAME,
    apply_interaction_event,
    cache_get_json,
    cache_replace_comments,
    refresh_news_projection_cache,
    refresh_user_interaction_cache,
    get_redis_client,
    redis_key_news_comments,
)

load_dotenv(override=True)

try:
    import pika
except ImportError:  # pragma: no cover - optional dependency
    pika = None


def run_worker() -> None:
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url or pika is None:
        raise RuntimeError("RabbitMQ is not configured. Set RABBITMQ_URL and install pika.")

    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=25)

    cache = get_redis_client()

    def handle_message(ch, method, properties, body):
        db = SessionLocal()
        try:
            event = json.loads(body.decode("utf-8"))
            result = apply_interaction_event(db, event)

            if result.get("applied"):
                if event.get("news_id") is not None:
                    news_id = event.get("news_id")
                    news = db.query(News).filter(News.news_id == news_id).first()
                    organization_id = news.organization_id if news else None
                    refresh_news_projection_cache(db, cache, news_id, organization_id)
                    if event.get("user_id") is not None:
                        refresh_user_interaction_cache(db, cache, event.get("user_id"))

            if event.get("event_type") == "comment" and result and cache is not None and result.get("applied"):
                news_id = result.get("news_id")
                if news_id is not None:
                    comments = cache_get_json(cache, redis_key_news_comments(news_id)) or []
                    temporary_comment_id = event.get("comment_id")
                    if temporary_comment_id is not None:
                        comments = [comment for comment in comments if comment.get("comment_id") != temporary_comment_id]
                    comments.append(
                        {
                            "comment_id": result.get("comment_id"),
                            "user_id": event.get("user_id"),
                            "user_email": event.get("user_email") or "Unknown",
                            "content": result.get("content") or event.get("content") or "",
                            "created_at": result.get("created_at"),
                        }
                    )
                    cache_replace_comments(cache, news_id, comments)

            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            db.rollback()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        finally:
            db.close()

    channel.basic_consume(queue=RABBITMQ_QUEUE_NAME, on_message_callback=handle_message)
    try:
        print(f"[worker] Waiting for events on queue '{RABBITMQ_QUEUE_NAME}'...")
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    while True:
        try:
            run_worker()
            break
        except Exception as exc:
            print(f"[worker] Worker stopped: {exc}")
            time.sleep(2)
