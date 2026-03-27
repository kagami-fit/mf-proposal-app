"""Google Alerts RSS解析"""

import re
from html import unescape
from urllib.parse import urlparse

import feedparser
import requests

from collectors.base_collector import BaseCollector
from config.settings import GOOGLE_ALERTS_RSS_URLS, REQUEST_HEADERS, REQUEST_TIMEOUT
from sheets.models import Company


class GoogleAlertsCollector(BaseCollector):
    """Google AlertsのRSSフィードから企業情報を収集"""

    @property
    def source_name(self) -> str:
        return "Google Alerts"

    def __init__(self, feed_urls: list[str] | None = None):
        self.feed_urls = feed_urls or GOOGLE_ALERTS_RSS_URLS

    def collect(self) -> list[Company]:
        companies = []
        for url in self.feed_urls:
            companies.extend(self._parse_feed(url))
        return companies

    def _parse_feed(self, feed_url: str) -> list[Company]:
        """RSSフィードを解析して企業情報を抽出"""
        try:
            response = requests.get(
                feed_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Google Alertsフィードの取得に失敗: {e}")
            return []

        feed = feedparser.parse(response.text)
        companies = []

        for entry in feed.entries:
            title = unescape(self._strip_html(entry.get("title", "")))
            link = entry.get("link", "")
            published = entry.get("published", "")

            # 記事URLからドメインを取得して企業URL候補にする
            parsed = urlparse(link)
            company_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""

            # タイトルから企業名を抽出（シンプルなヒューリスティック）
            company_name = self._extract_company_name(title)

            if company_name:
                companies.append(
                    Company(
                        name=company_name,
                        url=company_url,
                        source=self.source_name,
                        discovered_at=published[:10] if published else "",
                        article_title=title,
                        article_url=link,
                        status="新規",
                    )
                )

        return companies

    @staticmethod
    def _strip_html(text: str) -> str:
        """HTMLタグを除去"""
        return re.sub(r"<[^>]+>", "", text)

    @staticmethod
    def _extract_company_name(title: str) -> str:
        """タイトルから企業名を推定抽出

        日本語の記事タイトルから「株式会社XX」「XX社」などのパターンを探す。
        見つからない場合はタイトル全体を返す（後で人間が確認する）。
        """
        patterns = [
            r"((?:株式会社|㈱)[^\s、。,]+)",
            r"([^\s、。,]+(?:株式会社|㈱))",
            r"([^\s、。,]+(?:社|グループ|ホールディングス))",
        ]
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1)
        # パターンにマッチしなければタイトル全体を企業名として使用
        return title[:50] if title else ""
