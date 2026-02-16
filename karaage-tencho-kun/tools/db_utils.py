"""DuckDB インメモリデータベース管理ユーティリティ。

Difyクラウド環境はファイルシステムが読み取り専用のため、
全てのデータベースはインメモリで管理する。
各ツールが共通のパターン（シードデータ読み込み → スキーマ初期化 → 接続管理）を
重複なく利用できるようにするための共有モジュール。
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

# プラグインルートディレクトリ（data/ の親）
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent


class DuckDBManager:
    """インメモリDuckDB接続とシードデータのキャッシュを管理する。

    各ツールモジュール（sales_analytics, shift_manager, inventory_manager）が
    それぞれ独立したインスタンスを持ち、
    シードデータの読み込みとDB接続の初期化を一元管理する。

    使用例::

        def _init_schema(conn, seed_data):
            conn.execute("CREATE TABLE ...")
            # seed_data を使ってINSERT

        db = DuckDBManager("sales_analytics_seed.json", _init_schema)
        conn = db.get_connection()
    """

    def __init__(
        self,
        seed_filename: str,
        init_schema_fn: Callable[[duckdb.DuckDBPyConnection, dict[str, Any]], None],
    ) -> None:
        """マネージャーを初期化する。

        Args:
            seed_filename: data/ ディレクトリ内のJSONファイル名
            init_schema_fn: (conn, seed_data) を受け取りテーブル作成・データ挿入を行う関数
        """
        self._seed_file = _PLUGIN_ROOT / "data" / seed_filename
        self._init_schema_fn = init_schema_fn
        self._seed_cache: dict[str, Any] | None = None
        self._conn: duckdb.DuckDBPyConnection | None = None

    def load_seed_data(self) -> dict[str, Any]:
        """シードデータJSONを読み込み、キャッシュして返す。"""
        if self._seed_cache is None:
            self._seed_cache = json.loads(
                self._seed_file.read_text(encoding="utf-8")
            )
        return self._seed_cache

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """DuckDB接続を取得する。初回呼び出し時にスキーマを初期化する。"""
        if self._conn is None:
            self._conn = duckdb.connect(":memory:")
            self._init_schema_fn(self._conn, self.load_seed_data())
        return self._conn

    def reset(self) -> None:
        """接続とキャッシュをリセットする。主にテスト用。"""
        self._seed_cache = None
        self._conn = None
