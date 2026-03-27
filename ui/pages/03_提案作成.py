"""提案作成画面（企業マスター連携版）"""

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="提案作成", page_icon="📝", layout="wide")

from ui.theme import page_header, section_header, COLORS

page_header("提案作成", "分析結果をもとにAIが提案文を自動生成します")

try:
    from sheets.sync import (
        master_read_all, master_update_proposal,
        SHEET_PROPOSALS, read_all, append_row, find_row_by_id, update_row,
    )
    from sheets.models import Proposal
    import pandas as pd

    masters = master_read_all()
    proposals = read_all(SHEET_PROPOSALS, Proposal)
except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.stop()

analyzed_masters = [m for m in masters if m.is_analyzed]

if not analyzed_masters:
    st.info("まだ分析済みの企業がありません。「企業分析」画面で企業を分析してください。")
    st.stop()

proposal_map = {p.company_id: p for p in proposals}


def _get_reference_proposals(target_industry: str, exclude_id: str, max_count: int = 3) -> list[dict]:
    confirmed = [p for p in proposals if p.approval_status == "確定済み" and p.company_id != exclude_id]
    if not confirmed:
        return []
    same_industry_ids = {m.id for m in masters if target_industry and target_industry in m.industry}
    same = [p for p in confirmed if p.company_id in same_industry_ids]
    others = [p for p in confirmed if p.company_id not in same_industry_ids]
    return [
        {"company_name": p.company_name, "body": p.body, "subject": p.subject}
        for p in (same + others)[:max_count]
    ]


def _do_generate(target, *, revision_instruction="", previous_draft="", tone="丁寧", length_hint="400〜600文字", use_reference=True):
    """提案文を生成してsession_stateに保存。成功ならTrue。"""
    from analyzers.proposal_generator import ProposalGenerator

    generator = ProposalGenerator()
    ref_proposals = _get_reference_proposals(target.industry, target.id) if use_reference else None

    result = generator.generate(
        company_name=target.name,
        industry=target.industry,
        employee_scale=target.employee_scale,
        health_management_efforts=target.health_efforts,
        estimated_challenges=target.estimated_challenges,
        estimated_needs=target.estimated_needs,
        revision_instruction=revision_instruction,
        previous_draft=previous_draft,
        tone=tone,
        length_hint=length_hint,
        reference_proposals=ref_proposals,
    )

    if result:
        result.company_id = target.id
        result.company_name = target.name
        st.session_state["draft_proposal"] = {
            "company_id": result.company_id,
            "company_name": result.company_name,
            "subject": result.subject,
            "body": result.body,
            "key_points": result.key_points,
            "form_url": result.form_url,
            "generated_at": result.generated_at,
            "approval_status": "未確認",
            "approved_by": "",
        }
        # selectboxの選択を保持
        st.session_state["selected_company_id"] = target.id
        return True
    return False


# ============================================================
# 企業選択 — session_stateで選択を保持
# ============================================================
section_header("GENERATE", "提案文を生成する企業を選択")

options_list = [f"{m.id}: {m.name} [{m.source_category}] ({m.industry})" for m in analyzed_masters]
options_map = {f"{m.id}: {m.name} [{m.source_category}] ({m.industry})": m for m in analyzed_masters}

# ドラフトがある場合、その企業をデフォルト選択にする
default_idx = 0
saved_id = st.session_state.get("selected_company_id")
if saved_id:
    for i, m in enumerate(analyzed_masters):
        if m.id == saved_id:
            default_idx = i
            break

selected_key = st.selectbox("企業を選択", options_list, index=default_idx, key="company_select")
target = options_map[selected_key]
st.session_state["selected_company_id"] = target.id

existing_proposal = proposal_map.get(target.id)

# ドラフトが別企業のものならクリア。古いPydanticオブジェクトが残っていたらdictに変換。
draft_data = st.session_state.get("draft_proposal")
if draft_data is not None:
    if not isinstance(draft_data, dict):
        try:
            draft_data = draft_data.model_dump()
        except Exception:
            draft_data = None
        st.session_state["draft_proposal"] = draft_data
    if draft_data and draft_data.get("company_id") != target.id:
        del st.session_state["draft_proposal"]
        st.session_state.pop("revision_history", None)
        draft_data = None

