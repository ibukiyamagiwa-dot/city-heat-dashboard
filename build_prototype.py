from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = BASE_DIR / "prototype_data.json"
OUTPUT_HTML = BASE_DIR / "prototype_app.html"
DATA_SOURCES_FILE = BASE_DIR / "data_sources.yaml"
URBAN_CSV = BASE_DIR / "urban_indicators.csv"

# 試作対象都市（必要ならここへ都市を追加）
CITY_COORDS = {
    "TOKYO": (35.6762, 139.6503),
    "OSAKA": (34.6937, 135.5023),
    "NAGOYA": (35.1815, 136.9066),
    "FUKUOKA": (33.5904, 130.4017),
}

CITY_LABELS = {
    "TOKYO": "東京",
    "OSAKA": "大阪",
    "NAGOYA": "名古屋",
    "FUKUOKA": "福岡",
}

DATA_SOURCE_CATALOG = [
    {
        "id": "weather",
        "category": "気象",
        "name": "気温・降水量・風速",
        "provider": "Open-Meteo API",
        "reference_year": "取得時刻ベース（リアルタイム）",
        "trust_level": "high",
        "trust_label": "高",
        "trust_note": "APIから直接取得する実測値",
        "used_in_score": "今日のブースト（weather_boost）",
        "fixed_value": False,
    },
    {
        "id": "flow",
        "category": "人流",
        "name": "主要ターミナル駅 乗降客数（5駅合計）",
        "provider": "国土交通省 国土数値情報（駅別乗降客数）",
        "reference_year": "2023年度（令和5年度）",
        "trust_level": "medium",
        "trust_label": "中",
        "trust_note": "公的統計。都市間比較用に正規化して使用",
        "used_in_score": "都市の底力（city_power_score）",
        "fixed_value": False,
    },
    {
        "id": "venue",
        "category": "文化施設",
        "name": "劇場・音楽堂 施設数",
        "provider": "文部科学省 社会教育調査",
        "reference_year": "2021年度（令和3年度）",
        "trust_level": "medium",
        "trust_label": "中",
        "trust_note": "都道府県単位の施設数（開催数ではない）",
        "used_in_score": "都市の底力（city_power_score）",
        "fixed_value": False,
    },
    {
        "id": "base",
        "category": "設計",
        "name": "基準点",
        "provider": "本研究のスコア設計",
        "reference_year": "—",
        "trust_level": "medium",
        "trust_label": "中",
        "trust_note": "都市間比較の起点となる定数",
        "used_in_score": "底力の基準 45.0 点",
        "fixed_value": True,
    },
]

CITY_POWER_BASE = 45.0
FLOW_BONUS_RANGE = (0.0, 25.0)
VENUE_BONUS_RANGE = (0.0, 10.0)
ENTERTAINMENT_BONUS_RANGE = (0.0, 5.0)
WEATHER_BOOST_RANGE = (-20.0, 20.0)

ITERATION_STATE = {
    "version": "β再開発候補",
    "cycle": [
        {"name": "企画", "status": "done", "note": "都市熱狂度の可視化価値を定義"},
        {"name": "データ収集", "status": "done", "note": "Open-Meteo + CSV人流データを取得"},
        {"name": "監査", "status": "doing", "note": "CSV出典の正式化と数値検証を継続"},
        {"name": "α版開発", "status": "done", "note": "都市カードと詳細表を実装"},
        {"name": "フィードバック", "status": "done", "note": "スコア内訳・出典表示を改善"},
        {"name": "解決案", "status": "done", "note": "劇場・音楽堂データをスコアに接続済み"},
        {"name": "β版再開発", "status": "todo", "note": "地図/時系列の追加"},
    ],
    "todos": [
        {
            "id": "T-001",
            "title": "CSV人流データをスコア計算に接続する",
            "owner": "データ部門",
            "status": "達成",
            "next_action": "正式なオープンデータ出典へ差し替え",
        },
        {
            "id": "T-002",
            "title": "スコア根拠をユーザーに分かりやすく表示する",
            "owner": "開発部門",
            "status": "達成",
            "next_action": "地図表示で視覚的説明を追加",
        },
        {
            "id": "T-003",
            "title": "データ真偽監査の結果を画面上に表示する",
            "owner": "監査部門",
            "status": "達成",
            "next_action": "取得時刻の自動記録を強化",
        },
        {
            "id": "T-004",
            "title": "β版で地図表示を追加する",
            "owner": "開発部門",
            "status": "達成",
            "next_action": "時系列推移の追加を検討",
        },
        {
            "id": "T-005",
            "title": "event_venues（劇場・音楽堂）をスコア計算に接続する",
            "owner": "データ部門",
            "status": "達成",
            "next_action": "OpenStreetMap等での施設種別拡張を検討",
        },
    ],
    "feedback": [
        "スコア内訳と出典一覧により、非エンジニアにも説明しやすくなった。",
        "人流と劇場・音楽堂数の接続により、都市間差が公的データベースで説明できる。",
        "β版では地図・時系列推移を追加すると説得力がさらに上がる。",
    ],
}


