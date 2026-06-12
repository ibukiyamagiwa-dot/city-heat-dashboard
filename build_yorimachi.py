# -*- coding: utf-8 -*-
"""寄り町（YORIMACHI）ブラウザ用データを生成する。"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "tools"))
from yorimachi_weather import weather_today as fetch_weather_today  # noqa: E402
GRAPH_PATH = BASE_DIR / "rail_graph.json"
TOWNS_PATH = BASE_DIR / "data" / "towns.json"
INDEX_PATH = BASE_DIR / "stations_index.json"
TRENDS_CACHE_PATH = BASE_DIR / "td_trends_cache.json"
YORIMACHI_TRENDS_CACHE_PATH = BASE_DIR / "yorimachi_trends_cache.json"
OSM_CACHE_PATH = BASE_DIR / "town_osm_cache.json"
EVENTS_CACHE_PATH = BASE_DIR / "events_cache.json"
FLOW_PATH = BASE_DIR / "data" / "station_flow.yaml"
OUT_PATH = BASE_DIR / "yorimachi_data.js"
EVENT_MATCH_RADIUS_M = 2500

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


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_osm_cache() -> dict:
    if not OSM_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(OSM_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload.get("towns") or {}


def event_on_date(ev: dict, day: date) -> bool:
    es = ev.get("start")
    ee = ev.get("end") or es
    if not es:
        return False
    try:
        d_start = date.fromisoformat(es)
        d_end = date.fromisoformat(ee) if ee else d_start
    except ValueError:
        return False
    return d_start <= day <= d_end


def filter_events_for_day(events: list[dict], day: date) -> list[dict]:
    return [e for e in events if event_on_date(e, day)]


def load_events_cache() -> tuple[list[dict], str, dict]:
    if not EVENTS_CACHE_PATH.exists():
        return [], "none", {}
    try:
        payload = json.loads(EVENTS_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return [], "none", {}
    window = payload.get("events") or []
    with_coords = [
        e for e in window if e.get("lat") is not None and e.get("lon") is not None
    ]
    if with_coords:
        return with_coords, "window", payload
    if window:
        return window, "window_no_coords", payload
    geo = [
        e
        for e in (payload.get("events_all") or [])
        if e.get("lat") is not None and e.get("lon") is not None
    ]
    if geo:
        return geo, "geo_fallback_stale", payload
    return [], "none", payload


def load_station_flow() -> dict[str, int]:
    if not FLOW_PATH.exists():
        return {}
    try:
        payload = yaml.safe_load(FLOW_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload.get("by_slug") or {}


def tier_from_rank(rank: int, total: int) -> str:
    if total <= 1:
        return "mid"
    pct = rank / (total - 1)
    if pct >= 0.67:
        return "high"
    if pct >= 0.34:
        return "mid"
    return "low"


def build_flow_lookup(index: list[dict], by_slug: dict[str, int]) -> dict[str, dict]:
    """hub_node_id → flow_score tier + daily_passengers."""
    node_slug = {st["id"]: st.get("slug") for st in index}
    node_flow: dict[str, int] = {}
    for node_id, slug in node_slug.items():
        if slug and slug in by_slug:
            node_flow[node_id] = by_slug[slug]
    ordered = sorted(node_flow.items(), key=lambda x: x[1])
    tiers = {node: tier_from_rank(i, len(ordered)) for i, (node, _) in enumerate(ordered)}
    out: dict[str, dict] = {}
    for node_id, passengers in node_flow.items():
        out[node_id] = {
            "daily_passengers": passengers,
            "flow_score": tiers.get(node_id, "mid"),
            "station_slug": node_slug.get(node_id),
            "source": "国土数値情報 駅別乗降客数（station_flow.yaml）",
            "trust_level": "medium",
        }
    return out


def match_events_near_town(town: dict, events: list[dict]) -> list[dict]:
    lat, lon = town.get("lat"), town.get("lon")
    if lat is None or lon is None:
        return []
    matched: list[dict] = []
    for ev in events:
        elat, elon = ev.get("lat"), ev.get("lon")
        if elat is None or elon is None:
            continue
        dist = haversine_m(lat, lon, elat, elon)
        if dist > EVENT_MATCH_RADIUS_M:
            continue
        row = dict(ev)
        row["distance_m"] = round(dist)
        matched.append(row)
    matched.sort(key=lambda e: e["distance_m"])
    return matched[:5]


def enrich_town_phase3(
    town: dict,
    osm_towns: dict,
    flow_by_node: dict[str, dict],
    events: list[dict],
) -> dict:
    out = dict(town)
    tid = town.get("id")
    hub = town.get("hub_node_id")

    if tid and tid in osm_towns:
        osm = osm_towns[tid]
        scores = osm.get("scores") or {}
        out["research_tags"] = osm.get("research_tags") or []
        out["comfort"] = {
            "rain": scores.get("rain_comfort", "mid"),
            "heat": scores.get("heat_comfort", "mid"),
            "source": osm.get("source"),
            "trust_level": osm.get("trust_level", "low"),
        }
        out["rain_score"] = scores.get("rain_comfort", "mid")
        out["heat_score"] = scores.get("heat_comfort", "mid")
    elif town.get("tier") == "station":
        out.setdefault("comfort", {"rain": "mid", "heat": "mid", "trust_level": "low"})
        out.setdefault("rain_score", "mid")
        out.setdefault("heat_score", "mid")

    if hub and hub in flow_by_node:
        out["flow"] = flow_by_node[hub]
        out["flow_score"] = flow_by_node[hub]["flow_score"]

    if town.get("tier") != "station" or tid in osm_towns:
        near = match_events_near_town(town, events)
        if near:
            out["events_near"] = near
            out["event_pick"] = near[0]

    return out


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
    osm_towns = load_osm_cache()
    events_list, events_match_mode, events_cache_raw = load_events_cache()
    flow_by_slug = load_station_flow()
    flow_by_node = build_flow_lookup(index, flow_by_slug)

    try:
        weather_bundle = fetch_weather_today()
    except Exception as exc:
        print(f"WARN: weather fetch failed: {exc}")
        weather_bundle = {"date": date.today().isoformat(), "today": None, "forecast": {}}

    event_day_str = weather_bundle.get("date") or date.today().isoformat()
    try:
        event_day = date.fromisoformat(event_day_str)
    except ValueError:
        event_day = date.today()
    events_list = filter_events_for_day(events_list, event_day)
    events_match_mode = "today_only"

    day_candidates = set()
    for days in trends_stations.values():
        day_candidates.update(days.keys())
    for days in trends_towns.values():
        day_candidates.update(days.keys())
    day_str = max(day_candidates) if day_candidates else date.today().isoformat()
    prev_str = (date.fromisoformat(day_str) - timedelta(days=1)).isoformat()

    curated = towns["towns"]
    merged = merge_station_towns(curated, index)
    enriched_towns = []
    for t in merged:
        row = enrich_town_trends(t, trends_stations, trends_towns, day_str, prev_str)
        row = enrich_town_phase3(row, osm_towns, flow_by_node, events_list)
        enriched_towns.append(row)
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
    with_osm = sum(1 for t in enriched_towns if t.get("research_tags"))
    with_flow = sum(1 for t in enriched_towns if t.get("flow_score"))
    with_events = sum(1 for t in enriched_towns if t.get("events_near"))

    events_meta = {}
    if events_cache_raw:
        events_meta = {
            "updated_at": events_cache_raw.get("updated_at"),
            "display_mode": "today_only",
            "display_date": event_day.isoformat(),
            "window_start": events_cache_raw.get("window_start"),
            "window_end": events_cache_raw.get("window_end"),
            "count": len(events_list),
            "today_total": len(events_cache_raw.get("events") or []),
            "fetch_log": events_cache_raw.get("fetch_log"),
            "source_counts": events_cache_raw.get("today_source_counts"),
        }

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
        "weather_today": weather_bundle,
        "weather_meta": {
            "source": "Open-Meteo（東京駅周辺・予報）",
            "trust_level": "high",
            "note": "雨の日・暑い日タブは today の is_rain / is_hot で切り替え。",
        },
        "osm_meta": {
            "source": "OpenStreetMap Overpass API",
            "trust_level": "low",
            "cached_towns": len(osm_towns),
            "cache_path": "town_osm_cache.json",
        },
        "flow_meta": {
            "source": "国土数値情報 駅別乗降客数（station_flow.yaml）",
            "trust_level": "medium",
            "stations_matched": len(flow_by_node),
        },
        "events_meta": {
            "source": "複数ソース（区市OD・Doorkeeper・connpass・Big Sight）",
            "trust_level": "medium",
            "match_radius_m": EVENT_MATCH_RADIUS_M,
            "match_mode": events_match_mode,
            "note": (
                "今日開催のみを座標付き優先で町マッチ。"
                "Doorkeeper は当日更新。fetch は python tools/fetch_tokyo_events.py を毎日推奨。"
            ),
            **events_meta,
        },
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
        f"(town={town_source_td} proxy={proxy_source_td}) "
        f"osm={with_osm} flow={with_flow} events={with_events} date={day_str}"
    )


if __name__ == "__main__":
    main()
