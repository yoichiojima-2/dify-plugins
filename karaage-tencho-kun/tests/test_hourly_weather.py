import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import hourly_weather as hw


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class TestHourlyWeather(unittest.TestCase):
    def test_get_weather_description_returns_fallback_for_unknown_code(self) -> None:
        result = hw.get_weather_description(999)

        self.assertEqual(result["ja"], "不明")
        self.assertEqual(result["en"], "Unknown")
        self.assertEqual(result["icon"], "❓")

    def test_calculate_demand_impact_heavy_rain_reduces_traffic(self) -> None:
        result = hw.calculate_demand_impact(temp=3, precipitation=6, weather_code=65)

        self.assertEqual(result["traffic_impact"], 0.36)
        self.assertEqual(result["hot_food_demand"], 1.3)
        self.assertEqual(result["cold_drink_demand"], 0.6)
        self.assertEqual(result["umbrella_demand"], 3.0)

    @patch("tools.hourly_weather.requests.get")
    def test_invoke_returns_forecast_summary_and_hourly_rows(self, mock_get) -> None:
        payload = {
            "hourly": {
                "time": ["2026-02-14T00:00", "2026-02-14T01:00", "2026-02-14T02:00"],
                "temperature_2m": [10.0, 11.0, 12.0],
                "precipitation": [0.0, 1.2, 6.0],
                "weathercode": [1, 63, 65],
                "relative_humidity_2m": [40, 41],
                "wind_speed_10m": [5.1],
            }
        }
        mock_get.return_value = _FakeResponse(payload)

        tool = object.__new__(hw.HourlyWeatherTool)
        tool.create_json_message = lambda body: body

        messages = list(
            tool._invoke({"latitude": 35.0, "longitude": 139.0, "hours": 200})
        )

        self.assertEqual(len(messages), 1)
        body = messages[0]
        self.assertEqual(body["location"]["latitude"], 35.0)
        self.assertEqual(body["location"]["longitude"], 139.0)

        summary = body["summary"]
        self.assertEqual(summary["forecast_hours"], 3)
        self.assertEqual(summary["average_temperature_c"], 11.0)
        self.assertEqual(summary["total_precipitation_mm"], 7.2)

        hourly = body["hourly_forecast"]
        self.assertEqual(len(hourly), 3)
        self.assertEqual(hourly[0]["humidity_percent"], 40)
        self.assertEqual(hourly[1]["humidity_percent"], 41)
        self.assertIsNone(hourly[2]["humidity_percent"])
        self.assertEqual(hourly[0]["wind_speed_kmh"], 5.1)
        self.assertIsNone(hourly[1]["wind_speed_kmh"])

        self.assertAlmostEqual(summary["average_traffic_impact"], 0.69)

        self.assertEqual(mock_get.call_count, 1)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["forecast_days"], 8)

    @patch("tools.hourly_weather.requests.get")
    def test_invoke_returns_error_on_request_exception(self, mock_get) -> None:
        mock_get.side_effect = requests.RequestException("timeout")

        tool = object.__new__(hw.HourlyWeatherTool)
        tool.create_json_message = lambda body: body

        messages = list(tool._invoke({"latitude": 35.0, "longitude": 139.0, "hours": 3}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])
        self.assertIn("Failed to fetch weather data", messages[0]["error"])


if __name__ == "__main__":
    unittest.main()
