import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import line_composer as lc


class TestLineComposer(unittest.TestCase):
    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(lc.LineComposerTool)
        tool.create_json_message = lambda body: body
        return tool

    def test_invoke_returns_error_when_message_type_missing(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("available_types", messages[0])

    def test_invoke_returns_error_for_unknown_message_type(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"message_type": "unknown_type"}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("unknown_type", messages[0]["error"])

    def test_shift_reminder_generates_message(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke(
                {
                    "message_type": "shift_reminder",
                    "staff_name": "田中太郎",
                    "date": "2026-02-16",
                    "start_time": "09:00",
                    "end_time": "17:00",
                }
            )
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["message_type"], "shift_reminder")
        self.assertEqual(result["recipient"], "田中太郎")
        self.assertIn("田中太郎", result["message"])
        self.assertIn("2/16", result["message"])
        self.assertIn("09:00", result["message"])
        self.assertIn("17:00", result["message"])

    def test_swap_request_generates_message(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke(
                {
                    "message_type": "swap_request",
                    "original_staff": "山田美咲",
                    "date": "2026-02-20",
                    "start_time": "18:00",
                    "end_time": "22:00",
                    "reason": "バイト面接のため",
                }
            )
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["message_type"], "swap_request")
        self.assertEqual(result["recipient"], "all_staff")
        self.assertIn("山田美咲", result["message"])
        self.assertIn("バイト面接", result["message"])
        self.assertIn("18:00", result["message"])

    def test_emergency_coverage_generates_message(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke(
                {
                    "message_type": "emergency_coverage",
                    "start_time": "17:00",
                    "end_time": "22:00",
                }
            )
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["message_type"], "emergency_coverage")
        self.assertIn("緊急", result["message"])
        self.assertIn("17:00", result["message"])
        self.assertEqual(result["metadata"]["urgency"], "high")

    def test_schedule_update_generates_message(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"message_type": "schedule_update"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["message_type"], "schedule_update")
        self.assertIn("週間シフト", result["message"])
        self.assertIn("公開しました", result["message"])

    def test_meeting_notice_generates_message(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke(
                {
                    "message_type": "meeting_notice",
                    "date": "2026-02-20",
                    "time": "17:00",
                    "agenda": "2月の売上報告",
                }
            )
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["message_type"], "meeting_notice")
        self.assertIn("ミーティング", result["message"])
        self.assertIn("2月の売上報告", result["message"])
        self.assertIn("17:00", result["message"])

    def test_get_weekday_ja(self) -> None:
        self.assertEqual(lc.get_weekday_ja("2026-02-16"), "月")  # Monday
        self.assertEqual(lc.get_weekday_ja("2026-02-15"), "日")  # Sunday
        self.assertEqual(lc.get_weekday_ja("2026-02-20"), "金")  # Friday

    def test_format_date_ja(self) -> None:
        self.assertEqual(lc.format_date_ja("2026-02-15"), "2/15")
        self.assertEqual(lc.format_date_ja("2026-12-01"), "12/1")


if __name__ == "__main__":
    unittest.main()
