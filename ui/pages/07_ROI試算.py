"""ROI試算ツール画面"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import re

import streamlit as st

st.set_page_config(page_title="ROI試算", page_icon="💰", layout="wide")

from ui.theme import page_header, section_header, metric_card, COLORS

page_header("ROI試算ツール", "健康経営の損失コストと投資対効果を試算します")

# --- 企業マスターからデータ読み込み ---
try:
    from sheets.sync import master_read_all
    from sheets.models import CompanyMaster

    masters = master_read_all()
    # 分析済みのみ
    analyses = [m for m in masters if m.is_analyzed]
except Exception:
    masters = []
    analyses = []


def _parse_employee_count(scale_text: str) -> int | None:
    """従業員規模テキストから数値を抽出"""
    if not scale_text:
        return None
    range_match = re.search(r"(\d[\d,]*)\s*[〜~\-ー]\s*(\d[\d,]*)", scale_text)
    if range_match:
        low = int(range_match.group(1).replace(",", ""))
        high = int(range_match.group(2).replace(",", ""))
        return (low + high) // 2
    num_match = re.search(r"(\d[\d,]+)", scale_text)
    if num_match:
        return int(num_match.group(1).replace(",", ""))
    return None


# ==============================================
# INPUT
# ==============================================
section_header("INPUT", "試算条件の入力")

input_mode = st.radio(
    "入力方法",
    ["分析済み企業から選択", "手動入力"],
    horizontal=True,
)

company_name = ""
default_employees = 100
default_salary = 5_000_000

if input_mode == "分析済み企業から選択" and analyses:
    options = {}
    for m in analyses:
        label = f"{m.id}: {m.name} [{m.source_category}] ({m.industry})"
        options[label] = m

    selected_label = st.selectbox("企業を選択", list(options.keys()))
    if selected_label:
        selected = options[selected_label]
        company_name = selected.name

        parsed_emp = _parse_employee_count(selected.employee_scale)
        if parsed_emp:
            default_employees = parsed_emp
            st.markdown(
                f"""<div class="fr-info-card" style="border-left:4px solid {COLORS['gold']};">
                    <div class="fr-info-title">自動取得</div>
                    <div class="fr-info-content">従業員数: 約 {parsed_emp:,} 名（{selected.employee_scale}）</div>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.warning(f"従業員数を自動取得できませんでした（記載: {selected.employee_scale}）")

elif input_mode == "分析済み企業から選択" and not analyses:
    st.info("分析済み企業がありません。手動入力で試算できます。")

if input_mode == "手動入力":
    company_name = st.text_input("企業名（任意）", value="")

col1, col2 = st.columns(2)
with col1:
    employee_count = st.number_input(
        "従業員数",
        min_value=1,
        max_value=1_000_000,
        value=default_employees,
        step=10,
    )
with col2:
    avg_salary = st.number_input(
        "平均年収（円）",
        min_value=1_000_000,
        max_value=50_000_000,
        value=default_salary,
        step=100_000,
        format="%d",
    )

# ==============================================
# LOSS COST
# ==============================================
PRESENTEEISM_RATE = 0.11
ABSENTEEISM_RATE = 0.02

presenteeism_cost = avg_salary * PRESENTEEISM_RATE * employee_count
absenteeism_cost = avg_salary * ABSENTEEISM_RATE * employee_count
total_loss = presenteeism_cost + absenteeism_cost

section_header("LOSS COST", "損失コスト試算")

col1, col2, col3 = st.columns(3)
with col1:
    metric_card(
        "PRESENTEEISM",
        f"¥{presenteeism_cost:,.0f}",
        f"年収の11% × {employee_count:,}名",
    )
with col2:
    metric_card(
        "ABSENTEEISM",
        f"¥{absenteeism_cost:,.0f}",
        f"年収の2% × {employee_count:,}名",
    )
with col3:
    metric_card(
        "TOTAL LOSS / YEAR",
        f"¥{total_loss:,.0f}",
        "プレゼンティーズム + アブセンティーズム",
        accent=True,
    )

