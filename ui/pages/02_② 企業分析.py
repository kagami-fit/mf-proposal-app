"""企業分析画面（企業マスター連携版）"""

import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st

st.set_page_config(page_title="企業分析", page_icon="🔍", layout="wide")

from ui.theme import page_header, section_header, progress_bar, COLORS

page_header("企業分析", "企業HP + 外部ソースをAIで分析し、健康経営の課題を特定します")
progress_bar(2)

try:
    from sheets.sync import (
        master_read_all, find_row_by_id, update_cell, SHEET_MASTER,
    )
    from sheets.models import CompanyMaster, Analysis
    import pandas as pd

    masters = master_read_all()
except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.stop()

if not masters:
    st.info("まだ企業が登録されていません。「企業収集」画面で企業を追加してください。")
    st.stop()


# ============================================================
# スプレッドシート直接書き込み（キャッシュに依存しない）
# ============================================================
# 列番号マッピング（スプレッドシートのヘッダーと一致）
COL = {
    "url": 3,
    "industry": 9,
    "employee_scale": 10,
    "health_efforts": 11,
    "estimated_challenges": 12,
    "estimated_needs": 13,
    "confidence_score": 14,
    "proposal_status": 15,
    "proposal_date": 16,
    "send_date": 17,
    "email": 18,
    "phone": 19,
    "fax": 20,
    "address": 21,
    "contact_url": 22,
    "contact_form_url": 23,
    "representative": 24,
    "established": 25,
    "capital": 26,
    "revenue": 27,
    "listed": 28,
    "memo": 29,
    "analysis_date": 30,
    "analysis_notes": 31,
    "status": 32,
}


def _save_all_to_sheet(company_id: str, analysis: Analysis, contact: dict, llm_data: dict, structured_info: dict | None = None):
    """分析結果・連絡先・企業概要をスプレッドシートに直接書き込む"""
    row_idx = find_row_by_id(SHEET_MASTER, company_id)
    if row_idx is None:
        return

    # --- 分析結果 ---
    update_cell(SHEET_MASTER, row_idx, COL["industry"], analysis.industry)
    update_cell(SHEET_MASTER, row_idx, COL["employee_scale"], analysis.employee_scale)
    update_cell(SHEET_MASTER, row_idx, COL["health_efforts"], analysis.health_management_efforts)
    update_cell(SHEET_MASTER, row_idx, COL["estimated_challenges"], analysis.estimated_challenges)
    update_cell(SHEET_MASTER, row_idx, COL["estimated_needs"], analysis.estimated_needs)
    update_cell(SHEET_MASTER, row_idx, COL["confidence_score"], str(analysis.confidence_score))
    update_cell(SHEET_MASTER, row_idx, COL["analysis_date"], str(date.today()))
    update_cell(SHEET_MASTER, row_idx, COL["analysis_notes"], analysis.analysis_notes)
    update_cell(SHEET_MASTER, row_idx, COL["status"], "分析済み")

    # --- 連絡先 ---
    for key in ["email", "phone", "fax", "address", "contact_url", "contact_form_url"]:
        val = contact.get(key, "")
        if val:
            update_cell(SHEET_MASTER, row_idx, COL[key], val)

    # --- 企業概要（構造化データ優先 → LLMデータで補完） ---
    si = structured_info or {}
    for key in ["representative", "established", "capital", "revenue", "listed"]:
        val = si.get(key) or llm_data.get(key, "")
        if val:
            update_cell(SHEET_MASTER, row_idx, COL[key], val)

    # --- 企業URL ---
    if llm_data.get("corporate_url"):
        update_cell(SHEET_MASTER, row_idx, COL["url"], llm_data["corporate_url"])


# ============================================================
# URL解決
# ============================================================
def _is_news_url(url: str) -> bool:
    news_domains = [
        "prtimes.jp", "news.google", "news.yahoo", "nikkei.com",
        "toyokeizai.net", "diamond.jp", "itmedia.co.jp", "mynavi.jp",
        "okinawatimes.co.jp", "the-miyanichi.co.jp", "niconews.net",
    ]
    return any(d in url.lower() for d in news_domains)


