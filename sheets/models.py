"""データモデル（Company, Analysis, Proposal, CompanyMaster）"""

from datetime import datetime
from typing import ClassVar, Optional

from pydantic import BaseModel, Field


# ソースカテゴリ定数
class SourceCategory:
    PRTIMES = "PR TIMES"
    GOOGLE_NEWS = "Google News"
    GOOGLE_ALERTS = "Google Alerts"
    CERTIFIED = "健康経営優良法人"
    JOB_SITE = "求人サイト"
    FILE_IMPORT = "ファイルインポート"
    MANUAL = "手動追加"

    ALL = [PRTIMES, GOOGLE_NEWS, GOOGLE_ALERTS, CERTIFIED, JOB_SITE, FILE_IMPORT, MANUAL]

    @classmethod
    def from_source_text(cls, source: str) -> str:
        """ソーステキストからカテゴリを判定"""
        source_lower = source.lower()
        if "pr times" in source_lower or "prtimes" in source_lower:
            return cls.PRTIMES
        elif "google news" in source_lower or "gnews" in source_lower:
            return cls.GOOGLE_NEWS
        elif "google alerts" in source_lower or "alert" in source_lower:
            return cls.GOOGLE_ALERTS
        elif "認定" in source or "優良法人" in source or "certified" in source_lower:
            return cls.CERTIFIED
        elif "求人" in source or "indeed" in source_lower or "job" in source_lower:
            return cls.JOB_SITE
        elif "インポート" in source or "import" in source_lower:
            return cls.FILE_IMPORT
        elif "手動" in source:
            return cls.MANUAL
        else:
            return source[:20] if source else cls.MANUAL


class Company(BaseModel):
    """企業リストのデータモデル（後方互換用）"""

    id: str = Field(default="", description="企業ID")
    name: str = Field(description="企業名")
    url: str = Field(default="", description="企業URL")
    source: str = Field(default="", description="情報ソース")
    discovered_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="発見日",
    )
    article_title: str = Field(default="", description="記事タイトル")
    article_url: str = Field(default="", description="記事URL")
    status: str = Field(default="新規", description="ステータス")
    memo: str = Field(default="", description="メモ")

    def to_row(self) -> list[str]:
        return [
            self.id,
            self.name,
            self.url,
            self.source,
            self.discovered_at,
            self.article_title,
            self.article_url,
            self.status,
            self.memo,
        ]

    @classmethod
    def headers(cls) -> list[str]:
        return [
            "ID", "企業名", "URL", "ソース", "発見日",
            "記事タイトル", "記事URL", "ステータス", "メモ",
        ]

    @classmethod
    def from_row(cls, row: list[str]) -> "Company":
        padded = row + [""] * (9 - len(row))
        return cls(
            id=padded[0], name=padded[1], url=padded[2], source=padded[3],
            discovered_at=padded[4], article_title=padded[5], article_url=padded[6],
            status=padded[7], memo=padded[8],
        )


class Analysis(BaseModel):
    """企業分析のデータモデル（後方互換用）"""

    company_id: str = Field(description="企業ID")
    industry: str = Field(default="", description="業種")
    employee_scale: str = Field(default="", description="従業員規模")
    health_management_efforts: str = Field(default="", description="健康経営への取り組み")
    estimated_challenges: str = Field(default="", description="推定課題")
    estimated_needs: str = Field(default="", description="推定ニーズ")
    confidence_score: float = Field(default=0.0, description="確信度")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="分析日",
    )
    analysis_notes: str = Field(default="", description="分析メモ")

    def to_row(self) -> list[str]:
        return [
            self.company_id, self.industry, self.employee_scale,
            self.health_management_efforts, self.estimated_challenges,
            self.estimated_needs, str(self.confidence_score),
            self.analysis_date, self.analysis_notes,
        ]

    @classmethod
    def headers(cls) -> list[str]:
        return [
            "企業ID", "業種", "従業員規模", "健康経営への取り組み",
            "推定課題", "推定ニーズ", "確信度", "分析日", "分析メモ",
        ]

    @classmethod
    def from_row(cls, row: list[str]) -> "Analysis":
        padded = row + [""] * (9 - len(row))
        return cls(
            company_id=padded[0], industry=padded[1], employee_scale=padded[2],
            health_management_efforts=padded[3], estimated_challenges=padded[4],
            estimated_needs=padded[5],
            confidence_score=float(padded[6]) if padded[6] else 0.0,
            analysis_date=padded[7], analysis_notes=padded[8],
        )


