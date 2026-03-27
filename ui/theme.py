"""FRACTALブランドテーマ - 全ページ共通デザイン"""

import streamlit as st

# ブランドカラー定義
COLORS = {
    "primary_dark": "#2D3337",
    "secondary": "#738084",
    "accent": "#E4006F",
    "gold": "#C5BDAB",
    "bg_dark": "#535F62",
    "bg_light": "#EFEFEF",
    "bg_white": "#F8F8F8",
    "white": "#FFFFFF",
    "black": "#000000",
    "border": "#F1F1F1",
    "text": "#2D3337",
    "text_light": "#738184",
}


def apply_theme():
    """全ページ共通のカスタムCSSを適用"""
    st.markdown(_get_custom_css(), unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", icon: str = ""):
    """ブランド統一ヘッダー"""
    apply_theme()
    display_title = f"{icon} {title}".strip() if icon else title
    st.markdown(
        f"""
        <div class="fr-page-header">
            <h1 class="fr-title">{display_title}</h1>
            {f'<p class="fr-subtitle">{subtitle}</p>' if subtitle else ''}
            <div class="fr-accent-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title_en: str, title_ja: str):
    """セクション見出し（英語+日本語の2段構成）"""
    st.markdown(
        f"""
        <div class="fr-section-header">
            <span class="fr-section-en">{title_en}</span>
            <span class="fr-section-ja">{title_ja}</span>
            <div class="fr-accent-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, sub: str = "", accent: bool = False):
    """ブランドスタイルのメトリクスカード"""
    bg = COLORS["accent"] if accent else COLORS["primary_dark"]
    st.markdown(
        f"""
        <div class="fr-metric-card" style="background:{bg};">
            <div class="fr-metric-label">{label}</div>
            <div class="fr-metric-value">{value}</div>
            {f'<div class="fr-metric-sub">{sub}</div>' if sub else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


WORKFLOW_STEPS = [
    {"num": "①", "label": "企業収集", "page": "① 企業収集"},
    {"num": "②", "label": "企業分析", "page": "② 企業分析"},
    {"num": "③", "label": "提案作成", "page": "③ 提案作成"},
    {"num": "④", "label": "フォーム送信", "page": "④ フォーム送信"},
]


def progress_bar(current_step: int):
    """ワークフロー進捗バー。current_step は 1〜4。"""
    items_html = ""
    for i, step in enumerate(WORKFLOW_STEPS, 1):
        if i < current_step:
            status = "done"
        elif i == current_step:
            status = "active"
        else:
            status = "upcoming"
        items_html += f'<div class="fr-step {status}"><span class="fr-step-num">{step["num"]}</span><span class="fr-step-label">{step["label"]}</span></div>'
        if i < len(WORKFLOW_STEPS):
            arrow_status = "done" if i < current_step else ""
            items_html += f'<div class="fr-step-arrow {arrow_status}">▶</div>'

    st.markdown(
        f'<div class="fr-progress-bar">{items_html}</div>',
        unsafe_allow_html=True,
    )


def info_card(title: str, content: str, border_color: str = ""):
    """情報カード"""
    bc = border_color or COLORS["accent"]
    st.markdown(
        f"""
        <div class="fr-info-card" style="border-left:4px solid {bc};">
            <div class="fr-info-title">{title}</div>
            <div class="fr-info-content">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _get_custom_css() -> str:
    return f"""
    <style>
    /* ============================================================
       Google Fonts
       ============================================================ */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&family=Oswald:wght@500&display=swap');

    /* ============================================================
       Global
       ============================================================ */
    .stApp {{
        font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', sans-serif;
        color: {COLORS["text"]};
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: {COLORS["primary_dark"]};
    }}
    section[data-testid="stSidebar"] * {{
        color: {COLORS["white"]} !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stRadio label {{
        color: {COLORS["gold"]} !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: {COLORS["secondary"]} !important;
    }}

    /* ============================================================
       Page Header
       ============================================================ */
    .fr-page-header {{
        text-align: center;
        padding: 2rem 0 1rem;
        margin-bottom: 2rem;
    }}
    .fr-title {{
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        font-size: 2.4rem;
        color: {COLORS["primary_dark"]};
        letter-spacing: 0.05em;
        margin: 0;
    }}
    .fr-subtitle {{
        font-size: 1.05rem;
        color: {COLORS["secondary"]};
        margin: 0.5rem 0 0;
        letter-spacing: 0.03em;
    }}
    .fr-accent-line {{
        width: 100px;
        height: 4px;
        background: {COLORS["accent"]};
        margin: 1rem auto 0;
    }}

    /* ============================================================
       Section Header (EN + JA)
       ============================================================ */
    .fr-section-header {{
        text-align: center;
        padding: 1.5rem 0 1rem;
        margin: 1rem 0;
    }}
    .fr-section-en {{
        display: block;
        font-family: 'Oswald', sans-serif;
        font-weight: 500;
        font-size: 1.6rem;
        color: {COLORS["secondary"]};
        letter-spacing: 0.07em;
        text-transform: uppercase;
    }}
    .fr-section-ja {{
        display: block;
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        font-size: 1.3rem;
        color: {COLORS["primary_dark"]};
        margin-top: 0.3rem;
    }}

    /* ============================================================
       Metric Card
       ============================================================ */
    .fr-metric-card {{
        border-radius: 4px;
        padding: 1.5rem 1.2rem;
        text-align: center;
        color: {COLORS["white"]};
        margin-bottom: 1rem;
        box-shadow: 0 0 15px rgba(0,0,0,0.05);
        transition: transform 0.2s ease;
    }}
    .fr-metric-card:hover {{
        transform: translateY(-2px);
    }}
    .fr-metric-label {{
        font-size: 0.85rem;
        opacity: 0.85;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }}
    .fr-metric-value {{
        font-family: 'Oswald', sans-serif;
        font-weight: 500;
        font-size: 2rem;
        letter-spacing: 0.03em;
        line-height: 1.2;
    }}
    .fr-metric-sub {{
        font-size: 0.75rem;
        opacity: 0.7;
        margin-top: 0.4rem;
    }}

    /* ============================================================
       Info Card
       ============================================================ */
    .fr-info-card {{
        background: {COLORS["bg_white"]};
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 0 15px rgba(0,0,0,0.05);
    }}
    .fr-info-title {{
        font-weight: 700;
        font-size: 1rem;
        color: {COLORS["primary_dark"]};
        margin-bottom: 0.5rem;
    }}
    .fr-info-content {{
        font-size: 0.9rem;
        color: {COLORS["secondary"]};
        line-height: 1.85;
    }}

    /* ============================================================
       Streamlit Widgets Override
       ============================================================ */
    /* Buttons */
    .stButton > button {{
        background: {COLORS["primary_dark"]} !important;
        color: {COLORS["white"]} !important;
        border: none !important;
        border-radius: 4px !important;
        font-family: 'Noto Sans JP', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.05em !important;
        padding: 0.6rem 2rem !important;
        transition: all 0.3s ease !important;
    }}
    .stButton > button:hover {{
        background: {COLORS["bg_dark"]} !important;
        transform: translateY(-1px);
    }}
    .stButton > button:active {{
        background: {COLORS["black"]} !important;
    }}

    /* Download button */
    .stDownloadButton > button {{
        background: {COLORS["secondary"]} !important;
        color: {COLORS["white"]} !important;
        border: none !important;
        border-radius: 4px !important;
        font-family: 'Noto Sans JP', sans-serif !important;
        font-weight: 700 !important;
        transition: all 0.3s ease !important;
    }}
    .stDownloadButton > button:hover {{
        background: #5b6669 !important;
    }}

    /* Checkbox */
    .stCheckbox label span {{
        color: {COLORS["text"]} !important;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        border-bottom: 2px solid {COLORS["bg_light"]};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        color: {COLORS["secondary"]};
        border-bottom: 3px solid transparent;
        padding: 0.8rem 1.5rem;
    }}
    .stTabs [aria-selected="true"] {{
        color: {COLORS["primary_dark"]} !important;
        border-bottom-color: {COLORS["accent"]} !important;
    }}

    /* Expander */
    .streamlit-expanderHeader {{
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        color: {COLORS["primary_dark"]};
        background: {COLORS["bg_white"]};
        border-radius: 4px;
    }}

    /* Metrics */
    [data-testid="stMetric"] {{
        background: {COLORS["bg_white"]};
        padding: 1rem 1.2rem;
        border-radius: 4px;
        box-shadow: 0 0 15px rgba(0,0,0,0.05);
    }}
    [data-testid="stMetricLabel"] {{
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        color: {COLORS["secondary"]} !important;
    }}
    [data-testid="stMetricValue"] {{
        font-family: 'Oswald', sans-serif;
        font-weight: 500;
        color: {COLORS["primary_dark"]} !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-family: 'Noto Sans JP', sans-serif;
    }}

    /* Dataframe */
    .stDataFrame {{
        border: 1px solid {COLORS["border"]} !important;
        border-radius: 4px !important;
    }}

    /* Selectbox / Input */
    .stSelectbox [data-baseweb="select"] {{
        border-radius: 4px;
    }}
    .stTextInput input, .stNumberInput input, .stTextArea textarea {{
        border-radius: 4px !important;
        border: 1px solid {COLORS["bg_light"]} !important;
        font-family: 'Noto Sans JP', sans-serif !important;
        transition: all 0.3s ease !important;
    }}
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
        border-color: {COLORS["accent"]} !important;
        box-shadow: 0 0 0 1px {COLORS["accent"]} !important;
    }}

    /* Progress bar */
    .stProgress > div > div {{
        background: {COLORS["accent"]} !important;
    }}

    /* Success / Info / Warning / Error */
    .stSuccess {{
        background: rgba(115,128,132,0.08);
        border-left: 4px solid {COLORS["secondary"]};
    }}
    .stInfo {{
        background: rgba(45,51,55,0.05);
        border-left: 4px solid {COLORS["primary_dark"]};
    }}

    /* Divider */
    hr {{
        border-color: {COLORS["bg_light"]} !important;
    }}

    /* ============================================================
       Dark section utility
       ============================================================ */
    .fr-dark-section {{
        background: {COLORS["primary_dark"]};
        color: {COLORS["white"]};
        padding: 2rem;
        border-radius: 4px;
        margin: 1rem 0;
    }}
    .fr-dark-section h1, .fr-dark-section h2, .fr-dark-section h3 {{
        color: {COLORS["white"]};
    }}

    /* ============================================================
       Table style
       ============================================================ */
    .fr-table {{
        width: 100%;
        border-collapse: collapse;
        font-family: 'Noto Sans JP', sans-serif;
    }}
    .fr-table thead th {{
        background: {COLORS["bg_light"]};
        color: {COLORS["secondary"]};
        font-weight: 700;
        padding: 1rem;
        text-align: center;
        font-size: 0.9rem;
    }}
    .fr-table tbody td {{
        border-bottom: 1px solid {COLORS["bg_light"]};
        padding: 1rem;
        text-align: center;
        color: {COLORS["secondary"]};
    }}
    .fr-table tbody th {{
        border-bottom: 1px solid {COLORS["bg_light"]};
        padding: 1rem;
        font-weight: 700;
        color: {COLORS["primary_dark"]};
    }}
    .fr-table .accent {{
        color: {COLORS["accent"]};
        font-weight: 700;
    }}
    .fr-table .highlight {{
        background: {COLORS["gold"]};
        color: {COLORS["white"]};
    }}

    /* ============================================================
       Workflow Progress Bar
       ============================================================ */
    .fr-progress-bar {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.3rem;
        padding: 1rem 0;
        margin-bottom: 1.5rem;
        background: {COLORS["bg_white"]};
        border-radius: 4px;
        box-shadow: 0 0 15px rgba(0,0,0,0.05);
    }}
    .fr-step {{
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        font-size: 0.9rem;
        transition: all 0.3s ease;
    }}
    .fr-step.active {{
        background: {COLORS["accent"]};
        color: {COLORS["white"]};
        box-shadow: 0 2px 8px rgba(228,0,111,0.3);
    }}
    .fr-step.done {{
        background: {COLORS["primary_dark"]};
        color: {COLORS["white"]};
    }}
    .fr-step.upcoming {{
        background: {COLORS["bg_light"]};
        color: {COLORS["secondary"]};
    }}
    .fr-step-num {{
        font-size: 1rem;
    }}
    .fr-step-label {{
        font-size: 0.85rem;
    }}
    .fr-step-arrow {{
        color: {COLORS["bg_light"]};
        font-size: 0.7rem;
        margin: 0 0.1rem;
    }}
    .fr-step-arrow.done {{
        color: {COLORS["primary_dark"]};
    }}

    /* ============================================================
       Flow Card (Top page)
       ============================================================ */
    .fr-flow-container {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0;
        margin: 2rem 0;
        flex-wrap: wrap;
    }}
    .fr-flow-card {{
        background: {COLORS["primary_dark"]};
        color: {COLORS["white"]};
        border-radius: 8px;
        padding: 1.8rem 1.5rem;
        text-align: center;
        width: 200px;
        cursor: pointer;
        transition: all 0.3s ease;
        text-decoration: none;
    }}
    .fr-flow-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }}
    .fr-flow-card.accent {{
        background: {COLORS["accent"]};
    }}
    .fr-flow-num {{
        font-family: 'Oswald', sans-serif;
        font-size: 2rem;
        font-weight: 500;
        opacity: 0.7;
        margin-bottom: 0.3rem;
    }}
    .fr-flow-title {{
        font-family: 'Noto Sans JP', sans-serif;
        font-weight: 700;
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
    }}
    .fr-flow-desc {{
        font-size: 0.75rem;
        opacity: 0.7;
        line-height: 1.5;
    }}
    .fr-flow-arrow {{
        font-size: 1.8rem;
        color: {COLORS["secondary"]};
        margin: 0 0.5rem;
    }}

    /* ============================================================
       Footer
       ============================================================ */
    .fr-footer {{
        background: {COLORS["secondary"]};
        color: {COLORS["white"]};
        padding: 1.5rem;
        text-align: center;
        font-size: 0.85rem;
        margin-top: 3rem;
        border-radius: 4px 4px 0 0;
    }}
    </style>
    """
