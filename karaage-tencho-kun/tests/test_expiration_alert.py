import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import expiration_alert as ea


class TestExpirationAlert(unittest.TestCase):
    def setUp(self) -> None:
        ea._conn = None

    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(ea.ExpirationAlertTool)
        tool.create_json_message = lambda body: body
        return tool

    def test_get_connection_initializes_schema(self) -> None:
        conn = ea._get_connection()
        count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        self.assertGreater(count, 0)

    def test_invoke_returns_alerts(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("current_time", result)
        self.assertIn("alerts", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["alerts"], list)

    def test_alerts_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))
        result = messages[0]

        if result["alerts"]:
            alert = result["alerts"][0]
            self.assertIn("item_name", alert)
            self.assertIn("category", alert)
            self.assertIn("expires_at", alert)
            self.assertIn("remaining_hours", alert)
            self.assertIn("quantity", alert)
            self.assertIn("action", alert)
            self.assertIn("urgency", alert)

    def test_filter_by_category(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"category": "おにぎり"}))
        result = messages[0]

        for alert in result["alerts"]:
            self.assertEqual(alert["category"], "おにぎり")

    def test_filter_by_urgency(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"urgency": "high"}))
        result = messages[0]

        for alert in result["alerts"]:
            self.assertEqual(alert["urgency"], "high")

    def test_filter_by_hours_threshold(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"hours_threshold": 4}))
        result = messages[0]

        for alert in result["alerts"]:
            self.assertLessEqual(alert["remaining_hours"], 4)

    def test_summary_counts_urgency_levels(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))
        result = messages[0]

        summary = result["summary"]
        self.assertIn("high_urgency", summary)
        self.assertIn("medium_urgency", summary)
        self.assertIn("low_urgency", summary)
        self.assertIn("total", summary)

    def test_get_urgency(self) -> None:
        self.assertEqual(ea._get_urgency(1.0), "high")
        self.assertEqual(ea._get_urgency(2.0), "high")
        self.assertEqual(ea._get_urgency(3.0), "medium")
        self.assertEqual(ea._get_urgency(4.0), "medium")
        self.assertEqual(ea._get_urgency(5.0), "low")
        self.assertEqual(ea._get_urgency(8.0), "low")


if __name__ == "__main__":
    unittest.main()
