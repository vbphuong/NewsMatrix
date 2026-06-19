from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    ForeignKey,
    Table,
    TIMESTAMP,
    UniqueConstraint,
    func
)

from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from api.database import Base


# =========================
# ASSOCIATION TABLES
# =========================

news_categories = Table(
    "news_categories",
    Base.metadata,

    Column(
        "news_id",
        Integer,
        ForeignKey("news.news_id", ondelete="CASCADE"),
        primary_key=True
    ),

    Column(
        "category_id",
        Integer,
        ForeignKey("categories.category_id", ondelete="CASCADE"),
        primary_key=True
    )
)


authors = Table(
    "authors",
    Base.metadata,

    Column(
        "user_id",
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    ),

    Column(
        "news_id",
        Integer,
        ForeignKey("news.news_id", ondelete="CASCADE"),
        primary_key=True
    )
)


# =========================
# ROLE
# =========================

class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True)
    role_name = Column(String(50), unique=True, nullable=False)

    users = relationship("User", back_populates="role")


# =========================
# ORGANIZATION
# =========================

class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False)

    description = Column(Text)

    daily_post_limit = Column(
        Integer,
        nullable=False,
        default=5
    )

    current_edit_limit = Column(
        Integer,
        nullable=False,
        default=5
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    users = relationship(
        "User",
        back_populates="organization"
    )

    news = relationship(
        "News",
        back_populates="organization"
    )

    followers = relationship(
        "Follow",
        back_populates="organization"
    )


# =========================
# USER
# =========================

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)

    email = Column(
        String(255),
        unique=True,
        nullable=False
    )

    password = Column(
        String(255),
        nullable=False
    )

    role_id = Column(
        Integer,
        ForeignKey("roles.role_id")
    )

    organization_id = Column(
        Integer,
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL"
        )
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    role = relationship(
        "Role",
        back_populates="users"
    )

    organization = relationship(
        "Organization",
        back_populates="users"
    )

    authored_news = relationship(
        "News",
        secondary=authors,
        back_populates="authors"
    )

    likes = relationship(
        "Like",
        back_populates="user"
    )

    comments = relationship(
        "Comment",
        back_populates="user"
    )

    follows = relationship(
        "Follow",
        back_populates="user"
    )


# =========================
# NEWS
# =========================

class News(Base):
    __tablename__ = "news"

    news_id = Column(Integer, primary_key=True)

    organization_id = Column(
        Integer,
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    title = Column(
        String(500),
        nullable=False
    )

    content = Column(
        Text,
        nullable=False
    )

    status = Column(
        String(50),
        default="Draft"
    )

    published_at = Column(
        TIMESTAMP(timezone=True)
    )

    view_count = Column(
        Integer,
        default=0
    )

    organization = relationship(
        "Organization",
        back_populates="news"
    )

    authors = relationship(
        "User",
        secondary=authors,
        back_populates="authored_news"
    )

    categories = relationship(
        "Category",
        secondary=news_categories,
        back_populates="news"
    )

    likes = relationship(
        "Like",
        back_populates="news"
    )

    comments = relationship(
        "Comment",
        back_populates="news"
    )


# =========================
# CATEGORY
# =========================

class Category(Base):
    __tablename__ = "categories"

    category_id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String(100),
        unique=True,
        nullable=False
    )

    news = relationship(
        "News",
        secondary=news_categories,
        back_populates="categories"
    )


# =========================
# FOLLOW
# =========================

class Follow(Base):
    __tablename__ = "follows"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_follow"
        ),
    )

    follow_id = Column(
        Integer,
        primary_key=True
    )

    organization_id = Column(
        Integer,
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE"
        )
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE"
        )
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    organization = relationship(
        "Organization",
        back_populates="followers"
    )

    user = relationship(
        "User",
        back_populates="follows"
    )


# =========================
# LIKE
# =========================

class Like(Base):
    __tablename__ = "likes"

    __table_args__ = (
        UniqueConstraint(
            "news_id",
            "user_id",
            name="uq_like"
        ),
    )

    like_id = Column(
        Integer,
        primary_key=True
    )

    news_id = Column(
        Integer,
        ForeignKey(
            "news.news_id",
            ondelete="CASCADE"
        )
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE"
        )
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    news = relationship(
        "News",
        back_populates="likes"
    )

    user = relationship(
        "User",
        back_populates="likes"
    )


# =========================
# COMMENT
# =========================

class Comment(Base):
    __tablename__ = "comments"

    comment_id = Column(
        Integer,
        primary_key=True
    )

    news_id = Column(
        Integer,
        ForeignKey(
            "news.news_id",
            ondelete="CASCADE"
        )
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE"
        )
    )

    content = Column(
        Text,
        nullable=False
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    news = relationship(
        "News",
        back_populates="comments"
    )

    user = relationship(
        "User",
        back_populates="comments"
    )


# =========================
# INBOX
# =========================

class Inbox(Base):
    __tablename__ = "inbox"

    inbox_id = Column(
        Integer,
        primary_key=True
    )

    receiver_id = Column(
        Integer,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE"
        )
    )

    sender_id = Column(
        Integer,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE"
        )
    )

    message = Column(
        Text,
        nullable=False
    )

    status = Column(
        String(50),
        default="Unread"
    )

    sent_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

class Document(Base):
    __tablename__ = "documents"

    document_id = Column(
        BigInteger,
        primary_key=True
    )

    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    total_page = Column(Integer, nullable=False, default=0)
    total_chunk = Column(Integer, nullable=False, default=0)

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(
        BigInteger,
        primary_key=True
    )

    document_id = Column(
        BigInteger,
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False
    )

    embedding = Column(Vector(1536))
    chunk_index = Column(Integer, nullable=False)

    chunk_metadata = Column("metadata", JSONB)

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )
