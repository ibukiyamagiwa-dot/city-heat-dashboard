from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = BASE_DIR / "prototype_data.json"
OUTPUT_HTML = BASE_DIR / "prototype_app.html"
DATA_SOURCES_FILE = BASE_DIR / "data_sources.yaml"
URBAN_CSV = BASE_DIR / "urban_indicators.csv"
OSM_CACHE = BASE_DIR / "modern_entertainment_cache.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_SEARCH_RADIUS_M = 15000

OSM_ENTERTAINMENT_CATEGORIES = [
    {
        "id": "cinema",
        "label": "映画館",
        "selector": '["amenity"="cinema"]',
        "tag": "amenity=cinema",
    },
    {
        "id": "museum",
        "label": "博物館・美術館",
        "selector": '["tourism"="museum"]',
        "tag": "tourism=museum",
    },
    {
        "id": "stadium",
        "label": "スタジアム",
        "selector": '["leisure"="stadium"]',
        "tag": "leisure=stadium",
    },
    {
        "id": "theme_park",
        "label": "テーマパーク",
        "selector": '["tourism"="theme_park"]',
        "tag": "tourism=theme_park",
    },
    {
        "id": "arts_centre",
        "label": "アートセンター",
        "selector": '["amenity"="arts_centre"]',
        "tag": "amenity=arts_centre",
    },
    {
        "id": "nightclub",
        "label": "クラブ",
        "selector": '["amenity"="nightclub"]',
        "tag": "amenity=nightclub",
    },
    {
        "id": "theatre",
        "label": "劇場",
        "selector": '["amenity"="theatre"]',
        "tag": "amenity=theatre",
    },
    {
        "id": "sports_centre",
        "label": "スポーツセンター",
        "selector": '["leisure"="sports_centre"]',
        "tag": "leisure=sports_centre",
    },
]

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

CITY_STATIONS = {
    "TOKYO": [
        {"name": "新宿駅", "station_users": 1205116},
        {"name": "渋谷駅", "station_users": 936944},
        {"name": "池袋駅", "station_users": 917582},
        {"name": "東京駅", "station_users": 693316},
        {"name": "品川駅", "station_users": 497300},
    ],
    "OSAKA": [
        {"name": "大阪駅", "station_users": 694156},
        {"name": "大阪梅田駅", "station_users": 402947},
        {"name": "梅田駅", "station_users": 376997},
        {"name": "難波駅", "station_users": 298803},
        {"name": "天王寺駅", "station_users": 255496},
    ],
    "NAGOYA": [
        {"name": "名古屋駅（JR）", "station_users": 354486},
        {"name": "名古屋駅（市営）", "station_users": 334170},
        {"name": "名鉄名古屋駅", "station_users": 255163},
        {"name": "栄駅", "station_users": 183400},
        {"name": "金山駅", "station_users": 153073},
    ],
    "FUKUOKA": [
        {"name": "博多駅（JR）", "station_users": 216766},
        {"name": "博多駅（市営）", "station_users": 136165},
        {"name": "天神駅", "station_users": 118279},
        {"name": "西鉄福岡駅", "station_users": 109641},
        {"name": "姪浜駅", "station_users": 83991},
    ],
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
        "used_in_score": "規模パワー（scale_power）",
        "fixed_value": False,
    },
    {
        "id": "culture_venue",
        "category": "文化施設",
        "name": "劇場・音楽堂 施設数",
        "provider": "文部科学省 社会教育調査",
        "reference_year": "2021年度（令和3年度）",
        "trust_level": "medium",
        "trust_label": "中",
        "trust_note": "都道府県単位の施設数（開催数ではない）",
        "used_in_score": "文化施設スコア（culture_venue_bonus）",
        "fixed_value": False,
    },
    {
        "id": "modern_entertainment",
        "category": "現代エンタメ",
        "name": "映画館・博物館・スタジアム等",
        "provider": "OpenStreetMap / Overpass API",
        "reference_year": "取得時点ベース",
        "trust_level": "low",
        "trust_label": "低",
        "trust_note": "OSM登録状況に依存するため、カテゴリ別内訳つきの補助指標として扱う",
        "used_in_score": "現代エンタメ補正（modern_entertainment_bonus）",
        "fixed_value": False,
    },
    {
        "id": "station_focus",
        "category": "駅別プロトタイプ",
        "name": "注目駅の乗降客数・周辺エンタメ推定",
        "provider": "国土数値情報 + OSM都市合計の駅利用者比按分",
        "reference_year": "2023年度 + OSM取得時点",
        "trust_level": "low",
        "trust_label": "低",
        "trust_note": "駅別ビューの枠を確認するためのプロトタイプ推定",
        "used_in_score": "駅別熱狂度プロトタイプ（都市スコア本体には未使用）",
        "fixed_value": False,
    },
    {
        "id": "population",
        "category": "人口",
        "name": "都道府県人口",
        "provider": "総務省 人口推計",
        "reference_year": "2023年10月1日現在",
        "trust_level": "medium",
        "trust_label": "中",
        "trust_note": "人口あたり施設充実度の分母として使用",
        "used_in_score": "充実度スコア（accessibility_power）",
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
        "used_in_score": "規模パワーの基準 35.0 点",
        "fixed_value": True,
    },
]

