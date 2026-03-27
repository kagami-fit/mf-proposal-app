"""開発中のモジュール変更を即反映するためのリロードユーティリティ"""

import importlib
import sys


def reload_app_modules():
    """analyzers / config / sheets モジュールを強制リロード"""
    for mod_name in sorted(k for k in sys.modules if k.startswith(("analyzers.", "config.", "sheets."))):
        try:
            importlib.reload(sys.modules[mod_name])
        except Exception:
            pass
