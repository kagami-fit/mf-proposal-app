"""CSV/Excelファイル一括インポート

展示会の名刺リスト、業界団体の会員リスト等を
CSV/Excelファイルからまとめてインポートする。
"""

import io
from pathlib import Path

from sheets.models import Company


class CSVImporter:
    """CSV/Excelファイルから企業リストを一括インポート"""

    SOURCE_NAME = "ファイルインポート"

    # 企業名カラムの候補名（大文字小文字無視で部分一致）
    NAME_CANDIDATES = [
        "企業名", "会社名", "法人名", "社名", "名称",
        "company", "name", "corporation",
    ]

    URL_CANDIDATES = [
        "url", "hp", "ホームページ", "ウェブサイト", "website", "サイト",
    ]

    INDUSTRY_CANDIDATES = [
        "業種", "業界", "industry", "sector",
    ]

    MEMO_CANDIDATES = [
        "メモ", "備考", "memo", "note", "notes", "コメント",
    ]

    @classmethod
    def import_from_bytes(
        cls,
        data: bytes,
        filename: str,
        source_label: str = "",
    ) -> list[Company]:
        """バイトデータからインポート"""
        ext = Path(filename).suffix.lower()

        if ext == ".csv":
            return cls._parse_csv(data, source_label)
        elif ext == ".tsv":
            return cls._parse_csv(data, source_label, delimiter="\t")
        elif ext in (".xlsx", ".xls"):
            return cls._parse_excel(data, source_label)
        else:
            raise ValueError(f"未対応のファイル形式: {ext}（CSV, TSV, XLSX, XLS に対応）")

    @classmethod
    def _parse_csv(
        cls,
        data: bytes,
        source_label: str,
        delimiter: str = ",",
    ) -> list[Company]:
        """CSVファイルをパース"""
        import csv

        # エンコーディング検出
        text = None
        for encoding in ["utf-8-sig", "utf-8", "shift_jis", "cp932", "euc-jp"]:
            try:
                text = data.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if text is None:
            raise ValueError("ファイルのエンコーディングを判定できませんでした")

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("ヘッダー行が見つかりません")

        # カラムマッピング
        col_map = cls._detect_columns(reader.fieldnames)
        if not col_map.get("name"):
            raise ValueError(
                f"企業名カラムが見つかりません。ヘッダー: {reader.fieldnames}"
            )

        companies = []
        for row in reader:
            name = row.get(col_map["name"], "").strip()
            if not name:
                continue

            companies.append(
                Company(
                    name=name,
                    url=row.get(col_map.get("url", ""), "").strip(),
                    source=source_label or cls.SOURCE_NAME,
                    article_title="",
                    article_url="",
                    status="新規",
                    memo=row.get(col_map.get("memo", ""), "").strip(),
                )
            )

        return companies

    @classmethod
    def _parse_excel(cls, data: bytes, source_label: str) -> list[Company]:
        """Excelファイルをパース"""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandasが必要です: pip install pandas openpyxl")

        df = pd.read_excel(io.BytesIO(data))

        # カラムマッピング
        col_map = cls._detect_columns([str(c) for c in df.columns])
        if not col_map.get("name"):
            raise ValueError(
                f"企業名カラムが見つかりません。ヘッダー: {list(df.columns)}"
            )

        companies = []
        for _, row in df.iterrows():
            name = str(row.get(col_map["name"], "")).strip()
            if not name or name == "nan":
                continue

            url = ""
            if col_map.get("url"):
                url = str(row.get(col_map["url"], "")).strip()
                if url == "nan":
                    url = ""

            memo = ""
            if col_map.get("memo"):
                memo = str(row.get(col_map["memo"], "")).strip()
                if memo == "nan":
                    memo = ""

            # 業種がある場合はメモに追加
            if col_map.get("industry"):
                industry = str(row.get(col_map["industry"], "")).strip()
                if industry and industry != "nan":
                    memo = f"業種: {industry}" + (f" / {memo}" if memo else "")

            companies.append(
                Company(
                    name=name,
                    url=url,
                    source=source_label or cls.SOURCE_NAME,
                    article_title="",
                    article_url="",
                    status="新規",
                    memo=memo,
                )
            )

        return companies

    @classmethod
    def _detect_columns(cls, headers: list[str]) -> dict[str, str]:
        """ヘッダー名から自動でカラムマッピングを検出"""
        mapping = {}

        for header in headers:
            h_lower = header.lower().strip()

            if not mapping.get("name"):
                for candidate in cls.NAME_CANDIDATES:
                    if candidate.lower() in h_lower:
                        mapping["name"] = header
                        break

            if not mapping.get("url"):
                for candidate in cls.URL_CANDIDATES:
                    if candidate.lower() in h_lower:
                        mapping["url"] = header
                        break

            if not mapping.get("industry"):
                for candidate in cls.INDUSTRY_CANDIDATES:
                    if candidate.lower() in h_lower:
                        mapping["industry"] = header
                        break

            if not mapping.get("memo"):
                for candidate in cls.MEMO_CANDIDATES:
                    if candidate.lower() in h_lower:
                        mapping["memo"] = header
                        break

        return mapping

    @classmethod
    def get_supported_formats(cls) -> str:
        return "CSV (.csv), TSV (.tsv), Excel (.xlsx, .xls)"
