"""gspreadクライアント"""

from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from config.settings import GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SPREADSHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client() -> gspread.Client:
    """認証済みgspreadクライアントを返す"""
    creds_path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"サービスアカウントキーファイルが見つかりません: {creds_path}\n"
            "Google Cloud Consoleからダウンロードし、credentials/ディレクトリに配置してください。"
        )
    credentials = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    return gspread.authorize(credentials)


def get_spreadsheet() -> gspread.Spreadsheet:
    """設定済みスプレッドシートを返す"""
    client = get_client()
    if not GOOGLE_SPREADSHEET_ID:
        raise ValueError(
            "GOOGLE_SPREADSHEET_IDが設定されていません。.envファイルを確認してください。"
        )
    return client.open_by_key(GOOGLE_SPREADSHEET_ID)
