"""外部ソースから企業情報を収集してエンリッチメント"""

import re
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT


class WebEnricher:
    """複数の信頼性のある外部ソースから企業情報を収集"""

    def __init__(self, company_name: str, company_url: str = ""):
        self.company_name = company_name
        # 株式会社等を除去した短縮名（検索用）
        self.short_name = self._normalize_name(company_name)
        self.company_url = company_url
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """検索用に企業名を正規化"""
        cleaned = re.sub(r"(株式会社|㈱|有限会社|合同会社|一般社団法人|一般財団法人)", "", name)
        return cleaned.strip()

    def enrich(self) -> dict:
        """全ソースから情報を収集して統合"""
        result = {
            "company_name": self.company_name,
            "sources": [],
            "news_articles": [],
            "health_management_certification": None,
            "job_postings_info": None,
            "corporate_info": None,
            "industry_info": None,
        }

        # 各ソースから並列ではなく順次取得（レート制限考慮）
        collectors = [
            ("GNews", self._collect_gnews),
            ("PR TIMES記事", self._collect_prtimes_articles),
            ("求人情報", self._collect_job_info),
            ("Wantedly", self._collect_wantedly),
        ]

        for source_name, collector_fn in collectors:
            try:
                data = collector_fn()
                if data:
                    result["sources"].append(source_name)
                    if source_name == "GNews":
                        result["news_articles"] = data
                    elif source_name == "PR TIMES記事":
                        result["news_articles"].extend(data)
                    elif source_name == "求人情報":
                        result["job_postings_info"] = data
                    elif source_name == "Wantedly":
                        result["corporate_info"] = data
            except Exception as e:
                print(f"[WebEnricher] {source_name}の収集に失敗: {e}")

        return result

    def _collect_gnews(self) -> list[dict]:
        """GNewsライブラリで企業関連ニュースを収集"""
        try:
            from gnews import GNews

            google_news = GNews(language="ja", country="JP", max_results=5)

            articles = []
            # 健康経営関連のニュースを検索
            for query in [
                f"{self.short_name} 健康経営",
                f"{self.short_name} 従業員 福利厚生",
            ]:
                results = google_news.get_news(query)
                for item in results[:3]:
                    articles.append(
                        {
                            "title": item.get("title", ""),
                            "description": item.get("description", ""),
                            "published": item.get("published date", ""),
                            "source": item.get("publisher", {}).get("title", ""),
                            "url": item.get("url", ""),
                        }
                    )

            # 重複除去（タイトルベース）
            seen_titles = set()
            unique = []
            for a in articles:
                if a["title"] not in seen_titles:
                    seen_titles.add(a["title"])
                    unique.append(a)

            return unique[:8]
        except Exception as e:
            print(f"[WebEnricher] GNews収集エラー: {e}")
            return []

    def _collect_prtimes_articles(self) -> list[dict]:
        """PR TIMESで企業名を検索し、関連プレスリリースの詳細を取得"""
        url = f"https://prtimes.jp/main/action.php?run=html&page=searchkey&search_word={quote(self.short_name)}"

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return []
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        for article in soup.select("article")[:5]:
            title_elem = article.select_one("h2 a, a[href*='/main/html/rd/p']")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            link = title_elem.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://prtimes.jp{link}"

            # 記事本文の冒頭を取得
            snippet = self._fetch_article_snippet(link) if link else ""

            articles.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "source": "PR TIMES",
                }
            )

        return articles

    def _fetch_article_snippet(self, url: str) -> str:
        """記事URLから本文の冒頭を抽出"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return ""
            response.encoding = response.apparent_encoding or "utf-8"
            soup = BeautifulSoup(response.text, "lxml")

            # PR TIMESの記事本文
            body = soup.select_one(
                "[class*='rich-text'], .release--body, article .body"
            )
            if body:
                text = body.get_text(separator="\n", strip=True)
                return text[:800]

            return ""
        except requests.RequestException:
            return ""

    def _collect_job_info(self) -> dict | None:
        """求人ボックスから企業の求人情報を取得（従業員数・福利厚生等の手がかり）"""
        url = f"https://求人ボックス.com/求人?q={quote(self.company_name)}"

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return None
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")
        info = {"job_count": 0, "benefits": [], "salary_range": "", "details": []}

        job_cards = soup.select("[class*='job'], [class*='result'], article")[:5]
        info["job_count"] = len(job_cards)

        for card in job_cards[:3]:
            text = card.get_text(separator=" ", strip=True)
            # 福利厚生キーワード抽出
            benefit_keywords = [
                "健康診断",
                "社会保険",
                "育休",
                "産休",
                "リモート",
                "テレワーク",
                "フレックス",
                "健康経営",
                "EAP",
                "メンタルヘルス",
                "ストレスチェック",
                "健保",
                "企業年金",
                "退職金",
            ]
            for kw in benefit_keywords:
                if kw in text and kw not in info["benefits"]:
                    info["benefits"].append(kw)

            info["details"].append(text[:300])

        return info if info["job_count"] > 0 else None

    def _collect_wantedly(self) -> dict | None:
        """Wantedlyから企業情報を取得（企業文化・ミッション等）"""
        url = f"https://www.wantedly.com/search?q={quote(self.short_name)}&t=company"

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return None
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")
        info = {"mission": "", "description": "", "members_count": "", "details": ""}

        # 最初の検索結果の企業ページリンクを取得
        company_link = soup.select_one("a[href*='/companies/']")
        if not company_link:
            return None

        company_page_url = company_link.get("href", "")
        if company_page_url and not company_page_url.startswith("http"):
            company_page_url = f"https://www.wantedly.com{company_page_url}"

        # 企業ページを取得
        try:
            response = self.session.get(company_page_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return None
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        # ミッション・ビジョン
        mission_elem = soup.select_one(
            "[class*='mission'], [class*='vision'], h2"
        )
        if mission_elem:
            info["mission"] = mission_elem.get_text(strip=True)[:200]

        # 企業概要
        desc_elem = soup.select_one(
            "[class*='description'], [class*='about'], [class*='overview']"
        )
        if desc_elem:
            info["description"] = desc_elem.get_text(strip=True)[:500]

        # メンバー数
        members_elem = soup.select_one("[class*='member'] [class*='count'], [class*='staffCount']")
        if members_elem:
            info["members_count"] = members_elem.get_text(strip=True)

        # ページ全体から詳細テキストを取得
        body_text = soup.get_text(separator="\n", strip=True)
        info["details"] = body_text[:1000]

        return info if any(v for v in info.values()) else None

    def get_summary(self) -> str:
        """エンリッチメント結果をLLMに渡すためのサマリーテキストを返す"""
        data = self.enrich()
        parts = []

        if not data["sources"]:
            return ""

        parts.append(f"## 外部ソースからの追加情報（情報源: {', '.join(data['sources'])}）")

        # ニュース記事
        if data["news_articles"]:
            parts.append("\n### 関連ニュース・プレスリリース")
            for article in data["news_articles"][:6]:
                parts.append(f"\n**{article['title']}**")
                if article.get("source"):
                    parts.append(f"出典: {article['source']}")
                if article.get("description"):
                    parts.append(article["description"][:300])
                if article.get("snippet"):
                    parts.append(article["snippet"][:300])

        # 求人情報
        if data["job_postings_info"]:
            job = data["job_postings_info"]
            parts.append("\n### 求人情報から推定される情報")
            if job.get("benefits"):
                parts.append(f"確認された福利厚生キーワード: {', '.join(job['benefits'])}")
            if job.get("details"):
                for detail in job["details"][:2]:
                    parts.append(detail[:200])

        # 企業情報（Wantedly）
        if data["corporate_info"]:
            corp = data["corporate_info"]
            parts.append("\n### 企業文化・ミッション情報（Wantedly）")
            if corp.get("mission"):
                parts.append(f"ミッション: {corp['mission']}")
            if corp.get("description"):
                parts.append(corp["description"][:300])
            if corp.get("members_count"):
                parts.append(f"メンバー数: {corp['members_count']}")

        return "\n".join(parts)
