from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import DB_PATH


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    localized_name: Mapped[str] = mapped_column(String(200), default="")
    biography_zh: Mapped[str] = mapped_column(Text, default="")
    nationality: Mapped[str] = mapped_column(String(120), default="")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cover_theme: Mapped[str] = mapped_column(String(80), default="")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("year", "month", name="uq_issue_ym"),)


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    original_title: Mapped[str] = mapped_column(String(400), default="", index=True)
    chinese_title: Mapped[str] = mapped_column(String(400), default="")
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("authors.id"), nullable=True)
    language_code: Mapped[str] = mapped_column(String(8), default="", index=True)
    language_name: Mapped[str] = mapped_column(String(40), default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    publication_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True, index=True)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    isbn10: Mapped[str] = mapped_column(String(16), default="", index=True)
    isbn13: Mapped[str] = mapped_column(String(20), default="", index=True)
    primary_genre: Mapped[str] = mapped_column(String(40), default="其他", index=True)
    genres: Mapped[str] = mapped_column(String(400), default="")
    tags: Mapped[str] = mapped_column(String(400), default="")
    short_description_zh: Mapped[str] = mapped_column(Text, default="")
    full_description_zh: Mapped[str] = mapped_column(Text, default="")
    recommendation_zh: Mapped[str] = mapped_column(Text, default="")
    audience_zh: Mapped[str] = mapped_column(Text, default="")
    reading_mood_zh: Mapped[str] = mapped_column(String(200), default="")
    editor_quote_zh: Mapped[str] = mapped_column(String(200), default="")
    cover_image: Mapped[str] = mapped_column(String(300), default="/covers/placeholder.svg")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issues.id"), nullable=True)
    featured_rank: Mapped[int] = mapped_column(Integer, default=0)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_name: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str] = mapped_column(String(400), default="")
    selection_reason: Mapped[str] = mapped_column(Text, default="")
    source_file: Mapped[str] = mapped_column(String(200), default="")
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    author: Mapped[Optional["Author"]] = relationship()
    issue: Mapped[Optional["Issue"]] = relationship()

    def genre_list(self):
        return [g for g in (self.genres or self.primary_genre).split(",") if g]

    def tag_list(self):
        return [t for t in (self.tags or "").split(",") if t]


class Rating(Base):
    __tablename__ = "ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("book_id", "visitor_id", name="uq_rating_book_visitor"),)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    nickname: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("comments.id"), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CommentLike(Base):
    __tablename__ = "comment_likes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id"), index=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("comment_id", "visitor_id", name="uq_like_comment_visitor"),)


class CommentReport(Base):
    __tablename__ = "comment_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id"), index=True)
    visitor_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BookSubmission(Base):
    __tablename__ = "book_submissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, default="")
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    nickname: Mapped[str] = mapped_column(String(40), default="")
    contact_email: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(160), default="")
    original_title: Mapped[str] = mapped_column(String(400), default="")
    chinese_title: Mapped[str] = mapped_column(String(400), default="")
    chinese_title_is_temporary: Mapped[bool] = mapped_column(Boolean, default=False)
    authors: Mapped[str] = mapped_column(String(300), default="")
    cover_url: Mapped[str] = mapped_column(String(400), default="")
    introduction: Mapped[str] = mapped_column(Text, default="")
    recommendation_reason: Mapped[str] = mapped_column(Text, default="")
    suitable_readers: Mapped[str] = mapped_column(Text, default="")
    author_biography: Mapped[str] = mapped_column(Text, default="")
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    publication_date: Mapped[str] = mapped_column(String(20), default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    isbn: Mapped[str] = mapped_column(String(32), default="", index=True)
    language_code: Mapped[str] = mapped_column(String(16), default="")
    language_other: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(80), default="")
    genres: Mapped[str] = mapped_column(String(400), default="")
    tags: Mapped[str] = mapped_column(String(240), default="")
    information_source: Mapped[str] = mapped_column(String(80), default="")
    information_source_note: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    assigned_editor: Mapped[str] = mapped_column(String(80), default="")
    public_feedback: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    checklist: Mapped[str] = mapped_column(Text, default="")
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completeness: Mapped[int] = mapped_column(Integer, default=0)
    approved_book_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    candidate_pool: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SubmissionAuditLog(Base):
    __tablename__ = "submission_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("book_submissions.id"), index=True)
    operator_id: Mapped[str] = mapped_column(String(80), default="")
    action: Mapped[str] = mapped_column(String(40), index=True)
    previous_status: Mapped[str] = mapped_column(String(24), default="")
    next_status: Mapped[str] = mapped_column(String(24), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SiteNotice(Base):
    __tablename__ = "site_notices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    submission_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(40), default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        Base.metadata.create_all(engine)
    except OperationalError as exc:
        if "already exists" not in str(exc):
            raise


Index("ix_books_search", Book.original_title, Book.chinese_title, Book.isbn13)
