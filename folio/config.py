from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
TEMPLATE_DIR = ROOT / "templates"
DB_PATH = Path(os.environ.get("FOLIO_DB", DATA_DIR / "folio.db"))

SITE_NAME = "FOLIO 折页"
SITE_TAGLINE = "原版新书 · 编辑荐读"
ISSUE_YEAR = 2026
ISSUE_MONTH = 9
ISSUE_TITLE = "二〇二六年九月号"
CONTACT_EMAIL = "1797098277@qq.com"
SECRET_KEY = os.environ.get("FOLIO_SECRET_KEY", "dev-change-me-in-production")
ADMIN_KEY = os.environ.get("FOLIO_ADMIN_KEY", "dev-admin-change-me")
COOKIE_NAME = "folio_vid"
CSRF_COOKIE = "folio_csrf"
RATE_WINDOW_SEC = 60
RATE_LIMIT_POST = 8
COMMENT_MIN = 2
COMMENT_MAX = 2000
NICK_MIN = 1
NICK_MAX = 24

LANGS = {
    "en": {"zh": "英语", "native": "English", "accent": "#8c2f2a"},
    "es": {"zh": "西班牙语", "native": "Español", "accent": "#7a4a2b"},
    "ja": {"zh": "日语", "native": "日本語", "accent": "#4a5a3a"},
    "ko": {"zh": "韩语", "native": "한국어", "accent": "#3d4d6b"},
    "fr": {"zh": "法语", "native": "Français", "accent": "#5a3d5a"},
    "it": {"zh": "意大利语", "native": "Italiano", "accent": "#6b4a3d"},
}

GENRES = [
    "悬疑", "推理", "惊悚", "科幻", "奇幻", "爱情", "历史",
    "家庭", "成长", "社会议题", "文学小说", "非虚构", "传记", "随笔", "青少年", "其他",
]
