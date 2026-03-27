"""環境変数管理"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent

# Anthropic Claude API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))

# Google Sheets
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json"
)
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")

# Google Alerts
GOOGLE_ALERTS_RSS_URLS = [
    url.strip()
    for url in os.getenv("GOOGLE_ALERTS_RSS_URLS", "").split(",")
    if url.strip()
]

# PR TIMES
PRTIMES_KEYWORDS = [
    kw.strip()
    for kw in os.getenv("PRTIMES_KEYWORDS", "健康経営").split(",")
    if kw.strip()
]

# ナレッジファイル
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
SERVICE_DESCRIPTION_FILE = KNOWLEDGE_DIR / "service_description.md"

# 送信者情報
SENDER_INFO = {
    "company_name": os.getenv("SENDER_COMPANY", ""),
    "name": os.getenv("SENDER_NAME", ""),
    "name_kana": os.getenv("SENDER_NAME_KANA", ""),
    "email": os.getenv("SENDER_EMAIL", ""),
    "phone": os.getenv("SENDER_PHONE", ""),
    "department": os.getenv("SENDER_DEPARTMENT", ""),
    "zipcode": os.getenv("SENDER_ZIPCODE", ""),
    "prefecture": os.getenv("SENDER_PREFECTURE", ""),
    "address": os.getenv("SENDER_ADDRESS", ""),
    "building": os.getenv("SENDER_BUILDING", ""),
}

# スクレイピング設定
REQUEST_TIMEOUT = 15
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}
