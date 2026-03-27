"""GNews（Google News）による企業収集

健康経営関連キーワードでニュース記事を検索し、
記事に登場する企業を抽出する。
"""

import re

from collectors.base_collector import BaseCollector
from sheets.models import Company


# 健康経営関連の検索クエリ
DEFAULT_QUERIES = [
    "健康経営 導入",
    "健康経営 取り組み 企業",
    "ウェルビーイング 企業 施策",
    "従業員 健康管理 企業",
    "メンタルヘルス 企業 対策",
    "ストレスチェック 義務化 対応",
    "産業医 選任 企業",
    "健康経営優良法人 認定",
    "働き方改革 健康",
    "EAP 企業 導入",
]


class GNewsCollector(BaseCollector):
    """Google Newsからの健康経営関連企業収集"""

    @property
    def source_name(self) -> str:
        return "Google News"

    def __init__(self, queries: list[str] | None = None, max_results: int = 10):
        self.queries = queries or DEFAULT_QUERIES
        self.max_results = max_results

    def collect(self) -> list[Company]:
        """ニュース検索で企業を収集"""
        try:
            from gnews import GNews
        except ImportError:
            print("[GNews] gnewsライブラリが未インストールです")
            return []

        google_news = GNews(
            language="ja",
            country="JP",
            max_results=self.max_results,
        )

        all_companies = []
        seen_names = set()

        for query in self.queries:
            try:
                results = google_news.get_news(query)
            except Exception as e:
                print(f"[GNews] 検索エラー ({query}): {e}")
                continue

            for article in results:
                title = article.get("title", "")
                description = article.get("description", "")
                url = article.get("url", "")
                published = article.get("published date", "")
                publisher = article.get("publisher", {}).get("title", "")

                # タイトル・本文から企業名を抽出
                text = f"{title} {description}"
                names = self._extract_company_names(text)

                for name in names:
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    all_companies.append(
                        Company(
                            name=name,
                            url="",
                            source=f"{self.source_name}（{publisher}）",
                            discovered_at=published[:10] if published else "",
                            article_title=title[:100],
                            article_url=url,
                            status="新規",
                            memo=f"検索クエリ: {query}",
                        )
                    )

        return all_companies

    @staticmethod
    def _extract_company_names(text: str) -> list[str]:
        """テキストから企業名パターンを抽出"""
        patterns = [
            r"((?:株式会社|㈱)[^\s、。,\)）」】]+)",
            r"([^\s、。,\(（「【]+(?:株式会社|㈱))",
            r"([^\s、。,]+(?:ホールディングス|HD|グループ))",
        ]

        names = []
        seen = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                cleaned = match.strip("「」【】()（）『』")
                if cleaned and len(cleaned) >= 3 and cleaned not in seen:
                    seen.add(cleaned)
                    names.append(cleaned)

        return names
