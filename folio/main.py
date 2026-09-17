from __future__ import annotations

from datetime import datetime
from typing import Optional
import re

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .config import (
    CONTACT_EMAIL, GENRES, ISSUE_MONTH, ISSUE_TITLE, ISSUE_YEAR, LANGS, MONTH_EN, SITE_NAME,
    SITE_TAGLINE, STATIC_DIR, TEMPLATE_DIR, UPLOAD_DIR,
)
from .models import Book, Comment, CommentLike, CommentReport, Issue, Rating, SessionLocal, init_db
from .security import (
    clean_comment, clean_nick, get_or_set_visitor, html_safe, is_admin, rate_limit, require_csrf,
    user_role,
)
from .submissions import register as register_submissions

app = FastAPI(title=SITE_NAME, docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.filters["e"] = html_safe
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/covers", StaticFiles(directory=str(STATIC_DIR / "covers")), name="covers")


@app.exception_handler(StarletteHTTPException)
async def html_http_exception(request: Request, exc: StarletteHTTPException):
    accept = request.headers.get("accept", "")
    wants_json = "application/json" in accept and "text/html" not in accept
    if (
        exc.status_code in (403, 404)
        and not request.url.path.startswith("/api/")
        and not wants_json
    ):
        tpl = "403.html" if exc.status_code == 403 else "404.html"
        title = "没有权限｜FOLIO 折页" if exc.status_code == 403 else "未找到｜FOLIO 折页"
        desc = "没有权限访问这个页面。" if exc.status_code == 403 else "没有找到这本书或这个页面。"
        return templates.TemplateResponse(
            request,
            tpl,
            base_ctx(request, title=title, description=desc),
            status_code=exc.status_code,
        )
    return await http_exception_handler(request, exc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def nav_current(request: Request) -> str:
    path = request.url.path
    if path.startswith("/search"):
        return "search"
    if path.startswith("/archive"):
        return "archive"
    if path.startswith("/recommend") or path.startswith("/my-recommendations"):
        return "submit"
    if path.startswith("/admin"):
        return "admin"
    if path.startswith("/recommendations") or path.startswith("/books") or path.startswith("/explore"):
        return "issue"
    if path == "/":
        return "home"
    return ""


def page_kind(request: Request) -> str:
    path = request.url.path
    if path == "/":
        return "home"
    if path.startswith("/books/"):
        return "book"
    return "inner"


def as_paragraphs(text: str):
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"\n+", raw) if p.strip()]
    if len(parts) == 1 and len(parts[0]) > 90:
        grouped, buf = [], ""
        for chunk in re.split(r"(?<=。)", parts[0]):
            if not chunk.strip():
                continue
            buf += chunk
            if len(buf) >= 72:
                grouped.append(buf.strip())
                buf = ""
        if buf.strip():
            grouped.append(buf.strip())
        return grouped or parts
    return parts


def as_points(text: str):
    raw = (text or "").strip()
    if not raw:
        return []
    for sep in ["。", "；", ";", "、"]:
        if sep in raw:
            return [item.strip("。；;、 ") for item in raw.split(sep) if item.strip("。；;、 ")]
    return [raw]


def dist_rows_from(summary: dict):
    total = summary.get("count") or 0
    rows = []
    for n in [5, 4, 3, 2, 1]:
        count = (summary.get("distribution") or {}).get(n, 0)
        pct = int(round(count / total * 100)) if total else 0
        rows.append({"n": n, "c": count, "pct": pct})
    return rows


def related_books(db: Session, book: Book, limit: int = 6):
    q = db.query(Book).filter(Book.id != book.id)
    if book.author_id:
        q = q.filter(or_(
            Book.language_code == book.language_code,
            Book.primary_genre == book.primary_genre,
            Book.author_id == book.author_id,
        ))
    else:
        q = q.filter(or_(
            Book.language_code == book.language_code,
            Book.primary_genre == book.primary_genre,
        ))
    return q.order_by(Book.is_featured.desc(), Book.featured_rank.asc(), Book.id.asc()).limit(limit).all()


