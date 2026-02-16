import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import inventory_manager as im


class TestInventoryManager(unittest.TestCase):
    def setUp(self) -> None:
        im._db.reset()

    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(im.InventoryManagerTool)
        tool.create_json_message = lambda body: body
        return tool

    # === Schema Tests ===

    def test_get_connection_initializes_schema(self) -> None:
        conn = im._db.get_connection()
        inv_count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        self.assertGreater(inv_count, 0)

        mov_count = conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]
        self.assertGreater(mov_count, 0)

    def test_inventory_has_new_columns(self) -> None:
        conn = im._db.get_connection()
        result = conn.execute(
            "SELECT min_stock_level, reorder_point FROM inventory LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(result)
        self.assertIsNotNone(result[0])  # min_stock_level
        self.assertIsNotNone(result[1])  # reorder_point

    # === Action: list ===

    def test_action_list_returns_items(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "list"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("current_time", result)
        self.assertIn("items", result)
        self.assertIn("total_items", result)
        self.assertIn("category_summary", result)
        self.assertIsInstance(result["items"], list)
        self.assertGreater(len(result["items"]), 0)

    def test_action_list_items_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "list"}))
        result = messages[0]

        item = result["items"][0]
        self.assertIn("item_id", item)
        self.assertIn("item_name", item)
        self.assertIn("category", item)
        self.assertIn("quantity", item)
        self.assertIn("min_stock_level", item)
        self.assertIn("reorder_point", item)
        self.assertIn("expires_at", item)
        self.assertIn("remaining_hours", item)

    def test_action_list_filter_by_category(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "list", "category": "おにぎり"}))
        result = messages[0]

        for item in result["items"]:
            self.assertEqual(item["category"], "おにぎり")

    # === Action: check_expiration ===

    def test_action_check_expiration_returns_alerts(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "check_expiration"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("current_time", result)
        self.assertIn("alerts", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["alerts"], list)

    def test_action_check_expiration_alerts_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "check_expiration"}))
        result = messages[0]

        if result["alerts"]:
            alert = result["alerts"][0]
            self.assertIn("item_id", alert)
            self.assertIn("item_name", alert)
            self.assertIn("category", alert)
            self.assertIn("expires_at", alert)
            self.assertIn("remaining_hours", alert)
            self.assertIn("quantity", alert)
            self.assertIn("action", alert)
            self.assertIn("discount_percent", alert)
            self.assertIn("urgency", alert)

    def test_action_check_expiration_filter_by_urgency(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "check_expiration", "urgency": "high"}))
        result = messages[0]

        for alert in result["alerts"]:
            self.assertEqual(alert["urgency"], "high")

    def test_action_check_expiration_filter_by_hours_threshold(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "check_expiration", "hours_threshold": 4}))
        result = messages[0]

        for alert in result["alerts"]:
            self.assertLessEqual(alert["remaining_hours"], 4)

    def test_action_check_expiration_summary_counts(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "check_expiration"}))
        result = messages[0]

        summary = result["summary"]
        self.assertIn("high_urgency", summary)
        self.assertIn("medium_urgency", summary)
        self.assertIn("low_urgency", summary)
        self.assertIn("total", summary)

    # === Action: add_stock ===

    def test_action_add_stock_existing_item(self) -> None:
        tool = self._make_tool()

        # Get current quantity
        conn = im._db.get_connection()
        before = conn.execute(
            "SELECT quantity FROM inventory WHERE item_id = 'INV001'"
        ).fetchone()[0]

        # Add stock
        messages = list(tool._invoke({
            "action": "add_stock",
            "item_id": "INV001",
            "quantity": 5
        }))

        result = messages[0]
        self.assertTrue(result.get("success"))
        self.assertEqual(result["item_id"], "INV001")
        self.assertEqual(result["previous_quantity"], before)
        self.assertEqual(result["added_quantity"], 5)
        self.assertEqual(result["new_quantity"], before + 5)
        self.assertIn("movement_id", result)

    def test_action_add_stock_new_item(self) -> None:
        tool = self._make_tool()

        messages = list(tool._invoke({
            "action": "add_stock",
            "item_name": "テスト商品",
            "category": "おにぎり",
            "quantity": 10,
            "expires_in_hours": 8
        }))

        result = messages[0]
        self.assertTrue(result.get("success"))
        self.assertIn("item_id", result)
        self.assertEqual(result["item_name"], "テスト商品")
        self.assertEqual(result["category"], "おにぎり")
        self.assertEqual(result["quantity"], 10)
        self.assertIn("expires_at", result)
        self.assertIn("movement_id", result)

    def test_action_add_stock_requires_quantity(self) -> None:
        tool = self._make_tool()

        messages = list(tool._invoke({
            "action": "add_stock",
            "item_id": "INV001"
        }))

        result = messages[0]
        self.assertIn("error", result)

    # === Action: remove_stock ===

    def test_action_remove_stock_success(self) -> None:
        tool = self._make_tool()

        # Get current quantity
        conn = im._db.get_connection()
        before = conn.execute(
            "SELECT quantity FROM inventory WHERE item_id = 'INV001'"
        ).fetchone()[0]

        # Remove stock
        messages = list(tool._invoke({
            "action": "remove_stock",
            "item_id": "INV001",
            "quantity": 2,
            "reason": "販売"
        }))

        result = messages[0]
        self.assertTrue(result.get("success"))
        self.assertEqual(result["item_id"], "INV001")
        self.assertEqual(result["previous_quantity"], before)
        self.assertEqual(result["removed_quantity"], 2)
        self.assertEqual(result["new_quantity"], before - 2)
        self.assertEqual(result["reason"], "販売")
        self.assertIn("movement_id", result)

    def test_action_remove_stock_insufficient_quantity(self) -> None:
        tool = self._make_tool()

        messages = list(tool._invoke({
            "action": "remove_stock",
            "item_id": "INV001",
            "quantity": 9999
        }))

        result = messages[0]
        self.assertIn("error", result)
        self.assertIn("在庫不足", result["error"])

    def test_action_remove_stock_not_found(self) -> None:
        tool = self._make_tool()

        messages = list(tool._invoke({
            "action": "remove_stock",
            "item_id": "NONEXISTENT",
            "quantity": 1
        }))

        result = messages[0]
        self.assertIn("error", result)
        self.assertIn("見つかりません", result["error"])

    # === Action: low_stock_alert ===

    def test_action_low_stock_alert(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "low_stock_alert"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("current_time", result)
        self.assertIn("alerts", result)
        self.assertIn("summary", result)

        summary = result["summary"]
        self.assertIn("critical_count", summary)
        self.assertIn("warning_count", summary)
        self.assertIn("total", summary)

    def test_action_low_stock_alert_items_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "low_stock_alert"}))
        result = messages[0]

        if result["alerts"]:
            alert = result["alerts"][0]
            self.assertIn("item_id", alert)
            self.assertIn("item_name", alert)
            self.assertIn("category", alert)
            self.assertIn("current_quantity", alert)
            self.assertIn("min_stock_level", alert)
            self.assertIn("reorder_point", alert)
            self.assertIn("shortage", alert)
            self.assertIn("recommended_order_quantity", alert)
            self.assertIn("alert_level", alert)

    # === Action: order_recommendation ===

    def test_action_order_recommendation(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "order_recommendation"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("current_time", result)
        self.assertIn("recommendations", result)
        self.assertIn("category_orders", result)
        self.assertIn("summary", result)

        summary = result["summary"]
        self.assertIn("total_items", summary)
        self.assertIn("total_quantity_to_order", summary)

    def test_action_order_recommendation_items_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "order_recommendation"}))
        result = messages[0]

        if result["recommendations"]:
            rec = result["recommendations"][0]
            self.assertIn("item_id", rec)
            self.assertIn("item_name", rec)
            self.assertIn("category", rec)
            self.assertIn("current_quantity", rec)
            self.assertIn("reorder_point", rec)
            self.assertIn("shortage", rec)
            self.assertIn("recommended_order_quantity", rec)
            self.assertIn("remaining_hours_until_expiry", rec)
            self.assertIn("note", rec)

    # === Action: movement_history ===

    def test_action_movement_history(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "movement_history"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("current_time", result)
        self.assertIn("period_days", result)
        self.assertIn("movements", result)
        self.assertIn("summary", result)

        summary = result["summary"]
        self.assertIn("total_in", summary)
        self.assertIn("total_out", summary)
        self.assertIn("total_expired", summary)
        self.assertIn("total_movements", summary)

    def test_action_movement_history_items_have_required_fields(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "movement_history"}))
        result = messages[0]

        if result["movements"]:
            mov = result["movements"][0]
            self.assertIn("movement_id", mov)
            self.assertIn("item_id", mov)
            self.assertIn("item_name", mov)
            self.assertIn("movement_type", mov)
            self.assertIn("quantity", mov)
            self.assertIn("reason", mov)
            self.assertIn("created_at", mov)

    def test_action_movement_history_custom_days(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "movement_history", "days": 1}))
        result = messages[0]

        self.assertEqual(result["period_days"], 1)

    # === Utility Functions ===

    def test_get_urgency(self) -> None:
        self.assertEqual(im._get_urgency(1.0), "high")
        self.assertEqual(im._get_urgency(2.0), "high")
        self.assertEqual(im._get_urgency(3.0), "medium")
        self.assertEqual(im._get_urgency(4.0), "medium")
        self.assertEqual(im._get_urgency(5.0), "low")
        self.assertEqual(im._get_urgency(8.0), "low")

    def test_unknown_action_returns_error(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"action": "unknown_action"}))

        result = messages[0]
        self.assertIn("error", result)
        self.assertIn("Unknown action", result["error"])


if __name__ == "__main__":
    unittest.main()
