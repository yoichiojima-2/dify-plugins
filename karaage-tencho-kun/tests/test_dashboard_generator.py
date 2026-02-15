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
        sa._conn = None

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

    def test_daily_dashboard_generation(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "daily")
        self.assertIn("html", result)
        self.assertIn("generated_at", result)

    def test_weekly_dashboard_generation(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "weekly"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "weekly")
        self.assertIn("html", result)

    def test_comparison_dashboard_generation(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "comparison"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "comparison")
        self.assertIn("html", result)

    def test_default_report_type_is_daily(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["report_type"], "daily")

    def test_html_contains_chartjs(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("chart.js", html.lower())
        self.assertIn("Chart(", html)

    def test_html_contains_kpi_cards(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("kpi-card", html)
        self.assertIn("売上", html)

    def test_html_is_self_contained(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"report_type": "daily"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<html", html)
        self.assertIn("</html>", html)
        self.assertIn("<style>", html)
        self.assertIn("</style>", html)

    def test_format_currency(self) -> None:
        self.assertEqual(dg._format_currency(1000), "¥1,000")
        self.assertEqual(dg._format_currency(1234567), "¥1,234,567")
        self.assertEqual(dg._format_currency(0), "¥0")

    def test_format_change(self) -> None:
        change, css_class = dg._format_change(110, 100)
        self.assertEqual(change, "+10.0%")
        self.assertEqual(css_class, "positive")

        change, css_class = dg._format_change(90, 100)
        self.assertEqual(change, "-10.0%")
        self.assertEqual(css_class, "negative")

        change, css_class = dg._format_change(100, 100)
        self.assertEqual(change, "±0%")
        self.assertEqual(css_class, "")

        change, css_class = dg._format_change(100, 0)
        self.assertEqual(change, "N/A")


if __name__ == "__main__":
    unittest.main()