def format_score_equation(record: dict) -> str:
    """2層スコアの計算式を人が読める形で返す。"""
    city_power = record.get("city_power_score", 0.0)
    weather_boost = record.get("weather_boost", 0.0)
    sign = "+" if weather_boost >= 0 else "-"
    return (
        f"都市の底力 {city_power:.1f} {sign} "
        f"今日のブースト {abs(weather_boost):.1f} = {record['heat_score']}"
    )


def format_score_narrative(record: dict) -> str:
    """都市スコアの平易な説明文を生成する。"""
    label = record.get("city_label", record["city"])
    pref = record.get("prefecture") or ""
    area = f"{label}（{pref}）" if pref else label
    c = record.get("components") or {}
    temp = record.get("temperature_c", "—")
    users = record.get("station_users")
    venues = record.get("event_venues")
    user_text = f"約{users:,}人/日" if users else "データなし"
    venue_text = f"{venues}施設" if venues else "データなし"
    return (
        f"{area}の熱狂度は {record['heat_score']} 点です。"
        f"都市の底力は {record.get('city_power_score', 0)} 点で、"
        f"主要駅利用者数（{user_text}）と劇場・音楽堂（{venue_text}）が主な根拠です。"
        f"今日のブーストは {record.get('weather_boost', 0)} 点で、"
        f"気温 {temp}℃、降水、風速の影響を反映しています。"
        f"スコアは「真実」ではなく、公開データに基づく推定指標です。"
    )


def rank_records(records: list[dict], key: str, reverse: bool = True) -> dict[str, int]:
    ordered = sorted(records, key=lambda r: (r.get(key) is not None, r.get(key) or 0), reverse=reverse)
    return {record["city"]: idx + 1 for idx, record in enumerate(ordered)}


def attach_rank_and_insights(records: list[dict]) -> None:
    """順位と強み/弱みを自動生成する。"""
    if not records:
        return

    total = len(records)
    ranks = {
        "heat_score": rank_records(records, "heat_score"),
        "city_power_score": rank_records(records, "city_power_score"),
        "weather_boost": rank_records(records, "weather_boost"),
        "station_users": rank_records(records, "station_users"),
        "event_venues": rank_records(records, "event_venues"),
    }

    for record in records:
        city = record["city"]
        record["rank"] = ranks["heat_score"][city]
        record["city_power_rank"] = ranks["city_power_score"][city]
        record["weather_rank"] = ranks["weather_boost"][city]
        record["flow_rank"] = ranks["station_users"][city]
        record["venue_rank"] = ranks["event_venues"][city]

        strengths: list[str] = []
        weaknesses: list[str] = []
        if record["flow_rank"] == 1:
            strengths.append("主要駅利用者数が4都市中1位")
        elif record["flow_rank"] == total:
            weaknesses.append("主要駅利用者数が4都市中最少")

        if record["venue_rank"] == 1:
            strengths.append("劇場・音楽堂数が4都市中1位")
        elif record["venue_rank"] == total:
            weaknesses.append("劇場・音楽堂数が4都市中最少")

        if record["weather_rank"] == 1:
            strengths.append("今日の気象条件が最も追い風")
        elif record["weather_rank"] == total:
            weaknesses.append("今日の気象条件が最も向かい風")

        if not strengths:
            if record["city_power_rank"] <= 2:
                strengths.append(f"都市の底力が4都市中{record['city_power_rank']}位")
            elif record["venue_rank"] < total:
                strengths.append(f"劇場・音楽堂数が4都市中{record['venue_rank']}位")
            else:
                strengths.append("気象条件改善時の伸びしろが大きい")
        if not weaknesses:
            if record["weather_rank"] > 1:
                weaknesses.append(f"今日の気象条件が4都市中{record['weather_rank']}位")
            elif record["city_power_rank"] > 1:
                weaknesses.append(f"都市の底力が4都市中{record['city_power_rank']}位")
            else:
                weaknesses.append("目立った弱みは少ないが、気象次第で変動")

        record["strength_text"] = "強み: " + "、".join(strengths)
        record["weakness_text"] = "弱み: " + "、".join(weaknesses)


