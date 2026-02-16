import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import shift_manager as sm
from tools import shift_optimizer as so


class TestShiftOptimizer(unittest.TestCase):
    def setUp(self) -> None:
        sm._db.reset()

    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(so.ShiftOptimizerTool)
        tool.create_json_message = lambda body: body
        return tool

    def test_invoke_returns_error_when_date_missing(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("hint", messages[0])

    def test_invoke_returns_error_for_invalid_date(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"date": "invalid-date"}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_invoke_returns_optimization_result(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"date": "2026-02-20"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("date", result)
        self.assertIn("weekday", result)
        self.assertIn("predicted_demand", result)
        self.assertIn("suggested_shifts", result)
        self.assertIn("coverage_analysis", result)
        self.assertIn("cost_summary", result)

    def test_result_has_correct_date(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"date": "2026-02-20"}))
        result = messages[0]

        self.assertEqual(result["date"], "2026-02-20")
        self.assertEqual(result["weekday"], "金")

    def test_weather_affects_demand(self) -> None:
        tool = self._make_tool()

        sunny_result = list(tool._invoke({"date": "2026-02-20", "weather": "sunny"}))[0]
        rainy_result = list(tool._invoke({"date": "2026-02-20", "weather": "rainy"}))[0]

        sunny_impact = sunny_result["predicted_demand"]["weather_impact"]
        rainy_impact = rainy_result["predicted_demand"]["weather_impact"]

        self.assertGreater(sunny_impact, rainy_impact)

    def test_suggested_shifts_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"date": "2026-02-20"}))
        result = messages[0]

        if result["suggested_shifts"]:
            shift = result["suggested_shifts"][0]
            self.assertIn("staff_id", shift)
            self.assertIn("staff_name", shift)
            self.assertIn("start", shift)
            self.assertIn("end", shift)
            self.assertIn("reason", shift)
            self.assertIn("cost", shift)

    def test_coverage_analysis_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"date": "2026-02-20"}))
        result = messages[0]

        coverage = result["coverage_analysis"]
        self.assertIn("understaffed_hours", coverage)
        self.assertIn("overstaffed_hours", coverage)
        self.assertIn("hourly_requirements", coverage)

    def test_cost_summary_structure(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"date": "2026-02-20"}))
        result = messages[0]

        cost = result["cost_summary"]
        self.assertIn("estimated_labor_cost", cost)
        self.assertIn("total_hours", cost)
        self.assertIn("staff_count", cost)

    def test_parse_availability(self) -> None:
        avail_json = '{"mon": ["06:00-15:00"], "tue": ["17:00-22:00"]}'

        mon_slots = so._parse_availability(avail_json, "mon")
        self.assertEqual(mon_slots, [(6, 15)])

        tue_slots = so._parse_availability(avail_json, "tue")
        self.assertEqual(tue_slots, [(17, 22)])

        wed_slots = so._parse_availability(avail_json, "wed")
        self.assertEqual(wed_slots, [])

    def test_check_hour_coverage(self) -> None:
        self.assertTrue(so._check_hour_coverage(9, 17, 12))
        self.assertTrue(so._check_hour_coverage(9, 17, 9))
        self.assertFalse(so._check_hour_coverage(9, 17, 17))
        self.assertFalse(so._check_hour_coverage(9, 17, 8))


if __name__ == "__main__":
    unittest.main()