with st.expander("分析情報", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**業種:** {target.industry}")
        st.markdown(f"**従業員規模:** {target.employee_scale}")
        st.markdown(f"**健康経営への取り組み:** {target.health_efforts}")
    with col2:
        st.markdown(f"**推定課題:** {target.estimated_challenges}")
        st.markdown(f"**推定ニーズ:** {target.estimated_needs}")
        st.markdown(f"**確信度:** {target.confidence_score}")

if existing_proposal:
    st.info("この企業には既に提案文が生成されています。再生成も可能です。")

# --- 生成オプション ---
with st.expander("生成オプション", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        tone = st.selectbox("トーン", ["丁寧", "カジュアル", "簡潔"], index=0, key="tone")
    with col2:
        length_hint = st.selectbox(
            "文字数", ["200〜300文字", "400〜600文字", "600〜800文字"], index=1, key="length",
        )
    with col3:
        use_reference = st.checkbox("過去の確定済み提案を参考にする", value=True, key="use_ref")


# ============================================================
# 初回生成
# ============================================================
if not draft_data:
    if st.button("提案文を生成", key="generate_proposal"):
        with st.spinner("AIが提案文を生成中..."):
            ok = _do_generate(target, tone=tone, length_hint=length_hint, use_reference=use_reference)
        if ok:
            st.session_state["revision_history"] = []
            st.rerun()
        else:
            st.error("提案文の生成に失敗しました。")


# ============================================================
# レビュー画面（ドラフトがある場合のみ）
# ============================================================
draft_data = st.session_state.get("draft_proposal")
if draft_data and draft_data.get("company_id") == target.id:
    st.divider()
    section_header("REVIEW", "提案文レビュー")

    edited_subject = st.text_input("件名", value=draft_data["subject"], key="edit_subject")
    edited_body = st.text_area("本文", value=draft_data["body"], height=300, key="edit_body")
    edited_points = st.text_area("提案ポイント", value=draft_data["key_points"], height=100, key="edit_points")

    # やり直し履歴
    history = st.session_state.get("revision_history", [])
    if history:
        with st.expander(f"修正履歴（{len(history)}回）", expanded=False):
            for i, h in enumerate(history, 1):
                st.markdown(f"**{i}回目:** {h['instruction']}")

    # --- 確定ボタン ---
    if st.button("提案を確定する", key="approve_proposal", type="primary"):
        final = Proposal(
            company_id=target.id,
            company_name=target.name,
            subject=edited_subject,
            body=edited_body,
            key_points=edited_points,
            approval_status="確定済み",
        )
        if existing_proposal:
            row_idx = find_row_by_id(SHEET_PROPOSALS, target.id)
            if row_idx:
                update_row(SHEET_PROPOSALS, row_idx, final)
        else:
            append_row(SHEET_PROPOSALS, final)

        master_update_proposal(target.id, final)
        st.success("提案文を確定し、企業マスターに反映しました！")
        del st.session_state["draft_proposal"]
        st.session_state.pop("revision_history", None)
        st.rerun()

    # --- 修正して再生成 ---
    st.divider()
    section_header("REVISE", "修正して再生成")

    st.caption("例: 「もっと簡潔にして」「ROIの数字を入れて」「冒頭の挨拶を変えて」「業界特有の課題にフォーカスして」")

    revision_instruction = st.text_area(
        "修正指示（空欄ならゼロから再生成）",
        placeholder="修正したい内容を自由に書いてください...",
        key="revision_input",
        height=100,
    )

    if st.button("再生成する", key="do_revision"):
        previous_json = ""
        if revision_instruction.strip():
            previous_json = json.dumps({
                "subject": edited_subject,
                "body": edited_body,
                "key_points": edited_points.split(" / ") if " / " in edited_points else [edited_points],
            }, ensure_ascii=False)

        with st.spinner("再生成中..."):
            ok = _do_generate(
                target,
                revision_instruction=revision_instruction.strip(),
                previous_draft=previous_json,
                tone=tone,
                length_hint=length_hint,
                use_reference=use_reference,
            )

        if ok:
            if revision_instruction.strip():
                history = st.session_state.get("revision_history", [])
                history.append({"instruction": revision_instruction.strip()})
                st.session_state["revision_history"] = history
            st.rerun()
        else:
            st.error("再生成に失敗しました。")

# ============================================================
# 提案一覧
# ============================================================
st.divider()
section_header("LIST", "提案一覧")

if proposals:
    df = pd.DataFrame([p.model_dump() for p in proposals])
    st.dataframe(
        df[["company_id", "company_name", "subject", "approval_status", "generated_at"]].rename(columns={
            "company_id": "ID", "company_name": "企業名", "subject": "件名",
            "approval_status": "ステータス", "generated_at": "生成日時",
        }),
        use_container_width=True,
    )
else:
    st.info("まだ提案文が作成されていません。")
