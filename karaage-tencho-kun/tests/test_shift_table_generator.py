import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import shift_manager as sm
from tools import shift_table_generator as stg


class TestShiftTableGenerator(unittest.TestCase):
    def setUp(self) -> None:
        sm._conn = None

    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(stg.ShiftTableGeneratorTool)
        tool.create_json_message = lambda body: body
        return tool

    def test_invoke_returns_error_for_unknown_view_type(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "unknown"}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("available_types", messages[0])

    def test_weekly_view_returns_json(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "weekly")
        self.assertIn("generated_at", result)
        self.assertIn("start_date", result)
        self.assertIn("end_date", result)
        self.assertIn("dates", result)
        self.assertIn("schedule", result)
        self.assertIn("summary", result)

    def test_weekly_view_dates_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        self.assertEqual(len(result["dates"]), 7)
        date_info = result["dates"][0]
        self.assertIn("date", date_info)
        self.assertIn("weekday", date_info)
        self.assertIn("day", date_info)
        self.assertIn("month", date_info)
        self.assertIn("is_weekend", date_info)
        self.assertIn("is_today", date_info)

    def test_weekly_view_schedule_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        self.assertGreater(len(result["schedule"]), 0)
        staff_schedule = result["schedule"][0]
        self.assertIn("staff", staff_schedule)
        self.assertIn("shifts_by_date", staff_schedule)

        staff = staff_schedule["staff"]
        self.assertIn("id", staff)
        self.assertIn("name", staff)
        self.assertIn("role", staff)

    def test_weekly_view_summary_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        summary = result["summary"]
        self.assertIn("total_shifts", summary)
        self.assertIn("total_hours", summary)
        self.assertIn("staff_count", summary)
        self.assertIn("daily_avg_hours", summary)

    def test_daily_view_returns_json(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"view_type": "daily", "start_date": "2026-02-15"})
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "daily")
        self.assertIn("date", result)
        self.assertIn("weekday", result)
        self.assertIn("shifts", result)
        self.assertIn("hourly_coverage", result)
        self.assertIn("summary", result)

    def test_daily_view_hourly_coverage_structure(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"view_type": "daily", "start_date": "2026-02-15"})
        )
        result = messages[0]

        # hourly_coverage should have hours 6-23
        hourly_coverage = result["hourly_coverage"]
        self.assertEqual(len(hourly_coverage), 18)  # 6時〜23時
        for hour in range(6, 24):
            self.assertIn(hour, hourly_coverage)

    def test_staff_view_returns_json(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "staff"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "staff")
        self.assertIn("start_date", result)
        self.assertIn("end_date", result)
        self.assertIn("dates", result)
        self.assertIn("staff_summary", result)

    def test_staff_view_summary_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "staff"}))
        result = messages[0]

        # 2週間分の日付
        self.assertEqual(len(result["dates"]), 14)

        self.assertGreater(len(result["staff_summary"]), 0)
        staff_summary = result["staff_summary"][0]
        self.assertIn("staff", staff_summary)
        self.assertIn("total_hours", staff_summary)
        self.assertIn("estimated_pay", staff_summary)
        self.assertIn("shifts_by_date", staff_summary)

    def test_default_view_type_is_weekly(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "weekly")

    def test_invalid_date_format_returns_error(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"view_type": "weekly", "start_date": "invalid"})
        )

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_start_date_is_included_in_result(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"view_type": "weekly", "start_date": "2026-02-16"})
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["start_date"], "2026-02-16")

    def test_contains_staff_data(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        # スタッフデータが含まれていることを確認
        staff_names = [s["staff"]["name"] for s in result["schedule"]]
        self.assertIn("田中太郎", staff_names)


if __name__ == "__main__":
    unittest.main()
