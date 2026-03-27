"""企業概要の構造化データを取得するスクレイパー

公式HPの会社概要ページ（table/dl要素）およびPR TIMESプレスリリースの
会社概要セクションから、代表者名・設立年・資本金・住所等を抽出する。
"""

import re
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT

# 会社概要で使われる一般的なラベル → 正規化キー
_LABEL_MAP = {
    "会社名": "company_name",
    "社名": "company_name",
    "商号": "company_name",
    "正式名称": "company_name",
    "代表": "representative",
    "代表者": "representative",
    "代表者名": "representative",
    "代表取締役": "representative",
    "代表取締役社長": "representative",
    "役員": "representative",
    "CEO": "representative",
    "President": "representative",
    "設立": "established",
    "設立年月": "established",
    "設立年月日": "established",
    "創業": "established",
    "創立": "established",
    "資本金": "capital",
    "資本金等": "capital",
    "売上高": "revenue",
    "売上": "revenue",
    "年商": "revenue",
    "売上規模": "revenue",
    "連結売上高": "revenue",
    "従業員数": "employee_scale",
    "従業員": "employee_scale",
    "社員数": "employee_scale",
    "スタッフ数": "employee_scale",
    "人員": "employee_scale",
    "所在地": "address",
    "本社所在地": "address",
    "本社": "address",
    "住所": "address",
    "本社住所": "address",
    "電話": "phone",
    "電話番号": "phone",
    "TEL": "phone",
    "Tel": "phone",
    "FAX": "fax",
    "Fax": "fax",
    "ファックス": "fax",
    "メール": "email",
    "メールアドレス": "email",
    "E-mail": "email",
    "Email": "email",
    "URL": "corporate_url",
    "ホームページ": "corporate_url",
    "HP": "corporate_url",
    "Webサイト": "corporate_url",
    "WEB": "corporate_url",
    "上場": "listed",
    "上場区分": "listed",
    "上場市場": "listed",
    "事業内容": "business_description",
    "主な事業": "business_description",
    "事業概要": "business_description",
    "主要事業": "business_description",
    "取扱商品": "business_description",
    "受賞": "awards",
    "受賞歴": "awards",
    "認定": "awards",
    "許認可": "awards",
    "グループ会社": "group_companies",
    "関連会社": "group_companies",
    "取引銀行": "bank",
    "主要取引先": "clients",
    "取引先": "clients",
}


