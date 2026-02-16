"""需要予測ツール（sklearn RandomForest）。

天気・気温・湿度・曜日・時間帯を入力として、
商品カテゴリ別の需要予測を行う。
学習済みモデルは models/demand_model.pkl から読み込む。
"""

import pickle
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

MODEL_PATH = Path(__file__).parent.parent / "models" / "demand_model.pkl"

# モデルをグローバルにキャッシュ
_model_cache = None


def _load_model():
    """学習済みモデルを読み込み、キャッシュして返す。"""
    global _model_cache
    if _model_cache is None:
        with open(MODEL_PATH, "rb") as f:
            _model_cache = pickle.load(f)
    return _model_cache


class DemandForecastTool(Tool):
    """天気ベースの商品需要予測ツール。RandomForestモデルで予測する。"""

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        weather = tool_parameters.get("weather", "sunny").lower()
        temperature = tool_parameters.get("temperature", 20)
        humidity = tool_parameters.get("humidity", 60)

        try:
            temperature = float(temperature)
            humidity = float(humidity)
        except (ValueError, TypeError):
            temperature = 20
            humidity = 60

        # 現在時刻から曜日・時間を取得
        now = datetime.now()
        day_of_week = now.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        hour = now.hour

        try:
            predictions, weather_warning = self._predict(
                weather=weather,
                temperature=temperature,
                humidity=humidity,
                day_of_week=day_of_week,
                is_weekend=is_weekend,
                hour=hour,
            )

            result = {
                "input": {
                    "weather": weather,
                    "temperature": temperature,
                    "humidity": humidity,
                    "day_of_week": day_of_week,
                    "hour": hour,
                },
                "predictions": predictions,
                "model_info": {
                    "type": "RandomForestRegressor",
                    "version": "1.0.0",
                },
            }

            if weather_warning:
                result["warning"] = weather_warning

            yield self.create_json_message(result)

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _predict(
        self,
        weather: str,
        temperature: float,
        humidity: float,
        day_of_week: int,
        is_weekend: int,
        hour: int,
    ) -> list[dict]:
        """モデルで需要を予測する。

        Args:
            weather: 天気（sunny/cloudy/rainy等）
            temperature: 気温（℃）
            humidity: 湿度（%）
            day_of_week: 曜日（0=月曜）
            is_weekend: 週末フラグ（0 or 1）
            hour: 時間（0-23）

        Returns:
            (予測結果リスト, 天気警告メッセージまたはNone)
        """
        model_data = _load_model()

        model = model_data["model"]
        weather_encoder = model_data["weather_encoder"]
        item_encoder = model_data["item_encoder"]
        items = model_data["items"]
        base_demand = model_data["base_demand"]

        # 天気をエンコード（未対応の天気はcloudyにフォールバック）
        weather_warning = None
        if weather not in weather_encoder.classes_:
            valid = ", ".join(weather_encoder.classes_)
            weather_warning = f"'{weather}' は未対応です（対応: {valid}）。cloudy として予測します"
            weather = "cloudy"
        weather_encoded = weather_encoder.transform([weather])[0]

        predictions = []

        for item in items:
            item_encoded = item_encoder.transform([item])[0]

            # 特徴量を準備
            X = [[
                weather_encoded,
                temperature,
                humidity,
                day_of_week,
                is_weekend,
                hour,
                item_encoded,
            ]]

            # 予測
            predicted = int(model.predict(X)[0])
            base = base_demand.get(item, 50)
            change_pct = round((predicted / base - 1) * 100, 1)

            predictions.append({
                "item": item,
                "predicted_demand": predicted,
                "base_demand": base,
                "change_percent": change_pct,
            })

        # 変化率の絶対値でソート（影響が大きい順）
        predictions.sort(key=lambda x: abs(x["change_percent"]), reverse=True)

        return predictions, weather_warning
