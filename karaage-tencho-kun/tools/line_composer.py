"""LINE メッセージ作成ツール。

data/line_templates.json のテンプレートを使用し、
シフトリマインダー・交代依頼・緊急連絡等のLINEメッセージを生成する。
"""

from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.data_loader import CachedJSONLoader
from tools.datetime_utils import JST, format_date_ja, get_weekday_ja

_loader = CachedJSONLoader("line_templates.json")


class LineComposerTool(Tool):
    """LINE メッセージ生成ツール。

    テンプレートとパラメータからLINEメッセージ本文を組み立てて返す。
    """

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        message_type = tool_parameters.get("message_type", "").strip()
        templates_data = _loader.load()
        templates = templates_data["templates"]

        if not message_type:
            yield self.create_json_message(
                {
                    "error": "message_type が指定されていません",
                    "available_types": list(templates.keys()),
                }
            )
            return

        if message_type not in templates:
            yield self.create_json_message(
                {
                    "error": f"不明なメッセージタイプ: {message_type}",
                    "available_types": list(templates.keys()),
                }
            )
            return

        # パラメータ取得
        now = datetime.now(JST)
        tomorrow = now + timedelta(days=1)

        # 共通パラメータのデフォルト値
        date = tool_parameters.get("date") or tomorrow.strftime("%Y-%m-%d")
        weekday = get_weekday_ja(date)
        start_time = tool_parameters.get("start_time", "09:00")
        end_time = tool_parameters.get("end_time", "17:00")

        template_info = templates[message_type]
        template = template_info["template"]

        # メッセージタイプ別の処理
        if message_type == "shift_reminder":
            staff_name = tool_parameters.get("staff_name", "スタッフ")
            message = template.format(
                staff_name=staff_name,
                date=format_date_ja(date),
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
            )
            recipient = staff_name
            metadata = {
                "staff_name": staff_name,
                "date": date,
                "shift": f"{start_time}-{end_time}",
            }

        elif message_type == "swap_request":
            original_staff = tool_parameters.get("original_staff", "スタッフ")
            reason = tool_parameters.get("reason", "急用のため")
            message = template.format(
                original_staff=original_staff,
                date=format_date_ja(date),
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                reason=reason,
            )
            recipient = "all_staff"
            metadata = {
                "original_staff": original_staff,
                "date": date,
                "shift": f"{start_time}-{end_time}",
                "reason": reason,
            }

        elif message_type == "emergency_coverage":
            # 緊急の場合は今日
            date = tool_parameters.get("date") or now.strftime("%Y-%m-%d")
            weekday = get_weekday_ja(date)
            message = template.format(
                date=format_date_ja(date),
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
            )
            recipient = "all_staff"
            metadata = {
                "date": date,
                "shift": f"{start_time}-{end_time}",
                "urgency": "high",
            }

        elif message_type == "schedule_update":
            # 週の開始日（来週月曜）を計算
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            week_start_dt = now + timedelta(days=days_until_monday)
            week_end_dt = week_start_dt + timedelta(days=6)
            deadline_dt = now + timedelta(days=2)

            week_start = tool_parameters.get("week_start") or week_start_dt.strftime(
                "%Y-%m-%d"
            )
            week_end = tool_parameters.get("week_end") or week_end_dt.strftime(
                "%Y-%m-%d"
            )
            deadline = tool_parameters.get("deadline") or deadline_dt.strftime(
                "%Y-%m-%d"
            )

            message = template.format(
                week_start=format_date_ja(week_start),
                week_end=format_date_ja(week_end),
                deadline=format_date_ja(deadline),
            )
            recipient = "all_staff"
            metadata = {
                "week_start": week_start,
                "week_end": week_end,
                "deadline": deadline,
            }

        elif message_type == "meeting_notice":
            time = tool_parameters.get("time", "17:00")
            agenda = tool_parameters.get("agenda", "月次ミーティング")
            message = template.format(
                date=format_date_ja(date),
                weekday=weekday,
                time=time,
                agenda=agenda,
            )
            recipient = "all_staff"
            metadata = {
                "date": date,
                "time": time,
                "agenda": agenda,
            }

        else:
            # 未知のタイプ（到達しないはずだが念のため）
            message = ""
            recipient = ""
            metadata = {}

        yield self.create_json_message(
            {
                "message_type": message_type,
                "recipient": recipient,
                "message": message,
                "metadata": metadata,
                "generated_at": now.isoformat(),
            }
        )
