"""収集モジュールの抽象基底クラス"""

from abc import ABC, abstractmethod

from sheets.models import Company


class BaseCollector(ABC):
    """情報収集の基底クラス"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """ソース名を返す"""
        ...

    @abstractmethod
    def collect(self) -> list[Company]:
        """企業情報を収集してCompanyモデルのリストを返す"""
        ...
