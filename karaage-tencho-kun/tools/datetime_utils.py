"""日付・時刻ユーティリティ。

JST変換、曜日名（日本語）、日付フォーマットなど、
複数のツールで共通利用する日付関連のユーティリティを提供する。
"""

from collections.abc import Generator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# --- 共有定数 ---

JST = ZoneInfo("Asia/Tokyo")
"""日本標準時タイムゾーン。"""

JST_TZ = "Asia/Tokyo"
"""タイムゾーン文字列（ZoneInfoコンストラクタ用）。"""

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]
"""月曜始まりの日本語曜日リスト（datetime.weekday() のインデックスに対応）。"""

WEEKDAY_JA_SUN_START = ["日", "月", "火", "水", "木", "金", "土"]
"""日曜始まりの日本語曜日リスト（DuckDB EXTRACT(DOW) のインデックスに対応）。"""

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
"""曜日キー（英語略称、availability JSONのキーに対応）。"""


# --- 共有ユーティリティ関数 ---

def parse_datetime(value: str, source_timezone: str) -> datetime:
    """ISO形式の日時文字列をパースし、タイムゾーン情報を付与する。

    Args:
        value: パースする日時文字列（ISO 8601形式）
        source_timezone: ナイーブな日時の場合に付与するタイムゾーン
    """
    normalized = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(source_timezone))
    return dt


def to_jst(dt: datetime) -> datetime:
    """datetimeをJSTに変換する。"""
    return dt.astimezone(JST)


def get_weekday_ja(date_str: str) -> str:
    """日付文字列(YYYY-MM-DD)から日本語曜日を返す。パース失敗時は'?'。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return WEEKDAY_JA[dt.weekday()]
    except ValueError:
        return "?"


def format_date_ja(date_str: str) -> str:
    """日付文字列を日本語短縮形式にフォーマットする（例: '2/15'）。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}"
    except ValueError:
        return date_str


def parse_expires_at(expires_at: str | datetime, now: datetime) -> datetime:
    """消費期限をdatetimeに変換する。

    DuckDBから取得した値はstrまたはdatetimeの可能性があるため両方に対応。
    inventory_managerの複数メソッドで共通利用。

    Args:
        expires_at: 消費期限値（ISO文字列またはdatetime）
        now: 現在時刻（タイムゾーン付き、フォールバック用）
    """
    if isinstance(expires_at, str):
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    dt = expires_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


# --- ツールクラス ---

class DatetimeUtilsTool(Tool):
    """日時変換ツール。指定された日時をJSTに変換して返す。"""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        input_datetime = (tool_parameters.get("datetime") or "").strip()
        source_timezone = (tool_parameters.get("source_timezone") or "UTC").strip()

        try:
            if input_datetime:
                parsed = parse_datetime(input_datetime, source_timezone)
            else:
                parsed = datetime.now(ZoneInfo(source_timezone))
        except Exception as e:
            yield self.create_json_message(
                {
                    "error": f"日時またはタイムゾーンのパースに失敗: {e!s}",
                    "hint": "ISO 8601形式で指定してください（例: 2026-02-15T12:00:00Z）",
                }
            )
            return

        jst_dt = to_jst(parsed)

        yield self.create_json_message(
            {
                "input": {
                    "datetime": input_datetime or None,
                    "source_timezone": source_timezone,
                    "resolved_iso8601": parsed.isoformat(),
                },
                "jst": {
                    "timezone": JST_TZ,
                    "iso8601": jst_dt.isoformat(),
                    "date": jst_dt.date().isoformat(),
                    "time": jst_dt.strftime("%H:%M:%S"),
                    "unix_timestamp": int(jst_dt.timestamp()),
                },
            }
        )