def _resolve_url(company_name: str, current_url: str, sc=None) -> str:
    if current_url and not _is_news_url(current_url):
        return current_url

    if sc:
        msg = f"🔍 {company_name} の公式サイトURLを検索中..."
        if current_url:
            msg += "（現在のURLはニュースサイト）"
        sc.info(msg)

    from analyzers.url_finder import URLFinder
    found = URLFinder().find_url(company_name)

    if found and sc:
        sc.success(f"✅ 公式サイトを発見: {found}")
    elif sc:
        sc.warning("⚠️ 公式サイトURLが見つかりませんでした。外部ソース情報のみで分析します。")
    return found


# ============================================================
# 分析メインフロー
# ============================================================
def _run_full_analysis(target: CompanyMaster, use_enrichment: bool = True, status_container=None):
    """URL検索→HP解析→会社概要→連絡先→外部ソース→LLM分析→全項目保存"""
    sc = status_container or st

    # Step 1: URL解決
    url = _resolve_url(target.name, target.url, sc)
    if url and url != target.url:
        row_idx = find_row_by_id(SHEET_MASTER, target.id)
        if row_idx:
            update_cell(SHEET_MASTER, row_idx, COL["url"], url)
        target.url = url

    summary = ""
    contact_info = {}
    structured_info = {}  # 会社概要の構造化データ

    # Step 2: HPスクレイピング
    if url:
        with sc.status(f"📄 {target.name}のHPを解析中...", expanded=False) as s:
            from analyzers.company_scraper import CompanyScraper
            scraper = CompanyScraper(url)
            summary = scraper.get_summary()
            s.write(summary[:2000])

    # Step 3: 会社概要ページ + PR TIMESから構造化データを取得
    with sc.status("🏢 会社概要を取得中（HP会社概要ページ + PR TIMES）...", expanded=False) as s:
        from analyzers.company_info_scraper import CompanyInfoScraper
        # PR TIMESのURLを特定（article_urlに入っていることが多い）
        prtimes_url = ""
        if target.article_url and "prtimes.jp" in target.article_url:
            prtimes_url = target.article_url
        info_scraper = CompanyInfoScraper(
            company_name=target.name,
            company_url=url or "",
            prtimes_url=prtimes_url,
        )
        structured_info = info_scraper.get_structured_data()
        company_info_summary = info_scraper.get_summary()
        if structured_info:
            filled_keys = [k for k, v in structured_info.items() if v]
            s.write(f"✅ {len(filled_keys)}項目を取得: {', '.join(filled_keys)}")
            for k, v in structured_info.items():
                if v:
                    s.write(f"  **{k}:** {v}")
        else:
            s.write("HP会社概要・PR TIMESからの構造化データは取得できませんでした。")
            company_info_summary = ""

    # Step 4: 連絡先抽出
    if url:
        with sc.status("📞 連絡先情報を抽出中...", expanded=False) as s:
            from analyzers.contact_scraper import ContactScraper
            cs = ContactScraper(url)
            contact_info = cs.get_contact_info()
            # 構造化データからも連絡先を補完
            for key in ["email", "phone", "fax", "address"]:
                if not contact_info.get(key) and structured_info.get(key):
                    contact_info[key] = structured_info[key]
            if any(contact_info.values()):
                for k, v in contact_info.items():
                    if v:
                        s.write(f"**{k}:** {v}")
            else:
                s.write("HPからの連絡先情報は見つかりませんでした。LLMで補完します。")
    else:
        summary = "企業HPの情報を取得できませんでした（URLなし）。"
        # URLなしでも構造化データから連絡先を取得
        for key in ["email", "phone", "fax", "address"]:
            if structured_info.get(key):
                contact_info[key] = structured_info[key]

    # Step 5: 外部ソース
    enriched_summary = ""
    if use_enrichment:
        with sc.status("🌐 外部ソースから追加情報を収集中...", expanded=False) as s:
            from analyzers.web_enricher import WebEnricher
            enricher = WebEnricher(target.name, url or "")
            enriched_summary = enricher.get_summary()
            s.write(enriched_summary[:2000] if enriched_summary else "追加情報は見つかりませんでした。")

    # 会社概要の構造化データをenriched_summaryに追加（LLMへの入力に含める）
    if company_info_summary:
        enriched_summary = company_info_summary + "\n\n" + enriched_summary

    # Step 6: LLM分析
    with sc.status("🤖 AIで全項目を分析中...", expanded=False):
        from analyzers.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()
        analysis = analyzer.analyze(target.name, url or "", summary, enriched_summary)

    if not analysis:
        return None, contact_info

    analysis.company_id = target.id

    # LLMの生データ取得
    llm_data = getattr(analyzer, "_last_parsed_data", None) or {}

    # 連絡先: スクレイピング結果 + 構造化データ + LLMの知識をマージ（スクレイピング優先）
    for key in ["email", "phone", "fax", "address", "contact_url", "contact_form_url"]:
        if not contact_info.get(key) and llm_data.get(key):
            contact_info[key] = llm_data[key]

    # 企業概要: 構造化データ → LLMデータの順で優先
    for key in ["representative", "established", "capital", "revenue", "listed", "corporate_url"]:
        if structured_info.get(key) and not llm_data.get(key):
            llm_data[key] = structured_info[key]
        elif structured_info.get(key) and llm_data.get(key):
            # 構造化データ（HP/PR TIMES）を優先（より正確）
            llm_data[key] = structured_info[key]

    # === 全項目をスプレッドシートに直接書き込み ===
    _save_all_to_sheet(target.id, analysis, contact_info, llm_data, structured_info)

    return analysis, contact_info, llm_data


