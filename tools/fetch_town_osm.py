# -*- coding: utf-8 -*-
"""手選り町周辺の OSM 集計 → town_osm_cache.json"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
TOWNS_PATH = BASE / "data" / "towns.json"
CACHE_PATH = BASE / "town_osm_cache.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RADIUS_M = 700
REQUEST_DELAY = 2.0

# 研究 build_prototype.py のカテゴリ + 快適・タグ用
CATEGORIES = [
    {"id": "cinema", "label": "映画館", "selector": '["amenity"="cinema"]', "tag": "amenity=cinema", "rain": 2, "research": True},
    {"id": "museum", "label": "博物館・美術館", "selector": '["tourism"="museum"]', "tag": "tourism=museum", "rain": 2, "research": True},
    {"id": "library", "label": "図書館", "selector": '["amenity"="library"]', "tag": "amenity=library", "rain": 2, "research": True},
    {"id": "arts_centre", "label": "アートセンター", "selector": '["amenity"="arts_centre"]', "tag": "amenity=arts_centre", "rain": 1, "research": True},
    {"id": "theatre", "label": "劇場", "selector": '["amenity"="theatre"]', "tag": "amenity=theatre", "rain": 1, "research": True},
    {"id": "cafe", "label": "カフェ", "selector": '["amenity"="cafe"]', "tag": "amenity=cafe", "rain": 1, "research": True},
    {"id": "park", "label": "公園", "selector": '["leisure"="park"]', "tag": "leisure=park", "heat": 3, "research": True},
    {"id": "garden", "label": "庭園", "selector": '["leisure"="garden"]', "tag": "leisure=garden", "heat": 2, "research": False},
    {"id": "wood", "label": "森林・緑地", "selector": '["natural"="wood"]', "tag": "natural=wood", "heat": 2, "research": False},
    {"id": "stadium", "label": "スタジアム", "selector": '["leisure"="stadium"]', "tag": "leisure=stadium", "rain": 0, "research": True},
    {"id": "nightclub", "label": "クラブ", "selector": '["amenity"="nightclub"]', "tag": "amenity=nightclub", "rain": 1, "research": True},
    {"id": "sports_centre", "label": "スポーツ施設", "selector": '["leisure"="sports_centre"]', "tag": "leisure=sports_centre", "rain": 1, "research": False},
    {"id": "department_store", "label": "百貨店", "selector": '["shop"="department_store"]', "tag": "shop=department_store", "rain": 2, "research": False},
    {"id": "mall", "label": "モール", "selector": '["shop"="mall"]', "tag": "shop=mall", "rain": 2, "research": False},
    {"id": "marina", "label": "マリーナ", "selector": '["leisure"="marina"]', "tag": "leisure=marina", "outdoor": 3, "research": False},
    {"id": "beach", "label": "海岸", "selector": '["natural"="beach"]', "tag": "natural=beach", "outdoor": 3, "research": False},
]


def build_query(lat: float, lon: float, radius_m: int) -> str:
    lines = ["[out:json][timeout:45];"]
    for cat in CATEGORIES:
        sel = cat["selector"]
        lines.extend(
            [
                "(",
                f"  node(around:{radius_m},{lat},{lon}){sel};",
                f"  way(around:{radius_m},{lat},{lon}){sel};",
                f"  relation(around:{radius_m},{lat},{lon}){sel};",
                f")->.{cat['id']};",
                f".{cat['id']} out count;",
            ]
        )
    return "\n".join(lines)


def fetch_counts(lat: float, lon: float) -> dict[str, int]:
    query = build_query(lat, lon, RADIUS_M)
    body = urlencode({"data": query}).encode("utf-8")
    req = Request(
        OVERPASS_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "yorimachi/phase3",
        },
        method="POST",
    )
    with urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elements = payload.get("elements") or []
    counts: dict[str, int] = {}
    for cat, element in zip(CATEGORIES, elements):
        tags = element.get("tags", {}) if isinstance(element, dict) else {}
        counts[cat["id"]] = int(tags.get("total", 0))
    return counts


def tier_from_rank(rank: int, total: int) -> str:
    if total <= 1:
        return "mid"
    pct = rank / (total - 1)
    if pct >= 0.67:
        return "high"
    if pct >= 0.34:
        return "mid"
    return "low"


def enrich_town(town_id: str, counts: dict[str, int], ranks: dict) -> dict:
    rain_raw = sum(counts.get(c["id"], 0) * c.get("rain", 0) for c in CATEGORIES)
    heat_raw = sum(counts.get(c["id"], 0) * c.get("heat", 0) for c in CATEGORIES)
    outdoor_raw = sum(counts.get(c["id"], 0) * c.get("outdoor", 0) for c in CATEGORIES)
    research_tags = []
    for cat in CATEGORIES:
        if not cat.get("research"):
            continue
        n = counts.get(cat["id"], 0)
        if n > 0:
            research_tags.append(
                {
                    "id": cat["id"],
                    "label": cat["label"],
                    "count": n,
                    "tag": cat["tag"],
                    "trust_level": "low",
                    "source": "OpenStreetMap Overpass API",
                }
            )
    return {
        "counts": counts,
        "scores": {
            "rain_raw": rain_raw,
            "heat_raw": heat_raw,
            "outdoor_raw": outdoor_raw,
            "rain_comfort": ranks["rain"].get(town_id, "mid"),
            "heat_comfort": ranks["heat"].get(town_id, "mid"),
        },
        "research_tags": research_tags,
        "radius_m": RADIUS_M,
        "source": "OpenStreetMap Overpass API",
        "trust_level": "low",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    towns_data = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    curated = [t for t in towns_data["towns"] if t.get("tier") != "station"]

    cache: dict = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    town_cache = cache.get("towns") or {}

    raw_rain: dict[str, int] = {}
    raw_heat: dict[str, int] = {}

    for town in curated:
        tid = town["id"]
        if args.only_missing and tid in town_cache:
            entry = town_cache[tid]
            raw_rain[tid] = entry.get("scores", {}).get("rain_raw", 0)
            raw_heat[tid] = entry.get("scores", {}).get("heat_raw", 0)
            continue
        if args.skip_fetch:
            continue
        lat, lon = town["lat"], town["lon"]
        print(f"OSM: {town['name']} ({tid})", flush=True)
        try:
            counts = fetch_counts(lat, lon)
            town_cache[tid] = {"counts": counts, "fetched_at": date.today().isoformat()}
            raw_rain[tid] = sum(counts.get(c["id"], 0) * c.get("rain", 0) for c in CATEGORIES)
            raw_heat[tid] = sum(counts.get(c["id"], 0) * c.get("heat", 0) for c in CATEGORIES)
        except Exception as exc:
            print(f"  WARN: {tid} {exc}", flush=True)
        time.sleep(REQUEST_DELAY)

    rain_order = sorted(raw_rain.keys(), key=lambda k: raw_rain[k])
    heat_order = sorted(raw_heat.keys(), key=lambda k: raw_heat[k])
    rain_ranks = {tid: tier_from_rank(i, len(rain_order)) for i, tid in enumerate(rain_order)}
    heat_ranks = {tid: tier_from_rank(i, len(heat_order)) for i, tid in enumerate(heat_order)}

    for tid, entry in town_cache.items():
        counts = entry.get("counts") or {}
        entry.update(enrich_town(tid, counts, {"rain": rain_ranks, "heat": heat_ranks}))

    out = {
        "updated_at": date.today().isoformat(),
        "source": f"OpenStreetMap Overpass（半径{RADIUS_M}m）",
        "towns": town_cache,
    }
    CACHE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {CACHE_PATH} towns={len(town_cache)}")


if __name__ == "__main__":
    main()
