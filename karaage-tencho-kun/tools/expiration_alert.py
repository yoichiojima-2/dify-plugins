# 消費期限アラートツール

import json
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

JST = ZoneInfo("Asia/Tokyo")

_SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "expiration_alert_seed.json"
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


def _get_urgency(remaining_hours: float) -> str:
    """残り時間から緊急度を判定"""
    seed = _load_seed_data()
    rules = seed["markdown_rules"]
    if remaining_hours <= rules["high"]["threshold_hours"]:
        return "high"
    elif remaining_hours <= rules["medium"]["threshold_hours"]:
        return "medium"
    else:
        return "low"


class ExpirationAlertTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        category = tool_parameters.get("category", "").strip()
        urgency_filter = tool_parameters.get("urgency", "").strip().lower()
        hours_threshold = tool_parameters.get("hours_threshold")

        now = datetime.now(JST)
        seed = _load_seed_data()
        rules = seed["markdown_rules"]

        try:
            conn = _get_connection()

            # 在庫とアラートを取得
            query = """
                SELECT
                    item_name,
                    category,
                    quantity,
                    stocked_at,
                    expires_at
                FROM inventory
                WHERE quantity > 0
            """
            params = []

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY expires_at ASC"

            result = conn.execute(query, params).fetchall()

            alerts = []
            summary = {"high": 0, "medium": 0, "low": 0}

            for row in result:
                item_name, cat, qty, stocked_at, expires_at = row

                # 消費期限をdatetimeに変換
                if isinstance(expires_at, str):
                    exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                else:
                    exp_dt = expires_at
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=JST)

                remaining = (exp_dt - now).total_seconds() / 3600
                urgency = _get_urgency(remaining)

                # 時間しきい値でフィルタ
                if hours_threshold is not None and remaining > hours_threshold:
                    continue

                # 緊急度フィルタ
                if urgency_filter and urgency != urgency_filter:
                    continue

                summary[urgency] += 1

                rule = rules[urgency]
                alerts.append(
                    {
                        "item_name": item_name,
                        "category": cat,
                        "expires_at": exp_dt.isoformat(),
                        "remaining_hours": round(remaining, 1),
                        "quantity": qty,
                        "action": rule["action"],
                        "discount_percent": rule["discount"],
                        "urgency": urgency,
                    }
                )

            yield self.create_json_message(
                {
                    "current_time": now.isoformat(),
                    "alerts": alerts,
                    "summary": {
                        "high_urgency": summary["high"],
                        "medium_urgency": summary["medium"],
                        "low_urgency": summary["low"],
                        "total": len(alerts),
                    },
                }
            )

        except Exception as e:
            yield self.create_json_message({"error": str(e)})


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """スキーマとサンプルデータを初期化"""

    conn.execute("""
        CREATE TABLE inventory (
            item_id VARCHAR PRIMARY KEY,
            item_name VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            stocked_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
    """)

    # サンプル在庫データを生成（現在時刻基準）
    now = datetime.now(JST)
    seed = _load_seed_data()

    for item in seed["sample_inventory"]:
        stocked_at = now - timedelta(hours=item["stocked_hours_ago"])
        expires_at = now + timedelta(hours=item["expires_in_hours"])

        conn.execute(
            """
            INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                item["item_id"],
                item["item_name"],
                item["category"],
                item["quantity"],
                stocked_at.isoformat(),
                expires_at.isoformat(),
            ],
        )
