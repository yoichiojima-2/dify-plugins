import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import datetime_utils


class TestDatetimeUtils(unittest.TestCase):
    def test_parse_datetime_with_z_suffix(self) -> None:
        dt = datetime_utils.parse_datetime("2026-02-15T00:00:00Z", "UTC")

        self.assertEqual(dt.isoformat(), "2026-02-15T00:00:00+00:00")

    def test_to_jst_utility(self) -> None:
        dt = datetime_utils.parse_datetime("2026-02-15T00:00:00+00:00", "UTC")

        self.assertEqual(
            datetime_utils.to_jst(dt).isoformat(), "2026-02-15T09:00:00+09:00"
        )

    def test_invoke_converts_offset_input_to_jst(self) -> None:
        tool = object.__new__(datetime_utils.DatetimeUtilsTool)
        tool.create_json_message = lambda body: body

        messages = list(
            tool._invoke(
                {"datetime": "2026-02-15T00:00:00+00:00", "source_timezone": "UTC"}
            )
        )

        self.assertEqual(len(messages), 1)
        body = messages[0]
        self.assertEqual(body["jst"]["iso8601"], "2026-02-15T09:00:00+09:00")
        self.assertEqual(body["jst"]["date"], "2026-02-15")
        self.assertEqual(body["jst"]["time"], "09:00:00")

    def test_invoke_applies_source_timezone_for_naive_input(self) -> None:
        tool = object.__new__(datetime_utils.DatetimeUtilsTool)
        tool.create_json_message = lambda body: body

        messages = list(
            tool._invoke(
                {
                    "datetime": "2026-02-15 00:00:00",
                    "source_timezone": "America/New_York",
                }
            )
        )

        self.assertEqual(len(messages), 1)
        body = messages[0]
        self.assertEqual(body["jst"]["iso8601"], "2026-02-15T14:00:00+09:00")

    def test_invoke_returns_error_for_invalid_input(self) -> None:
        tool = object.__new__(datetime_utils.DatetimeUtilsTool)
        tool.create_json_message = lambda body: body

        messages = list(tool._invoke({"datetime": "not-a-date"}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("hint", messages[0])


if __name__ == "__main__":
    unittest.main()
