"""企業の公式サイトURLをWeb検索で自動取得"""

import re
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT


class URLFinder:
    """企業名からWeb検索で公式サイトURLを特定する"""

    # 除外するドメイン（ニュースサイト・SNS等）
    EXCLUDE_DOMAINS = {
        "wikipedia.org", "facebook.com", "twitter.com", "x.com",
        "instagram.com", "linkedin.com", "youtube.com", "tiktok.com",
        "prtimes.jp", "news.google.com", "news.yahoo.co.jp",
        "nikkei.com", "toyokeizai.net", "diamond.jp",
        "wantedly.com", "indeed.com", "recruit.co.jp",
        "google.com", "google.co.jp", "bing.com",
        "amazon.co.jp", "rakuten.co.jp", "minkabu.jp",
        "kabutan.jp", "duckduckgo.com", "nicovideo.jp",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def find_url(self, company_name: str) -> str:
        """企業名から公式サイトURLを検索して返す。見つからなければ空文字。"""
        # 方法1: Claude APIで企業URLを推定（最も正確）
        url = self._ask_llm(company_name)
        if url:
            return url

        # 方法2: Bing検索（フォールバック）
        short_name = self._normalize_name(company_name)
        url = self._search_bing(short_name)
        if url:
            return url

        return ""

    def _search_bing(self, company_name: str) -> str:
        """Bing検索で企業公式サイトを検索"""
        query = f"{company_name} 公式サイト"
        search_url = f"https://www.bing.com/search?q={quote(query)}&setlang=ja"

        try:
            response = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return ""
            response.encoding = "utf-8"
        except requests.RequestException:
            return ""

        soup = BeautifulSoup(response.text, "lxml")

        # Bing検索結果のリンクを解析
        for li in soup.select("#b_results li.b_algo"):
            a_tag = li.select_one("h2 a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if self._is_corporate_url(href):
                return self._normalize_url(href)

        return ""

    def _search_via_gnews(self, company_name: str) -> str:
        """GNews経由で企業の公式URLを推定"""
        try:
            from gnews import GNews
            gn = GNews(language="ja", country="JP", max_results=3)
            results = gn.get_news(f"{company_name} 会社")

            for item in results:
                url = item.get("url", "")
                # ニュース記事のURLからソースドメインを除外し、
                # 企業名が含まれるリンクを探す
                publisher = item.get("publisher", {}).get("href", "")
                if publisher and self._is_corporate_url(publisher):
                    return self._normalize_url(publisher)
        except Exception as e:
            print(f"[URLFinder] GNews検索エラー: {e}")

        return ""

    def _ask_llm(self, company_name: str) -> str:
        """Claude APIで企業の公式サイトURLを推定"""
        try:
            import anthropic
            from config.settings import ANTHROPIC_API_KEY

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": f"日本の企業「{company_name}」の公式コーポレートサイトのURLを教えてください。URLのみを1行で回答してください。わからない場合は「不明」と回答してください。",
                }],
            )
            text = response.content[0].text.strip()
            # URLを抽出
            match = re.search(r'https?://[^\s]+', text)
            if match:
                url = match.group(0).rstrip("。、）)")
                # URLが実際にアクセスできるか確認
                if self._verify_url(url):
                    return self._normalize_url(url)
        except Exception as e:
            print(f"[URLFinder] LLM推定エラー: {e}")

        return ""

    def _verify_url(self, url: str) -> bool:
        """URLが実際にアクセスできるか確認（403もOKとする：多くの企業サイトはbot検知あり）"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            # 403/405はbot検知やHEAD非対応の可能性が高いのでOKとする
            return response.status_code < 500
        except requests.RequestException:
            try:
                response = self.session.get(url, timeout=10, allow_redirects=True)
                return response.status_code < 500
            except requests.RequestException:
                return False

    @staticmethod
    def _normalize_name(name: str) -> str:
        """検索用に企業名を正規化"""
        cleaned = re.sub(r"(株式会社|㈱|有限会社|合同会社|一般社団法人|一般財団法人)", "", name)
        return cleaned.strip()

    def _is_corporate_url(self, url: str) -> bool:
        """URLが企業の公式サイトらしいかを判定"""
        if not url or not url.startswith("http"):
            return False

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for excluded in self.EXCLUDE_DOMAINS:
            if excluded in domain:
                return False

        corporate_tlds = [".co.jp", ".or.jp", ".ne.jp", ".jp", ".com", ".net"]
        if any(domain.endswith(tld) for tld in corporate_tlds):
            return True

        return False

    @staticmethod
    def _normalize_url(url: str) -> str:
        """URLをルートドメインに正規化"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