def base_ctx(request: Request, **extra):
    ctx = {
        "request": request,
        "site_name": SITE_NAME,
        "tagline": SITE_TAGLINE,
        "issue_title": ISSUE_TITLE,
        "issue_year": ISSUE_YEAR,
        "issue_month": ISSUE_MONTH,
        "month_en": MONTH_EN.get(ISSUE_MONTH, ""),
        "langs": LANGS,
        "genres": GENRES,
        "email": CONTACT_EMAIL,
        "now": datetime.utcnow(),
        "nav_current": nav_current(request),
        "page_kind": page_kind(request),
        "csrf": getattr(request.state, "csrf", "") or request.cookies.get("folio_csrf") or "",
        "role": user_role(request) if hasattr(request.state, "visitor_id") else "reader",
    }
    ctx.update(extra)
    return ctx


@app.middleware("http")
async def visitor_mw(request: Request, call_next):
    dummy = Response()
    vid = get_or_set_visitor(request, dummy)
    request.state.visitor_id = vid
    response = await call_next(request)
    for header, value in dummy.raw_headers:
        if header.lower() == b"set-cookie":
            response.raw_headers.append((header, value))
    return response


@app.on_event("startup")
def startup():
    init_db()
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "covers").mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def featured_books(db: Session, lang: str | None = None, limit: int | None = None):
    q = db.query(Book).filter(Book.is_featured.is_(True))
    if lang:
        q = q.filter(Book.language_code == lang)
    q = q.order_by(Book.featured_rank.asc(), Book.id.asc())
    if limit:
        q = q.limit(limit)
    return q.all()


def rating_summary(db: Session, book_id: int, visitor_id: str | None = None) -> dict:
    rows = db.query(Rating.score).filter(Rating.book_id == book_id).all()
    scores = [r[0] for r in rows]
    dist = {i: 0 for i in range(1, 6)}
    for s in scores:
        if 1 <= s <= 5:
            dist[s] += 1
    mine = None
    if visitor_id:
        mine_row = db.query(Rating).filter(Rating.book_id == book_id, Rating.visitor_id == visitor_id).one_or_none()
        mine = mine_row.score if mine_row else None
    avg = round(sum(scores) / len(scores), 1) if scores else None
    return {"count": len(scores), "average": avg, "distribution": dist, "mine": mine}


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    english = featured_books(db, "en", 8)
    others = []
    lang_cards = []
    for code, meta in LANGS.items():
        books = featured_books(db, code, 8)
        n = len(books)
        lang_cards.append({"code": code, "meta": meta, "count": n})
        if code != "en":
            others.append({"code": code, "meta": meta, "books": books[:4]})
    genre_counts = (
        db.query(Book.primary_genre, func.count(Book.id))
        .group_by(Book.primary_genre)
        .order_by(func.count(Book.id).desc())
        .all()
    )
    recent = (
        db.query(Comment)
        .filter(Comment.status == "published", Comment.deleted_at.is_(None), Comment.parent_id.is_(None))
        .order_by(Comment.created_at.desc())
        .limit(6)
        .all()
    )
    recent_view = []
    for c in recent:
        book = db.query(Book).filter(Book.id == c.book_id).one_or_none()
        if book:
            recent_view.append({"comment": c, "book": book})
    top_rated = []
    rated = db.query(Rating.book_id, func.avg(Rating.score), func.count(Rating.id)).group_by(Rating.book_id).having(func.count(Rating.id) >= 1).all()
    rated_sorted = sorted(rated, key=lambda x: (-x[1], -x[2]))[:6]
    for book_id, avg, n in rated_sorted:
        b = db.query(Book).filter(Book.id == book_id).one_or_none()
        if b:
            top_rated.append({"book": b, "avg": round(avg, 1), "n": n})
    return templates.TemplateResponse(
        request,
        "home.html",
        base_ctx(
            request,
            title="FOLIO 折页 · 二〇二六年九月号",
            description="以英文原版新书为轴的多语种荐读杂志。本期六种语言各八本2026年新书。",
            english=english,
            others=others,
            lang_cards=lang_cards,
            genre_counts=genre_counts,
            recent_view=recent_view,
            top_rated=top_rated,
        ),
    )


@app.get("/recommendations")
def recommendations_hub(request: Request, genre: str = "", db: Session = Depends(get_db)):
    blocks = []
    for code, meta in LANGS.items():
        books = featured_books(db, code, 8)
        if genre:
            books = [b for b in books if genre == b.primary_genre or genre in (b.genres or "")]
        blocks.append({"code": code, "meta": meta, "books": books})
    return templates.TemplateResponse(
        request,
        "recommendations.html",
        base_ctx(
            request,
            title=f"本期新书推荐 · {ISSUE_TITLE}",
            description="按语言与类型浏览本期经过出版时间核验的原版新书。",
            blocks=blocks,
            active_genre=genre,
        ),
    )


