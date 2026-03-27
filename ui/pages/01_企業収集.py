"""企業収集画面"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st

st.set_page_config(page_title="企業収集", page_icon="📡", layout="wide")

from ui.theme import page_header, section_header, COLORS

page_header("企業収集", "複数チャネルから健康経営に関心のある企業を収集します")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "認定企業リスト",
    "Google News",
    "求人サイト",
    "PR TIMES",
    "Google Alerts",
    "CSV/Excel インポート",
])

# === ヘルパー: 収集結果の登録処理（企業マスターに直接登録） ===
def _register_companies(new_companies: list, source_label: str):
    """収集結果を企業マスターシートに登録（重複自動除外）"""
    from sheets.sync import master_add_companies
    import pandas as pd

    if not new_companies:
        st.info("新しい企業が見つかりませんでした。")
        return

    added, duped = master_add_companies(new_companies)

    if added == 0:
        st.info(f"すべて既に登録済みの企業です。（候補: {len(new_companies)}社）")
        return

    msg = f"{added}社を企業マスターに登録しました！"
    if duped > 0:
        msg += f"（重複除外: {duped}社）"
    st.success(msg)

    # 登録した企業のプレビュー（元のCompanyリストから先頭を表示）
    from sheets.models import SourceCategory
    preview = new_companies[:added] if added <= len(new_companies) else new_companies
    df = pd.DataFrame([{
        "企業名": c.name,
        "ソース": SourceCategory.from_source_text(c.source),
        "メモ": c.memo,
    } for c in preview[:20]])
    st.dataframe(df, use_container_width=True)


# ==============================================
# TAB 1: 健康経営優良法人 認定企業リスト
# ==============================================
with tab1:
    section_header("CERTIFIED LIST", "健康経営優良法人 認定企業リスト")

    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['accent']};">
            <div class="fr-info-title">経産省公開データ</div>
            <div class="fr-info-content">
                健康経営優良法人として認定された企業一覧を取得します。<br>
                認定企業自体がターゲットになるだけでなく、
                「同業種でまだ認定を取得していない企業」への提案にも活用できます。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox(
            "取得カテゴリ",
            options=["large", "small", "brand"],
            format_func=lambda x: {
                "large": "大規模法人部門（ホワイト500含む）",
                "small": "中小規模法人部門（ブライト500含む）",
                "brand": "健康経営銘柄",
            }[x],
        )
    with col2:
        st.markdown("")  # スペーサー

    # ファイルアップロード（自動ダウンロードがうまくいかない場合）
    uploaded_excel = st.file_uploader(
        "または認定企業リストのExcelファイルを直接アップロード",
        type=["xlsx", "xls"],
        key="certified_upload",
        help="kenko-keiei.jp からダウンロードしたExcelファイル",
    )

    if st.button("認定企業リストを取得", key="collect_certified"):
        with st.spinner("認定企業リストを取得中..."):
            from collectors.certified_list import CertifiedListCollector

            collector = CertifiedListCollector(category=category)

            if uploaded_excel:
                new_companies = collector._parse_excel(uploaded_excel.read())
                for c in new_companies:
                    c.source = f"健康経営優良法人（アップロード）"
            else:
                new_companies = collector.collect()

        _register_companies(new_companies, "健康経営優良法人")


# ==============================================
# TAB 2: Google News
# ==============================================
with tab2:
    section_header("GOOGLE NEWS", "ニュース記事から企業を発見")

    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['gold']};">
            <div class="fr-info-title">ニュース記事から自動抽出</div>
            <div class="fr-info-content">
                健康経営関連のニュース記事を検索し、記事中に登場する企業名を自動抽出します。<br>
                「まだHPに情報は載せていないが、ニュースで取り上げられ始めた企業」を発見できます。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    from collectors.gnews_collector import DEFAULT_QUERIES

    col1, col2 = st.columns([3, 1])
    with col1:
        queries_input = st.text_area(
            "検索クエリ（1行に1つ）",
            value="\n".join(DEFAULT_QUERIES),
            height=200,
        )
    with col2:
        max_results = st.number_input(
            "各クエリの最大取得件数",
            min_value=3,
            max_value=30,
            value=10,
            step=1,
        )

    if st.button("Google Newsから収集", key="collect_gnews"):
        queries = [q.strip() for q in queries_input.split("\n") if q.strip()]
        if not queries:
            st.warning("検索クエリを入力してください。")
        else:
            with st.spinner(f"{len(queries)}件のクエリで検索中..."):
                from collectors.gnews_collector import GNewsCollector

                collector = GNewsCollector(queries=queries, max_results=max_results)
                new_companies = collector.collect()

            _register_companies(new_companies, "Google News")


# ==============================================
# TAB 3: 求人サイト
# ==============================================
with tab3:
    section_header("JOB SITES", "求人サイトから企業を発見")

    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['secondary']};">
            <div class="fr-info-title">求人情報から健康経営への関心度を推定</div>
            <div class="fr-info-content">
                求人に「健康経営」「ウェルビーイング」等を記載している企業 = 健康経営に関心が高い企業。<br>
                福利厚生の充実度や健康関連キーワードの有無も自動検出します。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    from collectors.job_site import DEFAULT_KEYWORDS as JOB_KEYWORDS

    col1, col2 = st.columns([3, 1])
    with col1:
        job_keywords_input = st.text_area(
            "検索キーワード（1行に1つ）",
            value="\n".join(JOB_KEYWORDS),
            height=150,
        )
    with col2:
        max_pages = st.number_input(
            "検索ページ数",
            min_value=1,
            max_value=5,
            value=2,
            step=1,
            help="1ページ = 約10件の求人",
        )

    if st.button("求人サイトから収集", key="collect_jobs"):
        keywords = [k.strip() for k in job_keywords_input.split("\n") if k.strip()]
        if not keywords:
            st.warning("検索キーワードを入力してください。")
        else:
            with st.spinner(f"{len(keywords)}件のキーワードでIndeedを検索中..."):
                from collectors.job_site import JobSiteCollector

                collector = JobSiteCollector(keywords=keywords, max_pages=max_pages)
                new_companies = collector.collect()

            _register_companies(new_companies, "求人サイト")


# ==============================================
# TAB 4: PR TIMES
# ==============================================
with tab4:
    section_header("PR TIMES", "プレスリリースから企業を発見")

    from config.settings import PRTIMES_KEYWORDS

    keywords_input = st.text_input(
        "検索キーワード（カンマ区切り）",
        value=", ".join(PRTIMES_KEYWORDS),
    )

    if st.button("PR TIMESから収集", key="collect_pr"):
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        if not keywords:
            st.warning("検索キーワードを入力してください。")
        else:
            with st.spinner("PR TIMESを検索中..."):
                from collectors.prtimes import PRTimesCollector

                collector = PRTimesCollector(keywords=keywords)
                new_companies = collector.collect()

            _register_companies(new_companies, "PR TIMES")


# ==============================================
# TAB 5: Google Alerts
# ==============================================
with tab5:
    section_header("GOOGLE ALERTS", "アラートRSSフィードから収集")

    from config.settings import GOOGLE_ALERTS_RSS_URLS

    feed_urls_input = st.text_area(
        "RSSフィードURL（1行に1つ）",
        value="\n".join(GOOGLE_ALERTS_RSS_URLS),
        height=100,
    )

    if st.button("Google Alertsから収集", key="collect_ga"):
        urls = [u.strip() for u in feed_urls_input.split("\n") if u.strip()]
        if not urls:
            st.warning("RSSフィードURLを入力してください。")
        else:
            with st.spinner("収集中..."):
                from collectors.google_alerts import GoogleAlertsCollector

                collector = GoogleAlertsCollector(feed_urls=urls)
                new_companies = collector.collect()

            _register_companies(new_companies, "Google Alerts")


# ==============================================
# TAB 6: CSV/Excel インポート
# ==============================================
with tab6:
    section_header("FILE IMPORT", "CSV/Excelファイルから一括インポート")

    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {COLORS['accent']};">
            <div class="fr-info-title">対応フォーマット</div>
            <div class="fr-info-content">
                CSV (.csv)、TSV (.tsv)、Excel (.xlsx, .xls)<br>
                ヘッダー行に「企業名」「会社名」等のカラムがあれば自動で検出します。<br>
                「URL」「業種」「メモ」カラムがあればそれも取り込みます。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "ファイルをアップロード",
            type=["csv", "tsv", "xlsx", "xls"],
            key="csv_upload",
        )
    with col2:
        source_label = st.text_input(
            "ソースラベル（任意）",
            value="",
            placeholder="例: 展示会名刺リスト2026",
            help="どこから入手したリストかメモ",
        )

    if uploaded_file:
        # プレビュー表示
        try:
            from collectors.csv_import import CSVImporter
            import pandas as pd

            data = uploaded_file.read()
            uploaded_file.seek(0)  # リセット

            preview_companies = CSVImporter.import_from_bytes(
                data, uploaded_file.name, source_label or "プレビュー"
            )

            if preview_companies:
                st.markdown(
                    f"""
                    <div class="fr-info-card" style="border-left:4px solid {COLORS['gold']};">
                        <div class="fr-info-title">プレビュー</div>
                        <div class="fr-info-content">{len(preview_companies)}社を検出しました</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                df = pd.DataFrame([c.model_dump() for c in preview_companies[:10]])
                st.dataframe(df[["name", "url", "memo"]], use_container_width=True)
                if len(preview_companies) > 10:
                    st.caption(f"他 {len(preview_companies) - 10}社...")
            else:
                st.warning("企業データを抽出できませんでした。ヘッダー行を確認してください。")
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")

    if st.button("インポート実行", key="import_csv", disabled=not uploaded_file):
        with st.spinner("インポート中..."):
            from collectors.csv_import import CSVImporter

            data = uploaded_file.read()
            try:
                new_companies = CSVImporter.import_from_bytes(
                    data, uploaded_file.name, source_label or "ファイルインポート"
                )
                _register_companies(new_companies, source_label or "ファイルインポート")
            except Exception as e:
                st.error(f"インポートエラー: {e}")