class CompanyInfoScraper:
    """企業の会社概要ページやPR TIMESから構造化された企業情報を取得"""

    # 会社概要ページの候補パス
    COMPANY_PATHS = [
        "/company",
        "/company/",
        "/about",
        "/about/",
        "/corporate",
        "/corporate/",
        "/company/overview",
        "/company/overview/",
        "/corporate/overview",
        "/corporate/overview/",
        "/about-us",
        "/about-us/",
        "/company/profile",
        "/company/profile/",
        "/corporate/profile",
        "/corporate/profile/",
        "/company/info",
        "/company/info/",
        "/outline",
        "/outline/",
        "/profile",
        "/profile/",
        "/aboutus",
        "/aboutus/",
        "/company-profile",
        "/info",
        "/info/",
        "/gaiyou",
        "/kaisya",
    ]

    def __init__(self, company_name: str, company_url: str = "", prtimes_url: str = ""):
        self.company_name = company_name
        self.short_name = re.sub(
            r"(株式会社|㈱|有限会社|合同会社|一般社団法人|一般財団法人)", "", company_name
        ).strip()
        self.company_url = company_url.rstrip("/") if company_url else ""
        self.prtimes_url = prtimes_url
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def scrape(self) -> dict:
        """全ソースから企業概要を取得して統合"""
        result = {}

        # 1) 公式HPの会社概要ページ
        if self.company_url:
            hp_data = self._scrape_hp_company_page()
            if hp_data:
                result.update(hp_data)

        # 2) PR TIMESプレスリリースの会社概要セクション
        pr_data = self._scrape_prtimes_company_info()
        if pr_data:
            # HPデータがない項目のみ埋める
            for k, v in pr_data.items():
                if v and not result.get(k):
                    result[k] = v

        return result

    # ─── 公式HP ───

    def _scrape_hp_company_page(self) -> dict:
        """公式HPの会社概要ページから構造化データを抽出"""
        result = {}

        for path in self.COMPANY_PATHS:
            url = urljoin(self.company_url + "/", path.lstrip("/"))
            page = self._fetch_page(url)
            if not page:
                continue

            soup = page["soup"]

            # table要素から抽出
            table_data = self._extract_from_tables(soup)
            if table_data:
                for k, v in table_data.items():
                    if v and not result.get(k):
                        result[k] = v

            # dl要素から抽出
            dl_data = self._extract_from_dl(soup)
            if dl_data:
                for k, v in dl_data.items():
                    if v and not result.get(k):
                        result[k] = v

            # 十分な情報が取れたら終了
            if len(result) >= 4:
                break

        return result

    def _extract_from_tables(self, soup: BeautifulSoup) -> dict:
        """table要素からキー・バリューを抽出"""
        result = {}
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(separator=" ", strip=True)
                    key = self._match_label(label)
                    if key and value:
                        result[key] = self._clean_value(key, value)
        return result

    def _extract_from_dl(self, soup: BeautifulSoup) -> dict:
        """dl要素からキー・バリューを抽出"""
        result = {}
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                label = dt.get_text(strip=True)
                value = dd.get_text(separator=" ", strip=True)
                key = self._match_label(label)
                if key and value:
                    result[key] = self._clean_value(key, value)
        return result

    # ─── PR TIMES ───

    def _scrape_prtimes_company_info(self) -> dict:
        """PR TIMESの最新プレスリリースから会社概要を抽出"""
        # PR TIMESのURLからcompany_idを取得
        company_id = self._get_prtimes_company_id()
        if not company_id:
            return {}

        # プレスリリースを順に取得して会社概要を探す
        for release_num in range(1, 8):
            url = f"https://prtimes.jp/main/html/rd/p/{release_num:09d}.{company_id}.html"
            page = self._fetch_page(url)
            if not page:
                continue

            text = page["text"]
            if "会社概要" not in text and "企業概要" not in text:
                continue

            # 会社概要セクションのテキストを取得
            keyword = "会社概要" if "会社概要" in text else "企業概要"
            idx = text.index(keyword)
            overview_text = text[idx:idx + 1000]

            # テキストからキーバリューを抽出
            return self._parse_overview_text(overview_text)

        return {}

    def _get_prtimes_company_id(self) -> str:
        """PR TIMESのcompany_idを取得"""
        # 既存のURLから抽出
        if self.prtimes_url:
            m = re.search(r"company_id[/=](\d+)", self.prtimes_url)
            if m:
                return m.group(1)

        # 記事URLから抽出（000000001.000XXXXX.html形式）
        if self.prtimes_url and "/rd/p/" in self.prtimes_url:
            m = re.search(r"\.(\d+)\.html", self.prtimes_url)
            if m:
                return m.group(1)

        # PR TIMES検索で見つける
        return self._search_prtimes_company_id()

    def _search_prtimes_company_id(self) -> str:
        """PR TIMESの検索から企業のcompany_idを特定"""
        url = f"https://prtimes.jp/main/action.php?run=html&page=searchkey&search_word={quote(self.short_name)}"
        page = self._fetch_page(url)
        if not page:
            return ""

        soup = page["soup"]
        # 検索結果のプレスリリースリンクからcompany_idを取得
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.search(r"\.(\d{6,})\.html", href)
            if m:
                return m.group(1)

        return ""

    def _parse_overview_text(self, text: str) -> dict:
        """会社概要のフリーテキストからキーバリューを抽出"""
        result = {}
        lines = text.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # "ラベル：値" or "ラベル: 値" パターン
            for sep in ["：", ":", "　"]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        label = parts[0].strip()
                        value = parts[1].strip()
                        key = self._match_label(label)
                        if key and value:
                            result[key] = self._clean_value(key, value)
                            break

            # 特殊パターン: テキスト内の「本社：東京都...」のようなインライン情報
            if not result.get("address"):
                m = re.search(r"(?:本社|所在地)[：:]\s*(.{2,4}[都道府県].+?)(?:[、,\n]|代表)", line)
                if m:
                    result["address"] = m.group(1).strip()[:80]

            if not result.get("representative"):
                m = re.search(r"代表取締役[：:\s]*([^\s、,()（）]+(?:\s+[^\s、,()（）]+)?)", line)
                if m:
                    result["representative"] = f"代表取締役 {m.group(1).strip()}"

        return result

    # ─── ユーティリティ ───

    def _fetch_page(self, url: str) -> dict | None:
        """ページ取得"""
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                return None
            resp.encoding = resp.apparent_encoding or "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        # 不要タグ除去
        for tag in soup.select("script, style, nav, footer"):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        return {"soup": soup, "text": text, "url": url}

    @staticmethod
    def _match_label(label: str) -> str:
        """ラベルテキストを正規化キーにマッチング"""
        label = label.strip().rstrip("：:※＊* ")

        # 完全一致
        if label in _LABEL_MAP:
            return _LABEL_MAP[label]

        # 部分一致（ラベルが長い場合）
        for map_label, key in _LABEL_MAP.items():
            if map_label in label and len(map_label) >= 2:
                return key

        return ""

    @staticmethod
    def _clean_value(key: str, value: str) -> str:
        """値をクリーニング"""
        # 改行・余分な空白を正規化
        value = re.sub(r"\s+", " ", value).strip()

        # 住所: 電話番号や余計な情報を除去
        if key == "address":
            # 電話番号以降をカット
            value = re.split(r"\s*(?:TEL|Tel|tel|電話|☎|📞)", value)[0]
            # 電話番号パターンが住所の直後にある場合もカット（ただし住所内のハイフン付き番地は残す）
            value = re.split(r"\s+\d{2,4}[-ー]\d{2,4}[-ー]\d{3,4}", value)[0]
            # 2つ目の住所（事業所等）をカット：「／」「/」「 ／ 」区切り、または明示的なラベル付き
            value = re.split(r"\s*[／/]\s*(?:〒|大阪|名古屋|福岡|仙台|広島|札幌)", value)[0]
            value = re.split(r"\s+(?:支店|事業所|営業所|東京オフィス|大阪オフィス|本店)", value)[0]
            value = value.strip()[:100]
        elif key == "business_description":
            value = value[:200]
        else:
            value = value[:120]
        return value

    def get_summary(self) -> str:
        """LLMに渡すサマリーテキストを生成"""
        data = self.scrape()
        if not data:
            return ""

        parts = ["## 会社概要（公式HP / PR TIMESから取得した構造化データ）"]
        label_names = {
            "company_name": "会社名",
            "representative": "代表者",
            "established": "設立",
            "capital": "資本金",
            "revenue": "売上高",
            "employee_scale": "従業員数",
            "address": "所在地",
            "phone": "電話番号",
            "fax": "FAX",
            "email": "メールアドレス",
            "corporate_url": "URL",
            "listed": "上場区分",
            "business_description": "事業内容",
        }
        for key, label in label_names.items():
            if data.get(key):
                parts.append(f"- {label}: {data[key]}")

        return "\n".join(parts) if len(parts) > 1 else ""

    def get_structured_data(self) -> dict:
        """構造化データをそのまま返す（直接スプレッドシートに書き込み用）"""
        return self.scrape()
