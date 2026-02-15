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

    def test_weekly_view_generation(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "weekly")
        self.assertIn("html", result)
        self.assertIn("generated_at", result)

    def test_daily_view_generation(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"view_type": "daily", "start_date": "2026-02-15"})
        )

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "daily")
        self.assertIn("html", result)

    def test_staff_view_generation(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "staff"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "staff")
        self.assertIn("html", result)

    def test_default_view_type_is_weekly(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result["view_type"], "weekly")

    def test_html_contains_shift_table(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("shift-table", html)
        self.assertIn("<table", html)

    def test_html_contains_staff_names(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("田中太郎", html)

    def test_html_contains_legend(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("legend", html)

    def test_html_is_self_contained(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"view_type": "weekly"}))
        result = messages[0]

        html = result["html"]
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<html", html)
        self.assertIn("</html>", html)
        self.assertIn("<style>", html)

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


if __name__ == "__main__":
    unittest.main()
