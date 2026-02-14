import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import shift_manager as sm


class TestShiftManager(unittest.TestCase):
    def setUp(self) -> None:
        sm._conn = None

    def test_get_connection_initializes_schema_and_seed_data(self) -> None:
        conn = sm._get_connection()

        staff_count = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
        shift_count = conn.execute("SELECT COUNT(*) FROM shifts").fetchone()[0]

        self.assertGreaterEqual(staff_count, 7)
        self.assertGreaterEqual(shift_count, 90)

    def test_invoke_returns_error_when_sql_missing(self) -> None:
        tool = object.__new__(sm.ShiftManagerTool)
        tool.create_json_message = lambda body: body

        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_invoke_runs_query_and_returns_rows(self) -> None:
        tool = object.__new__(sm.ShiftManagerTool)
        tool.create_json_message = lambda body: body

        messages = list(tool._invoke({"sql": "SELECT COUNT(*) AS c FROM staff"}))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0]["c"], 7)

    def test_invoke_returns_error_for_invalid_sql(self) -> None:
        tool = object.__new__(sm.ShiftManagerTool)
        tool.create_json_message = lambda body: body

        messages = list(tool._invoke({"sql": "SELECT * FROM no_such_table"}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])


if __name__ == "__main__":
    unittest.main()
