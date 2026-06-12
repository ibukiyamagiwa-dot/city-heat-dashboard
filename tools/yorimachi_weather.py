# -*- coding: utf-8 -*-
"""Open-Meteo 天気取得（寄り町 / TOKYO CLIMB 共通）。"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen

TOKYO_LAT = 35.6812
TOKYO_LON = 139.7671

WMO_SUMMARY = {
    0: ("快晴", "☀️"),
    1: ("晴れ", "🌤️"),
    2: ("くもり", "⛅"),
    3: ("曇り", "☁️"),
    45: ("霧", "🌫️"),
    48: ("霧", "🌫️"),
    51: ("小雨", "🌦️"),
    53: ("雨", "🌧️"),
    55: ("雨", "🌧️"),
    61: ("雨", "🌧️"),
    63: ("雨", "🌧️"),
    65: ("大雨", "🌧️"),
    80: ("にわか雨", "🌦️"),
    81: ("にわか雨", "🌦️"),
    82: ("豪雨", "🌧️"),
}


def describe_wmo(code: int) -> tuple[str, str]:
    if code in WMO_SUMMARY:
        return WMO_SUMMARY[code]
    if code in (56, 57, 66, 67):
        return "雨", "🌧️"
    if code in (71, 73, 75, 77, 85, 86):
        return "雪", "🌨️"
    return "不明", "🌡️"


def fetch_weather_forecast(forecast_days: int = 7) -> dict:
    """今日を含む予報を返す。"""
    params = urlencode(
        {
            "latitude": TOKYO_LAT,
            "longitude": TOKYO_LON,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max"
            ),
            "forecast_days": forecast_days,
            "timezone": "Asia/Tokyo",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urlopen(url, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    daily = payload["daily"]
    out: dict = {}
    for i, day_str in enumerate(daily["time"]):
        code = int(daily["weather_code"][i])
        t_max = float(daily["temperature_2m_max"][i])
        t_min = float(daily["temperature_2m_min"][i])
        precip = float(daily["precipitation_sum"][i] or 0.0)
        prob = daily.get("precipitation_probability_max")
        precip_prob = float(prob[i] or 0.0) if prob else None
        summary, icon = describe_wmo(code)
        out[day_str] = {
            "summary": summary,
            "icon": icon,
            "weather_code": code,
            "temperature_max_c": round(t_max, 1),
            "temperature_min_c": round(t_min, 1),
            "temperature_c": round((t_max + t_min) / 2, 1),
            "precipitation_mm": round(precip, 1),
            "precipitation_probability_max": precip_prob,
            "is_rain": precip >= 1.0 or code in (51, 53, 55, 61, 63, 65, 80, 81, 82),
            "is_hot": t_max >= 28.0,
            "source": "Open-Meteo（東京駅周辺・予報）",
            "trust_level": "high",
        }
    return out


def weather_today() -> dict:
    days = fetch_weather_forecast(forecast_days=7)
    today = min(days.keys())
    return {"date": today, "today": days[today], "forecast": days}