def attach_display_metadata(records: list[dict]) -> None:
    attach_rank_and_insights(records)
    for record in records:
        record["city_label"] = CITY_LABELS.get(record["city"], record["city"])
        record["score_equation"] = format_score_equation(record)
        record["score_narrative"] = format_score_narrative(record)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def normalize_to_range(
    value: float, min_v: float, max_v: float, out_min: float, out_max: float
) -> float:
    if max_v <= min_v:
        return (out_min + out_max) / 2
    ratio = (value - min_v) / (max_v - min_v)
    return out_min + ratio * (out_max - out_min)


def parse_csv_int(value: str | None, default: int = 0) -> int:
    text = (value or "").strip()
    if not text:
        return default
    return int(text)


def load_urban_indicators() -> dict[str, dict]:
    """都市指標CSVを読み込む。"""
    if not URBAN_CSV.exists():
        return {}

    rows: dict[str, dict] = {}
    with URBAN_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row["city"].strip().upper()
            entertainment_raw = (row.get("entertainment_facilities") or "").strip()
            rows[city] = {
                "prefecture": row.get("prefecture", "").strip(),
                "station_users": parse_csv_int(row.get("station_users")),
                "entertainment_facilities": parse_csv_int(row.get("entertainment_facilities")),
                "entertainment_pending": not entertainment_raw,
                "event_venues": parse_csv_int(row.get("event_venues")),
                "source": row.get("source", "").strip(),
                "notes": row.get("notes", "").strip(),
            }
    return rows


def compute_urban_bonuses(indicators: dict[str, dict]) -> dict[str, dict]:
    """駅利用者数・劇場音楽堂数・（任意）エンタメ施設数から都市別補正値を算出する。"""
    if not indicators:
        return {}

    users = [v["station_users"] for v in indicators.values()]
    venues = [v["event_venues"] for v in indicators.values()]
    ents = [v["entertainment_facilities"] for v in indicators.values()]
    min_u, max_u = min(users), max(users)
    min_v, max_v = min(venues), max(venues)
    has_entertainment = any(v > 0 for v in ents)
    min_e, max_e = (min(ents), max(ents)) if has_entertainment else (0, 0)

    result: dict[str, dict] = {}
    for city, data in indicators.items():
        flow_bonus = normalize_to_range(
            data["station_users"],
            min_u,
            max_u,
            FLOW_BONUS_RANGE[0],
            FLOW_BONUS_RANGE[1],
        )
        venue_bonus = normalize_to_range(
            data["event_venues"],
            min_v,
            max_v,
            VENUE_BONUS_RANGE[0],
            VENUE_BONUS_RANGE[1],
        )
        if has_entertainment and data["entertainment_facilities"] > 0:
            entertainment_bonus = normalize_to_range(
                data["entertainment_facilities"],
                min_e,
                max_e,
                ENTERTAINMENT_BONUS_RANGE[0],
                ENTERTAINMENT_BONUS_RANGE[1],
            )
        else:
            entertainment_bonus = 0.0
        city_power_score = clamp(
            CITY_POWER_BASE + flow_bonus + venue_bonus + entertainment_bonus,
            0.0,
            100.0,
        )
        result[city] = {
            **data,
            "flow_bonus": round(flow_bonus, 1),
            "venue_bonus": round(venue_bonus, 1),
            "entertainment_bonus": round(entertainment_bonus, 1),
            "city_power_score": round(city_power_score, 1),
        }
    return result


