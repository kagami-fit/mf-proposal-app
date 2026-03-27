"""求人サイト経由の企業収集

求人サイト（Indeed等）で健康経営関連キーワードを含む求人を出している企業を収集。
「健康経営」「ウェルビーイング」等を求人に記載 = 健康経営に関心が高い企業。
"""

import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from collectors.base_collector import BaseCollector
from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT
from sheets.models import Company


DEFAULT_KEYWORDS = [
    "健康経営",
    "ウェルビーイング 福利厚生",
    "産業保健 企業",
    "EAP 導入",
    "メンタルヘルス 推進",
]


class JobSiteCollector(BaseCollector):
    """求人サイトから健康経営に関心のある企業を収集"""

    @property
    def source_name(self) -> str:
        return "求人サイト"

    def __init__(self, keywords: list[str] | None = None, max_pages: int = 2):
        self.keywords = keywords or DEFAULT_KEYWORDS
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def collect(self) -> list[Company]:
        companies = []
        seen_names = set()

        for keyword in self.keywords:
            results = self._search_indeed(keyword)
            for company in results:
                if company.name not in seen_names:
                    seen_names.add(company.name)
                    companies.append(company)

        return companies

    def _search_indeed(self, keyword: str) -> list[Company]:
        """Indeed Japanで求人検索して企業名を抽出"""
        companies = []

        for page in range(self.max_pages):
            start = page * 10
            url = f"https://jp.indeed.com/jobs?q={quote(keyword)}&start={start}"

            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    break
                response.encoding = response.apparent_encoding or "utf-8"
            except requests.RequestException as e:
                print(f"[JobSite] Indeed検索エラー ({keyword}): {e}")
                break

            soup = BeautifulSoup(response.text, "lxml")

            # 求人カードから企業名を抽出
            job_cards = soup.select(
                "[data-testid='job-card'], .job_seen_beacon, .jobsearch-ResultsList > li"
            )

            for card in job_cards:
                company_name = self._extract_company_name(card)
                if not company_name:
                    continue

                job_title = ""
                title_elem = card.select_one(
                    "[data-testid='jobTitle'], .jobTitle, h2 a, h2 span"
                )
                if title_elem:
                    job_title = title_elem.get_text(strip=True)

                job_url = ""
                link_elem = card.select_one("a[href*='/rc/clk'], a[href*='/viewjob'], h2 a")
                if link_elem:
                    href = link_elem.get("href", "")
                    if href and not href.startswith("http"):
                        job_url = f"https://jp.indeed.com{href}"
                    else:
                        job_url = href

                # 福利厚生キーワードの検出
                card_text = card.get_text(" ", strip=True)
                health_keywords = self._detect_health_keywords(card_text)

                companies.append(
                    Company(
                        name=company_name,
                        url="",
                        source=f"{self.source_name}（Indeed）",
                        article_title=job_title[:100] if job_title else "",
                        article_url=job_url,
                        status="新規",
                        memo=f"検索: {keyword}" + (
                            f" / 健康関連: {', '.join(health_keywords)}"
                            if health_keywords else ""
                        ),
                    )
                )

        return companies

    @staticmethod
    def _extract_company_name(card) -> str:
        """求人カードから企業名を抽出"""
        selectors = [
            "[data-testid='company-name']",
            ".companyName",
            ".company_location .companyName",
            "span[class*='company']",
            ".css-1x7skt0",  # Indeed の動的クラス
        ]
        for sel in selectors:
            elem = card.select_one(sel)
            if elem:
                name = elem.get_text(strip=True)
                if name and len(name) >= 2:
                    return name

        # フォールバック: テキスト中から企業名パターンを探す
        text = card.get_text(" ", strip=True)
        match = re.search(
            r"((?:株式会社|㈱)[^\s、。,]+|[^\s、。,]+(?:株式会社|㈱))",
            text,
        )
        return match.group(1) if match else ""

    @staticmethod
    def _detect_health_keywords(text: str) -> list[str]:
        """テキストから健康経営関連キーワードを検出"""
        keywords = [
            "健康経営", "ウェルビーイング", "メンタルヘルス",
            "ストレスチェック", "産業医", "健康診断",
            "EAP", "健康保険組合", "健康増進",
            "働き方改革", "フレックス", "テレワーク", "リモートワーク",
        ]
        return [kw for kw in keywords if kw in text]
