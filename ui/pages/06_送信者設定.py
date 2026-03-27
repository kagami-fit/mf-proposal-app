"""送信者情報の設定・保存"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import json

import streamlit as st

st.set_page_config(page_title="送信者設定", page_icon="⚙️", layout="wide")

from ui.theme import page_header

page_header("送信者設定", "問い合わせフォームに自動入力する送信者情報を設定・保存")

SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "sender_settings.json"


def load_settings() -> dict:
    """保存済み設定を読み込み"""
    defaults = {
        "company_name": "",
        "department": "",
        "position": "",
        "name": "",
        "name_sei": "",
        "name_mei": "",
        "name_kana": "",
        "name_kana_sei": "",
        "name_kana_mei": "",
        "email": "",
        "phone": "",
        "fax": "",
        "zipcode": "",
        "prefecture": "",
        "address": "",
        "building": "",
        "url": "",
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass

    # .envのSENDER_INFOをデフォルト値として使う（未設定の項目のみ）
    try:
        from config.settings import SENDER_INFO
        for key in ["company_name", "name", "name_kana", "email", "phone",
                     "department", "zipcode", "prefecture", "address", "building"]:
            if not defaults.get(key) and SENDER_INFO.get(key):
                defaults[key] = SENDER_INFO[key]
    except Exception:
        pass

    return defaults


def save_settings(settings: dict):
    """設定をJSONに保存"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def auto_split_name(full_name: str) -> tuple[str, str]:
    """フルネームを姓・名に分割"""
    parts = full_name.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return full_name, ""


# 設定読み込み
settings = load_settings()

# --- フォーム ---
with st.form("sender_settings_form"):
    st.subheader("会社情報")
    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input("会社名", value=settings["company_name"])
        department = st.text_input("部署", value=settings["department"])
    with col2:
        position = st.text_input("役職", value=settings["position"])
        url = st.text_input("会社URL", value=settings["url"])

    st.divider()
    st.subheader("担当者情報")

    name = st.text_input("氏名（フルネーム）", value=settings["name"],
                         help="スペース区切りで入力すると姓・名が自動分割されます（例: 高瀬 雅弘）")

    col1, col2 = st.columns(2)
    with col1:
        # 自動分割のデフォルト値を計算
        default_sei, default_mei = auto_split_name(settings["name"])
        name_sei = st.text_input("姓", value=settings["name_sei"] or default_sei,
                                 help="自動分割されますが、手動で修正も可能です")
    with col2:
        name_mei = st.text_input("名", value=settings["name_mei"] or default_mei)

    name_kana = st.text_input("フリガナ（フルネーム）", value=settings["name_kana"],
                              help="スペース区切りで入力（例: タカセ マサヒロ）")

    col1, col2 = st.columns(2)
    with col1:
        default_kana_sei, default_kana_mei = auto_split_name(settings["name_kana"])
        name_kana_sei = st.text_input("セイ", value=settings["name_kana_sei"] or default_kana_sei)
    with col2:
        name_kana_mei = st.text_input("メイ", value=settings["name_kana_mei"] or default_kana_mei)

    st.divider()
    st.subheader("連絡先")

    col1, col2 = st.columns(2)
    with col1:
        email = st.text_input("メールアドレス", value=settings["email"])
        phone = st.text_input("電話番号", value=settings["phone"],
                              help="ハイフン区切りで入力（例: 03-1234-5678）。分割フォームにも自動対応します")
    with col2:
        fax = st.text_input("FAX番号", value=settings["fax"])

    st.divider()
    st.subheader("住所")

    col1, col2 = st.columns(2)
    with col1:
        zipcode = st.text_input("郵便番号", value=settings["zipcode"],
                                help="ハイフン区切り（例: 100-0001）")
        prefecture = st.text_input("都道府県", value=settings["prefecture"])
    with col2:
        address = st.text_input("市区町村以下", value=settings["address"])
        building = st.text_input("建物名", value=settings["building"])

    st.divider()
    submitted = st.form_submit_button("保存する", type="primary", use_container_width=True)

    if submitted:
        # 氏名から姓・名を自動分割（手動入力がなければ）
        auto_sei, auto_mei = auto_split_name(name)
        auto_kana_sei, auto_kana_mei = auto_split_name(name_kana)

        new_settings = {
            "company_name": company_name,
            "department": department,
            "position": position,
            "url": url,
            "name": name,
            "name_sei": name_sei or auto_sei,
            "name_mei": name_mei or auto_mei,
            "name_kana": name_kana,
            "name_kana_sei": name_kana_sei or auto_kana_sei,
            "name_kana_mei": name_kana_mei or auto_kana_mei,
            "email": email,
            "phone": phone,
            "fax": fax,
            "zipcode": zipcode,
            "prefecture": prefecture,
            "address": address,
            "building": building,
        }
        save_settings(new_settings)
        st.success("設定を保存しました！")
        st.balloons()

# --- プレビュー ---
st.divider()
st.subheader("保存済み設定プレビュー")
if SETTINGS_FILE.exists():
    with open(SETTINGS_FILE) as f:
        saved = json.load(f)

    preview_data = {
        "会社名": saved.get("company_name", ""),
        "部署": saved.get("department", ""),
        "役職": saved.get("position", ""),
        "氏名": saved.get("name", ""),
        "姓 / 名": f"{saved.get('name_sei', '')} / {saved.get('name_mei', '')}",
        "フリガナ": saved.get("name_kana", ""),
        "セイ / メイ": f"{saved.get('name_kana_sei', '')} / {saved.get('name_kana_mei', '')}",
        "メール": saved.get("email", ""),
        "電話番号": saved.get("phone", ""),
        "FAX": saved.get("fax", ""),
        "郵便番号": saved.get("zipcode", ""),
        "住所": f"{saved.get('prefecture', '')} {saved.get('address', '')} {saved.get('building', '')}".strip(),
    }
    for k, v in preview_data.items():
        if v and v.strip() != "/":
            st.text(f"{k}: {v}")
else:
    st.info("まだ設定が保存されていません。上のフォームから設定してください。")
