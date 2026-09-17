from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["FOLIO_DB"] = str(ROOT / "data" / "test.db")
os.environ["FOLIO_SECRET_KEY"] = "test-secret"
os.environ["FOLIO_ADMIN_KEY"] = "test-admin"

from fastapi.testclient import TestClient
from folio.models import Base, Book, SessionLocal, engine, init_db
from folio.main import app
from folio.seed import seed
from folio.config import DATA_DIR


def setup_module():
    db_path = DATA_DIR / "test.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    if (DATA_DIR / "cleaned-books.json").exists():
        seed()


def client():
    return TestClient(app)


def test_home_ok():
    r = client().get("/")
    assert r.status_code == 200
    assert "FOLIO" in r.text
    assert "1797098277@qq.com" in r.text
    assert "mailto:" not in r.text
    assert "amazon" not in r.text.lower()
    assert "购买" not in r.text or "不提供购买" in r.text
    assert "/covers/sleeping-sisters.jpg" in r.text
    assert "/covers/book-of-chuck.jpg" in r.text
    assert "/covers/calamities.jpg" in r.text
    assert "en-the-sleeping-sisters.jpg" not in r.text
    assert "Dear Debbie" in r.text
    assert "card-en-" in r.text
    assert "从一本书出发" in r.text
    assert "跨越语言，遇见故事" in r.text
    assert "开始翻阅本期新书" in r.text
    assert "folio-mark.png" in r.text
    assert "/static/img/shelf-transparent.png" in r.text
    assert "/static/img/lang-en.jpg" in r.text
    assert "/static/img/lang-fr.jpg" in r.text
    assert "/static/img/lang-es.jpg" in r.text
    assert "/static/img/lang-ja.jpg" in r.text
    assert "/static/img/lang-ko.jpg" in r.text
    assert "/static/img/lang-it.jpg" in r.text
    assert "page-home" in r.text
    assert "bg-home-desktop.jpg" in r.text
    assert "英文新书重点推荐" not in r.text
    assert "其他语言推荐" not in r.text
    for native in ["English", "Français", "Español", "日本語", "한국어", "Italiano"]:
        assert native in r.text


def test_language_pages_have_eight():
    for lang in ["en", "es", "ja", "ko", "fr", "it"]:
        r = client().get(f"/recommendations/{lang}")
        assert r.status_code == 200
        assert r.text.count("No.") >= 8 or r.text.count("book-") >= 8


def test_search_and_empty():
    r = client().get("/search?q=zzzzzz-not-a-book")
    assert r.status_code == 200
    assert "没有符合条件" in r.text
    r2 = client().get("/search?q=FOLIO")
    assert r2.status_code == 200
    r3 = client().get("/search?q=Sleeping")
    assert r3.status_code == 200
    assert "Sleeping" in r3.text
    r4 = client().get("/search?q=Sleeping&year=")
    assert r4.status_code == 200
    assert "Sleeping" in r4.text
    r5 = client().get("/search")
    assert r5.status_code == 200
    assert "请输入书名" in r5.text
    r6 = client().get("/search?q=god&lang=&genre=&year=&recommended=&sort=year")
    assert r6.status_code == 200
    assert "int_parsing" not in r6.text
    assert "God" in r6.text or "god" in r6.text.lower() or "检索" in r6.text


def test_archive_unknown_month():
    r = client().get("/archive?year=2024&month=1")
    assert r.status_code == 200
    assert "尚无该期" in r.text


