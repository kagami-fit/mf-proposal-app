"""Playwrightフォーム自動入力"""

import json
from pathlib import Path

import anthropic
from playwright.sync_api import Page, sync_playwright

from automation.form_schemas import FIELD_PATTERNS, SUBMIT_BUTTON_TEXTS
from config.prompts import FORM_FIELD_MAPPING_PROMPT
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MAX_TOKENS, CLAUDE_MODEL


class FormFiller:
    """Playwrightを使用してフォームに自動入力"""

    def __init__(self):
        self.claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def fill_form(
        self,
        form_url: str,
        sender_info: dict,
        proposal_subject: str,
        proposal_body: str,
        screenshot_path: str | None = None,
        headless: bool = True,
    ) -> dict:
        """フォームに自動入力して結果を返す（送信はしない）

        Args:
            form_url: フォームのURL
            sender_info: 送信者情報 {"company_name", "name", "email", "phone", "name_kana"}
            proposal_subject: 提案の件名
            proposal_body: 提案の本文
            screenshot_path: スクリーンショット保存先
            headless: ヘッドレスモードで実行するか

        Returns:
            {"success": bool, "filled_fields": dict, "screenshot": str, "errors": list}
        """
        result = {
            "success": False,
            "filled_fields": {},
            "screenshot": "",
            "errors": [],
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                locale="ja-JP",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()

            try:
                page.goto(form_url, wait_until="networkidle", timeout=30000)

                # フォームフィールドを検出
                form_fields = self._detect_fields(page)
                if not form_fields:
                    result["errors"].append("フォームフィールドが検出できませんでした")
                    return result

                # LLMでフィールドマッピングを生成
                mapping = self._get_field_mapping(
                    form_fields, sender_info, proposal_subject, proposal_body
                )

                # LLMマッピングが空またはNoneの場合、ルールベースにフォールバック
                if not mapping:
                    mapping = self._rule_based_mapping(
                        form_fields, sender_info, proposal_subject, proposal_body
                    )

                # LLMの結果もルールベースの結果もマージ（ルールベースで補完）
                rule_mapping = self._rule_based_mapping(
                    form_fields, sender_info, proposal_subject, proposal_body
                )
                for k, v in rule_mapping.items():
                    if k not in mapping:
                        mapping[k] = v

                # フォーム入力を実行
                filled = self._apply_mapping(page, mapping)
                result["filled_fields"] = filled

                # スクリーンショット撮影
                if screenshot_path is None:
                    screenshot_path = str(
                        Path("screenshots")
                        / f"form_{form_url.split('//')[-1].replace('/', '_')}.png"
                    )

                Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=screenshot_path, full_page=True)
                result["screenshot"] = screenshot_path
                result["success"] = True

            except Exception as e:
                result["errors"].append(f"フォーム入力中にエラー: {str(e)}")
            finally:
                browser.close()

        return result

    def open_filled_form(
        self,
        form_url: str,
        sender_info: dict,
        proposal_subject: str,
        proposal_body: str,
    ) -> None:
        """フォーム入力後にブラウザを開いたまま待機（人間が確認・送信用）"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(locale="ja-JP")
            page = context.new_page()

            page.goto(form_url, wait_until="networkidle", timeout=30000)

            form_fields = self._detect_fields(page)
            mapping = self._rule_based_mapping(
                form_fields, sender_info, proposal_subject, proposal_body
            )
            self._apply_mapping(page, mapping)

            # ユーザーがブラウザを閉じるまで待機
            print("ブラウザで内容を確認してください。ブラウザを閉じると処理が続行されます。")
            page.wait_for_event("close", timeout=0)
            browser.close()

    def submit_form(
        self,
        form_url: str,
        sender_info: dict,
        proposal_subject: str,
        proposal_body: str,
        screenshot_path: str | None = None,
    ) -> dict:
        """フォームに入力して送信する"""
        result = {
            "success": False,
            "screenshot": "",
            "errors": [],
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="ja-JP")
            page = context.new_page()

            try:
                page.goto(form_url, wait_until="networkidle", timeout=30000)

                form_fields = self._detect_fields(page)
                mapping = self._rule_based_mapping(
                    form_fields, sender_info, proposal_subject, proposal_body
                )
                self._apply_mapping(page, mapping)

                # 送信ボタンをクリック
                submitted = self._click_submit(page)
                if not submitted:
                    result["errors"].append("送信ボタンが見つかりませんでした")
                    return result

                # 送信後のページ読み込みを待機
                page.wait_for_load_state("networkidle", timeout=15000)

                # 送信完了のスクリーンショット
                if screenshot_path:
                    Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=screenshot_path, full_page=True)
                    result["screenshot"] = screenshot_path

                result["success"] = True

            except Exception as e:
                result["errors"].append(f"フォーム送信中にエラー: {str(e)}")
            finally:
                browser.close()

        return result

    def _detect_fields(self, page: Page) -> list[dict]:
        """ページからフォームフィールドを検出"""
        return page.evaluate(
            """() => {
            const fields = [];
            const inputs = document.querySelectorAll(
                'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select'
            );
            let idx = 0;

            function findLabel(el) {
                // 1. for属性で紐づくlabel
                if (el.id) {
                    const forLabel = document.querySelector(`label[for="${el.id}"]`);
                    if (forLabel) return forLabel.textContent.trim();
                }
                // 2. 親のlabel
                const parentLabel = el.closest('label');
                if (parentLabel) return parentLabel.textContent.trim();
                // 3. aria-label
                const ariaLabel = el.getAttribute('aria-label');
                if (ariaLabel) return ariaLabel;
                // 4. 直前の兄弟要素
                const prev = el.previousElementSibling;
                if (prev && ['LABEL', 'SPAN', 'DIV', 'P'].includes(prev.tagName)) {
                    return prev.textContent.trim();
                }
                return '';
            }

            function findRowLabel(el) {
                // フォーム行の親要素からラベルテキストを抽出
                // 段階的に親を遡り、ラベルが含まれる最小の行要素を見つける
                const rowSelectors = [
                    '.form-group', '.slds-form-element', 'tr',
                    '[class*="field"]', '[class*="item"]',
                ];
                let row = null;
                for (const sel of rowSelectors) {
                    row = el.closest(sel);
                    if (row) break;
                }
                if (!row) {
                    // フォールバック: 2-3階層上の親を使う
                    row = el.parentElement?.parentElement;
                }
                if (!row) return '';

                // 行内のラベル的要素を探す
                const labelSelectors = [
                    'label', 'th', '.label', '.col-md-4', '.form-label',
                    '[class*="label"]', '[class*="title"]', '[class*="heading"]',
                ];
                for (const sel of labelSelectors) {
                    const labelEl = row.querySelector(sel);
                    if (labelEl) {
                        const text = labelEl.textContent.trim();
                        // 「必須」「任意」を除去して返す
                        const cleaned = text.replace(/必須|任意/g, '').trim();
                        if (cleaned) return cleaned;
                    }
                }

                // 行全体のテキストから項目名を抽出
                const rowText = row.textContent.trim();
                const match = rowText.match(/^(.+?)(?:必須|任意)/);
                if (match) return match[1].trim();
                return rowText.substring(0, 30);
            }

            inputs.forEach(el => {
                let label = findLabel(el);
                // ラベルが取れなかった場合、行全体から探す
                if (!label) {
                    label = findRowLabel(el);
                }

                const uniqueId = el.id || el.name || `__field_${idx}`;

                // 必須判定: required属性 or 行内に「必須」テキスト
                let isRequired = el.required;
                if (!isRequired) {
                    const rowSelectors2 = ['.form-group', '.slds-form-element', 'tr', '[class*="field"]', '[class*="item"]'];
                    let row2 = null;
                    for (const sel of rowSelectors2) {
                        row2 = el.closest(sel);
                        if (row2) break;
                    }
                    if (!row2) row2 = el.parentElement?.parentElement;
                    if (row2 && row2.textContent.includes('必須')) {
                        isRequired = true;
                    }
                }

                fields.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    uniqueId: uniqueId,
                    placeholder: el.placeholder || '',
                    label: label,
                    required: isRequired,
                    options: el.tagName === 'SELECT'
                        ? Array.from(el.options).map(o => ({value: o.value, text: o.textContent.trim()}))
                        : [],
                    index: idx,
                });
                idx++;
            });

            // チェックボックス（重複除去）
            document.querySelectorAll('input[type="checkbox"]').forEach(el => {
                const alreadyFound = Array.from(inputs).includes(el);
                if (alreadyFound) return;

                let label = findLabel(el);
                if (!label) label = findRowLabel(el);

                fields.push({
                    tag: 'input',
                    type: 'checkbox',
                    name: el.name || '',
                    id: el.id || '',
                    uniqueId: el.id || el.name || `__checkbox_${idx}`,
                    placeholder: '',
                    label: label,
                    required: el.required,
                    options: [],
                    index: idx,
                });
                idx++;
            });

            // ラジオボタングループ（name単位でグループ化）
            const radioGroups = {};
            document.querySelectorAll('input[type="radio"]').forEach(el => {
                const groupName = el.name;
                if (!groupName) return;
                if (!radioGroups[groupName]) {
                    radioGroups[groupName] = {
                        name: groupName,
                        options: [],
                        label: '',
                        required: false,
                    };
                    // グループのラベルを取得
                    let groupLabel = findRowLabel(el);
                    if (!groupLabel) groupLabel = findLabel(el);
                    radioGroups[groupName].label = groupLabel;
                    radioGroups[groupName].required = el.required;
                }
                const optLabel = el.parentElement ? el.parentElement.textContent.trim() : el.value;
                radioGroups[groupName].options.push({
                    value: el.value,
                    text: optLabel,
                    id: el.id || '',
                });
            });
            Object.values(radioGroups).forEach(group => {
                fields.push({
                    tag: 'input',
                    type: 'radio',
                    name: group.name,
                    id: '',
                    uniqueId: `__radio_${group.name}`,
                    placeholder: '',
                    label: group.label,
                    required: group.required,
                    options: group.options,
                    index: idx,
                });
                idx++;
            });

            return fields;
        }"""
        )

    def _get_field_mapping(
        self,
        form_fields: list[dict],
        sender_info: dict,
        subject: str,
        body: str,
    ) -> dict | None:
        """LLMを使用してフォームフィールドのマッピングを生成"""
        try:
            prompt = FORM_FIELD_MAPPING_PROMPT.format(
                form_fields=json.dumps(form_fields, ensure_ascii=False, indent=2),
                company_name=sender_info.get("company_name", ""),
                sender_name=sender_info.get("name", ""),
                sender_name_kana=sender_info.get("name_kana", ""),
                sender_email=sender_info.get("email", ""),
                sender_phone=sender_info.get("phone", ""),
                sender_department=sender_info.get("department", ""),
                subject=subject,
                body=body,
            )
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception:
            return None

    def _rule_based_mapping(
        self,
        form_fields: list[dict],
        sender_info: dict,
        subject: str,
        body: str,
    ) -> dict:
        """ルールベースのフォームフィールドマッピング"""
        mapping = {}

        # 氏名を姓名に分割
        full_name = sender_info.get("name", "")
        name_parts = full_name.split() if " " in full_name else ([full_name[:1], full_name[1:]] if len(full_name) >= 2 else [full_name, ""])
        full_kana = sender_info.get("name_kana", "")
        kana_parts = full_kana.split() if " " in full_kana else ([full_kana[:2], full_kana[2:]] if len(full_kana) >= 3 else [full_kana, ""])

        # 電話番号を分割
        full_phone = sender_info.get("phone", "")
        phone_parts = full_phone.replace("-", " ").replace("−", " ").split()
        if len(phone_parts) < 3 and full_phone:
            # ハイフンなしの場合、前3-中4-後4で分割
            digits = full_phone.replace("-", "").replace("−", "")
            if len(digits) >= 10:
                phone_parts = [digits[:3], digits[3:7], digits[7:]]

        # 郵便番号を分割
        full_zipcode = sender_info.get("zipcode", "")
        zip_parts = full_zipcode.replace("-", " ").replace("−", " ").split()

        input_values = {
            "company_name": sender_info.get("company_name", ""),
            "name": full_name,
            "name_sei": sender_info.get("name_sei", "") or name_parts[0],
            "name_mei": sender_info.get("name_mei", "") or (name_parts[1] if len(name_parts) > 1 else ""),
            "name_kana": full_kana,
            "name_kana_sei": kana_parts[0],
            "name_kana_mei": kana_parts[1] if len(kana_parts) > 1 else "",
            "email": sender_info.get("email", ""),
            "email_confirm": sender_info.get("email", ""),  # 確認用も同じ値
            "phone": full_phone,
            "phone1": phone_parts[0] if len(phone_parts) >= 3 else "",
            "phone2": phone_parts[1] if len(phone_parts) >= 3 else "",
            "phone3": phone_parts[2] if len(phone_parts) >= 3 else "",
            "department": sender_info.get("department", ""),
            "zipcode": full_zipcode,
            "zipcode1": zip_parts[0] if len(zip_parts) >= 2 else "",
            "zipcode2": zip_parts[1] if len(zip_parts) >= 2 else "",
            "address_prefecture": sender_info.get("prefecture", ""),
            "address_city": sender_info.get("address", ""),
            "address_building": sender_info.get("building", ""),
            "subject": subject,
            "message": body,
        }

        # 連続するtel/zipフィールドを検出して分割対応
        tel_fields = []
        zip_fields = []
        email_fields = []
        for i, field in enumerate(form_fields):
            ftype = field.get("type", "").lower()
            name = field.get("name", "").lower()
            label = field.get("label", "")
            if ftype == "tel" or any(p in name for p in ["tel", "phone"]):
                tel_fields.append((i, field))
            if "zip" in name or "postal" in name or "郵便" in label:
                zip_fields.append((i, field))
            if ftype == "email" or "mail" in name:
                email_fields.append((i, field))

        # 同じラベル(電話番号)行内に3つのtelフィールドがある場合、phone1/2/3として扱う
        if len(tel_fields) >= 3:
            # 隣接する3つのtelフィールドをphone1/2/3にマッピング
            for j in range(len(tel_fields) - 2):
                idx1, idx2, idx3 = tel_fields[j][0], tel_fields[j+1][0], tel_fields[j+2][0]
                if idx2 - idx1 <= 2 and idx3 - idx2 <= 2:  # 隣接している
                    s1 = self._get_selector(tel_fields[j][1])
                    s2 = self._get_selector(tel_fields[j+1][1])
                    s3 = self._get_selector(tel_fields[j+2][1])
                    if s1 and phone_parts and len(phone_parts) >= 3:
                        mapping[s1] = phone_parts[0]
                        mapping[s2] = phone_parts[1]
                        mapping[s3] = phone_parts[2]
                    break

        # 2つのzipフィールドがある場合
        if len(zip_fields) >= 2:
            idx1, idx2 = zip_fields[0][0], zip_fields[1][0]
            if idx2 - idx1 <= 2:
                s1 = self._get_selector(zip_fields[0][1])
                s2 = self._get_selector(zip_fields[1][1])
                if s1 and zip_parts and len(zip_parts) >= 2:
                    mapping[s1] = zip_parts[0]
                    mapping[s2] = zip_parts[1]

        # 2つのemailフィールドがある場合、2つ目は確認用
        if len(email_fields) >= 2:
            s2 = self._get_selector(email_fields[1][1])
            if s2:
                mapping[s2] = sender_info.get("email", "")

        for field in form_fields:
            selector = self._get_selector(field)
            if not selector:
                continue
            # 既にマッピング済み（分割フィールド）はスキップ
            if selector in mapping:
                continue

            matched_type = self._match_field_type(field)
            if matched_type and matched_type in input_values:
                value = input_values[matched_type]
                if value:
                    mapping[selector] = value
            elif field["type"] == "checkbox":
                # プライバシーポリシー同意チェックボックスは自動チェック
                label = field.get("label", "")
                agreement_keywords = FIELD_PATTERNS["privacy_agreement"]["labels"] + [
                    "同意します", "同意する", "読んで同意", "確認しました", "了承",
                ]
                if any(kw in label for kw in agreement_keywords):
                    mapping[selector] = "__checkbox__"
            elif field["type"] == "radio":
                # ラジオボタンの自動選択
                label = field.get("label", "").lower()
                options = field.get("options", [])
                if not options:
                    continue
                # 性別: 法人営業では不要なので「無回答」を優先、なければ最後の選択肢
                if any(kw in label for kw in ["性別", "gender"]):
                    selected = None
                    for opt in options:
                        if any(kw in opt["text"] for kw in ["無回答", "回答しない", "その他", "未回答"]):
                            selected = opt
                            break
                    if not selected:
                        selected = options[-1]  # 最後の選択肢
                    mapping[f"__radio__{field['name']}__{selected['value']}"] = "__radio__"
                # お問い合わせ種別: ビジネス系を選択
                elif any(kw in label for kw in ["問い合わせ", "種別", "用件", "カテゴリ"]):
                    business_keywords = ["サービス", "提携", "協業", "法人", "ビジネス", "その他", "パートナー"]
                    selected = None
                    for opt in options:
                        if any(kw in opt["text"] for kw in business_keywords):
                            selected = opt
                            break
                    if not selected:
                        selected = options[-1]
                    mapping[f"__radio__{field['name']}__{selected['value']}"] = "__radio__"

        return mapping

    def _match_field_type(self, field: dict) -> str | None:
        """フィールド情報からフィールドタイプを推定"""
        label = field.get("label", "")
        name = field.get("name", "").lower()
        id_ = field.get("id", "").lower()
        placeholder = field.get("placeholder", "")
        field_type = field.get("type", "").lower()

        # メールアドレスはtype属性で判定
        if field_type == "email":
            # 確認用メールかどうか判定
            confirm_hints = ["confirm", "確認", "再入力", "kakunin", "email2", "mail2"]
            if any(h in name or h in id_ or h in label.lower() for h in confirm_hints):
                return "email_confirm"
            return "email"
        if field_type == "tel":
            # 分割電話番号の判定
            if any(p in name or p in id_ for p in ["tel1", "phone1", "tel-1"]):
                return "phone1"
            if any(p in name or p in id_ for p in ["tel2", "phone2", "tel-2"]):
                return "phone2"
            if any(p in name or p in id_ for p in ["tel3", "phone3", "tel-3"]):
                return "phone3"
            return "phone"

        # textareaはメッセージ
        if field.get("tag") == "textarea":
            return "message"

        # ラベルが明確にフルネーム/フリガナ全体を示す場合、先に判定
        full_name_labels = ["お名前", "氏名", "ご担当者名", "担当者名"]
        kana_labels = ["フリガナ", "ふりがな", "カナ", "お名前フリガナ", "お名前（フリガナ）"]
        if any(kw in label for kw in kana_labels):
            return "name_kana"
        if any(label.startswith(kw) or label == kw for kw in full_name_labels):
            # 「お名前」で始まり「フリガナ」「カナ」を含まない場合はフルネーム
            if not any(kw in label for kw in ["フリガナ", "ふりがな", "カナ"]):
                return "name"

        # placeholder直接マッチ（Salesforce等でラベルが無い場合）
        ph = placeholder.lower()
        if ph in ["姓", "せい"]:
            return "name_sei"
        if ph in ["名", "めい"]:
            return "name_mei"
        if "セイ" in placeholder:
            return "name_kana_sei"
        if "メイ" in placeholder:
            return "name_kana_mei"
        if any(p in ph for p in ["@", "example", "email", "mail"]):
            return "email"
        if any(p in ph for p in ["090", "03-", "電話", "tel"]):
            return "phone"
        if any(p in ph for p in ["郵便"]):
            return "zipcode"

        # 具体的なパターンを先にチェック（フリガナ > 名前、確認メール > メール等）
        # 順序が重要: より限定的なパターンから先にマッチさせる
        priority_order = [
            "name_kana_sei", "name_kana_mei", "name_kana",  # フリガナ系を先に
            "name_sei", "name_mei",  # 姓名分割を先に
            "email_confirm",  # 確認メールを先に
            "phone1", "phone2", "phone3",  # 分割電話を先に
            "zipcode1", "zipcode2",  # 分割郵便番号を先に
            "company_name", "department",
            "name",  # 「お名前」は最後
            "email", "phone", "zipcode",
            "address_prefecture", "address_city", "address_building",
            "gender",
            "subject", "inquiry_type", "message",
        ]

        for type_name in priority_order:
            if type_name not in FIELD_PATTERNS:
                continue
            patterns = FIELD_PATTERNS[type_name]
            if any(p in label for p in patterns["labels"]):
                return type_name
            if any(p in name or p in id_ for p in patterns["attributes"]):
                return type_name
            if patterns["placeholders"] and any(p in placeholder for p in patterns["placeholders"]):
                return type_name

        return None

    def _get_selector(self, field: dict) -> str:
        """フィールドのCSSセレクタを生成"""
        if field.get("id"):
            return f"#{field['id']}"
        if field.get("name"):
            tag = field.get("tag", "input")
            return f"{tag}[name=\"{field['name']}\"]"
        # name/idが無い場合はplaceholderやインデックスで特定
        if field.get("placeholder"):
            tag = field.get("tag", "input")
            return f"{tag}[placeholder=\"{field['placeholder']}\"]"
        # チェックボックスの場合、ラベルテキストで特定
        if field.get("type") == "checkbox" and field.get("label"):
            return f"input[type=\"checkbox\"]"
        return ""

    def _apply_mapping(self, page: Page, mapping: dict) -> dict:
        """マッピングに基づいてフォームに入力"""
        filled = {}
        for selector, value in mapping.items():
            if not value or not selector:
                continue
            try:
                # ラジオボタン
                if value == "__radio__" and selector.startswith("__radio__"):
                    parts = selector.split("__")
                    # __radio__{name}__{value} -> parts = ['', 'radio', '', name, '', value]
                    radio_name = parts[3]
                    radio_value = parts[5] if len(parts) > 5 else parts[-1]
                    try:
                        page.check(f'input[type="radio"][name="{radio_name}"][value="{radio_value}"]', timeout=3000)
                        filled[f"radio:{radio_name}"] = radio_value
                    except Exception:
                        # value属性で見つからない場合、テキスト一致で試す
                        try:
                            radios = page.query_selector_all(f'input[type="radio"][name="{radio_name}"]')
                            for radio in radios:
                                parent_text = radio.evaluate("el => el.parentElement ? el.parentElement.textContent.trim() : ''")
                                if radio_value in parent_text:
                                    radio.check()
                                    filled[f"radio:{radio_name}"] = radio_value
                                    break
                        except Exception as e:
                            print(f"ラジオボタン選択エラー ({radio_name}): {e}")
                    continue

                if value == "__checkbox__":
                    element = page.query_selector(selector)
                    if element:
                        # disabled状態のチェックボックスはスキップ
                        is_disabled = element.evaluate("el => el.disabled")
                        if not is_disabled:
                            page.check(selector, timeout=5000)
                            filled[selector] = "checked"
                        else:
                            # 同意文をスクロールして有効化を試みる
                            try:
                                element.evaluate("el => { const p = el.closest('.form-group') || el.parentElement; if(p) p.scrollIntoView(); }")
                                page.wait_for_timeout(500)
                                page.check(selector, timeout=5000)
                                filled[selector] = "checked"
                            except Exception:
                                print(f"チェックボックスが無効状態: {selector}")
                else:
                    element = page.query_selector(selector)
                    if element:
                        tag = element.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            # テキストで選択を試み、失敗したらvalueで選択
                            try:
                                page.select_option(selector, label=value)
                            except Exception:
                                try:
                                    page.select_option(selector, value=value)
                                except Exception:
                                    # 部分一致で探す
                                    options = element.evaluate("el => Array.from(el.options).map(o => ({v: o.value, t: o.textContent.trim()}))")
                                    for opt in options:
                                        if value in opt["t"] or opt["t"] in value:
                                            page.select_option(selector, value=opt["v"])
                                            break
                            filled[selector] = value
                        else:
                            page.fill(selector, str(value))
                            filled[selector] = value
            except Exception as e:
                print(f"フィールド入力エラー ({selector}): {e}")
        return filled

    def _click_submit(self, page: Page) -> bool:
        """送信ボタンをクリック"""
        # type="submit"のボタンを探す
        submit_btn = page.query_selector(
            'button[type="submit"], input[type="submit"]'
        )
        if submit_btn:
            submit_btn.click()
            return True

        # テキストで探す
        for text in SUBMIT_BUTTON_TEXTS:
            btn = page.query_selector(f'button:has-text("{text}"), a:has-text("{text}")')
            if btn:
                btn.click()
                return True

        return False
