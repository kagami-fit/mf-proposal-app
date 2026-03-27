"""企業HPから問い合わせ情報を抽出"""

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT


class ContactScraper:
    """企業HPから連絡先情報（メール・電話・FAX・住所・問い合わせURL）を抽出"""

    # 問い合わせページの候補パス
    CONTACT_PATHS = [
        "/contact",
        "/contact-us",
        "/inquiry",
        "/enquiry",
        "/contactus",
        "/お問い合わせ",
        "/お問合せ",
        "/toiawase",
        "/form",
        "/support",
        "/access",
        "/company",
        "/company/overview",
        "/about",
        "/corporate",
        "/corporate/overview",
        "/",
    ]

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def scrape(self) -> dict:
        """問い合わせ情報を抽出して返す"""
        result = {
            "emails": [],
            "phones": [],
            "fax": [],
            "address": "",
            "contact_url": "",
            "contact_form_url": "",
        }

        for path in self.CONTACT_PATHS:
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            page_data = self._fetch_page(url)
            if not page_data:
                continue

            soup = page_data["soup"]
            text = page_data["text"]
            html = page_data["html"]

            # メールアドレス抽出
            emails = self._extract_emails(text, html)
            for e in emails:
                if e not in result["emails"]:
                    result["emails"].append(e)

            # 電話番号抽出
            phones = self._extract_phones(text)
            for p in phones:
                if p not in result["phones"]:
                    result["phones"].append(p)

            # FAX抽出
            faxes = self._extract_fax(text)
            for f in faxes:
                if f not in result["fax"]:
                    result["fax"].append(f)

            # 住所抽出
            if not result["address"]:
                result["address"] = self._extract_address(text)

            # 問い合わせフォームURL検出
            if not result["contact_form_url"]:
                form_url = self._find_contact_form(soup, url)
                if form_url:
                    result["contact_form_url"] = form_url

            # 問い合わせページURL
            if not result["contact_url"] and path != "/":
                if any(kw in path for kw in ["contact", "inquiry", "問い合わせ", "問合せ", "toiawase"]):
                    result["contact_url"] = url

        # 問い合わせページへのリンクをトップページから探す
        if not result["contact_url"]:
            result["contact_url"] = self._find_contact_link()

        return result

    def _fetch_page(self, url: str) -> dict | None:
        """ページを取得"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if urlparse(response.url).netloc != urlparse(self.base_url).netloc:
                return None
            if response.status_code != 200:
                return None
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")
        text = soup.get_text(separator="\n", strip=True)

        return {"soup": soup, "text": text, "html": response.text, "url": url}

    def _extract_emails(self, text: str, html: str) -> list[str]:
        """メールアドレスを抽出"""
        emails = set()

        pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

        # テキストからの抽出
        for match in re.finditer(pattern, text):
            email = match.group(0).lower()
            if not self._is_junk_email(email):
                emails.add(email)

        # mailto: リンクからの抽出
        for match in re.finditer(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html):
            email = match.group(1).lower()
            if not self._is_junk_email(email):
                emails.add(email)

        # HTML属性内のメールアドレス（data-email, value, content等）
        for match in re.finditer(r'(?:data-email|value|content)\s*=\s*["\'](' + pattern + r')["\']', html):
            email = match.group(1).lower()
            if not self._is_junk_email(email):
                emails.add(email)

        # JavaScript内の難読化メール（"user" + "@" + "domain.co.jp" 等）
        for match in re.finditer(
            r'["\']([a-zA-Z0-9._%+\-]+)["\']'
            r'\s*\+\s*["\']@["\']'
            r'\s*\+\s*["\']([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})["\']',
            html,
        ):
            email = f"{match.group(1)}@{match.group(2)}".lower()
            if not self._is_junk_email(email):
                emails.add(email)

        return sorted(emails)

    @staticmethod
    def _is_junk_email(email: str) -> bool:
        """画像ファイル・トラッキング等の偽メールを除外"""
        # ドメイン部分で判定（サブストリング誤判定を防ぐ）
        local, _, domain = email.partition("@")
        if not domain:
            return True

        junk_domains = [
            "example.com", "test.com", "dummy.com",
            "wixpress.com", "sentry.io", "googleapis.com",
            "sentry-next.wixpress.com",
        ]
        if domain in junk_domains:
            return True

        junk_local_patterns = ["noreply", "no-reply", "mailer-daemon", "postmaster"]
        if local in junk_local_patterns:
            return True

        # 画像ファイル名が誤抽出されたケース（ローカル部にファイル拡張子）
        if re.search(r'\.(png|jpg|gif|svg|webp)$', local):
            return True

        return False

    def _extract_phones(self, text: str) -> list[str]:
        """電話番号を抽出（日本の番号形式）"""
        phones = set()

        patterns = [
            # 03-1234-5678, 0120-123-456
            r'(?:TEL|Tel|tel|電話|☎|📞)[:\s：・]*(\d{2,4}[\-ー]\d{2,4}[\-ー]\d{3,4})',
            # 括弧付き: (03) 1234-5678
            r'(?:TEL|Tel|tel|電話)[:\s：・]*\((\d{2,4})\)\s*(\d{2,4}[\-ー]\d{3,4})',
            # ラベルなし: 0X-XXXX-XXXX パターン
            r'(?<![0-9\-])(\d{2,4}[\-ー]\d{2,4}[\-ー]\d{3,4})(?![0-9\-])',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                phone = match.group(0)
                # TEL: 等のラベル部分を除去
                phone = re.sub(r'^(?:TEL|Tel|tel|電話|☎|📞)[:\s：・]*', '', phone)
                phone = phone.strip()
                # FAXっぽいものは除外（FAXラベルの直後）
                context_start = max(0, match.start() - 10)
                context = text[context_start:match.start()].upper()
                if "FAX" in context:
                    continue
                if phone and len(phone) >= 10:
                    phones.add(phone)

        return sorted(phones)

    def _extract_fax(self, text: str) -> list[str]:
        """FAX番号を抽出"""
        faxes = set()
        pattern = r'(?:FAX|Fax|fax|ファックス|ＦＡＸ)[:\s：・]*(\d{2,4}[\-ー]\d{2,4}[\-ー]\d{3,4})'
        for match in re.finditer(pattern, text):
            fax = match.group(1).strip()
            if fax and len(fax) >= 10:
                faxes.add(fax)
        return sorted(faxes)

    def _extract_address(self, text: str) -> str:
        """住所を抽出（日本の住所形式）"""
        # 全角数字・ハイフンを半角に正規化
        norm = text.translate(str.maketrans('０１２３４５６７８９ー－', '0123456789--'))

        # パターン1: 〒XXX-XXXX + 住所（郵便番号の後に都道府県がある場合）
        match = re.search(
            r'(〒?\s*\d{3}[\-]\d{4})\s*'
            r'((?:東京都|北海道|(?:京都|大阪)府|[^\s]{2,3}県)'
            r'[^\n\r]{5,60})',
            norm,
        )
        if match:
            addr = f"{match.group(1)} {match.group(2)}".strip()
            return self._clean_address(addr)

        # パターン2: 〒XXX-XXXX + 住所（都道府県なし、市区町から始まる場合）
        match = re.search(
            r'(〒?\s*\d{3}[\-]\d{4})\s*'
            r'([^\n\r]{2,10}[市区町村郡][^\n\r]{3,50})',
            norm,
        )
        if match:
            addr = f"{match.group(1)} {match.group(2)}".strip()
            return self._clean_address(addr)

        # パターン3: 都道府県から始まるパターン（郵便番号なし）
        prefectures = (
            '東京都|北海道|京都府|大阪府|'
            '青森県|岩手県|宮城県|秋田県|山形県|福島県|'
            '茨城県|栃木県|群馬県|埼玉県|千葉県|神奈川県|'
            '新潟県|富山県|石川県|福井県|山梨県|長野県|'
            '岐阜県|静岡県|愛知県|三重県|'
            '滋賀県|兵庫県|奈良県|和歌山県|'
            '鳥取県|島根県|岡山県|広島県|山口県|'
            '徳島県|香川県|愛媛県|高知県|'
            '福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県'
        )
        match = re.search(
            rf'((?:{prefectures})[^\n\r]{{5,60}})',
            norm,
        )
        if match:
            addr = match.group(1).strip()
            return self._clean_address(addr)

        return ""

    @staticmethod
    def _clean_address(addr: str) -> str:
        """抽出した住所から余分な情報を除去"""
        # 改行を空白に
        addr = re.sub(r'[\n\r]+', ' ', addr)
        # 電話番号・FAX以降をカット
        addr = re.split(r'\s*(?:TEL|Tel|tel|電話|FAX|Fax|fax|☎|📞)', addr)[0]
        # 電話番号パターン（XX-XXXX-XXXX）が続く場合もカット
        addr = re.split(r'\s+\d{2,4}[-]\d{2,4}[-]\d{3,4}', addr)[0]
        return addr.strip()[:100]

    def _find_contact_form(self, soup: BeautifulSoup, page_url: str) -> str:
        """ページ内のフォーム要素やお問い合わせフォームリンクを検出"""
        # formタグ検出
        form = soup.find("form")
        if form:
            action = form.get("action", "")
            if action and not action.startswith("#") and not action.startswith("javascript"):
                if not action.startswith("http"):
                    return urljoin(page_url, action)
                return action
            return page_url

        # お問い合わせリンク
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if any(kw in text for kw in ["お問い合わせ", "お問合せ", "問い合わせ", "Contact", "CONTACT"]):
                if not href.startswith("http"):
                    href = urljoin(page_url, href)
                return href

        return ""

    def _find_contact_link(self) -> str:
        """トップページからお問い合わせページへのリンクを探す"""
        page = self._fetch_page(self.base_url)
        if not page:
            return ""

        soup = page["soup"]
        contact_keywords = [
            "お問い合わせ", "お問合せ", "問い合わせ", "問合せ",
            "Contact", "CONTACT", "contact",
        ]

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if any(kw in text for kw in contact_keywords):
                if not href.startswith("http"):
                    href = urljoin(self.base_url, href)
                # 自社ドメイン内のリンクのみ
                if urlparse(href).netloc == urlparse(self.base_url).netloc or not urlparse(href).netloc:
                    return href

        return ""

    def get_contact_info(self) -> dict:
        """整形済みの連絡先情報を返す"""
        raw = self.scrape()
        return {
            "email": " / ".join(raw["emails"][:3]) if raw["emails"] else "",
            "phone": " / ".join(raw["phones"][:3]) if raw["phones"] else "",
            "fax": " / ".join(raw["fax"][:2]) if raw["fax"] else "",
            "address": raw["address"],
            "contact_url": raw["contact_url"] or raw["contact_form_url"],
            "contact_form_url": raw["contact_form_url"],
        }
