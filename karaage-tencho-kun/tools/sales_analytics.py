# 売上分析ツール - SQL版 (インメモリDB)

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

_SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "sales_analytics_seed.json"
_SEED_CACHE: dict[str, Any] | None = None
_conn = None


def _load_seed_data() -> dict[str, Any]:
    global _SEED_CACHE
    if _SEED_CACHE is None:
        _SEED_CACHE = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
    return _SEED_CACHE


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect(":memory:")
        _init_schema(_conn)
    return _conn


class SalesAnalyticsTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        sql = tool_parameters.get("sql", "").strip()

        if not sql:
            yield self.create_json_message({"error": "SQLが指定されていません"})
            return

        try:
            conn = _get_connection()
            result = conn.execute(sql).fetchdf()
            yield self.create_json_message(result.to_dict(orient="records"))

        except Exception as e:
            yield self.create_json_message({"error": str(e)})


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """スキーマとサンプルデータを初期化"""

    seed_data = _load_seed_data()

    conn.execute("""
        CREATE TABLE items (
            item_id VARCHAR PRIMARY KEY,
            item_name VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            unit_price INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE sales (
            sale_id VARCHAR,
            sale_date DATE,
            sale_hour INTEGER,
            item_id VARCHAR,
            item_name VARCHAR,
            category VARCHAR,
            quantity INTEGER,
            unit_price INTEGER,
            total_amount INTEGER,
            weather VARCHAR,
            temperature FLOAT,
            day_of_week INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE daily_summary (
            date DATE,
            total_sales INTEGER,
            total_items INTEGER,
            weather VARCHAR,
            temperature FLOAT,
            customer_count INTEGER
        )
    """)

    conn.executemany(
        "INSERT INTO items VALUES (?, ?, ?, ?)",
        [
            (
                item["item_id"],
                item["item_name"],
                item["category"],
                item["unit_price"],
            )
            for item in seed_data["items_master"]
        ],
    )

    _generate_sample_sales(conn, seed_data)


def _generate_sample_sales(conn: duckdb.DuckDBPyConnection, seed_data: dict[str, Any]) -> None:
    """サンプル売上データを生成（SQLで効率的に）"""

    daily_patterns = seed_data["daily_patterns"]
    item_profiles = seed_data["hourly_item_profiles"]

    sale_id = 1
    for pattern in daily_patterns:
        offset = pattern["offset"]
        weather = pattern["weather"]
        temp = pattern["temperature"]
        dow = pattern["day_of_week"]

        is_weekend = dow >= 5
        base_multiplier = 1.2 if is_weekend else 1.0

        if weather == "rainy":
            demand_mult = {"hot_snack": 0.8, "cold": 0.5, "warm": 1.5, "normal": 1.0}
        elif weather == "sunny" and temp > 12:
            demand_mult = {"hot_snack": 1.2, "cold": 1.3, "warm": 0.8, "normal": 1.0}
        else:
            demand_mult = {"hot_snack": 1.0, "cold": 1.0, "warm": 1.0, "normal": 1.0}

        daily_sales = 0
        daily_items = 0

        for hour in range(6, 24):
            if 7 <= hour <= 9:
                hour_mult = 1.5
            elif 11 <= hour <= 13:
                hour_mult = 2.0
            elif 17 <= hour <= 19:
                hour_mult = 1.8
            elif 21 <= hour <= 23:
                hour_mult = 0.6
            else:
                hour_mult = 1.0

            for item in item_profiles:
                cat_mult = demand_mult[item["demand_group"]]
                qty = max(
                    1,
                    int(
                        item["base_qty"]
                        * hour_mult
                        * base_multiplier
                        * cat_mult
                        * 0.3
                    ),
                )
                total = item["price"] * qty

                conn.execute(
                    """
                    INSERT INTO sales VALUES (?, CURRENT_DATE + ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f"S{sale_id:08d}",
                        offset,
                        hour,
                        item["item_id"],
                        item["item_name"],
                        item["category"],
                        qty,
                        item["price"],
                        total,
                        weather,
                        temp,
                        dow,
                    ],
                )

                sale_id += 1
                daily_sales += total
                daily_items += qty

        conn.execute(
            """
            INSERT INTO daily_summary VALUES (CURRENT_DATE + ?, ?, ?, ?, ?, ?)
            """,
            [offset, daily_sales, daily_items, weather, temp, int(daily_items * 0.7)],
        )
