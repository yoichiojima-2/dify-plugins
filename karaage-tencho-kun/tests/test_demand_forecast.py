import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import demand_forecast as df


class _FakeNow:
    def __init__(self, weekday_value: int, hour_value: int) -> None:
        self._weekday_value = weekday_value
        self.hour = hour_value

    def weekday(self) -> int:
        return self._weekday_value


class _FakeDateTime:
    @staticmethod
    def now() -> _FakeNow:
        return _FakeNow(6, 14)


class _FakeEncoder:
    def __init__(self, classes: list[str]) -> None:
        self.classes_ = classes

    def transform(self, values: list[str]) -> list[int]:
        lookup = {value: idx for idx, value in enumerate(self.classes_)}
        return [lookup[value] for value in values]


class _FakeModel:
    def predict(self, features):
        temperature = features[0][1]
        humidity = features[0][2]
        item_encoded = features[0][6]
        return [50 + int(temperature) + int(humidity / 10) + item_encoded]


class TestDemandForecast(unittest.TestCase):
    def setUp(self) -> None:
        df._model_cache = None

    @patch("tools.demand_forecast.pickle.load")
    @patch("tools.demand_forecast.open", create=True)
    def test_load_model_uses_cache(self, mock_open, mock_pickle_load) -> None:
        mock_open.return_value = io.BytesIO(b"model")
        mock_pickle_load.return_value = {"model": "x"}

        first = df._load_model()
        second = df._load_model()

        self.assertEqual(first, second)
        self.assertEqual(mock_pickle_load.call_count, 1)
        self.assertEqual(mock_open.call_count, 1)

    @patch("tools.demand_forecast._load_model")
    def test_predict_sorts_by_absolute_change_percent(self, mock_load_model) -> None:
        model_data = {
            "model": _FakeModel(),
            "weather_encoder": _FakeEncoder(["sunny", "cloudy", "rainy"]),
            "item_encoder": _FakeEncoder(["item_a", "item_b"]),
            "items": ["item_a", "item_b"],
            "base_demand": {"item_a": 40, "item_b": 80},
        }
        mock_load_model.return_value = model_data

        tool = object.__new__(df.DemandForecastTool)
        rows, warning = tool._predict(
            weather="storm",  # unknown weather should fallback to cloudy
            temperature=30,
            humidity=60,
            day_of_week=2,
            is_weekend=0,
            hour=12,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["item"], "item_a")
        self.assertEqual(rows[0]["predicted_demand"], 86)
        self.assertEqual(rows[0]["change_percent"], 115.0)
        self.assertEqual(rows[1]["item"], "item_b")
        self.assertIn("storm", warning)

    @patch("tools.demand_forecast.datetime", _FakeDateTime)
    def test_invoke_defaults_invalid_numeric_inputs(self) -> None:
        tool = object.__new__(df.DemandForecastTool)
        tool.create_json_message = lambda body: body
        tool._predict = MagicMock(return_value=([{"item": "x", "predicted_demand": 10}], None))

        messages = list(tool._invoke({"weather": "rainy", "temperature": "bad", "humidity": None}))

        self.assertEqual(len(messages), 1)
        body = messages[0]
        self.assertEqual(body["input"]["temperature"], 20)
        self.assertEqual(body["input"]["humidity"], 60)
        self.assertEqual(body["input"]["day_of_week"], 6)
        self.assertEqual(body["input"]["hour"], 14)
        self.assertEqual(body["predictions"][0]["item"], "x")

        kwargs = tool._predict.call_args.kwargs
        self.assertEqual(kwargs["is_weekend"], 1)
        self.assertEqual(kwargs["temperature"], 20)
        self.assertEqual(kwargs["humidity"], 60)

    def test_invoke_returns_error_when_prediction_fails(self) -> None:
        tool = object.__new__(df.DemandForecastTool)
        tool.create_json_message = lambda body: body
        tool._predict = MagicMock(side_effect=RuntimeError("model missing"))

        messages = list(tool._invoke({"weather": "sunny", "temperature": 22, "humidity": 55}))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], {"error": "model missing"})


if __name__ == "__main__":
    unittest.main()
