"""PR TIMESスクレイピング"""

import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from collectors.base_collector import BaseCollector
from config.settings import PRTIMES_KEYWORDS, REQUEST_HEADERS, REQUEST_TIMEOUT
from sheets.models import Company


class PRTimesCollector(BaseCollector):
    """PR TIMESからプレスリリースを検索して企業情報を収集"""

    BASE_URL = "https://prtimes.jp/main/action.php"

    @property
    def source_name(self) -> str:
        return "PR TIMES"

    def __init__(self, keywords: list[str] | None = None):
        self.keywords = keywords or PRTIMES_KEYWORDS

    def collect(self) -> list[Company]:
        companies = []
        for keyword in self.keywords:
            companies.extend(self._search(keyword))
        # 企業名で重複を除去
        seen = set()
        unique = []
        for c in companies:
            if c.name not in seen:
                seen.add(c.name)
                unique.append(c)
        return unique

    def _search(self, keyword: str) -> list[Company]:
        """キーワードでPR TIMESを検索"""
        url = f"{self.BASE_URL}?run=html&page=searchkey&search_word={quote(keyword)}"

        try:
            response = requests.get(
                url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"PR TIMES検索に失敗 ({keyword}): {e}")
            return []

        return self._parse_search_results(response.text)

    def _parse_search_results(self, html: str) -> list[Company]:
        """検索結果ページをパースして企業情報を抽出"""
        soup = BeautifulSoup(html, "lxml")
        companies = []

        # 現在のPR TIMESのHTML構造に対応
        articles = soup.select("article[class*='release-card_article']")
        if not articles:
            # フォールバック: 汎用的なarticleタグ
            articles = soup.select("article")

        for article in articles[:20]:  # 最新20件に制限
            company = self._parse_article(article)
            if company:
                companies.append(company)

        return companies

    def _parse_article(self, article) -> Company | None:
        """個別記事要素から企業情報を抽出"""
        # タイトル
        title_elem = article.select_one(
            "a[class*='release-card_link'], a[class*='release-card_title'], h2 a, a[href*='/main/html/rd/p']"
        )
        if not title_elem:
            return None

        # タイトルテキスト: title属性のある要素、またはリンク内のテキスト
        title_text_elem = article.select_one(
            "[class*='release-card_title'], h2, h3"
        )
        title = title_text_elem.get_text(strip=True) if title_text_elem else title_elem.get_text(strip=True)

        article_url = title_elem.get("href", "")
        if article_url and not article_url.startswith("http"):
            article_url = f"https://prtimes.jp{article_url}"

        # 企業名
        company_elem = article.select_one(
            "[class*='release-card_companyName'], [class*='companyLink'], .company-name"
        )
        company_name = company_elem.get_text(strip=True) if company_elem else ""

        if not company_name:
            # タイトルから企業名を推定
            match = re.search(r"((?:株式会社|㈱)[^\s、。,]+|[^\s、。,]+(?:株式会社|㈱))", title)
            company_name = match.group(1) if match else ""

        if not company_name:
            return None

        # 企業URL
        company_url = ""
        company_link = article.select_one("a[class*='companyLink'], a[class*='company']")
        if company_link and company_link.get("href"):
            company_url = company_link["href"]
            if not company_url.startswith("http"):
                company_url = f"https://prtimes.jp{company_url}"

        # 日付
        date_elem = article.select_one("time, [class*='timeAgo']")
        date_str = ""
        if date_elem:
            date_str = date_elem.get("datetime", date_elem.get_text(strip=True))[:10]

        return Company(
            name=company_name,
            url=company_url,
            source=self.source_name,
            discovered_at=date_str,
            article_title=title,
            article_url=article_url,
            status="新規",
        )
