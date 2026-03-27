"""問い合わせフォームURL探索"""

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from automation.form_schemas import CONTACT_URL_PATTERNS, CUSTOMER_URL_PATTERNS
from config.settings import REQUEST_HEADERS, REQUEST_TIMEOUT


class FormFinder:
    """企業HPから問い合わせフォームのURLを探索"""

    def __init__(self, base_url: str, company_name: str = "", article_url: str = ""):
        self.base_url = base_url.rstrip("/")
        self.company_name = company_name
        self.article_url = article_url  # PR TIMESのプレスリリース記事URL
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def find(self) -> list[dict]:
        """問い合わせフォームのURL候補を返す"""
        candidates = []

        # 0. PR TIMES記事から直接フォームURLと企業HPを探す
        base_domain = urlparse(self.base_url).netloc
        is_external = any(ext in base_domain for ext in ["prtimes.jp", "google.com", "news."])

        if is_external and self.article_url:
            article_forms, company_url = self._find_from_prtimes_article()
            candidates.extend(article_forms)
            if company_url:
                self.base_url = company_url.rstrip("/")

        # 0b. まだ外部サイトURLの場合、企業名から公式HPを探す
        base_domain = urlparse(self.base_url).netloc
        if any(ext in base_domain for ext in ["prtimes.jp", "google.com", "news."]):
            if self.company_name:
                real_url = self._find_company_website()
                if real_url:
                    self.base_url = real_url.rstrip("/")

        # 1. トップページからリンクを探索
        candidates.extend(self._find_from_links())

        # 2. よくあるURLパターンを直接試行
        candidates.extend(self._try_common_paths())

        # 3. 見つからなければWeb検索でフォームURLを直接探す
        if not candidates and self.company_name:
            search_forms = self._search_contact_form()
            candidates.extend(search_forms)

        # 4. それでも見つからなければLLMに推測させる
        if not candidates and self.company_name:
            llm_form = self._guess_form_url_with_llm()
            if llm_form:
                candidates.append(llm_form)

        # 重複を除去
        seen = set()
        unique = []
        for c in candidates:
            if c["url"] not in seen:
                seen.add(c["url"])
                unique.append(c)

        return unique

    def _find_from_prtimes_article(self) -> tuple[list[dict], str | None]:
        """PR TIMESの記事ページ本文から企業HPを取得"""
        candidates = []
        company_url = None
        try:
            response = self.session.get(self.article_url, timeout=REQUEST_TIMEOUT)
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "lxml")

            # 記事本文エリアのみ対象（PR TIMES共通のヘッダー/フッターを除外）
            body = soup.find("div", class_=lambda c: c and "press-release-body" in " ".join(c) if c else False)
            if not body:
                body = soup.find("article")
            if not body:
                return candidates, company_url

            excluded_domains = [
                "prtimes.jp", "google.", "facebook.", "twitter.", "instagram.",
                "youtube.", "linkedin.", "x.com", "line.me",
            ]

            contact_keywords = ["問い合わせ", "問合せ", "contact", "inquiry"]

            for link in body.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                domain = urlparse(href).netloc

                if not href.startswith("http") or not domain:
                    continue
                if any(ex in domain for ex in excluded_domains):
                    continue

                # 企業HP（外部ドメインのトップページ）
                path = urlparse(href).path.rstrip("/")
                if not company_url and (path == "" or path == "/"):
                    company_url = f"https://{domain}"

                # 問い合わせフォーム（記事本文内にある外部フォームサービスリンク）
                is_form_service = any(fs in domain for fs in [
                    "tayori.com", "formrun.com", "form.run", "forms.gle",
                    "docs.google.com", "my.site.com", "force.com",
                    "hubspot", "typeform.com",
                ])
                is_contact_text = any(kw in text for kw in contact_keywords)
                is_contact_url = any(kw in href.lower() for kw in contact_keywords)

                if is_form_service or is_contact_text or is_contact_url:
                    candidates.append({
                        "url": href,
                        "link_text": text[:40] if text else domain,
                        "source": "PR TIMES記事",
                    })

        except Exception as e:
            print(f"[FormFinder] PR TIMES記事解析エラー: {e}")

        return candidates, company_url

    def _search_contact_form(self) -> list[dict]:
        """Web検索で企業の問い合わせフォームURLを直接探す"""
        candidates = []
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()

            # 複数の検索クエリを試す
            queries = [
                f"{self.company_name} お問い合わせフォーム",
                f"{self.company_name} contact",
            ]

            seen_urls = set()
            contact_keywords = ["contact", "inquiry", "form", "問い合わせ", "問合せ", "toiawase", "otoiawase"]

            # 除外ドメイン
            excluded_domains = [
                "prtimes.jp", "google.", "youtube.", "facebook.", "twitter.",
                "instagram.", "wikipedia.", "linkedin.", "x.com", "note.com",
                "wantedly.", "en-gage.", "recruit.", "baidu.", "wikiru.",
                "yayoi-kk.", "amazon.", "rakuten.", "yahoo.", "bing.",
                "tabelog.", "gnavi.", "hotpepper.",
            ]

            # base_urlのドメイン
            base_domain = urlparse(self.base_url).netloc if self.base_url else ""

            # 企業名の短縮形（株式会社等を除去）
            short_name = self.company_name
            for prefix in ["株式会社", "有限会社", "(株)", "（株）"]:
                short_name = short_name.replace(prefix, "").strip()

            for query in queries:
                try:
                    results = list(ddgs.text(query, max_results=5, region="jp-jp"))
                except Exception:
                    continue

                for r in results:
                    url = r.get("href", "")
                    title = r.get("title", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    url_lower = url.lower()
                    domain = urlparse(url).netloc

                    # 除外ドメインチェック
                    if any(ex in domain for ex in excluded_domains):
                        continue

                    # カスタマー系を除外
                    if any(pat in url_lower for pat in CUSTOMER_URL_PATTERNS):
                        continue

                    # 問い合わせっぽいURLか
                    is_contact = any(kw in url_lower for kw in contact_keywords)

                    # ドメインの関連性を厳密にチェック
                    is_company_domain = False
                    if base_domain and base_domain == domain:
                        # base_urlと同一ドメインなら確実にOK
                        is_company_domain = True
                    elif short_name and short_name in title:
                        # 検索結果のタイトルに企業名が含まれていればOK
                        is_company_domain = True
                    elif short_name and short_name.lower() in domain.lower():
                        # ドメイン名に企業名が含まれていればOK
                        is_company_domain = True

                    if is_contact and is_company_domain:
                        if self._check_url(url):
                            candidates.append({
                                "url": url,
                                "link_text": title[:40],
                                "source": "Web検索",
                            })

        except Exception as e:
            print(f"[FormFinder] フォーム検索エラー: {e}")

        return candidates

    def _guess_form_url_with_llm(self) -> dict | None:
        """LLMに企業の法人向け問い合わせフォームURLを推測させる"""
        try:
            import anthropic
            from config.settings import ANTHROPIC_API_KEY

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": (
                        f"日本企業「{self.company_name}」（HP: {self.base_url}）の"
                        f"法人・企業向け問い合わせフォームのURLだけを1行で回答してください。"
                        f"カスタマーサポートではなく、ビジネス・法人向けの問い合わせページです。"
                        f"URLのみ、説明不要。わからない場合は「不明」と回答。"
                    ),
                }],
            )
            text = response.content[0].text.strip()
            print(f"[FormFinder] LLM form URL: {text}")
            if text.startswith("http") and "不明" not in text:
                if self._check_url(text):
                    return {
                        "url": text,
                        "link_text": "法人問い合わせ（AI推測）",
                        "source": "AI推測",
                    }
        except Exception as e:
            print(f"[FormFinder] LLM form error: {e}")
        return None

    def _find_company_website(self) -> str | None:
        """企業名から公式サイトURLを見つける"""
        # 1. PR TIMESの企業ページから実際のURLを取得
        if "prtimes.jp" in self.base_url:
            prtimes_url = self._get_url_from_prtimes()
            if prtimes_url:
                return prtimes_url

        # 2. Web検索で企業公式サイトを探す
        search_url = self._search_company_website()
        if search_url:
            return search_url

        # 3. LLMに企業ドメインを推測させる（フォールバック）
        llm_url = self._guess_url_with_llm()
        if llm_url:
            return llm_url

        return None

    def _search_company_website(self) -> str | None:
        """Web検索で企業公式サイトを探す"""
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()

            # 複数のクエリを試す
            queries = [
                f"{self.company_name} 公式サイト",
                f"{self.company_name} 会社概要",
            ]
            results = []
            for q in queries:
                try:
                    results = list(ddgs.text(q, max_results=5, region="jp-jp"))
                    if results:
                        break
                except Exception:
                    continue

            excluded_domains = [
                "prtimes.jp", "google.", "youtube.", "facebook.", "twitter.",
                "instagram.", "wikipedia.", "linkedin.", "x.com", "note.com",
                "wantedly.", "en-gage.", "recruit.", "baidu.", "wikiru.",
                "amazon.", "rakuten.", "yahoo.", "tabelog.", "gnavi.",
            ]

            # 企業名の短縮形
            short_name = self.company_name
            for prefix in ["株式会社", "有限会社", "(株)", "（株）"]:
                short_name = short_name.replace(prefix, "").strip()

            for r in results:
                url = r.get("href", "")
                title = r.get("title", "")
                domain = urlparse(url).netloc

                if any(ex in domain for ex in excluded_domains):
                    continue

                # タイトルかドメインに企業名が含まれているか確認
                if short_name not in title and short_name.lower() not in domain.lower():
                    continue

                # URLがアクセスできるか確認
                if self._check_url(url):
                    return f"https://{urlparse(url).netloc}"
        except Exception as e:
            print(f"[FormFinder] Web検索エラー: {e}")
        return None

    def _guess_url_with_llm(self) -> str | None:
        """LLMに企業名からドメインを推測させる"""
        try:
            import anthropic
            from config.settings import ANTHROPIC_API_KEY

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": f"日本企業「{self.company_name}」の公式ウェブサイトのURLだけを1行で回答してください。URLのみ、説明不要。わからない場合は「不明」と回答。",
                }],
            )
            text = response.content[0].text.strip()
            print(f"[FormFinder] LLM response: {text}")
            if text.startswith("http") and "不明" not in text:
                if self._check_url(text):
                    return text.rstrip("/")
                # URLが失敗した場合、www有無やco.jp/.jpの変形を試す
                parsed = urlparse(text)
                domain = parsed.netloc
                base = domain.replace("www.", "")
                variations = [
                    f"https://www.{base}",
                    f"https://{base}",
                ]
                # .co.jpを.jpに、またはその逆
                if base.endswith(".co.jp"):
                    variations.append(f"https://www.{base.replace('.co.jp', '.jp')}")
                elif base.endswith(".jp"):
                    variations.append(f"https://www.{base.replace('.jp', '.co.jp')}")
                # -group等のバリエーション
                name_part = base.split(".")[0]
                for suffix in ["-group.co.jp", "-holdings.co.jp", "-hd.co.jp"]:
                    variations.append(f"https://www.{name_part}{suffix}")
                for v in variations:
                    if v != text and self._check_url(v):
                        print(f"[FormFinder] URL variation found: {v}")
                        return v.rstrip("/")
                print(f"[FormFinder] URL check failed: {text}")
        except Exception as e:
            print(f"[FormFinder] LLM error: {e}")
        return None

    def _get_url_from_prtimes(self) -> str | None:
        """PR TIMESの企業ページからリンク先の公式HPを取得"""
        try:
            response = self.session.get(self.base_url, timeout=REQUEST_TIMEOUT)
            response.encoding = "utf-8"
            # PR TIMESのプレスリリース記事からリンク先を探す
            soup = BeautifulSoup(response.text, "lxml")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                domain = urlparse(href).netloc
                excluded = ["prtimes.jp", "google.", "facebook.", "twitter.",
                            "instagram.", "youtube.", "linkedin.", "x.com", ""]
                if href.startswith("http") and not any(ex in domain for ex in excluded):
                    return f"https://{domain}"
        except Exception:
            pass
        return None

    def _find_from_links(self) -> list[dict]:
        """トップページのリンクからフォームURLを探す"""
        try:
            response = self.session.get(
                self.base_url, timeout=REQUEST_TIMEOUT, allow_redirects=True
            )
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        candidates = []

        contact_keywords = [
            "お問い合わせ",
            "お問合せ",
            "問い合わせ",
            "問合せ",
            "Contact",
            "contact",
            "CONTACT",
            "ご相談",
            "資料請求",
            "法人のお客様",
            "企業の方",
        ]

        # カスタマー・求人向けを除外するキーワード
        customer_keywords = [
            "カスタマー",
            "お客様サポート",
            "ヘルプ",
            "よくある質問",
            "FAQ",
            "返品",
            "配送",
            "注文",
            "購入",
            "求人",
            "エントリー",
            "お気に入り",
            "キャリア",
            "転職",
            "応募",
        ]

        # 外部フォームサービスのドメイン（Salesforce, Google Forms等）
        external_form_domains = [
            "my.site.com", "force.com", "salesforce.com",
            "forms.gle", "docs.google.com/forms",
            "form.run", "formrun.com", "tayori.com",
            "hubspot", "typeform.com", "formbridge",
        ]

        candidates = self._extract_contact_links(
            soup, contact_keywords, customer_keywords, external_form_domains
        )

        # サブページ探索: トップページで見つからない場合、主要ページを1段深く探す
        if not candidates:
            subpage_keywords = ["会社概要", "about", "企業情報", "corporate"]
            base_domain = urlparse(self.base_url).netloc
            subpages = []
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True).lower()
                href = link["href"]
                if any(kw in text or kw in href.lower() for kw in subpage_keywords):
                    full_url = urljoin(self.base_url + "/", href)
                    if urlparse(full_url).netloc == base_domain:
                        subpages.append(full_url)

            for subpage_url in subpages[:3]:  # 最大3ページまで
                try:
                    resp = self.session.get(subpage_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    sub_soup = BeautifulSoup(resp.text, "lxml")
                    candidates.extend(self._extract_contact_links(
                        sub_soup, contact_keywords, customer_keywords, external_form_domains
                    ))
                except requests.RequestException:
                    continue
                if candidates:
                    break

        return candidates

    def _extract_contact_links(self, soup, contact_keywords, customer_keywords, external_form_domains) -> list[dict]:
        """BeautifulSoupオブジェクトから問い合わせリンクを抽出"""
        candidates = []
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            href_lower = href.lower()

            # カスタマー向けURLは除外
            if any(pat in href_lower for pat in CUSTOMER_URL_PATTERNS):
                continue
            if any(kw in text for kw in customer_keywords):
                continue

            is_contact_link = any(kw in text for kw in contact_keywords) or any(
                pat in href_lower for pat in CONTACT_URL_PATTERNS
            )
            is_external_form = any(domain in href_lower for domain in external_form_domains)

            if is_contact_link or is_external_form:
                full_url = urljoin(self.base_url + "/", href)
                link_domain = urlparse(full_url).netloc
                base_domain = urlparse(self.base_url).netloc

                # 同一ドメイン or 外部フォームサービス
                if link_domain == base_domain or any(domain in link_domain for domain in external_form_domains):
                    candidates.append(
                        {
                            "url": full_url,
                            "link_text": text,
                            "source": "リンク探索",
                        }
                    )

        return candidates

    def _try_common_paths(self) -> list[dict]:
        """一般的なURLパターンを直接試行"""
        candidates = []

        for path in CONTACT_URL_PATTERNS:
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            try:
                response = self.session.head(
                    url, timeout=REQUEST_TIMEOUT, allow_redirects=True
                )
                if response.status_code == 200:
                    final_url = response.url.lower()
                    # カスタマー向けURLは除外
                    if any(pat in final_url for pat in CUSTOMER_URL_PATTERNS):
                        continue
                    # 同一ドメインか確認
                    if urlparse(response.url).netloc == urlparse(self.base_url).netloc:
                        candidates.append(
                            {
                                "url": response.url,
                                "link_text": path,
                                "source": "パターン試行",
                            }
                        )
            except requests.RequestException:
                continue

        return candidates

    def _check_url(self, url: str) -> bool:
        """URLがアクセス可能か確認（HEAD失敗時はGETでフォールバック）"""
        try:
            r = self.session.head(url, timeout=5, allow_redirects=True)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        # HEADが失敗した場合、GETで再試行
        try:
            r = self.session.get(url, timeout=7, allow_redirects=True)
            return r.status_code == 200
        except Exception:
            return False

    def has_form(self, url: str) -> bool:
        """指定URLにフォームが存在するか確認"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.encoding = response.apparent_encoding or "utf-8"
            soup = BeautifulSoup(response.text, "lxml")
            forms = soup.find_all("form")
            return len(forms) > 0
        except requests.RequestException:
            return False
