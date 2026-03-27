"""確認用スクリーンショット管理"""

from pathlib import Path

SCREENSHOT_DIR = Path("screenshots")


def ensure_screenshot_dir() -> Path:
    """スクリーンショットディレクトリを作成"""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR


def get_screenshot_path(company_id: str, step: str = "form") -> str:
    """スクリーンショットのパスを生成"""
    ensure_screenshot_dir()
    return str(SCREENSHOT_DIR / f"{company_id}_{step}.png")


def list_screenshots(company_id: str | None = None) -> list[Path]:
    """スクリーンショット一覧を返す"""
    ensure_screenshot_dir()
    if company_id:
        return sorted(SCREENSHOT_DIR.glob(f"{company_id}_*.png"))
    return sorted(SCREENSHOT_DIR.glob("*.png"))
