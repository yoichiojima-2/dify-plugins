"""発注最適化ツール（需要予測 + 在庫レベル統合）。

天気ベースの需要予測と現在の在庫レベルを組み合わせて、
カテゴリ別・商品別の最適発注数量を推奨する。

shift_optimizer が shift_manager._get_connection を再利用するのと同様に、
inventory_manager._db と demand_forecast の予測機能を直接インポートして使う。
エージェントが複数ツール呼び出し結果をJSONで渡す必要なし。1回の呼び出しで完結。
"""

from collections.abc import Generator
from datetime import datetime

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.datetime_utils import JST, parse_expires_at
from tools.inventory_manager import _db as _inv_db


class OrderOptimizerTool(Tool):
    """需要予測ベースの発注最適化ツール。

    天気・気温から需要予測モデルを実行し、現在の在庫レベルと
    消費期限を考慮して最適な発注数量を推奨する。
    """

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        weather = tool_parameters.get("weather", "sunny").strip().lower()
        temperature = tool_parameters.get("temperature", 20)
        humidity = tool_parameters.get("humidity", 60)
        safety_stock_days = tool_parameters.get("safety_stock_days", 1)

        try:
            temperature = float(temperature)
        except (ValueError, TypeError):
            temperature = 20.0
        try:
            humidity = float(humidity)
        except (ValueError, TypeError):
            humidity = 60.0
        try:
            safety_stock_days = max(0.5, min(float(safety_stock_days), 3.0))
        except (ValueError, TypeError):
            safety_stock_days = 1.0

        now = datetime.now(JST)

        try:
            # 1. 需要予測を実行
            demand_predictions, weather_warning = self._get_demand_predictions(
                weather, temperature, humidity, now
            )

            # 2. 在庫データをカテゴリ別に取得
            inventory_by_category = self._get_inventory_by_category(now)

            # 3. 最適発注数量を計算
            recommendations = self._calculate_orders(
                demand_predictions, inventory_by_category, safety_stock_days, now
            )

            # 4. カテゴリ別集計
            category_summary = {}
            total_order_quantity = 0
            for rec in recommendations:
                cat = rec["category"]
                if cat not in category_summary:
                    category_summary[cat] = {
                        "order_quantity": 0,
                        "demand_ratio": rec["demand_ratio"],
                    }
                category_summary[cat]["order_quantity"] += rec["recommended_order_quantity"]
                total_order_quantity += rec["recommended_order_quantity"]

            result = {
                "current_time": now.isoformat(),
                "conditions": {
                    "weather": weather,
                    "temperature": temperature,
                    "humidity": humidity,
                    "safety_stock_days": safety_stock_days,
                },
                "demand_forecast": demand_predictions,
                "recommendations": recommendations,
                "category_summary": category_summary,
                "summary": {
                    "total_items": len(recommendations),
                    "items_to_order": sum(
                        1 for r in recommendations
                        if r["recommended_order_quantity"] > 0
                    ),
                    "total_order_quantity": total_order_quantity,
                },
            }

            if weather_warning:
                result["weather_warning"] = weather_warning

            yield self.create_json_message(result)

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _get_demand_predictions(
        self,
        weather: str,
        temperature: float,
        humidity: float,
        now: datetime,
    ) -> tuple[list[dict], str | None]:
        """demand_forecast のモデルを使って需要予測を取得する。

        Returns:
            (予測結果リスト, 天気警告メッセージまたはNone)
        """
        # NOTE: DemandForecastTool を遅延インポート。
        # モジュールレベルでインポートすると Dify の class_loader が
        # このファイル内で Tool サブクラスを2つ検出して起動に失敗する。
        from tools.demand_forecast import DemandForecastTool

        forecast_tool = object.__new__(DemandForecastTool)
        return forecast_tool._predict(
            weather=weather,
            temperature=temperature,
            humidity=humidity,
            day_of_week=now.weekday(),
            is_weekend=1 if now.weekday() >= 5 else 0,
            hour=now.hour,
        )

    def _get_inventory_by_category(self, now: datetime) -> dict[str, list[dict]]:
        """在庫データをカテゴリ別にグループ化して取得する。"""
        conn = _inv_db.get_connection()

        rows = conn.execute("""
            SELECT item_id, item_name, category, quantity,
                   min_stock_level, reorder_point, expires_at
            FROM inventory
            WHERE quantity >= 0
            ORDER BY category, item_name
        """).fetchall()

        by_category: dict[str, list[dict]] = {}
        for row in rows:
            item_id, item_name, cat, qty, min_level, reorder_pt, expires_at = row
            exp_dt = parse_expires_at(expires_at, now)
            remaining_hours = (exp_dt - now).total_seconds() / 3600

            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "item_id": item_id,
                "item_name": item_name,
                "category": cat,
                "quantity": qty,
                "min_stock_level": min_level,
                "reorder_point": reorder_pt,
                "remaining_hours": round(remaining_hours, 1),
            })

        return by_category

    @staticmethod
    def _calculate_orders(
        demand_predictions: list[dict],
        inventory_by_category: dict[str, list[dict]],
        safety_stock_days: float,
        now: datetime,
    ) -> list[dict]:
        """需要予測と在庫レベルを統合して発注推奨を計算する。

        Args:
            demand_predictions: カテゴリ別の需要予測結果
            inventory_by_category: カテゴリ別の在庫データ
            safety_stock_days: 安全在庫バッファ倍率
            now: 現在日時
        """
        # カテゴリ → demand_ratio マップを構築
        demand_ratio_map: dict[str, dict] = {}
        for pred in demand_predictions:
            category = pred["item"]
            base = pred["base_demand"]
            predicted = pred["predicted_demand"]
            ratio = predicted / base if base > 0 else 1.0
            demand_ratio_map[category] = {
                "ratio": ratio,
                "predicted_demand": predicted,
                "base_demand": base,
                "change_percent": pred["change_percent"],
            }

        recommendations = []

        for category, items in inventory_by_category.items():
            # カテゴリに対応する需要予測がなければ ratio=1.0
            demand_info = demand_ratio_map.get(category, {
                "ratio": 1.0,
                "predicted_demand": 0,
                "base_demand": 0,
                "change_percent": 0.0,
            })
            ratio = demand_info["ratio"]

            for item in items:
                # 需要調整後のターゲット在庫数
                adjusted_target = int(
                    item["reorder_point"] * ratio * safety_stock_days
                )

                # 基本発注数量
                base_order = max(0, adjusted_target - item["quantity"])

                # 消費期限による調整
                remaining_hours = item["remaining_hours"]
                if remaining_hours < 4:
                    order_quantity = 0
                    note = "期限切れ間近のため発注見送り"
                elif remaining_hours < 8:
                    order_quantity = max(0, base_order // 2)
                    note = "期限が近いため少量発注推奨"
                elif ratio > 1.2:
                    order_quantity = base_order
                    note = f"需要増加見込み（+{demand_info['change_percent']:.0f}%）"
                elif ratio < 0.8:
                    order_quantity = max(0, base_order // 2)
                    note = f"需要減少見込み（{demand_info['change_percent']:.0f}%）→ 控えめ発注"
                else:
                    order_quantity = base_order
                    note = "通常発注"

                recommendations.append({
                    "item_id": item["item_id"],
                    "item_name": item["item_name"],
                    "category": category,
                    "current_quantity": item["quantity"],
                    "reorder_point": item["reorder_point"],
                    "adjusted_target": adjusted_target,
                    "demand_ratio": round(ratio, 2),
                    "recommended_order_quantity": order_quantity,
                    "remaining_hours_until_expiry": remaining_hours,
                    "note": note,
                })

        # 発注数量の多い順にソート
        recommendations.sort(
            key=lambda x: (-x["recommended_order_quantity"], x["category"], x["item_name"])
        )

        return recommendations
