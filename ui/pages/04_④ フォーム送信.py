"""フォーム送信画面（3段階確認フロー）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import json
import streamlit as st

st.set_page_config(page_title="フォーム送信", page_icon="📮", layout="wide")

from ui.theme import page_header, progress_bar

page_header("フォーム送信", "問い合わせフォームへの自動入力・確認・送信")
progress_bar(4)

# 保存済み送信者設定を読み込み
SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "sender_settings.json"

def load_sender_settings() -> dict:
    """保存済み設定 → .env → 空のデフォルト"""
    defaults = {
        "company_name": "", "department": "", "position": "",
        "name": "", "name_sei": "", "name_mei": "",
        "name_kana": "", "name_kana_sei": "", "name_kana_mei": "",
        "email": "", "phone": "", "fax": "",
        "zipcode": "", "prefecture": "", "address": "", "building": "",
        "url": "",
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                defaults.update(json.load(f))
            return defaults
        except Exception:
            pass
    # フォールバック: .envから
    try:
        from config.settings import SENDER_INFO
        defaults.update({k: v for k, v in SENDER_INFO.items() if v})
    except Exception:
        pass
    return defaults

try:
    from sheets.sync import (
        SHEET_COMPANIES, SHEET_PROPOSALS,
        read_all, find_row_by_id, update_row,
    )
    from sheets.models import Company, Proposal
    import pandas as pd

    companies = read_all(SHEET_COMPANIES, Company)
    proposals = read_all(SHEET_PROPOSALS, Proposal)
except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.stop()

# 確定済みの提案のみ
approved_proposals = [p for p in proposals if p.approval_status == "確定済み"]
company_map = {c.id: c for c in companies}

if not approved_proposals:
    st.info("確定済みの提案がありません。「提案作成」画面で提案を確定してください。")
    st.stop()

# --- 送信者情報（保存済み設定から自動読み込み） ---
saved_settings = load_sender_settings()
has_settings = SETTINGS_FILE.exists()

if has_settings:
    with st.expander("送信者情報を確認", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.text(f"会社名: {saved_settings['company_name']}")
            st.text(f"担当者: {saved_settings['name']}")
            st.text(f"フリガナ: {saved_settings['name_kana']}")
            st.text(f"部署: {saved_settings['department']}")
        with col2:
            st.text(f"メール: {saved_settings['email']}")
            st.text(f"電話: {saved_settings['phone']}")
            st.text(f"住所: {saved_settings['prefecture']} {saved_settings['address']}")
        st.caption("変更は「送信者設定」ページから行えます。")
else:
    st.warning("送信者情報が未設定です。サイドバーの「送信者設定」ページから設定してください。")
    st.stop()

sender_info = saved_settings

# --- 企業選択 ---
st.divider()
st.subheader("送信する提案を選択")

options = {f"{p.company_id}: {p.company_name} — {p.subject}": p for p in approved_proposals}
selected_key = st.selectbox("提案を選択", list(options.keys()))

if selected_key:
    proposal = options[selected_key]
    company = company_map.get(proposal.company_id)

    # 提案内容の表示
    with st.expander("提案内容", expanded=False):
        st.markdown(f"**件名:** {proposal.subject}")
        st.markdown(f"**本文:**\n\n{proposal.body}")
        st.markdown(f"**ポイント:** {proposal.key_points}")

    # --- フォームURL設定 ---
    st.subheader("問い合わせフォーム")

    form_url = st.text_input(
        "フォームURL",
        value=st.session_state.get("form_url_selected", proposal.form_url),
        help="フォームのURLを入力するか、自動検索を使用してください",
    )

    # フォームURL自動検索
    if company and company.url:
        if st.button("フォームURLを自動検索", key="find_form"):
            with st.spinner("フォームを検索中..."):
                from automation.form_finder import FormFinder

                finder = FormFinder(company.url, company_name=company.name, article_url=company.article_url)
                candidates = finder.find()

            st.session_state["form_candidates"] = candidates

        # 検索結果を表示（session_stateから）
        candidates = st.session_state.get("form_candidates", [])
        if candidates:
            st.success(f"{len(candidates)}件のフォーム候補が見つかりました。")
            for i, c in enumerate(candidates):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📄 {c['url']} ({c['source']})")
                with col2:
                    if st.button("使用", key=f"use_form_{i}"):
                        st.session_state["form_url_selected"] = c["url"]
                        st.session_state.pop("form_candidates", None)
                        st.rerun()

    if not form_url:
        st.warning("フォームURLを入力してください。")
        st.stop()

    if not sender_info.get("name") or not sender_info.get("email"):
        st.warning("送信者名とメールアドレスが未設定です。「送信者設定」ページで設定してください。")
        st.stop()

    # --- フォーム項目プレビュー ---
    st.divider()
    st.subheader("フォーム自動入力")

    # フォーム項目の検出
    if st.button("フォーム項目を検出", key="detect_fields", type="primary"):
        with st.spinner("フォームを読み込み中..."):
            from automation.form_filler import FormFiller
            from playwright.sync_api import sync_playwright

            filler = FormFiller()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(form_url, wait_until="networkidle", timeout=30000)

                fields = filler._detect_fields(page)
                mapping = filler._rule_based_mapping(
                    fields, sender_info, proposal.subject, proposal.body
                )
                browser.close()

        if fields:
            st.session_state["detected_fields"] = fields
            st.session_state["field_mapping"] = mapping
            st.session_state["detect_form_url"] = form_url

            # 項目一覧を表示
            field_data = []
            for f in fields:
                selector = filler._get_selector(f)
                matched_type = filler._match_field_type(f)
                value = mapping.get(selector, "")
                field_name = f["label"] or f["name"] or f["id"] or f["placeholder"] or "(不明)"
                required_mark = "⚠️ 必須" if f.get("required") else ""

                field_data.append({
                    "項目名": field_name,
                    "種類": f["tag"] + (f" ({f['type']})" if f["type"] else ""),
                    "必須": required_mark,
                    "入力値": value[:50] if value and value != "__checkbox__" else ("✅ チェック" if value == "__checkbox__" else "❌ 未入力"),
                })

            st.dataframe(pd.DataFrame(field_data), use_container_width=True)

            # 未入力の必須項目があれば警告
            missing = [d for d in field_data if d["必須"] and "未入力" in d["入力値"]]
            if missing:
                st.warning(f"⚠️ 必須項目が {len(missing)} 件未入力です: {', '.join(d['項目名'] for d in missing)}")
            else:
                st.success("✅ すべての検出項目に入力値が設定されています。")
        else:
            st.error("フォーム項目が検出できませんでした。")

    # --- Gate 2: フォーム入力プレビュー ---
    if st.session_state.get("detected_fields"):
        if st.button("フォームに自動入力（プレビュー）", key="fill_form"):
            with st.spinner("フォームに自動入力中..."):
                from automation.form_filler import FormFiller
                from automation.screenshot import get_screenshot_path

                filler = FormFiller()
                screenshot_path = get_screenshot_path(proposal.company_id, "preview")

                result = filler.fill_form(
                    form_url=form_url,
                    sender_info=sender_info,
                    proposal_subject=proposal.subject,
                    proposal_body=proposal.body,
                    screenshot_path=screenshot_path,
                    headless=True,
                )

            if result["success"]:
                st.session_state["fill_result"] = result
                st.session_state["fill_form_url"] = form_url
                st.success(f"フォーム入力完了！ {len(result['filled_fields'])} 項目を入力しました。")
            else:
                st.error(f"フォーム入力に失敗しました: {', '.join(result['errors'])}")

    # プレビュー表示
    fill_result = st.session_state.get("fill_result")
    if fill_result and fill_result["success"]:
        # 入力内容テーブル
        st.markdown("**入力内容:**")
        filled_data = [
            {"フィールド": k, "入力値": v[:80]}
            for k, v in fill_result["filled_fields"].items()
        ]
        st.dataframe(pd.DataFrame(filled_data), use_container_width=True)

        # スクリーンショット表示
        screenshot_file = fill_result.get("screenshot", "")
        if screenshot_file and Path(screenshot_file).exists():
            st.markdown("**スクリーンショット:**")
            st.image(screenshot_file, use_container_width=True)

        # --- Gate 3: 最終確認 ---
        st.divider()
        st.subheader("最終確認（Gate 3）")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("送信する ✅", key="submit_form", type="primary"):
                with st.spinner("送信中..."):
                    from automation.form_filler import FormFiller
                    from automation.screenshot import get_screenshot_path

                    filler = FormFiller()
                    submit_screenshot = get_screenshot_path(proposal.company_id, "submitted")

                    submit_result = filler.submit_form(
                        form_url=st.session_state["fill_form_url"],
                        sender_info=sender_info,
                        proposal_subject=proposal.subject,
                        proposal_body=proposal.body,
                        screenshot_path=submit_screenshot,
                    )

                if submit_result["success"]:
                    st.success("送信完了！")
                    # ステータスを更新
                    proposal.approval_status = "送信済み"
                    row_idx = find_row_by_id(SHEET_PROPOSALS, proposal.company_id)
                    if row_idx:
                        update_row(SHEET_PROPOSALS, row_idx, proposal)

                    if Path(submit_screenshot).exists():
                        st.image(submit_screenshot, caption="送信後の画面")

                    # クリーンアップ
                    for key in ["fill_result", "fill_form_url", "form_url_selected", "detected_fields", "field_mapping"]:
                        st.session_state.pop(key, None)
                else:
                    st.error(f"送信に失敗: {', '.join(submit_result['errors'])}")

        with col2:
            if st.button("ブラウザで確認 🖥️", key="open_browser"):
                st.info("ブラウザを起動中... ブラウザ上で内容を確認し、手動で送信してください。")
                from automation.form_filler import FormFiller

                filler = FormFiller()
                filler.open_filled_form(
                    form_url=st.session_state["fill_form_url"],
                    sender_info=sender_info,
                    proposal_subject=proposal.subject,
                    proposal_body=proposal.body,
                )
                st.success("ブラウザ確認が完了しました。")

        with col3:
            if st.button("やり直す 🔄", key="retry_form"):
                for key in ["fill_result", "fill_form_url", "detected_fields", "field_mapping"]:
                    st.session_state.pop(key, None)
                st.rerun()