@app.get("/recommendations/{lang}")
def recommendations(lang: str, request: Request, db: Session = Depends(get_db)):
    if lang not in LANGS:
        raise HTTPException(404)
    books = featured_books(db, lang, 8)
    return templates.TemplateResponse(
        request,
        "language.html",
        base_ctx(
            request,
            title=f"{LANGS[lang]['zh']}原版新书 · {ISSUE_TITLE}",
            description=f"本期{LANGS[lang]['zh']}八本经过出版时间核验的2026年原版新书。",
            lang=lang,
            lang_meta=LANGS[lang],
            books=books,
        ),
    )


@app.get("/books/{slug}")
def book_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.slug == slug).one_or_none()
    if not book:
        raise HTTPException(404)
    summary = rating_summary(db, book.id, request.state.visitor_id)
    siblings = []
    if book.is_featured:
        siblings = featured_books(db, book.language_code, 8)
    else:
        siblings = (
            db.query(Book)
            .filter(Book.language_code == book.language_code)
            .order_by(Book.publication_year.desc(), Book.id.asc())
            .limit(24)
            .all()
        )
    idx = next((i for i, b in enumerate(siblings) if b.id == book.id), None)
    prev_b = siblings[idx - 1] if idx not in (None, 0) else None
    next_b = siblings[idx + 1] if idx is not None and idx + 1 < len(siblings) else None
    chinese = book.chinese_title or book.original_title
    host = str(request.base_url).rstrip("/")
    cover = book.cover_image or ""
    og_image = cover if cover.startswith("http") else (host + cover if cover else "")
    return templates.TemplateResponse(
        request,
        "book.html",
        base_ctx(
            request,
            title=f"《{chinese}》书籍介绍与读者评价｜FOLIO 折页",
            description=(book.short_description_zh or book.full_description_zh or f"了解{chinese}的出版信息、内容简介、推荐理由与读者讨论。")[:160],
            book=book,
            summary=summary,
            dist_rows=dist_rows_from(summary),
            prev_b=prev_b,
            next_b=next_b,
            related=related_books(db, book),
            synopsis_paras=as_paragraphs(book.full_description_zh),
            reason_paras=as_paragraphs(book.recommendation_zh),
            audience_points=as_points(book.audience_zh),
            author_paras=as_paragraphs(book.author.biography_zh if book.author else ""),
            title_status=(
                "temporary" if "暂译" in (book.chinese_title or "")
                else "official" if book.chinese_title else "missing"
            ),
            verification_note=(
                "书名、作者、出版社和出版日期已经核对。"
                if book.verification_status == "verified"
                else "部分信息仍待核对。"
                if book.verification_status == "partial"
                else "出版信息待核对。"
            ),
            csrf=getattr(request.state, "csrf", "") or request.cookies.get("folio_csrf") or "",
            visitor_id=request.state.visitor_id,
            og_image=og_image,
            og_type="book",
        ),
    )


@app.get("/explore")
def explore(request: Request, genre: str = "", db: Session = Depends(get_db)):
    q = db.query(Book).filter(Book.is_recommended.is_(True))
    if genre:
        q = q.filter(or_(Book.primary_genre == genre, Book.genres.contains(genre)))
    books = q.order_by(Book.language_code, Book.featured_rank).all()
    return templates.TemplateResponse(
        request,
        "explore.html",
        base_ctx(
            request,
            title=f"按类型浏览 · {genre or '全部'}",
            description="按标准化类型浏览本期推荐图书。",
            books=books,
            active_genre=genre,
        ),
    )


