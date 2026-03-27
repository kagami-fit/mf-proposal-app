"""ダッシュボード画面（企業マスター連携版）"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st

st.set_page_config(page_title="ダッシュボード", page_icon="📊", layout="wide")

from ui.theme import page_header, section_header, COLORS

page_header("ダッシュボード", "進捗状況の一覧と統計")

try:
    from sheets.sync import master_read_all
    from sheets.models import CompanyMaster
    import pandas as pd

    masters = master_read_all()
except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.stop()

if not masters:
    st.info("まだデータがありません。「企業収集」画面から始めてください。")
    st.stop()

# --- サマリー指標 ---
total = len(masters)
analyzed = len([m for m in masters if m.is_analyzed])
proposed = len([m for m in masters if m.is_proposed])
sent = len([m for m in masters if m.status == "送信済み"])

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""<div class="fr-metric-card" style="background:{COLORS['primary_dark']};">
            <div class="fr-metric-label">TOTAL</div>
            <div class="fr-metric-value">{total}</div>
            <div class="fr-metric-sub">収集企業数</div>
        </div>""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""<div class="fr-metric-card" style="background:{COLORS['secondary']};">
            <div class="fr-metric-label">ANALYZED</div>
            <div class="fr-metric-value">{analyzed}</div>
            <div class="fr-metric-sub">分析済み</div>
        </div>""",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"""<div class="fr-metric-card" style="background:{COLORS['gold']};">
            <div class="fr-metric-label">PROPOSED</div>
            <div class="fr-metric-value">{proposed}</div>
            <div class="fr-metric-sub">提案作成済み</div>
        </div>""",
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"""<div class="fr-metric-card" style="background:{COLORS['accent']};">
            <div class="fr-metric-label">SENT</div>
            <div class="fr-metric-value">{sent}</div>
            <div class="fr-metric-sub">送信済み</div>
        </div>""",
        unsafe_allow_html=True,
    )

# --- パイプライン ---
st.divider()
section_header("PIPELINE", "パイプライン状況")

df = pd.DataFrame([m.model_dump() for m in masters])

# ステータス別の件数
status_counts = df["status"].value_counts()
st.bar_chart(status_counts)

# フィルタ付きテーブル
col1, col2 = st.columns(2)
with col1:
    status_filter = st.multiselect(
        "ステータスでフィルタ",
        options=sorted(df["status"].unique().tolist()),
        default=[],
    )
with col2:
    source_filter = st.multiselect(
        "ソースでフィルタ",
        options=sorted(df["source_category"].unique().tolist()),
        default=[],
    )

filtered = df.copy()
if status_filter:
    filtered = filtered[filtered["status"].isin(status_filter)]
if source_filter:
    filtered = filtered[filtered["source_category"].isin(source_filter)]

st.dataframe(
    filtered[[
        "id", "name", "source_category", "industry", "employee_scale",
        "status", "confidence_score", "analysis_date", "proposal_status", "send_date",
        "email", "phone", "contact_url",
    ]].rename(columns={
        "id": "ID", "name": "企業名", "source_category": "ソース",
        "industry": "業種", "employee_scale": "従業員規模",
        "status": "進捗", "confidence_score": "確信度",
        "analysis_date": "分析日", "proposal_status": "提案",
        "send_date": "送信日", "email": "メール",
        "phone": "電話", "contact_url": "問い合わせURL",
    }),
    use_container_width=True,
)
st.caption(f"表示: {len(filtered)}社 / 全{len(df)}社")

# --- ソースカテゴリ別統計 ---
st.divider()
section_header("SOURCE", "ソースカテゴリ別統計")

source_counts = df["source_category"].value_counts()
st.bar_chart(source_counts)

# --- 分析品質 ---
analyzed_df = df[df["confidence_score"] != ""]
if not analyzed_df.empty:
    st.divider()
    section_header("QUALITY", "分析品質")

    scores = analyzed_df["confidence_score"].astype(float)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("平均確信度", f"{scores.mean():.2f}")
    with col2:
        st.metric("最高確信度", f"{scores.max():.2f}")
    with col3:
        st.metric("最低確信度", f"{scores.min():.2f}")

    # 業種分布
    industries = analyzed_df[analyzed_df["industry"] != ""]["industry"]
    if not industries.empty:
        st.bar_chart(industries.value_counts())