def fetch_city_weather(
    city: str, lat: float, lon: float, urban: dict | None = None
) -> dict:
    """Open-Meteo から都市の最新気象データを取得する。"""
    params = urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": "Asia/Tokyo",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urlopen(url, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    current = payload.get("current", {})
    temp = float(current.get("temperature_2m", 20.0))
    precip = float(current.get("precipitation", 0.0))
    wind = float(current.get("wind_speed_10m", 3.0))

    # 2層スコア:
    # - 都市の底力は人流・劇場数など固定データで決める
    # - 今日のブーストは気象で上下させる
    temp_score = clamp((temp - 10.0) * 1.2, 0.0, 18.0)
    precip_penalty = clamp(precip * 5.0, 0.0, 18.0)
    wind_penalty = clamp(wind * 1.1, 0.0, 18.0)

    if urban:
        flow_bonus = urban["flow_bonus"]
        venue_bonus = urban["venue_bonus"]
        entertainment_bonus = urban["entertainment_bonus"]
        city_power_score = urban["city_power_score"]
        station_users = urban["station_users"]
        event_venues = urban["event_venues"]
        urban_source = urban["source"]
        audit_status = "CSV接続済み: 人流(国交省) + 劇場・音楽堂(文科省社会教育調査)"
        if urban.get("entertainment_pending"):
            audit_status += " / 遊園地等は未接続（将来拡張）"
        trust_level = "high"
        source = f"Open-Meteo (weather) + {URBAN_CSV.name} (urban indicators)"
        source_mode = "mixed"
    else:
        flow_bonus = 0.0
        venue_bonus = 0.0
        entertainment_bonus = 0.0
        city_power_score = CITY_POWER_BASE
        station_users = None
        event_venues = None
        urban_source = "未接続"
        audit_status = "要注意: 人流CSVに該当都市なし"
        trust_level = "medium"
        source = "Open-Meteo (weather) only"
        source_mode = "weather_only"

    weather_boost = clamp(
        temp_score - precip_penalty - wind_penalty,
        WEATHER_BOOST_RANGE[0],
        WEATHER_BOOST_RANGE[1],
    )
    heat_score = clamp(city_power_score + weather_boost, 0, 100)

    components = {
        "city_power_base": {
            "value": CITY_POWER_BASE,
            "trust_level": "medium",
            "label": "底力の基準点",
            "layer": "都市の底力",
        },
        "temp_score": {
            "value": round(temp_score, 1),
            "trust_level": "high",
            "label": "気温補正（実データ）",
            "layer": "今日のブースト",
        },
        "flow_bonus": {
            "value": flow_bonus,
            "trust_level": "medium",
            "label": "人流補正（国交省CSV）",
            "layer": "都市の底力",
        },
        "venue_bonus": {
            "value": venue_bonus,
            "trust_level": "medium",
            "label": "劇場・音楽堂補正（文科省調査）",
            "layer": "都市の底力",
        },
        "precip_penalty": {
            "value": round(-precip_penalty, 1),
            "trust_level": "high",
            "label": "降水ペナルティ（実データ）",
            "layer": "今日のブースト",
        },
        "wind_penalty": {
            "value": round(-wind_penalty, 1),
            "trust_level": "high",
            "label": "風速ペナルティ（実データ）",
            "layer": "今日のブースト",
        },
    }
    if entertainment_bonus > 0:
        components["entertainment_bonus"] = {
            "value": entertainment_bonus,
            "trust_level": "medium",
            "label": "エンタメ施設補正（CSV参照値）",
            "layer": "都市の底力",
        }

    return {
        "city": city,
        "city_label": CITY_LABELS.get(city, city),
        "prefecture": urban.get("prefecture") if urban else None,
        "lat": lat,
        "lon": lon,
        "temperature_c": round(temp, 1),
        "precipitation_mm": round(precip, 1),
        "wind_speed_mps": round(wind, 1),
        "station_users": station_users,
        "event_venues": event_venues,
        "city_power_score": round(city_power_score, 1),
        "weather_boost": round(weather_boost, 1),
        "flow_bonus": flow_bonus,
        "venue_bonus": venue_bonus,
        "entertainment_bonus": entertainment_bonus,
        "heat_score": round(heat_score, 1),
        "urban_source": urban_source,
        "source": source,
        "source_mode": source_mode,
        "trust_level": trust_level,
        "audit_status": audit_status,
        "components": components,
    }