class Proposal(BaseModel):
    """提案内容のデータモデル（後方互換用）"""

    company_id: str = Field(description="企業ID")
    company_name: str = Field(default="", description="企業名")
    subject: str = Field(default="", description="提案タイトル（件名）")
    body: str = Field(default="", description="提案本文")
    key_points: str = Field(default="", description="提案ポイント")
    form_url: str = Field(default="", description="フォームURL")
    generated_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"),
        description="生成日時",
    )
    approval_status: str = Field(default="未確認", description="承認ステータス")
    approved_by: str = Field(default="", description="承認者")

    def to_row(self) -> list[str]:
        return [
            self.company_id, self.company_name, self.subject, self.body,
            self.key_points, self.form_url, self.generated_at,
            self.approval_status, self.approved_by,
        ]

    @classmethod
    def headers(cls) -> list[str]:
        return [
            "企業ID", "企業名", "提案タイトル", "提案本文", "提案ポイント",
            "フォームURL", "生成日時", "承認ステータス", "承認者",
        ]

    @classmethod
    def from_row(cls, row: list[str]) -> "Proposal":
        padded = row + [""] * (9 - len(row))
        return cls(
            company_id=padded[0], company_name=padded[1], subject=padded[2],
            body=padded[3], key_points=padded[4], form_url=padded[5],
            generated_at=padded[6], approval_status=padded[7], approved_by=padded[8],
        )


# ============================================================
# 企業マスター（統合モデル）
# ============================================================

