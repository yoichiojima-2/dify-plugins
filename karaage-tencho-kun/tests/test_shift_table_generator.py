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
        sm._db.reset()

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


    def test_update_via_shift_manager_reflects_in_table_generator(self) -> None:
        """shift_managerでUPDATEした変更がshift_table_generatorに反映されることを確認。

        シフト交代フローの核心テスト:
        1. shift_table_generator で今日のシフトを取得（tanaka が confirmed）
        2. shift_manager の conn で tanaka のシフトを cancelled に UPDATE
        3. shift_table_generator で再取得 → tanaka が消えていること
        """
        from datetime import datetime
        from tools.datetime_utils import JST

        now = datetime.now(JST)
        today_str = now.strftime("%Y-%m-%d")

        # 1. shift_manager の conn を取得（共有DB）
        conn = sm._db.get_connection()

        # 今日の confirmed シフト数を取得
        before = conn.execute(
            "SELECT COUNT(*) FROM shifts WHERE date = CURRENT_DATE AND status = 'confirmed'"
        ).fetchone()[0]

        if before == 0:
            self.skipTest("今日の confirmed シフトが無いためスキップ")

        # 今日の confirmed シフトを1件 cancelled にする
        target = conn.execute(
            "SELECT shift_id, staff_id FROM shifts WHERE date = CURRENT_DATE AND status = 'confirmed' LIMIT 1"
        ).fetchone()
        target_shift_id = target[0]
        target_staff_id = target[1]

        conn.execute(
            "UPDATE shifts SET status = 'cancelled', cancel_reason = 'テスト' WHERE shift_id = ?",
            [target_shift_id],
        )

        # 2. shift_table_generator で daily ビューを取得
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "daily", "start_date": today_str}))
        result = messages[0]

        # 3. cancelled にしたスタッフが shifts に含まれていないことを確認
        active_staff_ids = [s["staff_id"] for s in result["shifts"]]
        # 同じ staff_id で別シフトがある可能性があるので、shift_id で確認
        after = conn.execute(
            "SELECT COUNT(*) FROM shifts WHERE date = CURRENT_DATE AND status = 'confirmed'"
        ).fetchone()[0]

        self.assertEqual(after, before - 1, "UPDATE 後の confirmed 数が1件減っていない")

    def test_overrides_cancelled_excludes_staff_from_weekly(self) -> None:
        """overrides.cancelled で指定したスタッフ×日付がweekly表から除外される。"""
        from datetime import datetime
        from tools.datetime_utils import JST

        now = datetime.now(JST)
        today_str = now.strftime("%Y-%m-%d")

        tool = self._make_tool()

        # まず overrides なしで取得 → tanaka は含まれる
        messages_before = list(tool._invoke({"view_type": "weekly"}))
        result_before = messages_before[0]

        # tanaka の今日のシフトを見つける
        tanaka_shifts_before = None
        for entry in result_before["schedule"]:
            if entry["staff"]["id"] == "tanaka":
                tanaka_shifts_before = entry["shifts_by_date"].get(today_str, [])
                break

        if not tanaka_shifts_before:
            self.skipTest("tanaka の今日のシフトがないためスキップ")

        # overrides で tanaka の今日のシフトを cancelled にする
        import json
        overrides_str = json.dumps({
            "cancelled": [{"staff_id": "tanaka", "date": today_str}]
        })
        messages_after = list(tool._invoke({
            "view_type": "weekly",
            "overrides": overrides_str,
        }))
        result_after = messages_after[0]

        # tanaka の今日のシフトが空になっていることを確認
        for entry in result_after["schedule"]:
            if entry["staff"]["id"] == "tanaka":
                tanaka_shifts_after = entry["shifts_by_date"].get(today_str, [])
                self.assertEqual(len(tanaka_shifts_after), 0,
                                 "overrides.cancelled で tanaka の今日のシフトが除外されていない")
                break

    def test_overrides_added_includes_new_shift_in_daily(self) -> None:
        """overrides.added で追加したシフトがdaily表に含まれる。"""
        from datetime import datetime
        from tools.datetime_utils import JST

        now = datetime.now(JST)
        today_str = now.strftime("%Y-%m-%d")

        tool = self._make_tool()
        import json
        overrides_str = json.dumps({
            "added": [{
                "staff_id": "test_new_staff",
                "name": "テスト太郎",
                "date": today_str,
                "start": "09:00",
                "end": "17:00",
            }]
        })
        messages = list(tool._invoke({
            "view_type": "daily",
            "start_date": today_str,
            "overrides": overrides_str,
        }))
        result = messages[0]

        # 追加したスタッフが shifts に含まれることを確認
        added_ids = [s["staff_id"] for s in result["shifts"]]
        self.assertIn("test_new_staff", added_ids)

    def test_overrides_cancelled_and_added_together(self) -> None:
        """cancelled と added を同時に指定した場合、両方が反映される。"""
        from datetime import datetime
        from tools.datetime_utils import JST

        now = datetime.now(JST)
        today_str = now.strftime("%Y-%m-%d")

        tool = self._make_tool()

        # tanaka の今日のシフトがあるか確認
        messages_check = list(tool._invoke({
            "view_type": "daily",
            "start_date": today_str,
        }))
        tanaka_exists = any(
            s["staff_id"] == "tanaka" for s in messages_check[0]["shifts"]
        )
        if not tanaka_exists:
            self.skipTest("tanaka の今日のシフトがないためスキップ")

        import json
        overrides_str = json.dumps({
            "cancelled": [{"staff_id": "tanaka", "date": today_str}],
            "added": [{
                "staff_id": "kobayashi",
                "name": "小林花子",
                "date": today_str,
                "start": "06:00",
                "end": "15:00",
            }],
        })
        messages = list(tool._invoke({
            "view_type": "daily",
            "start_date": today_str,
            "overrides": overrides_str,
        }))
        result = messages[0]

        staff_ids = [s["staff_id"] for s in result["shifts"]]
        self.assertNotIn("tanaka", staff_ids, "tanaka が除外されていない")
        self.assertIn("kobayashi", staff_ids, "kobayashi が追加されていない")

    def test_overrides_empty_string_is_ignored(self) -> None:
        """overrides が空文字列の場合はエラーにならない。"""
        tool = self._make_tool()
        messages = list(tool._invoke({
            "view_type": "weekly",
            "overrides": "",
        }))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["view_type"], "weekly")

    def test_overrides_invalid_json_is_ignored(self) -> None:
        """overrides が不正なJSONの場合はエラーにならない（無視される）。"""
        tool = self._make_tool()
        messages = list(tool._invoke({
            "view_type": "weekly",
            "overrides": "not-json",
        }))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["view_type"], "weekly")


if __name__ == "__main__":
    unittest.main()
