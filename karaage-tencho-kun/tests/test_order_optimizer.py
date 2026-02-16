import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import inventory_manager as im
from tools import order_optimizer as oo


# --- テスト用フェイク ---

FAKE_PREDICTIONS = [
    {"item": "おにぎり", "predicted_demand": 60, "base_demand": 50, "change_percent": 20.0},
    {"item": "ホットスナック", "predicted_demand": 65, "base_demand": 50, "change_percent": 30.0},
    {"item": "サンドイッチ", "predicted_demand": 35, "base_demand": 50, "change_percent": -30.0},
    {"item": "弁当", "predicted_demand": 50, "base_demand": 50, "change_percent": 0.0},
]


def _fake_predictions_high_demand(self, weather, temperature, humidity, now):
    """需要増加の予測を返すフェイク。"""
    return FAKE_PREDICTIONS, None


def _fake_predictions_with_warning(self, weather, temperature, humidity, now):
    """天気警告付きの予測を返すフェイク。"""
    return FAKE_PREDICTIONS, "'storm' は未対応です。cloudy として予測します"


class TestOrderOptimizer(unittest.TestCase):
    def setUp(self) -> None:
        im._db.reset()

    def _make_tool(self):
        """テスト用のツールインスタンスを作成。"""
        tool = object.__new__(oo.OrderOptimizerTool)
        tool.create_json_message = lambda body: body
        return tool

    # --- 基本構造テスト ---

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_result_has_required_top_level_keys(self) -> None:
        """結果に必須のトップレベルキーが含まれる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        for key in ("current_time", "conditions", "demand_forecast",
                     "recommendations", "category_summary", "summary"):
            self.assertIn(key, result, f"missing key: {key}")

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_conditions_reflect_input(self) -> None:
        """入力パラメータが conditions に反映される。"""
        tool = self._make_tool()
        messages = list(tool._invoke({
            "weather": "rainy", "temperature": 10, "humidity": 80, "safety_stock_days": 2,
        }))
        conditions = messages[0]["conditions"]

        self.assertEqual(conditions["weather"], "rainy")
        self.assertEqual(conditions["temperature"], 10.0)
        self.assertEqual(conditions["humidity"], 80.0)
        self.assertEqual(conditions["safety_stock_days"], 2.0)

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_recommendations_have_required_fields(self) -> None:
        """各 recommendation に必須フィールドが含まれる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        self.assertGreater(len(result["recommendations"]), 0)
        required_fields = (
            "item_id", "item_name", "category", "current_quantity",
            "reorder_point", "adjusted_target", "demand_ratio",
            "recommended_order_quantity", "remaining_hours_until_expiry", "note",
        )
        for rec in result["recommendations"]:
            for field in required_fields:
                self.assertIn(field, rec, f"missing field: {field}")

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_summary_has_required_fields(self) -> None:
        """summary に total_items, items_to_order, total_order_quantity が含まれる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        summary = messages[0]["summary"]

        self.assertIn("total_items", summary)
        self.assertIn("items_to_order", summary)
        self.assertIn("total_order_quantity", summary)

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_demand_forecast_included_in_result(self) -> None:
        """demand_forecast が結果に含まれる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        self.assertEqual(result["demand_forecast"], FAKE_PREDICTIONS)

    # --- アルゴリズムテスト ---

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_high_demand_category_has_higher_ratio(self) -> None:
        """需要増加カテゴリは demand_ratio > 1.0 になる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        hot_snack_recs = [r for r in result["recommendations"] if r["category"] == "ホットスナック"]
        for rec in hot_snack_recs:
            self.assertGreater(rec["demand_ratio"], 1.0)

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_low_demand_category_has_lower_ratio(self) -> None:
        """需要減少カテゴリは demand_ratio < 1.0 になる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        sandwich_recs = [r for r in result["recommendations"] if r["category"] == "サンドイッチ"]
        for rec in sandwich_recs:
            self.assertLess(rec["demand_ratio"], 1.0)

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_category_without_forecast_uses_ratio_1(self) -> None:
        """需要予測にないカテゴリは ratio=1.0 になる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        # "デザート" や "パン" は FAKE_PREDICTIONS にない
        unmapped_recs = [
            r for r in result["recommendations"]
            if r["category"] not in ("おにぎり", "ホットスナック", "サンドイッチ", "弁当")
        ]
        for rec in unmapped_recs:
            self.assertEqual(rec["demand_ratio"], 1.0,
                             f"{rec['category']} should have ratio 1.0 but got {rec['demand_ratio']}")

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_recommendations_sorted_by_order_quantity_desc(self) -> None:
        """recommendations が発注数量の降順でソートされる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        quantities = [r["recommended_order_quantity"] for r in result["recommendations"]]
        self.assertEqual(quantities, sorted(quantities, reverse=True))

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_safety_stock_days_increases_target(self) -> None:
        """safety_stock_days が大きいほど adjusted_target が大きくなる。"""
        tool = self._make_tool()

        msgs_1 = list(tool._invoke({"weather": "sunny", "temperature": 25, "safety_stock_days": 1}))
        msgs_2 = list(tool._invoke({"weather": "sunny", "temperature": 25, "safety_stock_days": 2}))

        recs_1 = {r["item_id"]: r for r in msgs_1[0]["recommendations"]}
        recs_2 = {r["item_id"]: r for r in msgs_2[0]["recommendations"]}

        # 少なくとも1つの商品で safety_stock_days=2 の方が大きい target
        found_larger = False
        for item_id in recs_1:
            if item_id in recs_2:
                if recs_2[item_id]["adjusted_target"] > recs_1[item_id]["adjusted_target"]:
                    found_larger = True
                    break
        self.assertTrue(found_larger, "safety_stock_days=2 で adjusted_target が増加する商品がない")

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_safety_stock_days_clamped(self) -> None:
        """safety_stock_days が 0.5〜3 にクランプされる。"""
        tool = self._make_tool()

        msgs = list(tool._invoke({"weather": "sunny", "temperature": 25, "safety_stock_days": 10}))
        self.assertEqual(msgs[0]["conditions"]["safety_stock_days"], 3.0)

        msgs = list(tool._invoke({"weather": "sunny", "temperature": 25, "safety_stock_days": 0.1}))
        self.assertEqual(msgs[0]["conditions"]["safety_stock_days"], 0.5)

    # --- _calculate_orders 直接テスト ---

    def test_calculate_orders_expiry_less_than_4h_skips(self) -> None:
        """消費期限が4時間未満の商品は発注見送り。"""
        predictions = [{"item": "テスト", "predicted_demand": 60, "base_demand": 50, "change_percent": 20.0}]
        inventory = {
            "テスト": [{
                "item_id": "T001", "item_name": "テスト商品", "category": "テスト",
                "quantity": 2, "min_stock_level": 5, "reorder_point": 10,
                "remaining_hours": 3.0,
            }],
        }
        from datetime import datetime
        from tools.datetime_utils import JST
        now = datetime.now(JST)

        recs = oo.OrderOptimizerTool._calculate_orders(predictions, inventory, 1.0, now)
        self.assertEqual(recs[0]["recommended_order_quantity"], 0)
        self.assertIn("期限切れ間近", recs[0]["note"])

    def test_calculate_orders_expiry_4_to_8h_halves(self) -> None:
        """消費期限が4-8時間の商品は半量発注。"""
        predictions = [{"item": "テスト", "predicted_demand": 50, "base_demand": 50, "change_percent": 0.0}]
        inventory = {
            "テスト": [{
                "item_id": "T001", "item_name": "テスト商品", "category": "テスト",
                "quantity": 2, "min_stock_level": 5, "reorder_point": 10,
                "remaining_hours": 6.0,
            }],
        }
        from datetime import datetime
        from tools.datetime_utils import JST
        now = datetime.now(JST)

        recs = oo.OrderOptimizerTool._calculate_orders(predictions, inventory, 1.0, now)
        # adjusted_target = 10 * 1.0 * 1.0 = 10, base_order = 10 - 2 = 8, halved = 4
        self.assertEqual(recs[0]["recommended_order_quantity"], 4)
        self.assertIn("少量発注", recs[0]["note"])

    def test_calculate_orders_low_demand_halves(self) -> None:
        """需要減少時（ratio < 0.8）は半量発注。"""
        predictions = [{"item": "テスト", "predicted_demand": 35, "base_demand": 50, "change_percent": -30.0}]
        inventory = {
            "テスト": [{
                "item_id": "T001", "item_name": "テスト商品", "category": "テスト",
                "quantity": 2, "min_stock_level": 5, "reorder_point": 10,
                "remaining_hours": 24.0,
            }],
        }
        from datetime import datetime
        from tools.datetime_utils import JST
        now = datetime.now(JST)

        recs = oo.OrderOptimizerTool._calculate_orders(predictions, inventory, 1.0, now)
        # ratio = 35/50 = 0.7, adjusted_target = 10 * 0.7 = 7, base_order = 7 - 2 = 5, halved = 2
        self.assertEqual(recs[0]["recommended_order_quantity"], 2)
        self.assertIn("控えめ発注", recs[0]["note"])

    def test_calculate_orders_high_demand_full_order(self) -> None:
        """需要増加時（ratio > 1.2）は全量発注。"""
        predictions = [{"item": "テスト", "predicted_demand": 70, "base_demand": 50, "change_percent": 40.0}]
        inventory = {
            "テスト": [{
                "item_id": "T001", "item_name": "テスト商品", "category": "テスト",
                "quantity": 2, "min_stock_level": 5, "reorder_point": 10,
                "remaining_hours": 24.0,
            }],
        }
        from datetime import datetime
        from tools.datetime_utils import JST
        now = datetime.now(JST)

        recs = oo.OrderOptimizerTool._calculate_orders(predictions, inventory, 1.0, now)
        # ratio = 70/50 = 1.4, adjusted_target = 10 * 1.4 = 14, base_order = 14 - 2 = 12
        self.assertEqual(recs[0]["recommended_order_quantity"], 12)
        self.assertIn("需要増加", recs[0]["note"])

    # --- エッジケース ---

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_invalid_numeric_inputs_fallback(self) -> None:
        """不正な数値入力はデフォルト値にフォールバック。"""
        tool = self._make_tool()
        messages = list(tool._invoke({
            "weather": "sunny", "temperature": "bad", "humidity": None,
        }))
        conditions = messages[0]["conditions"]
        self.assertEqual(conditions["temperature"], 20.0)
        self.assertEqual(conditions["humidity"], 60.0)
        self.assertEqual(conditions["safety_stock_days"], 1.0)

    def test_error_returns_error_message(self) -> None:
        """例外発生時はエラーメッセージを返す。"""
        tool = self._make_tool()
        tool._get_demand_predictions = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("model missing"))

        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_with_warning)
    def test_weather_warning_included(self) -> None:
        """天気警告がある場合は weather_warning が含まれる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "storm", "temperature": 25}))
        result = messages[0]
        self.assertIn("weather_warning", result)

    @patch.object(oo.OrderOptimizerTool, "_get_demand_predictions", _fake_predictions_high_demand)
    def test_category_summary_has_demand_ratio(self) -> None:
        """category_summary に demand_ratio が含まれる。"""
        tool = self._make_tool()
        messages = list(tool._invoke({"weather": "sunny", "temperature": 25}))
        result = messages[0]

        for cat, summary in result["category_summary"].items():
            self.assertIn("order_quantity", summary)
            self.assertIn("demand_ratio", summary)


if __name__ == "__main__":
    unittest.main()