# ============================================================
# UI: ステータスサマリー
# ============================================================
analyzed = [m for m in masters if m.is_analyzed]
unanalyzed = [m for m in masters if not m.is_analyzed]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("全企業", f"{len(masters)}社")
with col2:
    st.metric("分析済み", f"{len(analyzed)}社")
with col3:
    st.metric("未分析", f"{len(unanalyzed)}社")

# ============================================================
# UI: 個別分析
# ============================================================
section_header("ANALYZE", "企業を選択して分析")

all_options = {f"{m.id}: {m.name} [{m.source_category}]": m for m in masters}

selected_key = st.selectbox("分析する企業を選択", options=list(all_options.keys()), index=0)

if selected_key:
    target = all_options[selected_key]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**企業名:** {target.name}")
        st.markdown(f"**URL:** {target.url or '（未設定 → 自動検索します）'}")
        st.markdown(f"**ソース:** {target.source_category}")
    with col2:
        st.markdown(f"**記事:** {target.article_title}")
        if target.industry:
            st.markdown(f"**業種:** {target.industry}")
        if target.is_analyzed:
            st.info("この企業は分析済みです。再分析も可能です。")

    use_enrichment = st.checkbox("外部ソースからも情報を収集する（精度向上）", value=True, key="enrich_single")

    if st.button("この企業を分析する", key="analyze_single"):
        result = _run_full_analysis(target, use_enrichment)

        if result and result[0]:
            analysis, contact_info, llm_data = result
            st.success("分析完了！ スプレッドシートに全項目を保存しました。")

            # --- 分析結果表示 ---
            st.subheader("分析結果")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**業種:** {analysis.industry}")
                st.markdown(f"**従業員規模:** {analysis.employee_scale}")
                st.markdown(f"**確信度:** {analysis.confidence_score}")
            with c2:
                st.markdown(f"**健康経営への取り組み:**\n{analysis.health_management_efforts}")
                st.markdown(f"**推定課題:**\n{analysis.estimated_challenges}")
                st.markdown(f"**推定ニーズ:**\n{analysis.estimated_needs}")

            if analysis.analysis_notes:
                st.markdown(f"**分析メモ:** {analysis.analysis_notes}")

            # --- 企業概要表示 ---
            st.subheader("企業概要")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**代表者:** {llm_data.get('representative', '―')}")
                st.markdown(f"**設立:** {llm_data.get('established', '―')}")
            with c2:
                st.markdown(f"**資本金:** {llm_data.get('capital', '―')}")
                st.markdown(f"**売上高:** {llm_data.get('revenue', '―')}")
            with c3:
                st.markdown(f"**上場:** {llm_data.get('listed', '―')}")
                st.markdown(f"**URL:** {llm_data.get('corporate_url', '―')}")

            # --- 連絡先表示 ---
            st.subheader("連絡先")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**メール:** {contact_info.get('email') or '―'}")
                st.markdown(f"**電話:** {contact_info.get('phone') or '―'}")
            with c2:
                st.markdown(f"**FAX:** {contact_info.get('fax') or '―'}")
                st.markdown(f"**住所:** {contact_info.get('address') or '―'}")
            with c3:
                st.markdown(f"**問い合わせ:** {contact_info.get('contact_url') or '―'}")
                st.markdown(f"**フォーム:** {contact_info.get('contact_form_url') or '―'}")

            # 埋まった項目数を表示
            all_keys = ["industry", "employee_scale", "representative", "established",
                        "capital", "revenue", "listed", "email", "phone", "fax",
                        "address", "contact_url", "contact_form_url"]
            merged = {**llm_data, **contact_info, "industry": analysis.industry, "employee_scale": analysis.employee_scale}
            filled = sum(1 for k in all_keys if merged.get(k))
            st.info(f"📊 調査可能な項目のうち **{filled}/{len(all_keys)}** 項目を取得しました")
        else:
            st.error("分析に失敗しました。ログを確認してください。")