# ==============================================
# 手動追加
# ==============================================
st.divider()
section_header("MANUAL", "手動追加")

with st.form("manual_add"):
    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input("企業名 *")
        company_url = st.text_input("企業URL")
    with col2:
        article_title = st.text_input("関連記事タイトル")
        article_url = st.text_input("関連記事URL")
    memo = st.text_area("メモ", height=68)
    submitted = st.form_submit_button("追加する")

    if submitted:
        if not company_name:
            st.error("企業名は必須です。")
        else:
            from sheets.models import Company
            from sheets.sync import master_add_companies

            company = Company(
                name=company_name,
                url=company_url,
                source="手動追加",
                article_title=article_title,
                article_url=article_url,
                memo=memo,
            )
            added, _ = master_add_companies([company])
            if added > 0:
                st.success(f"{company_name}を企業マスターに登録しました！")
            else:
                st.warning(f"{company_name}は既に登録済みです。")


# ==============================================
# 登録企業一覧
# ==============================================
st.divider()
section_header("DATABASE", "登録企業一覧")

if st.button("一覧を更新", key="refresh_list"):
    st.rerun()

try:
    from sheets.sync import master_read_all
    from sheets.models import CompanyMaster
    import pandas as pd

    masters = master_read_all()
    if masters:
        df = pd.DataFrame([m.model_dump() for m in masters])

        # ソースカテゴリ別の集計
        source_counts = df["source_category"].value_counts()
        cols = st.columns(min(len(source_counts), 6))
        for i, (source, count) in enumerate(source_counts.items()):
            with cols[i % len(cols)]:
                st.markdown(
                    f"""<div class="fr-metric-card" style="background:{COLORS['primary_dark']}; padding:1rem;">
                        <div class="fr-metric-label" style="font-size:0.75rem;">{source}</div>
                        <div class="fr-metric-value" style="font-size:1.5rem;">{count}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        # ステータス別集計
        status_counts = df["status"].value_counts()
        status_cols = st.columns(min(len(status_counts), 5))
        for i, (status, count) in enumerate(status_counts.items()):
            with status_cols[i % len(status_cols)]:
                st.metric(status, f"{count}社")

        # フィルタ
        filter_source = st.multiselect(
            "ソースでフィルタ",
            options=sorted(df["source_category"].unique()),
            default=[],
        )
        if filter_source:
            df = df[df["source_category"].isin(filter_source)]

        st.dataframe(
            df[[
                "id", "name", "url", "source_category", "industry",
                "employee_scale", "status", "discovered_at", "memo",
            ]].rename(columns={
                "id": "ID", "name": "企業名", "url": "URL",
                "source_category": "ソース", "industry": "業種",
                "employee_scale": "従業員規模", "status": "ステータス",
                "discovered_at": "発見日", "memo": "メモ",
            }),
            use_container_width=True,
        )
        st.caption(f"表示: {len(df)}社 / 全{len(masters)}社")
    else:
        st.info("まだ企業が登録されていません。上のタブから収集を開始してください。")
except Exception as e:
    st.error(f"企業マスターの読み込みに失敗しました: {e}")
