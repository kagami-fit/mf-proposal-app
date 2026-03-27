"""Streamlitメインアプリ"""

import streamlit as st

st.set_page_config(
    page_title="MF企業分析・提案ツール",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.theme import apply_theme, page_header, section_header, COLORS

apply_theme()

page_header(
    "MF企業分析・提案ツール",
    "健康経営に関心のある企業を収集・分析し、提案文を生成する統合プラットフォーム",
)

# ステップカード
st.markdown(
    f"""
    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:1.2rem; margin:2rem 0;">
        <div class="fr-metric-card" style="background:{COLORS['primary_dark']};">
            <div class="fr-metric-label">STEP 01</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">企業収集</div>
            <div class="fr-metric-sub">Google Alerts / PR TIMES から自動収集</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['primary_dark']};">
            <div class="fr-metric-label">STEP 02</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">企業分析</div>
            <div class="fr-metric-sub">HP + 外部ソースをAIで課題分析</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['primary_dark']};">
            <div class="fr-metric-label">STEP 03</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">提案作成</div>
            <div class="fr-metric-sub">分析結果から提案文を自動生成</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['secondary']};">
            <div class="fr-metric-label">STEP 04</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">フォーム送信</div>
            <div class="fr-metric-sub">問い合わせフォームへ自動入力</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['secondary']};">
            <div class="fr-metric-label">STEP 05</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">ダッシュボード</div>
            <div class="fr-metric-sub">進捗状況の一覧・統計</div>
        </div>
        <div class="fr-metric-card" style="background:{COLORS['accent']};">
            <div class="fr-metric-label">STEP 07</div>
            <div class="fr-metric-value" style="font-size:1.3rem;">ROI試算</div>
            <div class="fr-metric-sub">プレゼン・アブセン損失とROI試算</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <p style="text-align:center; color:{COLORS['secondary']}; margin:1rem 0 2rem;">
        左のサイドバーから各機能にアクセスしてください。
    </p>
    """,
    unsafe_allow_html=True,
)

# セットアップ
section_header("SETUP", "セットアップ")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['accent']};">
            <div class="fr-info-title">1. 環境変数</div>
            <div class="fr-info-content">.env ファイルにAPIキーとスプレッドシートIDを設定</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['gold']};">
            <div class="fr-info-title">2. Google認証</div>
            <div class="fr-info-content">サービスアカウントのJSONキーを credentials/ に配置</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['secondary']};">
            <div class="fr-info-title">3. サービス情報</div>
            <div class="fr-info-content">knowledge/service_description.md に自社サービス情報を記入</div>
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
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        st.success("Playwright: 起動OK")
    except Exception as e:
        st.error(f"Playwright: {e}")

# マイグレーション（旧データ→企業マスター）
section_header("MIGRATION", "データ移行")

st.markdown(
    f"""
    <div class="fr-info-card" style="border-left:4px solid {COLORS['gold']};">
        <div class="fr-info-title">旧シートからの移行</div>
        <div class="fr-info-content">
            旧「企業リスト」「企業分析」「提案内容」の3シートのデータを、<br>
            新しい「企業マスター」シートに統合します。既存データがある場合にのみ使用してください。
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.button("旧データを企業マスターに移行", key="migrate"):
    with st.spinner("移行中..."):
        from sheets.sync import migrate_to_master
        result = migrate_to_master()
    st.success(f"移行完了: {result['migrated']}社を移行、{result['skipped']}社はスキップ（重複）")

# Footer
st.markdown(
    f"""
    <div class="fr-footer">
        MF企業分析・提案ツール &mdash; Powered by Claude AI
    </div>
    """,
    unsafe_allow_html=True,
)