@app.get("/archive")
def archive(
    request: Request,
    year: Optional[str] = Query(default=None),
    month: Optional[str] = Query(default=None),
    lang: str = "",
    genre: str = "",
    db: Session = Depends(get_db),
):
    def to_int(value: Optional[str]):
        raw = (value or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    year_n = to_int(year)
    month_n = to_int(month)
    q = db.query(Book).filter(Book.is_recommended.is_(True), Book.issue_id.isnot(None))
    if year_n or month_n:
        q = q.join(Issue, Book.issue_id == Issue.id)
        if year_n:
            q = q.filter(Issue.year == year_n)
        if month_n:
            q = q.filter(Issue.month == month_n)
    if lang:
        q = q.filter(Book.language_code == lang)
    if genre:
        q = q.filter(or_(Book.primary_genre == genre, Book.genres.contains(genre)))
    books = q.order_by(Book.language_code, Book.featured_rank, Book.id).all()
    if not books:
        if (year_n and year_n != ISSUE_YEAR) or (month_n and month_n != ISSUE_MONTH):
            empty_reason = "尚无该期书单。目前仅发布 2026 年 9 月号。"
        else:
            empty_reason = "这一期还没有可展示的书单。"
    else:
        empty_reason = ""
    return templates.TemplateResponse(
        request,
        "archive.html",
        base_ctx(
            request,
            title="往期推荐",
            description="按年份与月份归档的编辑荐读书单。",
            books=books,
            year=year_n or ISSUE_YEAR,
            month=month_n or ISSUE_MONTH,
            lang=lang,
            genre=genre,
            empty_reason=empty_reason,
            current_only=not (year_n or month_n) or (year_n == ISSUE_YEAR and (not month_n or month_n == ISSUE_MONTH)),
        ),
    )


@app.get("/search")
def search(
    request: Request,
    q: str = "",
    lang: str = "",
    genre: str = "",
    year: Optional[str] = Query(default=None),
    recommended: str = "",
    sort: str = "year",
    db: Session = Depends(get_db),
):
    from .models import Author
    query = db.query(Book)
    keyword = (q or "").strip()
    year_value = None
    raw_year = (year or "").strip()
    if raw_year:
        try:
            year_value = int(raw_year)
        except ValueError:
            year_value = None
    if keyword:
        like = f"%{keyword}%"
        author_ids = [a.id for a in db.query(Author).filter(Author.name.ilike(like)).all()]
        filters = [
            Book.original_title.ilike(like),
            Book.chinese_title.ilike(like),
            Book.isbn13.ilike(like),
            Book.isbn10.ilike(like),
            Book.short_description_zh.ilike(like),
            Book.full_description_zh.ilike(like),
            Book.tags.ilike(like),
            Book.publisher.ilike(like),
        ]
        if author_ids:
            filters.append(Book.author_id.in_(author_ids))
        query = query.filter(or_(*filters))
    if lang:
        query = query.filter(Book.language_code == lang)
    if genre:
        query = query.filter(or_(Book.primary_genre == genre, Book.genres.contains(genre), Book.tags.contains(genre)))
    if year_value:
        query = query.filter(Book.publication_year == year_value)
    if recommended == "1":
        query = query.filter(Book.is_recommended.is_(True))
    elif recommended == "0":
        query = query.filter(Book.is_recommended.is_(False))
    if sort == "title":
        query = query.order_by(Book.original_title.asc())
    elif sort == "rating":
        query = query.outerjoin(Rating).group_by(Book.id).order_by(func.avg(Rating.score).desc(), Book.publication_year.desc())
    else:
        query = query.order_by(Book.publication_year.desc(), Book.original_title.asc())
    need_keyword = not keyword
    if need_keyword:
        books = []
    else:
        books = query.limit(200).all()
    summaries = {b.id: rating_summary(db, b.id) for b in books[:80]}
    empty_message = "请输入书名、作者、ISBN 或关键词后再检索。出版年、语言和类型都是可选项。"
    if keyword and not books:
        empty_message = "没有符合条件的书。试试只保留关键词，或去掉年份等筛选。"
    return templates.TemplateResponse(
        request,
        "search.html",
        base_ctx(
            request,
            title="书籍检索",
            description="检索全部已整理原版书目与正式推荐。",
            books=books,
            q=keyword,
            lang=lang,
            genre=genre,
            year=raw_year,
            recommended=recommended,
            sort=sort,
            summaries=summaries,
            years=list(range(2026, 1999, -1)),
            empty_message=empty_message,
            need_keyword=need_keyword,
        ),
    )


class RatingIn(BaseModel):
    score: int = Field(ge=1, le=5)
    csrf: str = ""


class CommentIn(BaseModel):
    nickname: str
    content: str
    parent_id: Optional[int] = None
    spoiler: bool = False
    csrf: str = ""


@app.get("/api/books/{slug}/ratings")
def api_ratings(slug: str, request: Request, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.slug == slug).one_or_none()
    if not book:
        raise HTTPException(404)
    return rating_summary(db, book.id, request.state.visitor_id)


@app.post("/api/books/{slug}/ratings")
def api_rate(slug: str, payload: RatingIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request, payload.csrf)
    rate_limit(request, "rate")
    book = db.query(Book).filter(Book.slug == slug).one_or_none()
    if not book:
        raise HTTPException(404)
    vid = request.state.visitor_id
    row = db.query(Rating).filter(Rating.book_id == book.id, Rating.visitor_id == vid).one_or_none()
    if row:
        row.score = payload.score
        row.updated_at = datetime.utcnow()
    else:
        db.add(Rating(book_id=book.id, visitor_id=vid, score=payload.score))
    db.commit()
    return rating_summary(db, book.id, vid)


@app.get("/api/books/{slug}/comments")
def api_comments(
    slug: str,
    request: Request,
    sort: str = "newest",
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.slug == slug).one_or_none()
    if not book:
        raise HTTPException(404)
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    q = db.query(Comment).filter(
        Comment.book_id == book.id, Comment.parent_id.is_(None),
        Comment.status == "published", Comment.deleted_at.is_(None),
    )
    if sort == "oldest":
        q = q.order_by(Comment.created_at.asc())
    elif sort == "popular":
        q = q.order_by(Comment.like_count.desc(), Comment.created_at.desc())
    else:
        q = q.order_by(Comment.created_at.desc())
    total = q.count()
    roots = q.offset(offset).limit(limit).all()
    vid = request.state.visitor_id
    liked = {
        x.comment_id for x in db.query(CommentLike).filter(CommentLike.visitor_id == vid).all()
    }

    def unpack(text: str):
        spoiler = (text or "").startswith("[剧透]")
        body = (text or "")[3:].lstrip() if spoiler else (text or "")
        return spoiler, body

    def pack(c: Comment):
        spoiler, body = unpack(c.content)
        replies = (
            db.query(Comment)
            .filter(Comment.parent_id == c.id, Comment.status == "published", Comment.deleted_at.is_(None))
            .order_by(Comment.created_at.asc())
            .all()
        )
        packed_replies = []
        for r in replies:
            rs, rb = unpack(r.content)
            packed_replies.append({
                "id": r.id,
                "nickname": r.nickname,
                "content": rb,
                "containsSpoiler": rs,
                "createdAt": r.created_at.isoformat(),
                "likeCount": r.like_count,
                "liked": r.id in liked,
                "mine": r.visitor_id == vid,
            })
        return {
            "id": c.id,
            "nickname": c.nickname,
            "content": body,
            "containsSpoiler": spoiler,
            "createdAt": c.created_at.isoformat(),
            "likeCount": c.like_count,
            "liked": c.id in liked,
            "mine": c.visitor_id == vid,
            "replies": packed_replies,
        }

    return {"comments": [pack(c) for c in roots], "total": total, "offset": offset, "hasMore": offset + len(roots) < total}


@app.post("/api/books/{slug}/comments")
def api_comment(slug: str, payload: CommentIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request, payload.csrf)
    rate_limit(request, "comment")
    book = db.query(Book).filter(Book.slug == slug).one_or_none()
    if not book:
        raise HTTPException(404)
    nick = clean_nick(payload.nickname)
    content = clean_comment(payload.content)
    if payload.spoiler and not content.startswith("[剧透]"):
        content = "[剧透] " + content
    parent = None
    if payload.parent_id:
        parent = db.query(Comment).filter(Comment.id == payload.parent_id, Comment.book_id == book.id).one_or_none()
        if not parent or parent.parent_id is not None:
            raise HTTPException(400, "只能回复一层评论。")
        if parent.status != "published" or parent.deleted_at:
            raise HTTPException(400, "原评论不可回复。")
    row = Comment(
        book_id=book.id,
        visitor_id=request.state.visitor_id,
        nickname=nick,
        content=content,
        parent_id=parent.id if parent else None,
        status="published",
    )
    db.add(row)
    db.commit()
    return {"ok": True, "id": row.id}


@app.post("/api/comments/{cid}/like")
async def api_like(cid: int, request: Request, db: Session = Depends(get_db)):
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    csrf = body.get("csrf") or request.headers.get("x-csrf-token") or ""
    require_csrf(request, csrf)
    rate_limit(request, "like")
    comment = db.query(Comment).filter(Comment.id == cid, Comment.deleted_at.is_(None)).one_or_none()
    if not comment:
        raise HTTPException(404)
    vid = request.state.visitor_id
    existing = db.query(CommentLike).filter(CommentLike.comment_id == cid, CommentLike.visitor_id == vid).one_or_none()
    if existing:
        db.delete(existing)
        comment.like_count = max(0, comment.like_count - 1)
        liked = False
    else:
        db.add(CommentLike(comment_id=cid, visitor_id=vid))
        comment.like_count += 1
        liked = True
    db.commit()
    return {"liked": liked, "likeCount": comment.like_count}


@app.post("/api/comments/{cid}/like-json")
async def api_like_json(cid: int, request: Request, db: Session = Depends(get_db)):
    return await api_like(cid, request, db)


@app.post("/api/comments/{cid}/delete")
async def api_delete(cid: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    require_csrf(request, body.get("csrf", ""))
    comment = db.query(Comment).filter(Comment.id == cid).one_or_none()
    if not comment:
        raise HTTPException(404)
    if comment.visitor_id != request.state.visitor_id and not is_admin(request):
        raise HTTPException(403, "不能删除他人评论。")
    comment.deleted_at = datetime.utcnow()
    comment.status = "deleted"
    db.commit()
    return {"ok": True}


@app.post("/api/comments/{cid}/edit")
async def api_edit(cid: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    require_csrf(request, body.get("csrf", ""))
    comment = db.query(Comment).filter(Comment.id == cid, Comment.deleted_at.is_(None)).one_or_none()
    if not comment:
        raise HTTPException(404)
    if comment.visitor_id != request.state.visitor_id:
        raise HTTPException(403, "不能编辑他人评论。")
    comment.content = clean_comment(body.get("content") or "")
    comment.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "content": comment.content}


@app.post("/api/comments/{cid}/report")
async def api_report(cid: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    require_csrf(request, body.get("csrf", ""))
    rate_limit(request, "report")
    comment = db.query(Comment).filter(Comment.id == cid).one_or_none()
    if not comment:
        raise HTTPException(404)
    db.add(CommentReport(
        comment_id=cid,
        visitor_id=request.state.visitor_id,
        reason=(body.get("reason") or "")[:200],
    ))
    comment.status = "flagged"
    db.commit()
    return {"ok": True}


@app.post("/api/admin/comments/{cid}/moderate")
async def api_moderate(cid: int, request: Request, db: Session = Depends(get_db)):
    if not is_admin(request):
        raise HTTPException(403)
    body = await request.json()
    comment = db.query(Comment).filter(Comment.id == cid).one_or_none()
    if not comment:
        raise HTTPException(404)
    action = body.get("action")
    if action == "hide":
        comment.status = "hidden"
    elif action == "restore":
        comment.status = "published"
        comment.deleted_at = None
    elif action == "delete":
        comment.status = "deleted"
        comment.deleted_at = datetime.utcnow()
    else:
        raise HTTPException(400)
    db.commit()
    return {"ok": True, "status": comment.status}


@app.get("/api/search/suggest")
def search_suggest(q: str = "", db: Session = Depends(get_db)):
    keyword = (q or "").strip()
    if len(keyword) < 1:
        return {"results": []}
    like = f"%{keyword}%"
    from .models import Author
    author_ids = [a.id for a in db.query(Author).filter(Author.name.ilike(like)).limit(8).all()]
    filters = [
        Book.original_title.ilike(like),
        Book.chinese_title.ilike(like),
        Book.isbn13.ilike(like),
        Book.isbn10.ilike(like),
        Book.tags.ilike(like),
        Book.primary_genre.ilike(like),
        Book.language_name.ilike(like),
        Book.language_code.ilike(like),
    ]
    if author_ids:
        filters.append(Book.author_id.in_(author_ids))
    books = db.query(Book).filter(or_(*filters)).order_by(Book.is_featured.desc(), Book.id.desc()).limit(8).all()
    return {
        "results": [
            {
                "slug": b.slug,
                "title": b.original_title,
                "chinese": b.chinese_title,
                "cover": b.cover_image,
            }
            for b in books
        ]
    }


@app.get("/robots.txt")
def robots():
    return PlainTextResponse("User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")


@app.get("/sitemap.xml")
def sitemap(request: Request, db: Session = Depends(get_db)):
    host = str(request.base_url).rstrip("/")
    urls = ["/", "/recommendations", "/search", "/archive", "/explore", "/recommend"]
    for code in LANGS:
        urls.append(f"/recommendations/{code}")
    for b in db.query(Book.slug).all():
        urls.append(f"/books/{b[0]}")
    xml = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append(f"<url><loc>{host}{u}</loc></url>")
    xml.append("</urlset>")
    return Response("".join(xml), media_type="application/xml")


@app.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    n = db.query(func.count(Book.id)).scalar()
    return {"ok": True, "books": n}


register_submissions(app, templates, base_ctx)
