"""JSON静的データ読み込みユーティリティ。

data/ ディレクトリ内のJSONファイルをキャッシュ付きで読み込む共有モジュール。
lawson_items, line_composer, dashboard_template 等、
静的JSONデータを使用するツールで共通利用する。
"""

import json
from pathlib import Path
from typing import Any

# プラグインルートディレクトリ（data/ の親）
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent


class CachedJSONLoader:
    """JSONファイルをキャッシュ付きで読み込むクラス。

    初回読み込み時にファイル内容をメモリにキャッシュし、
    以降はキャッシュから返すことでファイルI/Oを削減する。

    使用例::

        loader = CachedJSONLoader("lawson_items.json")
        data = loader.load()
    """

    def __init__(self, filename: str) -> None:
        """ローダーを初期化する。

        Args:
            filename: data/ ディレクトリ内のJSONファイル名
        """
        self._file_path = _PLUGIN_ROOT / "data" / filename
        self._cache: dict[str, Any] | None = None

    @property
    def file_path(self) -> Path:
        """データファイルのパスを返す。"""
        return self._file_path

    def load(self) -> dict[str, Any]:
        """JSONデータを読み込み、キャッシュして返す。"""
        if self._cache is None:
            self._cache = json.loads(
                self._file_path.read_text(encoding="utf-8")
            )
        return self._cache

    def reset(self) -> None:
        """キャッシュをリセットする。主にテスト用。"""
        self._cache = None
