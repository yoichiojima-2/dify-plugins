# シフト管理ツール - SQL版 (インメモリDB)

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

_SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "shift_manager_seed.json"
_SEED_CACHE: dict[str, Any] | None = None

# インメモリDBを使用（Difyクラウド環境はファイルシステムが読み取り専用のため）
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


class ShiftManagerTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        # Some agents may send alternative keys after a failed call.
        # Accept aliases to avoid retry loops caused only by key mismatch.
        sql = (
            tool_parameters.get("sql")
            or tool_parameters.get("query")
            or tool_parameters.get("statement")
            or ""
        ).strip()

        if not sql:
            yield self.create_json_message(
                {
                    "error": "SQLが指定されていません",
                    "hint": "tool_parameters に `sql` キーでSQL文字列を指定してください",
                }
            )
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

    # スキーマ作成
    conn.execute("""
        CREATE TABLE staff (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            name_reading VARCHAR,
            role VARCHAR,
            role_ja VARCHAR,
            hourly_rate INTEGER,
            skills VARCHAR[],
            availability JSON,
            preferred_hours INTEGER,
            phone VARCHAR,
            line_id VARCHAR,
            color VARCHAR,
            notes VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE shifts (
            shift_id VARCHAR PRIMARY KEY,
            staff_id VARCHAR NOT NULL,
            staff_name VARCHAR NOT NULL,
            date DATE NOT NULL,
            start_time VARCHAR NOT NULL,
            end_time VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'confirmed',
            created_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancel_reason VARCHAR,
            swapped_from VARCHAR,
            swapped_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE swap_requests (
            swap_id VARCHAR PRIMARY KEY,
            shift_id VARCHAR NOT NULL,
            original_staff_id VARCHAR NOT NULL,
            original_staff_name VARCHAR NOT NULL,
            date DATE NOT NULL,
            start_time VARCHAR NOT NULL,
            end_time VARCHAR NOT NULL,
            reason VARCHAR,
            status VARCHAR DEFAULT 'pending',
            requested_at TIMESTAMP,
            approved_staff_id VARCHAR,
            approved_staff_name VARCHAR,
            approved_at TIMESTAMP
        )
    """)

    # スタッフデータを挿入
    staff_map = {}  # id -> name mapping for shifts
    for s in seed_data["staff"]:
        staff_map[s["id"]] = s["name"]
        conn.execute(
            """
            INSERT INTO staff VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                s["id"],
                s["name"],
                s.get("name_reading"),
                s.get("role"),
                s.get("role_ja"),
                s.get("hourly_rate"),
                s.get("skills", []),
                json.dumps(s.get("availability", {})),
                s.get("preferred_hours"),
                s.get("phone"),
                s.get("line_id"),
                s.get("color"),
                s.get("notes"),
            ],
        )

    # シフトデータを挿入（day_offset を CURRENT_DATE + offset で変換）
    for shift in seed_data["shifts"]:
        staff_name = staff_map.get(shift["staff_id"], "")
        offset = shift["day_offset"]
        conn.execute(
            f"""
            INSERT INTO shifts VALUES (
                ?, ?, ?, CURRENT_DATE + ?, ?, ?, ?,
                NOW() + INTERVAL '{offset}' DAY, ?, ?, ?, ?
            )
            """,
            [
                shift["id"],
                shift["staff_id"],
                staff_name,
                offset,
                shift["start"],
                shift["end"],
                shift.get("status", "confirmed"),
                None,  # cancelled_at
                shift.get("cancel_reason"),
                shift.get("swapped_from"),
                None,  # swapped_at
            ],
        )

    # シフト交代リクエストを挿入
    for swap in seed_data["swap_requests"]:
        original_name = staff_map.get(swap["original_staff_id"], "")
        approved_name = staff_map.get(swap.get("approved_staff_id", ""), None)
        offset = swap["day_offset"]
        conn.execute(
            f"""
            INSERT INTO swap_requests VALUES (
                ?, ?, ?, ?, CURRENT_DATE + ?, ?, ?, ?,
                ?, NOW() + INTERVAL '{offset}' DAY, ?, ?, ?
            )
            """,
            [
                swap["id"],
                swap["shift_id"],
                swap["original_staff_id"],
                original_name,
                offset,
                swap["start"],
                swap["end"],
                swap.get("reason"),
                swap.get("status", "pending"),
                swap.get("approved_staff_id"),
                approved_name,
                None,  # approved_at
            ],
        )
