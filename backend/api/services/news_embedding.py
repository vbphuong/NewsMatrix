"""
Service for generating and managing embeddings for news articles.

When a journalist publishes or updates a news article, this service
generates a vector embedding from the article's title and content,
enabling the RAG chatbot to search and answer questions about news.
"""

import os

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session

from api.models import News

load_dotenv()

_openai_key = os.getenv("OPENAI_API_KEY")
_embedding_model = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=_openai_key)


def _build_news_text(title: str, content: str) -> str:
    """Combine title and content into a single string for embedding."""
    return f"Title: {title}\n\n{content}"


def generate_news_embedding(title: str, content: str) -> list[float]:
    """Generate a 1536-dim embedding vector from a news article's title and content."""
    text = _build_news_text(title, content)
    return _embedding_model.embed_query(text)


def update_news_embedding(db: Session, news_id: int) -> None:
    """Load a news article from the database, generate its embedding, and persist it."""
    news = db.query(News).filter(News.news_id == news_id).first()
    if news is None:
        return

    embedding = generate_news_embedding(news.title, news.content)
    news.embedding = embedding
    db.commit()
    print(f"✅ Embedding generated for news article #{news_id}: \"{news.title[:60]}\"")


def backfill_news_embeddings(db: Session) -> dict:
    """
    Generate embeddings for all published news articles that don't have one yet.
    Returns a summary dict with counts.
    """
    news_without_embedding = (
        db.query(News)
        .filter(News.status == "Published", News.embedding.is_(None))
        .all()
    )

    total = len(news_without_embedding)
    if total == 0:
        return {"total": 0, "processed": 0, "message": "All published news already have embeddings."}

    processed = 0
    for news in news_without_embedding:
        try:
            embedding = generate_news_embedding(news.title, news.content)
            news.embedding = embedding
            processed += 1
            print(f"  ✅ [{processed}/{total}] news #{news.news_id}: \"{news.title[:50]}\"")
        except Exception as e:
            print(f"  ❌ Failed news #{news.news_id}: {e}")

    db.commit()
    return {
        "total": total,
        "processed": processed,
        "message": f"Generated embeddings for {processed}/{total} published news articles.",
    }
