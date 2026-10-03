from typing import Any

from myharness.tools.base import BaseTool
import requests
from utils.logger_tool import logger


class WeatherTool(BaseTool):

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "根据传入的城市名查询该城市的天气状况"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名",
                }
            },
            "required": ["city"]
        }

    def run(self, **kwargs: str) -> str:

        city = kwargs.get("city", "")

        if not city:
            msg = "错误: 未提供城市名"
            logger.error(msg)
            return msg

        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh"},
            timeout=20,
        )

        if geo_resp.status_code != 200:
            return f"城市查询请求失败，HTTP状态码：{geo_resp.status_code}"

        geo_data = geo_resp.json()

        if "results" not in geo_data or not geo_data["results"]:
            return f"未找到城市：{city}"

        result = geo_data["results"][0]
        lat = result["latitude"]
        lon = result["longitude"]
        city_name = result["name"]

        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
            },
            timeout=20,
        )

        if weather_resp.status_code != 200:
            return f"天气查询请求失败，HTTP状态码：{weather_resp.status_code}"

        weather_data = weather_resp.json()
        current = weather_data["current"]

        wmo_codes = {
            0: "晴", 1: "大部晴朗", 2: "多云", 3: "阴天",
            45: "雾", 48: "雾凇", 51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
            61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨(小)", 67: "冻雨(大)",
            71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
            80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
            85: "小阵雪", 86: "大阵雪",
            95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
        }

        weather_text = wmo_codes.get(current["weather_code"], f"未知({current['weather_code']})")

        return (
            f"城市：{city_name}，天气：{weather_text}，"
            f"温度：{current['temperature_2m']}℃，体感温度：{current['apparent_temperature']}℃，"
            f"风速：{current['wind_speed_10m']}km/h，风向：{current['wind_direction_10m']}°，"
            f"相对湿度：{current['relative_humidity_2m']}%"
        )