def fallback_city_data(urban_bonuses: dict[str, dict] | None = None) -> list[dict]:
    """API取得失敗時のフォールバックデータ。"""
    samples = [
        ("TOKYO", 35.6762, 139.6503, 25.2, 0.0, 3.9),
        ("OSAKA", 34.6937, 135.5023, 24.0, 0.4, 4.5),
        ("NAGOYA", 35.1815, 136.9066, 23.3, 0.0, 2.7),
        ("FUKUOKA", 33.5904, 130.4017, 22.7, 1.0, 5.0),
    ]
    records: list[dict] = []
    urban_bonuses = urban_bonuses or {}

    for city, lat, lon, temp, precip, wind in samples:
        urban = urban_bonuses.get(city)
        temp_score = clamp((temp - 10.0) * 1.2, 0.0, 18.0)
        precip_penalty = clamp(precip * 5.0, 0.0, 18.0)
        wind_penalty = clamp(wind * 1.1, 0.0, 18.0)
        flow_bonus = urban["flow_bonus"] if urban else 0.0
        venue_bonus = urban["venue_bonus"] if urban else 0.0
        entertainment_bonus = urban["entertainment_bonus"] if urban else 0.0
        city_power_score = (
            urban["city_power_score"] if urban else CITY_POWER_BASE
        )
        weather_boost = clamp(
            temp_score - precip_penalty - wind_penalty,
            WEATHER_BOOST_RANGE[0],
            WEATHER_BOOST_RANGE[1],
        )
        heat_score = clamp(city_power_score + weather_boost, 0, 100)
        records.append(
            {
                "city": city,
                "city_label": CITY_LABELS.get(city, city),
                "prefecture": urban.get("prefecture") if urban else None,
                "lat": lat,
                "lon": lon,
                "temperature_c": temp,
                "precipitation_mm": precip,
                "wind_speed_mps": wind,
                "station_users": urban["station_users"] if urban else None,
                "event_venues": urban["event_venues"] if urban else None,
                "city_power_score": round(city_power_score, 1),
                "weather_boost": round(weather_boost, 1),
                "flow_bonus": flow_bonus,
                "venue_bonus": venue_bonus,
                "entertainment_bonus": entertainment_bonus,
                "heat_score": round(heat_score, 1),
                "urban_source": urban["source"] if urban else "未接続",
                "source": "fallback sample",
                "source_mode": "fallback",
                "trust_level": "low",
                "audit_status": "要注意: API取得失敗時のサンプル値",
                "components": {},
            }
        )
    return records


def build_dataset() -> dict:
    urban_bonuses = compute_urban_bonuses(load_urban_indicators())
    records: list[dict] = []
    had_error = False

    for city, (lat, lon) in CITY_COORDS.items():
        try:
            records.append(
                fetch_city_weather(city, lat, lon, urban_bonuses.get(city))
            )
        except (TimeoutError, URLError, ValueError):
            had_error = True
            break

    if had_error or len(records) != len(CITY_COORDS):
        records = fallback_city_data(urban_bonuses)

    attach_display_metadata(records)

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "records": records,
        "note": "prototype dataset for alpha demo",
        "iteration": ITERATION_STATE,
        "data_sources": DATA_SOURCE_CATALOG,
        "score_policy": {
            "formula": "heat_score = city_power_score + weather_boost",
            "city_power_formula": "city_power_score = 45.0 + flow_bonus + venue_bonus",
            "weather_formula": "weather_boost = temp_score - precip_penalty - wind_penalty",
            "summary": "熱狂度は、都市の底力（人流・文化施設）と今日のブースト（気象）を分けて評価する2層スコアです。",
            "warning": "固定の仮説値は使用していません。施設数は開催数ではなく、都道府県統計に基づく参考指標です。",
            "data_sources_file": DATA_SOURCES_FILE.name,
            "urban_csv": URBAN_CSV.name,
        },
    }


def build_html(dataset: dict) -> str:
    template = (BASE_DIR / "prototype_template.html").read_text(encoding="utf-8")
    data_json = json.dumps(dataset, ensure_ascii=False)
    return template.replace("__DATA_JSON__", data_json)


def main() -> None:
    dataset = build_dataset()
    OUTPUT_JSON.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUTPUT_HTML.write_text(build_html(dataset), encoding="utf-8")
    print(f"作成完了: {OUTPUT_JSON}")
    print(f"作成完了: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
