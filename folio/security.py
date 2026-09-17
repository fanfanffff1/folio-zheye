from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from html import escape

from fastapi import HTTPException, Request, Response

from .config import (
    ADMIN_KEY, COMMENT_MAX, COMMENT_MIN, COOKIE_NAME, CSRF_COOKIE, NICK_MAX, NICK_MIN,
    RATE_LIMIT_POST, RATE_WINDOW_SEC, SECRET_KEY,
)

_RATE: dict[str, deque] = defaultdict(deque)


def sign(value: str) -> str:
    digest = hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{digest}"


def unsign(token: str) -> str | None:
    if "." not in token:
        return None
    value, digest = token.rsplit(".", 1)
    expected = hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return None
    return value


def get_or_set_visitor(request: Request, response: Response) -> str:
    raw = request.cookies.get(COOKIE_NAME)
    vid = unsign(raw) if raw else None
    if not vid:
        vid = secrets.token_hex(16)
        response.set_cookie(
            COOKIE_NAME, sign(vid), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 400, path="/"
        )
    csrf = request.cookies.get(CSRF_COOKIE)
    if not csrf:
        csrf = secrets.token_urlsafe(24)
        response.set_cookie(
            CSRF_COOKIE, csrf, httponly=False, samesite="lax",
            max_age=60 * 60 * 24 * 400, path="/"
        )
    request.state.csrf = csrf
    return vid


def require_csrf(request: Request, token: str) -> None:
    cookie = request.cookies.get(CSRF_COOKIE) or ""
    if not token or not cookie or not hmac.compare_digest(token, cookie):
        raise HTTPException(403, "CSRF 校验失败，请刷新后重试。")


def rate_limit(request: Request, key: str) -> None:
    ip = request.client.host if request.client else "unknown"
    bucket = f"{ip}:{key}"
    now = time.time()
    q = _RATE[bucket]
    while q and now - q[0] > RATE_WINDOW_SEC:
        q.popleft()
    if len(q) >= RATE_LIMIT_POST:
        raise HTTPException(429, "操作过于频繁，请稍后再试。")
    q.append(now)


def clean_text(text: str, min_len: int, max_len: int, field: str) -> str:
    value = (text or "").replace("\x00", "").strip()
    if len(value) < min_len or len(value) > max_len:
        raise HTTPException(400, f"{field}长度需在 {min_len}–{max_len} 字之间。")
    lowered = value.lower()
    if "<script" in lowered or "javascript:" in lowered:
        raise HTTPException(400, "评论包含不被允许的内容。")
    return value


def clean_nick(nick: str) -> str:
    return clean_text(nick, NICK_MIN, NICK_MAX, "昵称")


def clean_comment(content: str) -> str:
    return clean_text(content, COMMENT_MIN, COMMENT_MAX, "评论")


def is_admin(request: Request) -> bool:
    candidates = [
        request.headers.get("x-folio-admin") or "",
        request.query_params.get("admin") or "",
        request.cookies.get("folio_admin") or "",
    ]
    for value in candidates:
        if value and len(value) == len(ADMIN_KEY) and hmac.compare_digest(value, ADMIN_KEY):
            return True
    return False


def html_safe(text: str) -> str:
    return escape(text or "", quote=True)
