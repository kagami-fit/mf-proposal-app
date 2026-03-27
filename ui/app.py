"""Streamlitメインアプリ"""

import streamlit as st

st.set_page_config(
    page_title="フォーム営業管理シート",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.theme import apply_theme, page_header, section_header, COLORS

apply_theme()

page_header(
    "フォーム営業管理シート",
    "健康経営に関心のある企業を収集・分析し、提案文を生成する統合プラットフォーム",
)

# ============================================================
# 案C: フロー図（メインワークフロー）
# ============================================================
section_header("WORKFLOW", "ご利用の流れ")

st.markdown(
    f"""
    <div class="fr-flow-container">
        <div class="fr-flow-card">
            <div class="fr-flow-num">01</div>
            <div class="fr-flow-title">① 企業収集</div>
            <div class="fr-flow-desc">認定リスト・PR TIMES・<br>Google Newsなどから企業を収集</div>
        </div>
        <div class="fr-flow-arrow">▶</div>
        <div class="fr-flow-card">
            <div class="fr-flow-num">02</div>
            <div class="fr-flow-title">② 企業分析</div>
            <div class="fr-flow-desc">HP・外部ソースをAIが分析し<br>課題・ニーズを自動推定</div>
        </div>
        <div class="fr-flow-arrow">▶</div>
        <div class="fr-flow-card accent">
            <div class="fr-flow-num">03</div>
            <div class="fr-flow-title">③ 提案作成</div>
            <div class="fr-flow-desc">分析結果をもとに<br>AIが提案文を自動生成</div>
        </div>
        <div class="fr-flow-arrow">▶</div>
        <div class="fr-flow-card">
            <div class="fr-flow-num">04</div>
            <div class="fr-flow-title">④ フォーム送信</div>
            <div class="fr-flow-desc">問い合わせフォームへ<br>提案文を自動入力・送信</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <p style="text-align:center; color:{COLORS['secondary']}; margin:0.5rem 0 2rem; font-size:0.95rem;">
        左のサイドバーから ①→②→③→④ の順に進めてください
    </p>
    """,
    unsafe_allow_html=True,
)

# 補助ツール
section_header("TOOLS", "補助ツール")

st.markdown(
    f"""
    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:1.2rem; margin:1rem 0 2rem;">
        <div class="fr-metric-card" style="background:{COLORS['secondary']};">
            <div class="fr-metric-label">TOOL</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">ダッシュボード</div>
            <div class="fr-metric-sub">進捗状況の一覧・統計</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['secondary']};">
            <div class="fr-metric-label">TOOL</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">送信者設定</div>
            <div class="fr-metric-sub">フォーム送信時の送信者情報</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['gold']};">
            <div class="fr-metric-label">TOOL</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">ROI試算</div>
            <div class="fr-metric-sub">プレゼン・アブセン損失とROI試算</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 接続状態チェック
section_header("STATUS", "接続状態")

col1, col2, col3 = st.columns(3)

with col1:
    try:
        from sheets.client import get_spreadsheet
        sp = get_spreadsheet()
        st.success(f"Google Sheets: {sp.title}")
    except Exception as e:
        st.error(f"Google Sheets: {e}")

with col2:
    try:
        from config.settings import ANTHROPIC_API_KEY
        if ANTHROPIC_API_KEY:
            st.success("Claude API: 設定済み")
        else:
            st.warning("Claude API: APIキー未設定")
    except Exception as e:
        st.error(f"Claude API: {e}")

with col3:
    import os
    if os.environ.get("STREAMLIT_SHARING_MODE") or os.path.exists("/home/appuser"):
        st.info("Playwright: クラウド環境では利用不可（ローカル専用）")
    else:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            st.success("Playwright: 起動OK")
        except Exception as e:
            st.error(f"Playwright: {e}")

# Footer
st.markdown(
    f"""
    <div class="fr-footer">
        フォーム営業管理シート &mdash; Powered by Claude AI
    </div>
    """,
    unsafe_allow_html=True,
)
