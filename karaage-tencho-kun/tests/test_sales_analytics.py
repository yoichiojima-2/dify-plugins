import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import sales_analytics as sa


class TestSalesAnalytics(unittest.TestCase):
    def setUp(self) -> None:
        sa._SEED_CACHE = None
        sa._conn = None

    def test_seed_loads_with_expected_shape(self) -> None:
        seed = sa._load_seed_data()

        self.assertIn("items_master", seed)
        self.assertIn("daily_patterns", seed)
        self.assertIn("hourly_item_profiles", seed)

        self.assertEqual(len(seed["items_master"]), 29)
        self.assertEqual(len(seed["daily_patterns"]), 31)
        self.assertEqual(len(seed["hourly_item_profiles"]), 17)

    def test_connection_initializes_seeded_tables(self) -> None:
        conn = sa._get_connection()

        item_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        sales_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        daily_count = conn.execute("SELECT COUNT(*) FROM daily_summary").fetchone()[0]

        self.assertEqual(item_count, 29)
        self.assertEqual(daily_count, 31)
        self.assertGreater(sales_count, 9000)

    def test_invoke_returns_error_when_sql_missing(self) -> None:
        tool = object.__new__(sa.SalesAnalyticsTool)
        tool.create_json_message = lambda payload: payload

        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_invoke_runs_simple_query(self) -> None:
        tool = object.__new__(sa.SalesAnalyticsTool)
        tool.create_json_message = lambda payload: payload

        messages = list(tool._invoke({"sql": "SELECT COUNT(*) AS c FROM items"}))

        self.assertEqual(len(messages), 1)
        rows = messages[0]
        self.assertIsInstance(rows, list)
        self.assertEqual(rows[0]["c"], 29)


if __name__ == "__main__":
    unittest.main()
