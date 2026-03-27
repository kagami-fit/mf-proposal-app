"""企業HPスクレイピング"""

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT


class CompanyScraper:
    """企業HPから情報をスクレイピング"""

    # 取得対象のページパス（日本の企業サイトで一般的なもの）
    TARGET_PATHS = [
        "/",
        "/company",
        "/about",
        "/about-us",
        "/corporate",
        "/company/overview",
        "/health",
        "/csr",
        "/sustainability",
        "/welfare",
        "/recruit",
    ]

    # 健康経営関連キーワード
    HEALTH_KEYWORDS = [
        "健康経営",
        "ウェルビーイング",
        "well-being",
        "wellbeing",
        "メンタルヘルス",
        "産業医",
        "健康診断",
        "ストレスチェック",
        "従業員の健康",
        "働き方改革",
        "ワークライフバランス",
        "健康保険組合",
        "EAP",
        "健康増進",
        "健康宣言",
        "安全衛生",
        "労働安全",
    ]

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def scrape(self) -> dict:
        """企業HPをスクレイピングして情報を返す"""
        result = {
            "base_url": self.base_url,
            "pages": [],
            "health_related_content": [],
            "company_info": {},
        }

        for path in self.TARGET_PATHS:
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            page_data = self._fetch_page(url)
            if page_data:
                result["pages"].append(page_data)
                # 健康経営関連コンテンツを抽出
                health_content = self._extract_health_content(page_data["text"])
                if health_content:
                    result["health_related_content"].append(
                        {"url": url, "content": health_content}
                    )

        # トップページから企業基本情報を抽出
        if result["pages"]:
            result["company_info"] = self._extract_company_info(result["pages"][0])

        return result

    def _fetch_page(self, url: str) -> dict | None:
        """ページを取得してテキストとメタ情報を抽出"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            # リダイレクトで外部サイトに飛んだ場合はスキップ
            if urlparse(response.url).netloc != urlparse(self.base_url).netloc:
                return None
            if response.status_code != 200:
                return None
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        # 不要な要素を除去
        for tag in soup.select("script, style, nav, footer, header, aside"):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)

        # メタディスクリプション
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            meta_desc = meta_tag.get("content", "")

        # テキストを適切な長さに制限（LLMに送るため）
        text = text[:5000]

        return {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "text": text,
        }

    def _extract_health_content(self, text: str) -> str:
        """テキストから健康経営関連部分を抽出"""
        lines = text.split("\n")
        relevant_lines = []
        for i, line in enumerate(lines):
            if any(kw in line for kw in self.HEALTH_KEYWORDS):
                # 前後3行もコンテキストとして取得
                start = max(0, i - 3)
                end = min(len(lines), i + 4)
                context = "\n".join(lines[start:end])
                relevant_lines.append(context)

        return "\n---\n".join(relevant_lines) if relevant_lines else ""

    def _extract_company_info(self, page_data: dict) -> dict:
        """ページデータから企業基本情報を抽出"""
        text = page_data.get("text", "")
        info = {
            "title": page_data.get("title", ""),
            "description": page_data.get("meta_description", ""),
        }

        # 従業員数の抽出
        import re

        emp_match = re.search(r"従業員[数:]?\s*[約]?(\d[\d,]+)\s*名?人?", text)
        if emp_match:
            info["employees"] = emp_match.group(1).replace(",", "")

        # 設立年の抽出
        est_match = re.search(r"設立[:\s]*(\d{4})年", text)
        if est_match:
            info["established"] = est_match.group(1)

        return info

    def get_summary(self) -> str:
        """スクレイピング結果をLLMに渡すためのサマリーテキストを返す"""
        data = self.scrape()
        parts = []

        if data["company_info"]:
            parts.append("## 企業基本情報")
            for k, v in data["company_info"].items():
                parts.append(f"- {k}: {v}")

        if data["health_related_content"]:
            parts.append("\n## 健康経営関連コンテンツ")
            for item in data["health_related_content"]:
                parts.append(f"\n### {item['url']}")
                parts.append(item["content"][:2000])

        if not data["health_related_content"] and data["pages"]:
            parts.append("\n## HPコンテンツ（健康経営関連の直接的な記述なし）")
            for page in data["pages"][:3]:
                parts.append(f"\n### {page['url']}")
                parts.append(page["text"][:1000])

        return "\n".join(parts) if parts else "企業HPの情報を取得できませんでした。"