# 内訳テーブル
st.markdown(
    f"""
    <table class="fr-table" style="margin:1.5rem 0;">
        <thead>
            <tr>
                <th>項目</th>
                <th>計算式</th>
                <th>1人あたり</th>
                <th>全社合計</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <th>プレゼンティーズム</th>
                <td>¥{avg_salary:,} × 11%</td>
                <td>¥{avg_salary * PRESENTEEISM_RATE:,.0f}</td>
                <td class="accent">¥{presenteeism_cost:,.0f}</td>
            </tr>
            <tr>
                <th>アブセンティーズム</th>
                <td>¥{avg_salary:,} × 2%</td>
                <td>¥{avg_salary * ABSENTEEISM_RATE:,.0f}</td>
                <td class="accent">¥{absenteeism_cost:,.0f}</td>
            </tr>
            <tr>
                <th>合計</th>
                <td>年収 × 13%</td>
                <td>¥{avg_salary * (PRESENTEEISM_RATE + ABSENTEEISM_RATE):,.0f}</td>
                <td class="accent" style="font-size:1.2rem; font-weight:700;">¥{total_loss:,.0f}</td>
            </tr>
        </tbody>
    </table>
    """,
    unsafe_allow_html=True,
)

# ==============================================
# ROI
# ==============================================
section_header("ROI", "投資対効果の試算")

col1, col2 = st.columns(2)
with col1:
    investment = st.number_input(
        "健康経営への投資額（年間・円）",
        min_value=0,
        max_value=10_000_000_000,
        value=min(int(total_loss * 0.05), 100_000_000),
        step=100_000,
        format="%d",
    )
with col2:
    improvement_rate = st.slider(
        "損失改善率（%）",
        min_value=1,
        max_value=50,
        value=10,
    )

improvement_amount = total_loss * (improvement_rate / 100)
net_benefit = improvement_amount - investment
roi = (net_benefit / investment * 100) if investment > 0 else 0

col1, col2, col3 = st.columns(3)
with col1:
    metric_card(
        "IMPROVEMENT",
        f"¥{improvement_amount:,.0f}",
        f"損失額 × 改善率{improvement_rate}%",
    )
with col2:
    bg = COLORS["primary_dark"] if net_benefit >= 0 else COLORS["accent"]
    st.markdown(
        f"""<div class="fr-metric-card" style="background:{bg};">
            <div class="fr-metric-label">NET BENEFIT</div>
            <div class="fr-metric-value">¥{net_benefit:,.0f}</div>
            <div class="fr-metric-sub">改善見込額 − 投資額</div>
        </div>""",
        unsafe_allow_html=True,
    )
with col3:
    roi_bg = COLORS["primary_dark"] if roi >= 0 else COLORS["accent"]
    st.markdown(
        f"""<div class="fr-metric-card" style="background:{roi_bg};">
            <div class="fr-metric-label">ROI</div>
            <div class="fr-metric-value" style="font-size:2.8rem;">{roi:,.1f}%</div>
            <div class="fr-metric-sub">{'投資対効果あり' if roi > 0 else '投資超過'}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# ==============================================
# SUMMARY
# ==============================================
section_header("PROPOSAL SUMMARY", "提案用サマリー")

target_label = f"（{company_name}様）" if company_name else ""

summary_text = f"""【健康経営ROI試算{target_label}】

■ 試算条件
・従業員数: {employee_count:,}名
・平均年収: ¥{avg_salary:,}

■ 現状の推定損失額（年間）
・プレゼンティーズム損失（年収×11%）: ¥{presenteeism_cost:,.0f}
・アブセンティーズム損失（年収×2%）: ¥{absenteeism_cost:,.0f}
・合計: ¥{total_loss:,.0f}
・1人あたり: ¥{avg_salary * (PRESENTEEISM_RATE + ABSENTEEISM_RATE):,.0f}

■ 施策導入後の効果試算
・投資額: ¥{investment:,}
・改善率: {improvement_rate}%
・改善見込額: ¥{improvement_amount:,.0f}
・純効果額: ¥{net_benefit:,.0f}
・ROI: {roi:,.1f}%"""

st.text_area("コピーして提案資料にお使いください", value=summary_text, height=320)

st.download_button(
    label="テキストファイルでダウンロード",
    data=summary_text,
    file_name=f"ROI試算_{company_name or '企業名'}.txt",
    mime="text/plain",
)

# Footer
st.markdown(
    f"""<div class="fr-footer">
        フォーム営業管理シート &mdash; ROI試算
    </div>""",
    unsafe_allow_html=True,
)
