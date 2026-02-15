from collections.abc import Generator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


JST_TZ = "Asia/Tokyo"


def parse_datetime(value: str, source_timezone: str) -> datetime:
    """Parse an ISO-like datetime string and attach source timezone if naive."""
    normalized = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(source_timezone))
    return dt


def to_jst(dt: datetime) -> datetime:
    """Convert datetime to JST."""
    return dt.astimezone(ZoneInfo(JST_TZ))


class DatetimeUtilsTool(Tool):
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
                    "error": f"Failed to parse datetime or timezone: {str(e)}",
                    "hint": "Use ISO 8601 format like 2026-02-15T12:00:00Z or 2026-02-15 12:00:00",
                }
            )
            return

        jst = to_jst(parsed)

        yield self.create_json_message(
            {
                "input": {
                    "datetime": input_datetime or None,
                    "source_timezone": source_timezone,
                    "resolved_iso8601": parsed.isoformat(),
                },
                "jst": {
                    "timezone": JST_TZ,
                    "iso8601": jst.isoformat(),
                    "date": jst.date().isoformat(),
                    "time": jst.strftime("%H:%M:%S"),
                    "unix_timestamp": int(jst.timestamp()),
                },
            }
        )