# ============================================================
# UI: 一括分析
# ============================================================
st.divider()
section_header("BATCH", "一括分析")

if unanalyzed:
    st.write(f"未分析の企業: {len(unanalyzed)}社")

    max_count = st.number_input(
        "一括分析する企業数", min_value=1, max_value=len(unanalyzed), value=min(5, len(unanalyzed))
    )
    use_enrichment_batch = st.checkbox("外部ソースからも情報を収集する（精度向上・時間増）", value=True, key="enrich_batch")

    if st.button("一括分析を開始", key="batch_analyze"):
        progress = st.progress(0)
        results = []

        for i, m in enumerate(unanalyzed[:max_count]):
            progress.progress((i + 1) / max_count, text=f"分析中: {m.name} ({i+1}/{max_count})")
            try:
                result = _run_full_analysis(m, use_enrichment_batch)
                if result and result[0]:
                    analysis, contact_info, llm_data = result
                    merged = {**llm_data, **contact_info}
                    all_keys = ["industry", "employee_scale", "representative", "established",
                                "capital", "revenue", "listed", "email", "phone", "fax",
                                "address", "contact_url", "contact_form_url"]
                    filled = sum(1 for k in all_keys if merged.get(k))
                    results.append({
                        "企業名": m.name,
                        "業種": analysis.industry,
                        "従業員規模": analysis.employee_scale,
                        "代表者": llm_data.get("representative", ""),
                        "電話": contact_info.get("phone", ""),
                        "メール": contact_info.get("email", ""),
                        "取得項目": f"{filled}/{len(all_keys)}",
                        "結果": "✅",
                    })
                else:
                    results.append({"企業名": m.name, "業種": "", "従業員規模": "",
                                    "代表者": "", "電話": "", "メール": "", "取得項目": "0", "結果": "❌"})
            except Exception as e:
                results.append({"企業名": m.name, "業種": "", "従業員規模": "",
                                "代表者": "", "電話": "", "メール": "", "取得項目": "0",
                                "結果": f"❌ {str(e)[:30]}"})

        progress.progress(1.0, text="完了！")
        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
else:
    st.info("すべての企業が分析済みです。")

# ============================================================
# UI: 分析結果一覧
# ============================================================
st.divider()
section_header("RESULTS", "分析結果一覧")

if analyzed:
    df = pd.DataFrame([m.model_dump() for m in analyzed])
    display_cols = [
        "id", "name", "url", "industry", "employee_scale",
        "health_efforts", "estimated_challenges", "estimated_needs",
        "confidence_score", "email", "phone", "address",
        "representative", "established", "capital", "revenue", "listed",
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[display_cols].rename(columns={
            "id": "ID", "name": "企業名", "url": "URL",
            "industry": "業種", "employee_scale": "従業員規模",
            "health_efforts": "健康経営取り組み",
            "estimated_challenges": "推定課題", "estimated_needs": "推定ニーズ",
            "confidence_score": "確信度", "email": "メール", "phone": "電話",
            "address": "住所", "representative": "代表者",
            "established": "設立", "capital": "資本金",
            "revenue": "売上高", "listed": "上場",
        }),
        use_container_width=True,
    )
else:
    st.info("まだ分析結果がありません。")
