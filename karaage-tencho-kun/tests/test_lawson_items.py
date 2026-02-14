import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import lawson_items as li


class TestLawsonItems(unittest.TestCase):
    def setUp(self) -> None:
        li._DATA_CACHE = None

    def test_catalog_loads_with_expected_shape(self) -> None:
        catalog = li._load_catalog()

        self.assertIn("items", catalog)
        self.assertIn("categories", catalog)
        self.assertGreaterEqual(len(catalog["items"]), 40)
        self.assertGreaterEqual(len(catalog["categories"]), 5)

    def test_invoke_filters_by_category_keyword_and_seasonal(self) -> None:
        tool = object.__new__(li.LawsonItemsTool)
        tool.create_json_message = lambda payload: payload

        messages = list(
            tool._invoke(
                {
                    "category": "hot_snack",
                    "keyword": "からあげ",
                    "include_seasonal": False,
                }
            )
        )

        self.assertEqual(len(messages), 1)
        payload = messages[0]

        self.assertIsInstance(payload["items"], list)
        self.assertEqual(payload["total_count"], len(payload["items"]))
        self.assertGreater(len(payload["items"]), 0)

        for item in payload["items"]:
            self.assertEqual(item["category"], "hot_snack")
            self.assertFalse(item["is_seasonal"])
            self.assertIn("からあげ", item["name"])


if __name__ == "__main__":
    unittest.main()
