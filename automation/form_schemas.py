"""日本語フォームフィールドパターン定義"""

# 日本語の問い合わせフォームで一般的なフィールドのラベル・属性パターン
FIELD_PATTERNS = {
    "company_name": {
        "labels": ["会社名", "企業名", "法人名", "組織名", "御社名", "貴社名"],
        "attributes": ["company", "organization", "corp"],
        "placeholders": ["株式会社", "会社名"],
    },
    "department": {
        "labels": ["部署", "部門", "所属"],
        "attributes": ["department", "division", "section"],
        "placeholders": ["部署名"],
    },
    "name": {
        "labels": ["お名前", "氏名", "ご担当者名", "担当者名", "名前"],
        "attributes": ["name", "fullname", "your-name"],
        "placeholders": ["山田太郎", "お名前"],
    },
    "name_sei": {
        "labels": ["姓", "名字"],
        "attributes": ["sei", "last-name", "lastname", "family-name"],
        "placeholders": ["山田"],
    },
    "name_mei": {
        "labels": ["名", "名前"],
        "attributes": ["mei", "first-name", "firstname", "given-name"],
        "placeholders": ["太郎"],
    },
    "name_kana": {
        "labels": ["フリガナ", "ふりがな", "カナ"],
        "attributes": ["kana", "furigana", "reading"],
        "placeholders": ["ヤマダタロウ"],
    },
    "email": {
        "labels": ["メールアドレス", "Eメール", "E-mail", "メール"],
        "attributes": ["email", "mail", "e-mail"],
        "placeholders": ["example@company.co.jp"],
    },
    "phone": {
        "labels": ["電話番号", "TEL", "お電話番号", "連絡先"],
        "attributes": ["tel", "phone", "telephone"],
        "placeholders": ["03-1234-5678", "000-0000-0000"],
    },
    "phone1": {
        "labels": [],
        "attributes": ["tel1", "phone1", "tel-1"],
        "placeholders": ["03", "090", "市外局番"],
    },
    "phone2": {
        "labels": [],
        "attributes": ["tel2", "phone2", "tel-2"],
        "placeholders": ["1234", "4567"],
    },
    "phone3": {
        "labels": [],
        "attributes": ["tel3", "phone3", "tel-3"],
        "placeholders": ["5678", "8910"],
    },
    "zipcode": {
        "labels": ["郵便番号", "〒"],
        "attributes": ["zip", "zipcode", "postal"],
        "placeholders": ["000-0000"],
    },
    "zipcode1": {
        "labels": [],
        "attributes": ["zip1", "zipcode1", "postal1"],
        "placeholders": ["012", "100"],
    },
    "zipcode2": {
        "labels": [],
        "attributes": ["zip2", "zipcode2", "postal2"],
        "placeholders": ["3456", "0001"],
    },
    "email_confirm": {
        "labels": ["メールアドレス（確認）", "確認用メールアドレス", "メールアドレス確認", "再入力"],
        "attributes": ["email_confirm", "email-confirm", "mail_confirm", "email2", "confirm_email"],
        "placeholders": ["確認のため再入力", "再度入力"],
    },
    "address_prefecture": {
        "labels": ["都道府県"],
        "attributes": ["prefecture", "pref", "state"],
        "placeholders": ["都道府県"],
    },
    "address_city": {
        "labels": ["市区町村以下", "市区町村", "住所"],
        "attributes": ["city", "address1", "addr1"],
        "placeholders": ["千代田区"],
    },
    "address_building": {
        "labels": ["建物名", "ビル名", "マンション名"],
        "attributes": ["building", "address2", "addr2"],
        "placeholders": ["ABCビル", "建物名"],
    },
    "gender": {
        "labels": ["性別"],
        "attributes": ["gender", "sex"],
        "placeholders": [],
    },
    "subject": {
        "labels": ["件名", "お問い合わせ件名", "タイトル", "題名"],
        "attributes": ["subject", "title"],
        "placeholders": ["件名"],
    },
    "inquiry_type": {
        "labels": [
            "お問い合わせ種別",
            "お問い合わせ内容",
            "種類",
            "カテゴリ",
            "ご用件",
        ],
        "attributes": ["type", "category", "inquiry-type"],
        "placeholders": [],
    },
    "message": {
        "labels": [
            "お問い合わせ内容",
            "メッセージ",
            "ご質問・ご相談内容",
            "内容",
            "本文",
            "ご相談内容",
            "お問い合わせ詳細",
        ],
        "attributes": ["message", "body", "content", "inquiry", "textarea"],
        "placeholders": ["お問い合わせ内容をご記入ください"],
    },
    "privacy_agreement": {
        "labels": [
            "個人情報",
            "プライバシーポリシー",
            "個人情報の取り扱い",
            "同意",
            "承諾",
        ],
        "attributes": ["privacy", "agree", "consent", "policy"],
        "placeholders": [],
    },
}

# お問い合わせフォームでよく使われるボタンテキスト
SUBMIT_BUTTON_TEXTS = [
    "送信",
    "送信する",
    "確認",
    "確認する",
    "確認画面へ",
    "入力内容を確認する",
    "次へ",
    "Submit",
    "送信ボタン",
]

# 法人・企業向け問い合わせフォームによくあるURLパターン（優先度順）
CONTACT_URL_PATTERNS = [
    "/contact",
    "/contact/",
    "/inquiry",
    "/otoiawase",
    "/toiawase",
    "/お問い合わせ",
    "/お問合せ",
    "/form",
    "/ask",
    "/mail",
    "/corporate/contact",
    "/company/contact",
    "/business/contact",
    "/biz/contact",
]

# カスタマー向け（除外対象）のURLパターン
CUSTOMER_URL_PATTERNS = [
    "customer",
    "support",
    "help",
    "faq",
    "store",
    "shop",
    "cart",
    "order",
    "mypage",
    "login",
    "signup",
    "register",
    "delivery",
    "shipping",
    "return",
    "cancel",
    "job",
    "recruit",
    "career",
    "entry",
    "resume",
    "mypage",
]