def test_rating_upsert_and_comment(tmp_path=None):
    c = client()
    home = c.get("/")
    # pick a book link
    db = SessionLocal()
    book = db.query(Book).filter(Book.is_featured.is_(True)).first()
    db.close()
    assert book
    page = c.get(f"/books/{book.slug}")
    assert page.status_code == 200
    csrf = c.cookies.get("folio_csrf")
    r1 = c.post(f"/api/books/{book.slug}/ratings", json={"score": 5, "csrf": csrf})
    assert r1.status_code == 200
    assert r1.json()["average"] == 5
    r2 = c.post(f"/api/books/{book.slug}/ratings", json={"score": 3, "csrf": csrf})
    assert r2.json()["count"] == 1
    assert r2.json()["average"] == 3.0
    r3 = c.post(
        f"/api/books/{book.slug}/comments",
        json={"nickname": "fan", "content": "安静好读。", "csrf": csrf},
    )
    assert r3.status_code == 200
    cid = r3.json()["id"]
    r4 = c.post(f"/api/comments/{cid}/like-json", json={"csrf": csrf})
    assert r4.json()["liked"] is True
    r5 = c.post(f"/api/comments/{cid}/like-json", json={"csrf": csrf})
    assert r5.json()["liked"] is False
    r6 = c.post(
        f"/api/books/{book.slug}/comments",
        json={"nickname": "x", "content": "<script>alert(1)</script>hello", "csrf": csrf},
    )
    assert r6.status_code == 400
    comments = c.get(f"/api/books/{book.slug}/comments").json()["comments"]
    assert any(x["id"] == cid for x in comments)
    spoil = c.post(
        f"/api/books/{book.slug}/comments",
        json={"nickname": "fan", "content": "结局其实是……", "csrf": csrf, "spoiler": True},
    )
    assert spoil.status_code == 200
    listed = c.get(f"/api/books/{book.slug}/comments?sort=popular").json()["comments"]
    spoil_row = next(x for x in listed if x["id"] == spoil.json()["id"])
    assert spoil_row["containsSpoiler"] is True
    assert not spoil_row["content"].startswith("[剧透]")
    sug = c.get("/api/search/suggest?q=Sleeping")
    assert sug.status_code == 200
    assert sug.json()["results"]
    r7 = c.post(f"/api/comments/{cid}/delete", json={"csrf": csrf})
    assert r7.status_code == 200


def test_language_hub_and_sitemap():
    c = client()
    r = c.get("/recommendations")
    assert r.status_code == 200
    assert "本期新书推荐" in r.text
    sm = c.get("/sitemap.xml")
    assert sm.status_code == 200
    assert "/recommendations/ja" in sm.text
    robots = c.get("/robots.txt")
    assert "Sitemap" in robots.text


def test_other_visitor_cannot_delete():
    c1 = client()
    db = SessionLocal()
    book = db.query(Book).filter(Book.is_featured.is_(True)).first()
    db.close()
    c1.get(f"/books/{book.slug}")
    csrf = c1.cookies.get("folio_csrf")
    posted = c1.post(
        f"/api/books/{book.slug}/comments",
        json={"nickname": "owner", "content": "这是我的评论。", "csrf": csrf},
    )
    cid = posted.json()["id"]
    c2 = client()
    c2.get(f"/books/{book.slug}")
    csrf2 = c2.cookies.get("folio_csrf")
    denied = c2.post(f"/api/comments/{cid}/delete", json={"csrf": csrf2})
    assert denied.status_code == 403


def test_featured_eight_per_language():
    db = SessionLocal()
    for lang in ["en", "es", "ja", "ko", "fr", "it"]:
        n = db.query(Book).filter(Book.language_code == lang, Book.is_featured.is_(True)).count()
        assert n == 8, lang
    db.close()


def test_no_shop_links_on_home():
    text = client().get("/").text.lower()
    for bad in ["amazon", "bookshop.org", "taobao", "jd.com", "mailto:", "kindle"]:
        assert bad not in text


def test_book_detail_layout():
    c = client()
    db = SessionLocal()
    book = db.query(Book).filter(Book.is_featured.is_(True), Book.language_code == "ja").first()
    db.close()
    assert book
    r = c.get(f"/books/{book.slug}")
    assert r.status_code == 200
    assert "返回首页" in r.text
    assert "一起聊聊这本书" in r.text
    assert "读者评分" in r.text
    assert "内容简介" in r.text or "简介" in r.text
    assert "page-book" in r.text
    assert "bg-detail-desktop.jpg" in r.text
    assert "mailto:" not in r.text
    assert "data-lightbox" in r.text
    assert "data-suggest" in r.text
    assert "上一本" in r.text
    assert "下一本" in r.text
    assert "你可能还会喜欢" in r.text
    assert "购买" not in r.text or "不提供购买" in r.text
    assert "amazon" not in r.text.lower()
    missing = c.get("/books/not-a-real-slug")
    assert missing.status_code == 404
    assert "没有找到这本书" in missing.text
