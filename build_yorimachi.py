# -*- coding: utf-8 -*-
"""寄り町（YORIMACHI）ブラウザ用データを生成する。"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GRAPH_PATH = BASE_DIR / "rail_graph.json"
TOWNS_PATH = BASE_DIR / "data" / "towns.json"
INDEX_PATH = BASE_DIR / "stations_index.json"
TRENDS_CACHE_PATH = BASE_DIR / "td_trends_cache.json"
YORIMACHI_TRENDS_CACHE_PATH = BASE_DIR / "yorimachi_trends_cache.json"
OUT_PATH = BASE_DIR / "yorimachi_data.js"

TRENDS_TD_HIGH = 8.0
TRENDS_TD_MID = 3.0
TRENDS_TD_LOW = -3.0


def load_trends_cache() -> dict:
    if not TRENDS_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(TRENDS_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload.get("stations") or {}


def load_yorimachi_trends_cache() -> dict:
    if not YORIMACHI_TRENDS_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(YORIMACHI_TRENDS_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload.get("towns") or {}


def load_yorimachi_trends_meta() -> dict:
    if not YORIMACHI_TRENDS_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(YORIMACHI_TRENDS_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "updated_at": payload.get("updated_at"),
        "fetch_status": payload.get("fetch_status"),
        "phase": payload.get("phase"),
    }


def latest_trends_date(stations: dict) -> str | None:
    dates: set[str] = set()
    for days in stations.values():
        dates.update(days.keys())
    return max(dates) if dates else None


def classify_td(td: float | None) -> str:
    if td is None:
        return "unknown"
    if td > TRENDS_TD_HIGH:
        return "hot"
    if td > TRENDS_TD_MID:
        return "up"
    if td < TRENDS_TD_LOW:
        return "calm"
    return "neutral"


def enrich_town_trends(
    town: dict,
    stations: dict,
    towns_trends: dict,
    day_str: str,
    prev_str: str,
) -> dict:
    out = dict(town)
    tid = town.get("id")
    proxy_key = town.get("trends_key")

    days = None
    source = "none"
    lookup_key = None

    if tid and tid in towns_trends:
        days = towns_trends[tid]
        source = "google_trends_town"
        lookup_key = tid
    elif proxy_key and proxy_key in stations:
        days = stations[proxy_key]
        source = "google_trends_proxy"
        lookup_key = proxy_key

    if not days:
        out["trends"] = {
            "date": day_str,
            "interest": None,
            "td": None,
            "mood": "unknown",
            "source": "none",
        }
        return out

    cur = days.get(day_str)
    prev = days.get(prev_str)
    if cur is None or prev is None:
        td = None
        mood = "unknown"
    else:
        td = round((cur - prev) / max(prev, 1) * 100.0, 1)
        mood = classify_td(td)

    trends_payload: dict = {
        "date": day_str,
        "interest": cur,
        "td": td,
        "mood": mood,
        "source": source,
    }
    if source == "google_trends_proxy":
        trends_payload["proxy_key"] = lookup_key
    elif source == "google_trends_town":
        trends_payload["town_id"] = lookup_key
        trends_payload["query"] = town.get("trends_query")

    out["trends"] = trends_payload
    return out


def make_station_town(station: dict) -> dict:
    name = station["name"]
    sid = station["id"].replace("g_", "")
    return {
        "id": f"st_{sid}",
        "name": name,
        "tagline": f"{name}駅周辺を散歩",
        "flavors": ["街歩き"],
        "hub_node_id": station["id"],
        "lat": station["lat"],
        "lon": station["lon"],
        "in_graph": True,
        "tier": "station",
        "trends_key": None,
        "trends_query": name,
        "today_hints": {
            "default": f"{name}周辺をぶらつく",
            "high_td": "話題の店を1軒チェック",
            "low_td": "静かな路地を散歩",
        },
    }


def merge_station_towns(curated: list[dict], index: list[dict]) -> list[dict]:
    """手選り町の hub でカバーされていない駅を tier=station として追加。"""
    hubs = {
        t["hub_node_id"]
        for t in curated
        if t.get("in_graph") and t.get("hub_node_id") and t.get("tier") != "station"
    }
    extra: list[dict] = []
    for st in index:
        if st["id"] in hubs:
            continue
        extra.append(make_station_town(st))
    return curated + extra


def main() -> None:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    towns = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    trends_stations = load_trends_cache()
    trends_towns = load_yorimachi_trends_cache()
    yorimachi_trends_meta = load_yorimachi_trends_meta()

    day_candidates = set()
    for days in trends_stations.values():
        day_candidates.update(days.keys())
    for days in trends_towns.values():
        day_candidates.update(days.keys())
    day_str = max(day_candidates) if day_candidates else date.today().isoformat()
    prev_str = (date.fromisoformat(day_str) - timedelta(days=1)).isoformat()

    curated = towns["towns"]
    merged = merge_station_towns(curated, index)
    enriched_towns = [
        enrich_town_trends(t, trends_stations, trends_towns, day_str, prev_str)
        for t in merged
    ]
    curated_n = sum(1 for t in enriched_towns if t.get("tier") != "station")
    station_n = len(enriched_towns) - curated_n

    graph_edges = [
        {
            "from": e["from"],
            "to": e["to"],
            "minutes": e["minutes"],
            "line": e.get("line"),
        }
        for e in graph["edges"]
    ]

    with_trends = sum(1 for t in enriched_towns if t.get("trends", {}).get("td") is not None)
    town_source_td = sum(
        1 for t in enriched_towns if t.get("trends", {}).get("source") == "google_trends_town"
    )
    proxy_source_td = sum(
        1 for t in enriched_towns if t.get("trends", {}).get("source") == "google_trends_proxy"
    )

    payload = {
        "generated_at": date.today().isoformat(),
        "app": {
            "name": "寄り町",
            "name_en": "YORIMACHI",
            "tagline": "空いた時間に、寄れる町を。",
        },
        "graph_meta": {
            "version": graph.get("version"),
            "source": graph.get("source"),
            "stats": graph.get("stats"),
        },
        "routing": graph.get("routing") or {},
        "trends_meta": {
            "source": "Google Trends（Phase2 町名 + Phase1 駅代理）",
            "trust_level": "low",
            "date": day_str,
            "thresholds": {
                "hot": TRENDS_TD_HIGH,
                "up": TRENDS_TD_MID,
                "calm": TRENDS_TD_LOW,
            },
            "phase2_cache": yorimachi_trends_meta,
            "town_queries": len(trends_towns),
            "station_proxies": len(trends_stations),
            "note": (
                "Phase2: trends_query の町名検索（yorimachi_trends_cache.json）。"
                "未取得時は trends_key の駅代理（td_trends_cache.json）。"
                "絶対値は町間で比較しない。"
            ),
        },
        "graph_edges": graph_edges,
        "departure_shortcuts": towns["departure_shortcuts"],
        "stations": index,
        "towns_meta": {
            "curated": curated_n,
            "station": station_n,
            "total": len(enriched_towns),
        },
        "towns": enriched_towns,
    }

    js = "// 寄り町データ（build_yorimachi.py が自動生成。手編集しない）\n"
    js += "window.YORIMACHI_DATA = "
    js += json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js += ";\n"
    OUT_PATH.write_text(js, encoding="utf-8")
    print(
        f"Wrote {OUT_PATH} - stations={len(index)} towns={len(enriched_towns)} "
        f"(curated={curated_n} station={station_n}) trends_td={with_trends} "
        f"(town={town_source_td} proxy={proxy_source_td}) date={day_str}"
    )


if __name__ == "__main__":
    main()
