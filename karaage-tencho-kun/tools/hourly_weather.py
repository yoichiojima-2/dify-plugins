from collections.abc import Generator
from typing import Any
import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


# WMO Weather Code mapping
WEATHER_CODES = {
    0: {"ja": "快晴", "en": "Clear sky", "icon": "☀️"},
    1: {"ja": "晴れ", "en": "Mainly clear", "icon": "🌤️"},
    2: {"ja": "一部曇り", "en": "Partly cloudy", "icon": "⛅"},
    3: {"ja": "曇り", "en": "Overcast", "icon": "☁️"},
    45: {"ja": "霧", "en": "Fog", "icon": "🌫️"},
    48: {"ja": "着氷性の霧", "en": "Depositing rime fog", "icon": "🌫️"},
    51: {"ja": "霧雨（弱）", "en": "Light drizzle", "icon": "🌧️"},
    53: {"ja": "霧雨（中）", "en": "Moderate drizzle", "icon": "🌧️"},
    55: {"ja": "霧雨（強）", "en": "Dense drizzle", "icon": "🌧️"},
    61: {"ja": "雨（弱）", "en": "Slight rain", "icon": "🌧️"},
    63: {"ja": "雨（中）", "en": "Moderate rain", "icon": "🌧️"},
    65: {"ja": "雨（強）", "en": "Heavy rain", "icon": "🌧️"},
    66: {"ja": "着氷性の雨（弱）", "en": "Light freezing rain", "icon": "🌨️"},
    67: {"ja": "着氷性の雨（強）", "en": "Heavy freezing rain", "icon": "🌨️"},
    71: {"ja": "雪（弱）", "en": "Slight snow", "icon": "🌨️"},
    73: {"ja": "雪（中）", "en": "Moderate snow", "icon": "🌨️"},
    75: {"ja": "雪（強）", "en": "Heavy snow", "icon": "❄️"},
    77: {"ja": "霧雪", "en": "Snow grains", "icon": "🌨️"},
    80: {"ja": "にわか雨（弱）", "en": "Slight rain showers", "icon": "🌦️"},
    81: {"ja": "にわか雨（中）", "en": "Moderate rain showers", "icon": "🌦️"},
    82: {"ja": "にわか雨（強）", "en": "Violent rain showers", "icon": "⛈️"},
    85: {"ja": "にわか雪（弱）", "en": "Slight snow showers", "icon": "🌨️"},
    86: {"ja": "にわか雪（強）", "en": "Heavy snow showers", "icon": "🌨️"},
    95: {"ja": "雷雨", "en": "Thunderstorm", "icon": "⛈️"},
    96: {"ja": "雷雨（雹あり）", "en": "Thunderstorm with slight hail", "icon": "⛈️"},
    99: {"ja": "雷雨（激しい雹）", "en": "Thunderstorm with heavy hail", "icon": "⛈️"},
}


def get_weather_description(code: int) -> dict:
    """Get weather description from WMO code."""
    return WEATHER_CODES.get(code, {"ja": "不明", "en": "Unknown", "icon": "❓"})


def calculate_demand_impact(
    temp: float, precipitation: float, weather_code: int
) -> dict:
    """Calculate estimated impact on customer traffic and product demand."""
    # Base impact (1.0 = normal)
    traffic_impact = 1.0
    hot_food_demand = 1.0  # からあげクン, おでん etc.
    cold_drink_demand = 1.0
    umbrella_demand = 1.0

    # Temperature effects
    if temp < 5:
        traffic_impact *= 0.85
        hot_food_demand *= 1.3
        cold_drink_demand *= 0.6
    elif temp < 10:
        hot_food_demand *= 1.15
        cold_drink_demand *= 0.8
    elif temp > 25:
        traffic_impact *= 0.95
        hot_food_demand *= 0.7
        cold_drink_demand *= 1.4
    elif temp > 30:
        traffic_impact *= 0.85
        hot_food_demand *= 0.5
        cold_drink_demand *= 1.6

    # Precipitation effects
    if precipitation > 0:
        umbrella_demand *= 2.0
        if precipitation > 5:
            traffic_impact *= 0.7
            umbrella_demand *= 1.5
        elif precipitation > 1:
            traffic_impact *= 0.85

    # Weather code effects (rain/snow significantly reduces traffic)
    if weather_code in [65, 75, 82, 86, 95, 96, 99]:  # Heavy precipitation
        traffic_impact *= 0.6
    elif weather_code in [63, 73, 81, 85]:  # Moderate precipitation
        traffic_impact *= 0.75

    return {
        "traffic_impact": round(traffic_impact, 2),
        "hot_food_demand": round(hot_food_demand, 2),
        "cold_drink_demand": round(cold_drink_demand, 2),
        "umbrella_demand": round(umbrella_demand, 2),
    }


class HourlyWeatherTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        latitude = tool_parameters.get("latitude")
        longitude = tool_parameters.get("longitude")
        hours = min(int(tool_parameters.get("hours", 24)), 168)

        # Calculate forecast days needed
        forecast_days = (hours // 24) + 1

        # Call Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,precipitation,weathercode,relative_humidity_2m,wind_speed_10m",
            "timezone": "Asia/Tokyo",
            "forecast_days": forecast_days,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            yield self.create_json_message(
                {"error": f"Failed to fetch weather data: {str(e)}"}
            )
            return

        # Process hourly data
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])[:hours]
        temperatures = hourly.get("temperature_2m", [])[:hours]
        precipitations = hourly.get("precipitation", [])[:hours]
        weather_codes = hourly.get("weathercode", [])[:hours]
        humidities = hourly.get("relative_humidity_2m", [])[:hours]
        wind_speeds = hourly.get("wind_speed_10m", [])[:hours]

        # Build hourly forecast with demand impact
        hourly_forecast = []
        for i in range(len(times)):
            weather_info = get_weather_description(weather_codes[i])
            demand_impact = calculate_demand_impact(
                temperatures[i], precipitations[i], weather_codes[i]
            )

            hourly_forecast.append(
                {
                    "time": times[i],
                    "temperature_c": temperatures[i],
                    "precipitation_mm": precipitations[i],
                    "humidity_percent": humidities[i] if i < len(humidities) else None,
                    "wind_speed_kmh": wind_speeds[i] if i < len(wind_speeds) else None,
                    "weather_code": weather_codes[i],
                    "weather_ja": weather_info["ja"],
                    "weather_en": weather_info["en"],
                    "weather_icon": weather_info["icon"],
                    "demand_impact": demand_impact,
                }
            )

        # Calculate summary statistics
        avg_temp = sum(temperatures) / len(temperatures) if temperatures else 0
        total_precip = sum(precipitations) if precipitations else 0
        avg_traffic_impact = (
            sum(h["demand_impact"]["traffic_impact"] for h in hourly_forecast)
            / len(hourly_forecast)
            if hourly_forecast
            else 1.0
        )

        result = {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "summary": {
                "forecast_hours": len(hourly_forecast),
                "average_temperature_c": round(avg_temp, 1),
                "total_precipitation_mm": round(total_precip, 1),
                "average_traffic_impact": round(avg_traffic_impact, 2),
            },
            "hourly_forecast": hourly_forecast,
        }

        yield self.create_json_message(result)
