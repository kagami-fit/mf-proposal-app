"""Google Sheets読み書き（Google Sheets未設定時はローカルJSON保存にフォールバック）

企業マスターシートを中心とした統合データ管理。
旧シート名での呼び出しも後方互換で対応。
"""

import json
from pathlib import Path
from typing import Type, TypeVar

from sheets.models import Analysis, Company, CompanyMaster, Proposal, SourceCategory

T = TypeVar("T", Company, Analysis, Proposal, CompanyMaster)

# シート名定数
SHEET_MASTER = "企業マスター"
SHEET_PROPOSALS = "提案内容"

# 後方互換
SHEET_COMPANIES = "企業リスト"
SHEET_ANALYSIS = "企業分析"

# ローカル保存先
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Google Sheets が使えるかチェック
_use_gsheets = False
try:
    from sheets.client import get_spreadsheet

    get_spreadsheet()
    _use_gsheets = True
except Exception:
    _use_gsheets = False


# ─── ローカルJSON ストレージ ───

def _local_path(sheet_name: str) -> Path:
    LOCAL_DATA_DIR.mkdir(exist_ok=True)
    return LOCAL_DATA_DIR / f"{sheet_name}.json"


def _local_read_rows(sheet_name: str) -> list[list[str]]:
    path = _local_path(sheet_name)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _local_write_rows(sheet_name: str, rows: list[list[str]]) -> None:
    path = _local_path(sheet_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


# ─── Google Sheets ストレージ ───

def _gs_get_sheet(sheet_name: str):
    import gspread

    sp = get_spreadsheet()
    headers_map = {
        SHEET_MASTER: CompanyMaster.headers(),
        SHEET_PROPOSALS: Proposal.headers(),
        # 後方互換
        SHEET_COMPANIES: Company.headers(),
        SHEET_ANALYSIS: Analysis.headers(),
    }
    headers = headers_map.get(sheet_name, [])
    try:
        ws = sp.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        cols = max(len(headers), 27)
        ws = sp.add_worksheet(title=sheet_name, rows=2000, cols=cols)
        if headers:
            ws.append_row(headers)
            # マスターシートのヘッダーに色付け書式設定
            if sheet_name == SHEET_MASTER:
                _format_master_header(ws)
    return ws


def _format_master_header(ws):
    """マスターシートのヘッダー行にフォーマットを適用"""
    try:
        ws.format("A1:AA1", {
            "backgroundColor": {"red": 0.176, "green": 0.2, "blue": 0.216},  # #2D3337
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "fontSize": 10,
            },
            "horizontalAlignment": "CENTER",
        })
        # 列幅を設定（シート全体で使いやすく）
        ws.freeze(rows=1)  # ヘッダー固定
    except Exception:
        pass  # フォーマット設定に失敗しても処理は続行


# ─── 共通インターフェース ───

def read_all(sheet_name: str, model_class: Type[T]) -> list[T]:
    """全データを読み込み"""
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        return [model_class.from_row(row) for row in rows[1:] if any(row)]
    else:
        rows = _local_read_rows(sheet_name)
        return [model_class.from_row(row) for row in rows if any(row)]


def append_row(sheet_name: str, model_instance) -> None:
    """1行追加"""
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        ws.append_row(model_instance.to_row())
    else:
        rows = _local_read_rows(sheet_name)
        rows.append(model_instance.to_row())
        _local_write_rows(sheet_name, rows)


def append_rows(sheet_name: str, models: list) -> None:
    """複数行を一括追加"""
    if not models:
        return
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        ws.append_rows([m.to_row() for m in models])
    else:
        rows = _local_read_rows(sheet_name)
        rows.extend(m.to_row() for m in models)
        _local_write_rows(sheet_name, rows)


def update_cell(sheet_name: str, row_index: int, col_index: int, value: str) -> None:
    """特定セルを更新（row_index, col_indexは1始まり、ヘッダー含む）"""
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        ws.update_cell(row_index, col_index, value)
    else:
        rows = _local_read_rows(sheet_name)
        idx = row_index - 2
        if 0 <= idx < len(rows):
            rows[idx][col_index - 1] = value
            _local_write_rows(sheet_name, rows)


def find_row_by_id(sheet_name: str, target_id: str) -> int | None:
    """IDカラムで行番号を検索。Google Sheets互換の行番号（ヘッダー込み1始まり）を返す"""
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        all_values = ws.col_values(1)
        for i, val in enumerate(all_values):
            if val == target_id:
                return i + 1
        return None
    else:
        rows = _local_read_rows(sheet_name)
        for i, row in enumerate(rows):
            if row and row[0] == target_id:
                return i + 2
        return None


def update_row(sheet_name: str, row_index: int, model_instance) -> None:
    """行全体を更新"""
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        row_data = model_instance.to_row()
        col_count = len(row_data)
        cell_range = ws.range(row_index, 1, row_index, col_count)
        for cell, value in zip(cell_range, row_data):
            cell.value = value
        ws.update_cells(cell_range)
    else:
        rows = _local_read_rows(sheet_name)
        idx = row_index - 2
        if 0 <= idx < len(rows):
            rows[idx] = model_instance.to_row()
            _local_write_rows(sheet_name, rows)


def get_next_id(sheet_name: str, prefix: str = "C") -> str:
    """次のID番号を生成（例: C001, A001, P001）"""
    if _use_gsheets:
        ws = _gs_get_sheet(sheet_name)
        ids = ws.col_values(1)
        if len(ids) <= 1:
            return f"{prefix}001"
        id_list = ids[1:]
    else:
        rows = _local_read_rows(sheet_name)
        if not rows:
            return f"{prefix}001"
        id_list = [row[0] for row in rows if row]

    max_num = 0
    for id_val in id_list:
        if id_val.startswith(prefix):
            try:
                num = int(id_val[len(prefix):])
                max_num = max(max_num, num)
            except ValueError:
                continue
    return f"{prefix}{max_num + 1:03d}"