class CompanyMaster(BaseModel):
    """企業マスター: 収集・分析・提案の全情報を1行に集約"""

    # --- 基本情報 ---
    id: str = Field(default="", description="企業ID")
    name: str = Field(description="企業名")
    url: str = Field(default="", description="企業URL")

    # --- 収集情報 ---
    source_category: str = Field(default="", description="ソースカテゴリ")
    source_detail: str = Field(default="", description="ソース詳細")
    discovered_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="発見日",
    )
    article_title: str = Field(default="", description="関連記事")
    article_url: str = Field(default="", description="記事URL")

    # --- 企業属性（分析結果） ---
    industry: str = Field(default="", description="業種")
    employee_scale: str = Field(default="", description="従業員規模")
    health_efforts: str = Field(default="", description="健康経営への取り組み")
    estimated_challenges: str = Field(default="", description="推定課題")
    estimated_needs: str = Field(default="", description="推定ニーズ")

    # --- 分析メタ ---
    confidence_score: str = Field(default="", description="確信度")
    analysis_date: str = Field(default="", description="分析日")
    analysis_notes: str = Field(default="", description="分析メモ")

    # --- 提案・進捗 ---
    status: str = Field(default="新規", description="進捗ステータス")
    proposal_status: str = Field(default="", description="提案ステータス")
    proposal_date: str = Field(default="", description="提案作成日")
    send_date: str = Field(default="", description="送信日")

    # --- 連絡先情報 ---
    email: str = Field(default="", description="メールアドレス")
    phone: str = Field(default="", description="電話番号")
    fax: str = Field(default="", description="FAX番号")
    address: str = Field(default="", description="住所")
    contact_url: str = Field(default="", description="問い合わせページURL")
    contact_form_url: str = Field(default="", description="問い合わせフォームURL")

    # --- 企業概要（分析で取得） ---
    representative: str = Field(default="", description="代表者名")
    established: str = Field(default="", description="設立年")
    capital: str = Field(default="", description="資本金")
    revenue: str = Field(default="", description="売上高")
    listed: str = Field(default="", description="上場区分")

    # --- 自由記入 ---
    memo: str = Field(default="", description="メモ")

    # カラム数: 32

    def to_row(self) -> list[str]:
        return [
            self.id,
            self.name,
            self.url,
            self.source_category,
            self.source_detail,
            self.discovered_at,
            self.article_title,
            self.article_url,
            self.industry,
            self.employee_scale,
            self.health_efforts,
            self.estimated_challenges,
            self.estimated_needs,
            self.confidence_score,
            self.analysis_date,
            self.analysis_notes,
            self.status,
            self.proposal_status,
            self.proposal_date,
            self.send_date,
            self.email,
            self.phone,
            self.fax,
            self.address,
            self.contact_url,
            self.contact_form_url,
            self.representative,
            self.established,
            self.capital,
            self.revenue,
            self.listed,
            self.memo,
        ]

    @classmethod
    def headers(cls) -> list[str]:
        return [
            "ID",
            "企業名",
            "企業URL",
            "ソースカテゴリ",
            "ソース詳細",
            "発見日",
            "関連記事",
            "記事URL",
            "業種",
            "従業員規模",
            "健康経営への取り組み",
            "推定課題",
            "推定ニーズ",
            "確信度",
            "分析日",
            "分析メモ",
            "進捗ステータス",
            "提案ステータス",
            "提案作成日",
            "送信日",
            "メールアドレス",
            "電話番号",
            "FAX",
            "住所",
            "問い合わせURL",
            "フォームURL",
            "代表者名",
            "設立年",
            "資本金",
            "売上高",
            "上場区分",
            "メモ",
        ]

    COL_COUNT: ClassVar[int] = 32

    @classmethod
    def from_row(cls, row: list[str]) -> "CompanyMaster":
        padded = row + [""] * (cls.COL_COUNT - len(row))
        return cls(
            id=padded[0],
            name=padded[1],
            url=padded[2],
            source_category=padded[3],
            source_detail=padded[4],
            discovered_at=padded[5],
            article_title=padded[6],
            article_url=padded[7],
            industry=padded[8],
            employee_scale=padded[9],
            health_efforts=padded[10],
            estimated_challenges=padded[11],
            estimated_needs=padded[12],
            confidence_score=padded[13],
            analysis_date=padded[14],
            analysis_notes=padded[15],
            status=padded[16] or "新規",
            proposal_status=padded[17],
            proposal_date=padded[18],
            send_date=padded[19],
            email=padded[20],
            phone=padded[21],
            fax=padded[22],
            address=padded[23],
            contact_url=padded[24],
            contact_form_url=padded[25],
            representative=padded[26],
            established=padded[27],
            capital=padded[28],
            revenue=padded[29],
            listed=padded[30],
            memo=padded[31],
        )

    @classmethod
    def from_company(cls, c: Company) -> "CompanyMaster":
        """旧Companyモデルからマスターに変換"""
        return cls(
            id=c.id,
            name=c.name,
            url=c.url,
            source_category=SourceCategory.from_source_text(c.source),
            source_detail=c.source,
            discovered_at=c.discovered_at,
            article_title=c.article_title,
            article_url=c.article_url,
            status=c.status,
            memo=c.memo,
        )

    def apply_analysis(self, a: Analysis, extra: dict | None = None) -> None:
        """分析結果をこの行に反映。extraにLLMの生データを渡すと企業概要も更新"""
        self.industry = a.industry
        self.employee_scale = a.employee_scale
        self.health_efforts = a.health_management_efforts
        self.estimated_challenges = a.estimated_challenges
        self.estimated_needs = a.estimated_needs
        self.confidence_score = str(a.confidence_score)
        self.analysis_date = a.analysis_date
        self.analysis_notes = a.analysis_notes
        if self.status == "新規":
            self.status = "分析済み"

        # 企業概要（extraからLLMの生データを反映）
        if extra:
            if extra.get("representative"):
                self.representative = extra["representative"]
            if extra.get("established"):
                self.established = extra["established"]
            if extra.get("capital"):
                self.capital = extra["capital"]
            if extra.get("revenue"):
                self.revenue = extra["revenue"]
            if extra.get("listed"):
                self.listed = extra["listed"]
            if extra.get("corporate_url") and not self.url:
                self.url = extra["corporate_url"]

    def apply_contact(self, contact: dict) -> None:
        """連絡先情報をこの行に反映（空でない値のみ上書き）"""
        if contact.get("email"):
            self.email = contact["email"]
        if contact.get("phone"):
            self.phone = contact["phone"]
        if contact.get("fax"):
            self.fax = contact["fax"]
        if contact.get("address"):
            self.address = contact["address"]
        if contact.get("contact_url"):
            self.contact_url = contact["contact_url"]
        if contact.get("contact_form_url"):
            self.contact_form_url = contact["contact_form_url"]

    def apply_proposal(self, p: Proposal) -> None:
        """提案情報をこの行に反映"""
        self.proposal_status = p.approval_status
        self.proposal_date = p.generated_at
        if self.status in ("新規", "分析済み"):
            self.status = "提案済み"

    @property
    def is_analyzed(self) -> bool:
        return bool(self.analysis_date)

    @property
    def is_proposed(self) -> bool:
        return bool(self.proposal_date)

    def to_company(self) -> Company:
        """後方互換: 旧Companyモデルに変換"""
        return Company(
            id=self.id, name=self.name, url=self.url,
            source=self.source_detail or self.source_category,
            discovered_at=self.discovered_at,
            article_title=self.article_title, article_url=self.article_url,
            status=self.status, memo=self.memo,
        )

    def to_analysis(self) -> Analysis | None:
        """後方互換: 旧Analysisモデルに変換"""
        if not self.is_analyzed:
            return None
        return Analysis(
            company_id=self.id, industry=self.industry,
            employee_scale=self.employee_scale,
            health_management_efforts=self.health_efforts,
            estimated_challenges=self.estimated_challenges,
            estimated_needs=self.estimated_needs,
            confidence_score=float(self.confidence_score) if self.confidence_score else 0.0,
            analysis_date=self.analysis_date, analysis_notes=self.analysis_notes,
        )