SCALE_BASE = 35.0
FLOW_BONUS_RANGE = (0.0, 18.0)
CULTURE_VENUE_BONUS_RANGE = (0.0, 7.0)
MODERN_ENTERTAINMENT_BONUS_RANGE = (0.0, 8.0)
ACCESSIBILITY_BONUS_RANGE = (0.0, 22.0)
WEATHER_BOOST_RANGE = (-20.0, 20.0)

ITERATION_STATE = {
    "version": "β再開発候補",
    "cycle": [
        {"name": "企画", "status": "done", "note": "都市熱狂度の可視化価値を定義"},
        {"name": "データ収集", "status": "done", "note": "Open-Meteo + CSV + OSM施設数を取得"},
        {"name": "監査", "status": "doing", "note": "人口補正とOSM補助指標の妥当性を検証"},
        {"name": "α版開発", "status": "done", "note": "都市カードと詳細表を実装"},
        {"name": "フィードバック", "status": "done", "note": "スコア内訳・出典表示を改善"},
        {"name": "解決案", "status": "done", "note": "絶対量と人口/人流あたり充実度を分離"},
        {"name": "β版再開発", "status": "todo", "note": "OSMタグ精査と時系列の追加"},
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
            "title": "劇場・音楽堂を文化施設スコアとして再定義する",
            "owner": "データ部門",
            "status": "達成",
            "next_action": "文化施設以外の現代エンタメ指標と分離して説明",
        },
        {
            "id": "T-006",
            "title": "人口・人流あたり施設充実度を追加する",
            "owner": "分析部門",
            "status": "達成",
            "next_action": "都道府県単位から市区町村単位への改善を検討",
        },
        {
            "id": "T-007",
            "title": "OSMで現代エンタメ施設数を自動取得する",
            "owner": "開発部門",
            "status": "検証中",
            "next_action": "タグの重複・網羅性を監査",
        },
    ],
    "feedback": [
        "スコア内訳と出典一覧により、非エンジニアにも説明しやすくなった。",
        "人流と劇場・音楽堂数の接続により、都市間差が公的データベースで説明できる。",
        "人口・人流あたり補正により、大都市偏重の疑問に答えやすくなった。",
    ],
}