# ============================================================
# 企業マスター専用操作
# ============================================================

def master_read_all() -> list[CompanyMaster]:
    """企業マスターの全データを読み込み"""
    return read_all(SHEET_MASTER, CompanyMaster)


def master_add_companies(companies: list[Company]) -> tuple[int, int]:
    """Companyリストをマスターに追加（重複除外）。
    Returns: (追加数, 重複数)
    """
    existing = master_read_all()
    existing_names = {m.name for m in existing}

    new_masters = []
    dup_count = 0

    next_num = _get_next_master_id_num(existing)

    for c in companies:
        if c.name in existing_names:
            dup_count += 1
            continue

        existing_names.add(c.name)
        master = CompanyMaster.from_company(c)
        master.id = f"C{next_num:03d}"
        next_num += 1
        new_masters.append(master)

    if new_masters:
        append_rows(SHEET_MASTER, new_masters)

    return len(new_masters), dup_count


def master_update_analysis(company_id: str, analysis: Analysis, extra: dict | None = None) -> bool:
    """マスター上の企業に分析結果を反映。extraにLLMの生データを渡すと企業概要も更新"""
    row_idx = find_row_by_id(SHEET_MASTER, company_id)
    if row_idx is None:
        return False

    # 既存行を読み込み
    masters = master_read_all()
    target = None
    for m in masters:
        if m.id == company_id:
            target = m
            break

    if target is None:
        return False

    target.apply_analysis(analysis, extra=extra)
    update_row(SHEET_MASTER, row_idx, target)
    return True


def master_update_proposal(company_id: str, proposal: Proposal) -> bool:
    """マスター上の企業に提案情報を反映"""
    row_idx = find_row_by_id(SHEET_MASTER, company_id)
    if row_idx is None:
        return False

    masters = master_read_all()
    target = None
    for m in masters:
        if m.id == company_id:
            target = m
            break

    if target is None:
        return False

    target.apply_proposal(proposal)
    update_row(SHEET_MASTER, row_idx, target)
    return True


def master_update_status(company_id: str, status: str) -> bool:
    """マスター上の企業のステータスを更新"""
    row_idx = find_row_by_id(SHEET_MASTER, company_id)
    if row_idx is None:
        return False
    # ステータスは17列目（1始まり）
    update_cell(SHEET_MASTER, row_idx, 17, status)
    return True


def master_update_send_date(company_id: str, send_date: str) -> bool:
    """送信日を更新"""
    row_idx = find_row_by_id(SHEET_MASTER, company_id)
    if row_idx is None:
        return False
    # 送信日は20列目
    update_cell(SHEET_MASTER, row_idx, 20, send_date)
    # ステータスも更新
    update_cell(SHEET_MASTER, row_idx, 17, "送信済み")
    return True


def master_update_contact(company_id: str, contact: dict) -> bool:
    """マスター上の企業に連絡先情報を反映"""
    row_idx = find_row_by_id(SHEET_MASTER, company_id)
    if row_idx is None:
        return False

    masters = master_read_all()
    target = None
    for m in masters:
        if m.id == company_id:
            target = m
            break

    if target is None:
        return False

    target.apply_contact(contact)
    update_row(SHEET_MASTER, row_idx, target)
    return True


def master_get_by_id(company_id: str) -> CompanyMaster | None:
    """IDでマスターから1件取得"""
    masters = master_read_all()
    for m in masters:
        if m.id == company_id:
            return m
    return None


def _get_next_master_id_num(existing: list[CompanyMaster]) -> int:
    """マスター用の次のID番号を取得"""
    max_num = 0
    for m in existing:
        if m.id.startswith("C"):
            try:
                num = int(m.id[1:])
                max_num = max(max_num, num)
            except ValueError:
                continue
    return max_num + 1


# ============================================================
# マイグレーション: 旧3シート → 企業マスター
# ============================================================

def migrate_to_master() -> dict:
    """旧シート（企業リスト + 企業分析 + 提案内容）のデータを企業マスターに統合

    Returns:
        {"migrated": 件数, "skipped": 件数, "errors": エラーリスト}
    """
    result = {"migrated": 0, "skipped": 0, "errors": []}

    # 旧データ読み込み
    try:
        old_companies = read_all(SHEET_COMPANIES, Company)
    except Exception:
        old_companies = []

    try:
        old_analyses = read_all(SHEET_ANALYSIS, Analysis)
    except Exception:
        old_analyses = []

    try:
        old_proposals = read_all(SHEET_PROPOSALS, Proposal)
    except Exception:
        old_proposals = []

    if not old_companies:
        return result

    # マスターの既存データ
    existing_master = master_read_all()
    existing_names = {m.name for m in existing_master}

    # インデックス作成
    analysis_map = {a.company_id: a for a in old_analyses}
    proposal_map = {p.company_id: p for p in old_proposals}

    new_masters = []
    next_num = _get_next_master_id_num(existing_master)

    for c in old_companies:
        if c.name in existing_names:
            result["skipped"] += 1
            continue

        existing_names.add(c.name)

        master = CompanyMaster.from_company(c)
        master.id = f"C{next_num:03d}"
        next_num += 1

        # 分析結果があれば反映
        old_id = c.id
        if old_id in analysis_map:
            master.apply_analysis(analysis_map[old_id])

        # 提案があれば反映
        if old_id in proposal_map:
            master.apply_proposal(proposal_map[old_id])

        new_masters.append(master)
        result["migrated"] += 1

    if new_masters:
        append_rows(SHEET_MASTER, new_masters)

    return result
