import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import sales_analytics as sa
from tools import dashboard_generator as dg


class TestDashboardGenerator(unittest.TestCase):
    def setUp(self) -> None:
        sa._db.reset()

    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(dg.DashboardGeneratorTool)
        tool.create_json_message = lambda body: body
        return tool

    def test_invoke_returns_error_for_unknown_report_type(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "unknown"}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("available_types", messages[0])

    def test_daily_dashboard_returns_json(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "daily")
        self.assertIn("generated_at", result)
        self.assertIn("date", result)
        self.assertIn("kpi", result)
        self.assertIn("hourly_sales", result)
        self.assertIn("category_sales", result)

    def test_daily_dashboard_kpi_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))
        result = messages[0]

        kpi = result["kpi"]
        self.assertIn("total_sales", kpi)
        self.assertIn("total_items", kpi)
        self.assertIn("transactions", kpi)
        self.assertIn("avg_transaction", kpi)
        self.assertIn("yesterday_sales", kpi)
        self.assertIn("sales_change_pct", kpi)

    def test_daily_dashboard_hourly_sales_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))
        result = messages[0]

        hourly_sales = result["hourly_sales"]
        # 6時〜23時（18時間分）
        self.assertEqual(len(hourly_sales), 18)
        self.assertEqual(hourly_sales[0]["hour"], 6)
        self.assertEqual(hourly_sales[-1]["hour"], 23)

    def test_weekly_dashboard_returns_json(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "weekly"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "weekly")
        self.assertIn("period", result)
        self.assertIn("kpi", result)
        self.assertIn("daily_sales", result)
        self.assertIn("category_sales", result)
        self.assertIn("weather_sales", result)

    def test_weekly_dashboard_kpi_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "weekly"}))
        result = messages[0]

        kpi = result["kpi"]
        self.assertIn("total_sales", kpi)
        self.assertIn("total_items", kpi)
        self.assertIn("transactions", kpi)
        self.assertIn("daily_avg", kpi)
        self.assertIn("prev_week_sales", kpi)
        self.assertIn("sales_change_pct", kpi)

    def test_comparison_dashboard_returns_json(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "comparison"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "comparison")
        self.assertIn("period", result)
        self.assertIn("kpi", result)
        self.assertIn("dow_comparison", result)
        self.assertIn("category_comparison", result)

    def test_comparison_dashboard_kpi_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "comparison"}))
        result = messages[0]

        kpi = result["kpi"]
        self.assertIn("this_week_total", kpi)
        self.assertIn("last_week_total", kpi)
        self.assertIn("change_amount", kpi)
        self.assertIn("change_pct", kpi)
        self.assertIn("daily_avg_diff", kpi)

    def test_comparison_dashboard_dow_comparison_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "comparison"}))
        result = messages[0]

        dow_comparison = result["dow_comparison"]
        self.assertEqual(len(dow_comparison), 7)

        for item in dow_comparison:
            self.assertIn("dow", item)
            self.assertIn("dow_label", item)
            self.assertIn("this_week", item)
            self.assertIn("last_week", item)

        # 曜日ラベルの確認
        labels = [item["dow_label"] for item in dow_comparison]
        self.assertEqual(labels, ["日", "月", "火", "水", "木", "金", "土"])

    def test_default_report_type_is_daily(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "daily")

    def test_calc_change_positive(self) -> None:
        tool = self._make_tool()
        change = tool._calc_change(110, 100)
        self.assertEqual(change, 10.0)

    def test_calc_change_negative(self) -> None:
        tool = self._make_tool()
        change = tool._calc_change(90, 100)
        self.assertEqual(change, -10.0)

    def test_calc_change_zero_previous(self) -> None:
        tool = self._make_tool()
        change = tool._calc_change(100, 0)
        self.assertIsNone(change)


if __name__ == "__main__":
    unittest.main()