def format_score_equation(record: dict) -> str:
    """拡張スコアの計算式を人が読める形で返す。"""
    scale_power = record.get("scale_power", 0.0)
    accessibility_power = record.get("accessibility_power", 0.0)
    weather_boost = record.get("weather_boost", 0.0)
    sign = "+" if weather_boost >= 0 else "-"
    return (
        f"規模パワー {scale_power:.1f} + 充実度 {accessibility_power:.1f} {sign} "
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
    population = record.get("population")
    modern = record.get("modern_entertainment_facilities")
    user_text = f"約{users:,}人/日" if users else "データなし"
    venue_text = f"{venues}施設" if venues else "データなし"
    population_text = f"約{population:,}人" if population else "データなし"
    modern_text = f"{modern}施設" if modern is not None else "データなし"
    modern_breakdown = sorted(
        record.get("modern_entertainment_breakdown") or [],
        key=lambda item: item.get("count", 0),
        reverse=True,
    )
    top_modern = [item for item in modern_breakdown if item.get("count", 0) > 0][:2]
    modern_detail = (
        "（"
        + "、".join(f"{item['label']} {item['count']}件" for item in top_modern)
        + "が中心）"
        if top_modern
        else ""
    )
    return (
        f"{area}の熱狂度は {record['heat_score']} 点です。"
        f"規模パワーは {record.get('scale_power', 0)} 点で、"
        f"主要駅利用者数（{user_text}）、文化施設（{venue_text}）、"
        f"現代エンタメ施設（{modern_text}）{modern_detail}が主な根拠です。"
        f"充実度は {record.get('accessibility_power', 0)} 点で、"
        f"人口（{population_text}）や人流あたりの施設数を反映しています。"
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
        "scale_power": rank_records(records, "scale_power"),
        "accessibility_power": rank_records(records, "accessibility_power"),
        "weather_boost": rank_records(records, "weather_boost"),
        "station_users": rank_records(records, "station_users"),
        "event_venues": rank_records(records, "event_venues"),
        "modern_entertainment_facilities": rank_records(
            records, "modern_entertainment_facilities"
        ),
        "culture_venues_per_100k": rank_records(records, "culture_venues_per_100k"),
        "modern_entertainment_per_100k": rank_records(
            records, "modern_entertainment_per_100k"
        ),
        "culture_venues_per_million_station_users": rank_records(
            records, "culture_venues_per_million_station_users"
        ),
    }

    for record in records:
        city = record["city"]
        record["rank"] = ranks["heat_score"][city]
        record["city_power_rank"] = ranks["city_power_score"][city]
        record["weather_rank"] = ranks["weather_boost"][city]
        record["scale_rank"] = ranks["scale_power"][city]
        record["accessibility_rank"] = ranks["accessibility_power"][city]
        record["flow_rank"] = ranks["station_users"][city]
        record["culture_venue_rank"] = ranks["event_venues"][city]
        record["venue_rank"] = record["culture_venue_rank"]
        record["modern_entertainment_rank"] = ranks["modern_entertainment_facilities"][city]
        record["culture_per_population_rank"] = ranks["culture_venues_per_100k"][city]
        record["modern_per_population_rank"] = ranks["modern_entertainment_per_100k"][city]
        record["culture_per_flow_rank"] = ranks[
            "culture_venues_per_million_station_users"
        ][city]

        strengths: list[str] = []
        weaknesses: list[str] = []
        if record["flow_rank"] == 1:
            strengths.append("主要駅利用者数が4都市中1位")
        elif record["flow_rank"] == total:
            weaknesses.append("主要駅利用者数が4都市中最少")

        if record["culture_venue_rank"] == 1:
            strengths.append("文化施設数が4都市中1位")
        elif record["culture_venue_rank"] == total:
            weaknesses.append("文化施設数が4都市中最少")

        if record["modern_entertainment_rank"] == 1:
            strengths.append("現代エンタメ施設数が4都市中1位")
        elif record["modern_entertainment_rank"] == total:
            weaknesses.append("現代エンタメ施設数が4都市中最少")

        if record["culture_per_population_rank"] == 1:
            strengths.append("人口あたり文化施設数が4都市中1位")
        elif record["culture_per_population_rank"] == total:
            weaknesses.append("人口あたり文化施設数が4都市中最少")

        if record["modern_per_population_rank"] == 1:
            strengths.append("人口あたり現代エンタメ施設数が4都市中1位")
        elif record["modern_per_population_rank"] == total:
            weaknesses.append("人口あたり現代エンタメ施設数が4都市中最少")

        if record["weather_rank"] == 1:
            strengths.append("今日の気象条件が最も追い風")
        elif record["weather_rank"] == total:
            weaknesses.append("今日の気象条件が最も向かい風")

        if not strengths:
            if record["accessibility_rank"] <= 2:
                strengths.append(f"人口/人流あたり充実度が4都市中{record['accessibility_rank']}位")
            elif record["scale_rank"] <= 2:
                strengths.append(f"絶対量の規模パワーが4都市中{record['scale_rank']}位")
            else:
                strengths.append("気象条件改善時の伸びしろが大きい")
        if not weaknesses:
            if record["weather_rank"] > 1:
                weaknesses.append(f"今日の気象条件が4都市中{record['weather_rank']}位")
            elif record["accessibility_rank"] > 1:
                weaknesses.append(f"人口/人流あたり充実度が4都市中{record['accessibility_rank']}位")
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


def per_capita(value: float, population: float, multiplier: float) -> float:
    if population <= 0:
        return 0.0
    return value / population * multiplier


def parse_csv_int(value: str | None, default: int = 0) -> int:
    text = (value or "").strip()
    if not text:
        return default
    return int(text)


def load_osm_cache() -> dict[str, dict]:
    if not OSM_CACHE.exists():
        return {}
    try:
        return json.loads(OSM_CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_osm_cache(cache: dict[str, dict]) -> None:
    OSM_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def build_overpass_breakdown_query(
    lat: float, lon: float, radius_m: int = OSM_SEARCH_RADIUS_M
) -> str:
    """現代エンタメ施設をカテゴリ別に数えるOverpass QL。"""
    lines = ["[out:json][timeout:45];"]
    for category in OSM_ENTERTAINMENT_CATEGORIES:
        selector = category["selector"]
        lines.extend(
            [
                "(",
                f"  node(around:{radius_m},{lat},{lon}){selector};",
                f"  way(around:{radius_m},{lat},{lon}){selector};",
                f"  relation(around:{radius_m},{lat},{lon}){selector};",
                f")->.{category['id']};",
                f".{category['id']} out count;",
            ]
        )
    return "\n".join(lines)


def normalize_modern_entertainment_breakdown(raw_breakdown: list[dict] | None) -> list[dict]:
    by_id = {
        str(item.get("id")): int(item.get("count", 0))
        for item in (raw_breakdown or [])
        if isinstance(item, dict)
    }
    return [
        {
            "id": category["id"],
            "label": category["label"],
            "tag": category["tag"],
            "count": by_id.get(category["id"], 0),
            "trust_level": "low",
            "source": "OpenStreetMap Overpass API",
        }
        for category in OSM_ENTERTAINMENT_CATEGORIES
    ]


def station_profile_label(flow_rank: int, density_rank: int) -> str:
    if flow_rank == 1 and density_rank > 2:
        return "人流型"
    if density_rank <= 2 and flow_rank > 2:
        return "カルチャー型"
    if flow_rank <= 2 and density_rank <= 2:
        return "総合熱狂型"
    return "バランス型"


def build_station_focus(city: str, urban: dict, weather_boost: float) -> list[dict]:
    """都市内ドリルダウン用の駅別プロトタイプ指標を作る。"""
    stations = CITY_STATIONS.get(city, [])
    if not stations:
        return []

    station_users = [station["station_users"] for station in stations]
    total_users = sum(station_users) or urban.get("station_users", 0) or 1
    city_entertainment = urban.get("modern_entertainment_facilities", 0) or 0

    station_rows: list[dict] = []
    for station in stations:
        users = station["station_users"]
        user_share = users / total_users
        # 駅別OSM取得は次フェーズ。現時点は都市OSM合計を駅利用者比で按分した透明な試算。
        station_entertainment = round(city_entertainment * user_share)
        entertainment_density = per_capita(station_entertainment, users, 1_000_000)
        station_rows.append(
            {
                "name": station["name"],
                "station_users": users,
                "station_user_share": round(user_share, 3),
                "station_osm_entertainment_facilities": station_entertainment,
                "entertainment_density_per_million_users": round(
                    entertainment_density, 2
                ),
                "source_mode": "city_osm_share_prototype",
                "trust_level": "low",
            }
        )

    user_ranks = rank_records(
        [{"city": row["name"], "station_users": row["station_users"]} for row in station_rows],
        "station_users",
    )
    density_ranks = rank_records(
        [
            {
                "city": row["name"],
                "density": row["entertainment_density_per_million_users"],
            }
            for row in station_rows
        ],
        "density",
    )
    min_users, max_users = min(station_users), max(station_users)
    densities = [row["entertainment_density_per_million_users"] for row in station_rows]
    min_density, max_density = min(densities), max(densities)

    for row in station_rows:
        flow_bonus = normalize_to_range(row["station_users"], min_users, max_users, 0.0, 36.0)
        density_bonus = normalize_to_range(
            row["entertainment_density_per_million_users"],
            min_density,
            max_density,
            0.0,
            24.0,
        )
        station_weather = clamp(weather_boost * 0.3, -6.0, 6.0)
        station_heat = clamp(35.0 + flow_bonus + density_bonus + station_weather, 0.0, 100.0)
        flow_rank = user_ranks[row["name"]]
        density_rank = density_ranks[row["name"]]
        row["flow_rank"] = flow_rank
        row["density_rank"] = density_rank
        row["station_heat_score"] = round(station_heat, 1)
        row["profile_type"] = station_profile_label(flow_rank, density_rank)
        row["score_note"] = (
            "駅別熱狂度は都市スコア本体とは別枠の試算です。"
            "乗降客数と都市OSM現代エンタメ合計の按分値から算出しています。"
        )

    return sorted(station_rows, key=lambda row: row["station_heat_score"], reverse=True)


def fetch_modern_entertainment_count(city: str, lat: float, lon: float, cache: dict[str, dict]) -> dict:
    """Overpass APIで現代エンタメ施設数とカテゴリ内訳を取得する。"""
    cached = cache.get(city)
    query = build_overpass_breakdown_query(lat, lon)
    body = urlencode({"data": query}).encode("utf-8")
    req = Request(
        OVERPASS_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "city-heat-dashboard-prototype/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        elements = payload.get("elements") or []
        breakdown: list[dict] = []
        for category, element in zip(OSM_ENTERTAINMENT_CATEGORIES, elements):
            tags = element.get("tags", {}) if isinstance(element, dict) else {}
            breakdown.append(
                {
                    "id": category["id"],
                    "label": category["label"],
                    "tag": category["tag"],
                    "count": int(tags.get("total", 0)),
                    "trust_level": "low",
                    "source": "OpenStreetMap Overpass API",
                }
            )
        breakdown = normalize_modern_entertainment_breakdown(breakdown)
        count = sum(item["count"] for item in breakdown)
        result = {
            "count": count,
            "breakdown": breakdown,
            "source": "OpenStreetMap Overpass API",
            "source_mode": "live",
            "trust_level": "low",
            "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "radius_m": OSM_SEARCH_RADIUS_M,
        }
        cache[city] = result
        return result
    except Exception:
        if cached:
            breakdown = normalize_modern_entertainment_breakdown(cached.get("breakdown"))
            count = sum(item["count"] for item in breakdown) or int(cached.get("count", 0))
            return {**cached, "count": count, "breakdown": breakdown, "source_mode": "cache"}
        return {
            "count": 0,
            "breakdown": normalize_modern_entertainment_breakdown(None),
            "source": "OpenStreetMap Overpass API",
            "source_mode": "unavailable",
            "trust_level": "low",
            "fetched_at": None,
            "radius_m": OSM_SEARCH_RADIUS_M,
        }


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
                "population": parse_csv_int(row.get("population")),
                "station_users": parse_csv_int(row.get("station_users")),
                "entertainment_facilities": parse_csv_int(row.get("entertainment_facilities")),
                "entertainment_pending": not entertainment_raw,
                "event_venues": parse_csv_int(row.get("event_venues")),
                "source": row.get("source", "").strip(),
                "notes": row.get("notes", "").strip(),
            }
    return rows


def compute_urban_bonuses(indicators: dict[str, dict]) -> dict[str, dict]:
    """絶対量と人口/人流あたり充実度から都市別補正値を算出する。"""
    if not indicators:
        return {}

    users = [v["station_users"] for v in indicators.values()]
    culture_venues = [v["event_venues"] for v in indicators.values()]
    modern_facilities = [v["modern_entertainment_facilities"] for v in indicators.values()]
    min_u, max_u = min(users), max(users)
    min_c, max_c = min(culture_venues), max(culture_venues)
    min_m, max_m = min(modern_facilities), max(modern_facilities)

    for data in indicators.values():
        population = data["population"]
        station_users = data["station_users"]
        culture_count = data["event_venues"]
        modern_count = data["modern_entertainment_facilities"]
        data["culture_venues_per_100k"] = per_capita(culture_count, population, 100_000)
        data["modern_entertainment_per_100k"] = per_capita(modern_count, population, 100_000)
        data["culture_venues_per_million_station_users"] = per_capita(
            culture_count, station_users, 1_000_000
        )

    culture_per_pop = [v["culture_venues_per_100k"] for v in indicators.values()]
    modern_per_pop = [v["modern_entertainment_per_100k"] for v in indicators.values()]
    culture_per_flow = [
        v["culture_venues_per_million_station_users"] for v in indicators.values()
    ]
    min_cpp, max_cpp = min(culture_per_pop), max(culture_per_pop)
    min_mpp, max_mpp = min(modern_per_pop), max(modern_per_pop)
    min_cpf, max_cpf = min(culture_per_flow), max(culture_per_flow)

    result: dict[str, dict] = {}
    for city, data in indicators.items():
        flow_bonus = normalize_to_range(
            data["station_users"],
            min_u,
            max_u,
            FLOW_BONUS_RANGE[0],
            FLOW_BONUS_RANGE[1],
        )
        culture_venue_bonus = normalize_to_range(
            data["event_venues"],
            min_c,
            max_c,
            CULTURE_VENUE_BONUS_RANGE[0],
            CULTURE_VENUE_BONUS_RANGE[1],
        )
        modern_entertainment_bonus = normalize_to_range(
            data["modern_entertainment_facilities"],
            min_m,
            max_m,
            MODERN_ENTERTAINMENT_BONUS_RANGE[0],
            MODERN_ENTERTAINMENT_BONUS_RANGE[1],
        )
        culture_per_population_bonus = normalize_to_range(
            data["culture_venues_per_100k"], min_cpp, max_cpp, 0.0, 8.0
        )
        modern_per_population_bonus = normalize_to_range(
            data["modern_entertainment_per_100k"], min_mpp, max_mpp, 0.0, 8.0
        )
        culture_per_flow_bonus = normalize_to_range(
            data["culture_venues_per_million_station_users"], min_cpf, max_cpf, 0.0, 6.0
        )
        scale_power = clamp(
            SCALE_BASE + flow_bonus + culture_venue_bonus + modern_entertainment_bonus,
            0.0,
            100.0,
        )
        accessibility_power = clamp(
            culture_per_population_bonus
            + modern_per_population_bonus
            + culture_per_flow_bonus,
            ACCESSIBILITY_BONUS_RANGE[0],
            ACCESSIBILITY_BONUS_RANGE[1],
        )
        city_power_score = clamp(scale_power + accessibility_power, 0.0, 100.0)
        result[city] = {
            **data,
            "flow_bonus": round(flow_bonus, 1),
            "culture_venue_bonus": round(culture_venue_bonus, 1),
            "modern_entertainment_bonus": round(modern_entertainment_bonus, 1),
            "culture_per_population_bonus": round(culture_per_population_bonus, 1),
            "modern_per_population_bonus": round(modern_per_population_bonus, 1),
            "culture_per_flow_bonus": round(culture_per_flow_bonus, 1),
            "scale_power": round(scale_power, 1),
            "accessibility_power": round(accessibility_power, 1),
            "city_power_score": round(city_power_score, 1),
            "culture_venues_per_100k": round(data["culture_venues_per_100k"], 3),
            "modern_entertainment_per_100k": round(
                data["modern_entertainment_per_100k"], 3
            ),
            "culture_venues_per_million_station_users": round(
                data["culture_venues_per_million_station_users"], 2
            ),
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
        culture_venue_bonus = urban["culture_venue_bonus"]
        modern_entertainment_bonus = urban["modern_entertainment_bonus"]
        scale_power = urban["scale_power"]
        accessibility_power = urban["accessibility_power"]
        city_power_score = urban["city_power_score"]
        population = urban["population"]
        station_users = urban["station_users"]
        event_venues = urban["event_venues"]
        modern_entertainment_facilities = urban["modern_entertainment_facilities"]
        urban_source = urban["source"]
        audit_status = (
            "CSV接続済み: 人流(国交省) + 文化施設(文科省) + 人口(総務省)"
            f" / 現代エンタメ(OSM:{urban['modern_entertainment_source_mode']})"
        )
        trust_level = "high"
        source = f"Open-Meteo (weather) + {URBAN_CSV.name} (urban indicators)"
        source_mode = "mixed"
    else:
        flow_bonus = 0.0
        culture_venue_bonus = 0.0
        modern_entertainment_bonus = 0.0
        scale_power = SCALE_BASE
        accessibility_power = 0.0
        city_power_score = SCALE_BASE
        population = None
        station_users = None
        event_venues = None
        modern_entertainment_facilities = None
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
        "scale_base": {
            "value": SCALE_BASE,
            "trust_level": "medium",
            "label": "規模パワーの基準点",
            "layer": "規模パワー",
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
            "layer": "規模パワー",
        },
        "culture_venue_bonus": {
            "value": culture_venue_bonus,
            "trust_level": "medium",
            "label": "文化施設補正（劇場・音楽堂）",
            "layer": "規模パワー",
        },
        "modern_entertainment_bonus": {
            "value": modern_entertainment_bonus,
            "trust_level": "low",
            "label": "現代エンタメ補正（OSM）",
            "layer": "規模パワー",
        },
        "accessibility_power": {
            "value": accessibility_power,
            "trust_level": "medium",
            "label": "人口/人流あたり充実度",
            "layer": "充実度",
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
    return {
        "city": city,
        "city_label": CITY_LABELS.get(city, city),
        "prefecture": urban.get("prefecture") if urban else None,
        "lat": lat,
        "lon": lon,
        "temperature_c": round(temp, 1),
        "precipitation_mm": round(precip, 1),
        "wind_speed_mps": round(wind, 1),
        "population": population,
        "station_users": station_users,
        "event_venues": event_venues,
        "modern_entertainment_facilities": modern_entertainment_facilities,
        "modern_entertainment_breakdown": (
            urban.get("modern_entertainment_breakdown") if urban else []
        ),
        "modern_entertainment_categories": OSM_ENTERTAINMENT_CATEGORIES,
        "modern_entertainment_source_mode": (
            urban.get("modern_entertainment_source_mode") if urban else None
        ),
        "modern_entertainment_radius_m": (
            urban.get("modern_entertainment_radius_m") if urban else None
        ),
        "station_focus": build_station_focus(city, urban, weather_boost) if urban else [],
        "culture_venues_per_100k": urban.get("culture_venues_per_100k") if urban else None,
        "modern_entertainment_per_100k": (
            urban.get("modern_entertainment_per_100k") if urban else None
        ),
        "culture_venues_per_million_station_users": (
            urban.get("culture_venues_per_million_station_users") if urban else None
        ),
        "scale_power": round(scale_power, 1),
        "accessibility_power": round(accessibility_power, 1),
        "city_power_score": round(city_power_score, 1),
        "weather_boost": round(weather_boost, 1),
        "flow_bonus": flow_bonus,
        "culture_venue_bonus": culture_venue_bonus,
        "modern_entertainment_bonus": modern_entertainment_bonus,
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
        culture_venue_bonus = urban["culture_venue_bonus"] if urban else 0.0
        modern_entertainment_bonus = (
            urban["modern_entertainment_bonus"] if urban else 0.0
        )
        scale_power = urban["scale_power"] if urban else SCALE_BASE
        accessibility_power = urban["accessibility_power"] if urban else 0.0
        city_power_score = urban["city_power_score"] if urban else SCALE_BASE
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
                "population": urban["population"] if urban else None,
                "station_users": urban["station_users"] if urban else None,
                "event_venues": urban["event_venues"] if urban else None,
                "modern_entertainment_facilities": (
                    urban["modern_entertainment_facilities"] if urban else None
                ),
                "modern_entertainment_breakdown": (
                    urban["modern_entertainment_breakdown"] if urban else []
                ),
                "modern_entertainment_categories": OSM_ENTERTAINMENT_CATEGORIES,
                "modern_entertainment_source_mode": (
                    urban["modern_entertainment_source_mode"] if urban else None
                ),
                "modern_entertainment_radius_m": (
                    urban["modern_entertainment_radius_m"] if urban else None
                ),
                "station_focus": (
                    build_station_focus(city, urban, weather_boost) if urban else []
                ),
                "culture_venues_per_100k": (
                    urban["culture_venues_per_100k"] if urban else None
                ),
                "modern_entertainment_per_100k": (
                    urban["modern_entertainment_per_100k"] if urban else None
                ),
                "culture_venues_per_million_station_users": (
                    urban["culture_venues_per_million_station_users"] if urban else None
                ),
                "scale_power": round(scale_power, 1),
                "accessibility_power": round(accessibility_power, 1),
                "city_power_score": round(city_power_score, 1),
                "weather_boost": round(weather_boost, 1),
                "flow_bonus": flow_bonus,
                "culture_venue_bonus": culture_venue_bonus,
                "modern_entertainment_bonus": modern_entertainment_bonus,
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
    urban_indicators = load_urban_indicators()
    osm_cache = load_osm_cache()
    cache_changed = False
    for city, (lat, lon) in CITY_COORDS.items():
        if city not in urban_indicators:
            continue
        before = dict(osm_cache)
        osm_result = fetch_modern_entertainment_count(city, lat, lon, osm_cache)
        urban_indicators[city]["modern_entertainment_facilities"] = osm_result["count"]
        urban_indicators[city]["modern_entertainment_breakdown"] = osm_result[
            "breakdown"
        ]
        urban_indicators[city]["modern_entertainment_source"] = osm_result["source"]
        urban_indicators[city]["modern_entertainment_source_mode"] = osm_result[
            "source_mode"
        ]
        urban_indicators[city]["modern_entertainment_radius_m"] = osm_result["radius_m"]
        cache_changed = cache_changed or before != osm_cache
    if cache_changed:
        save_osm_cache(osm_cache)

    urban_bonuses = compute_urban_bonuses(urban_indicators)
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
            "formula": "heat_score = scale_power + accessibility_power + weather_boost",
            "city_power_formula": "city_power_score = scale_power + accessibility_power",
            "scale_formula": "scale_power = 35.0 + flow_bonus + culture_venue_bonus + modern_entertainment_bonus",
            "accessibility_formula": "accessibility_power = culture_per_population_bonus + modern_per_population_bonus + culture_per_flow_bonus",
            "weather_formula": "weather_boost = temp_score - precip_penalty - wind_penalty",
            "summary": "熱狂度は、絶対量の規模パワー、人口/人流あたりの充実度、今日のブーストを分けて評価するモデル検証版です。",
            "warning": "固定の仮説値は使用していません。公的統計とOSM補助指標は信頼度を分けて表示し、施設数は開催数ではない点に注意してください。",
            "station_view_note": "駅別ビューは都市スコア式を変更しないプロトタイプ枠です。駅周辺OSM数は現時点では都市OSM合計を駅利用者比で按分した試算として表示します。",
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
