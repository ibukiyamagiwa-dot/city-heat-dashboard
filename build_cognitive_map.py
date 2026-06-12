# -*- coding: utf-8 -*-
"""認知距離マップ（Phase A）用データを生成する。

地理距離: rail_graph 最短乗車時間（乗換ペナルティ込み）
機能距離: town_osm_cache の POI 構成比 + TF-IDF + コサイン距離
記述距離: tagline + flavors の bag-of-words コサイン距離（探索用）

出力:
  data/cognitive/cognitive_map.json
  cognitive_map_data.js
"""

from __future__ import annotations

import heapq
import json
import math
import re
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GRAPH_PATH = BASE_DIR / "rail_graph.json"
TOWNS_PATH = BASE_DIR / "data" / "towns.json"
OSM_CACHE_PATH = BASE_DIR / "town_osm_cache.json"
OUT_JSON = BASE_DIR / "data" / "cognitive" / "cognitive_map.json"
OUT_JS = BASE_DIR / "cognitive_map_data.js"

POI_CATEGORIES = [
    "cinema",
    "museum",
    "library",
    "arts_centre",
    "theatre",
    "cafe",
    "park",
    "garden",
    "wood",
    "stadium",
    "nightclub",
    "sports_centre",
    "department_store",
    "mall",
    "marina",
    "beach",
]


def load_towns() -> list[dict]:
    payload = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    towns = [
        t
        for t in payload["towns"]
        if t.get("in_graph") and t.get("hub_node_id") and t.get("lat") is not None
    ]
    towns.sort(key=lambda t: t["name"])
    return towns


def build_adjacency(graph: dict) -> dict[str, list[dict]]:
    adj: dict[str, list[dict]] = {}
    for edge in graph["edges"]:
        adj.setdefault(edge["from"], []).append(edge)
    return adj


def shortest_minutes(
    adj: dict[str, list[dict]],
    from_id: str,
    to_id: str,
    transfer_penalty: int,
) -> int | None:
    if from_id == to_id:
        return 0

    dist: dict[str, int] = {}
    heap: list[tuple[int, str, str | None, str]] = []
    start_key = f"{from_id}|"
    dist[start_key] = 0
    heapq.heappush(heap, (0, from_id, None, start_key))

    while heap:
        cost, node, line, key = heapq.heappop(heap)
        if cost > dist.get(key, 10**9):
            continue
        for edge in adj.get(node, []):
            transfer = transfer_penalty if line and edge["line"] != line else 0
            new_cost = cost + edge["minutes"] + transfer
            new_key = f"{edge['to']}|{edge['line']}"
            if new_cost < dist.get(new_key, 10**9):
                dist[new_key] = new_cost
                heapq.heappush(heap, (new_cost, edge["to"], edge["line"], new_key))

    matches = [cost for key, cost in dist.items() if key.startswith(f"{to_id}|")]
    return min(matches) if matches else None


def compute_geo_matrix(
    towns: list[dict],
    graph: dict,
) -> dict[str, dict[str, int | None]]:
    routing = graph.get("routing") or {}
    transfer_penalty = int(routing.get("transfer_penalty_minutes", 5))
    adj = build_adjacency(graph)
    ids = [t["id"] for t in towns]
    hub_by_town = {t["id"]: t["hub_node_id"] for t in towns}

    matrix: dict[str, dict[str, int | None]] = {}
    for src in ids:
        row: dict[str, int | None] = {}
        for dst in ids:
            if src == dst:
                row[dst] = 0
                continue
            row[dst] = shortest_minutes(
                adj,
                hub_by_town[src],
                hub_by_town[dst],
                transfer_penalty,
            )
        matrix[src] = row
    return matrix


def poi_counts_for_towns(towns: list[dict], osm_cache: dict) -> dict[str, dict[str, int]]:
    town_osm = osm_cache.get("towns") or {}
    out: dict[str, dict[str, int]] = {}
    for town in towns:
        tid = town["id"]
        entry = town_osm.get(tid) or {}
        counts = entry.get("counts") or {}
        out[tid] = {cat: int(counts.get(cat, 0)) for cat in POI_CATEGORIES}
    return out


def l1_normalize(vec: dict[str, float]) -> dict[str, float]:
    total = sum(vec.values())
    if total <= 0:
        return {k: 0.0 for k in vec}
    return {k: v / total for k, v in vec.items()}


def tfidf_vectors(counts_by_town: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    n_docs = len(counts_by_town)
    df: dict[str, int] = {cat: 0 for cat in POI_CATEGORIES}
    for counts in counts_by_town.values():
        for cat in POI_CATEGORIES:
            if counts.get(cat, 0) > 0:
                df[cat] += 1

    vectors: dict[str, dict[str, float]] = {}
    for tid, counts in counts_by_town.items():
        total = float(sum(counts.values()) or 1.0)
        vec: dict[str, float] = {}
        for cat in POI_CATEGORIES:
            tf = counts.get(cat, 0) / total
            idf = math.log((1 + n_docs) / (1 + df[cat])) + 1.0
            vec[cat] = tf * idf
        vectors[tid] = vec
    return vectors


def cosine_distance(a: dict[str, float], b: dict[str, float], keys: list[str]) -> float:
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(a.get(k, 0.0) ** 2 for k in keys))
    nb = math.sqrt(sum(b.get(k, 0.0) ** 2 for k in keys))
    if na <= 0 or nb <= 0:
        return 1.0
    sim = dot / (na * nb)
    return max(0.0, min(1.0, 1.0 - sim))


def compute_poi_matrix(
    towns: list[dict],
    osm_cache: dict,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, int]]]:
    counts_by_town = poi_counts_for_towns(towns, osm_cache)
    vectors = tfidf_vectors(counts_by_town)
    ids = [t["id"] for t in towns]
    matrix: dict[str, dict[str, float]] = {}
    for src in ids:
        row: dict[str, float] = {}
        for dst in ids:
            if src == dst:
                row[dst] = 0.0
                continue
            row[dst] = cosine_distance(vectors[src], vectors[dst], POI_CATEGORIES)
        matrix[src] = row
    return matrix, counts_by_town


def tokenize_text(text: str) -> dict[str, float]:
    text = text.lower()
    tokens = re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]+|[a-z0-9]+", text)
    bag: dict[str, float] = {}
    for token in tokens:
        bag[token] = bag.get(token, 0.0) + 1.0
    return bag


def text_profile(town: dict) -> dict[str, float]:
    parts = [town.get("tagline") or "", town.get("name") or ""]
    parts.extend(town.get("flavors") or [])
    return tokenize_text(" ".join(parts))


def compute_text_matrix(towns: list[dict]) -> dict[str, dict[str, float]]:
    profiles = {t["id"]: text_profile(t) for t in towns}
    keys_union: set[str] = set()
    for bag in profiles.values():
        keys_union.update(bag.keys())
    keys = sorted(keys_union)
    ids = [t["id"] for t in towns]
    matrix: dict[str, dict[str, float]] = {}
    for src in ids:
        row: dict[str, float] = {}
        for dst in ids:
            if src == dst:
                row[dst] = 0.0
                continue
            row[dst] = cosine_distance(profiles[src], profiles[dst], keys)
        matrix[src] = row
    return matrix


def top_neighbors(
    matrix: dict[str, dict[str, float | int | None]],
    anchor_id: str,
    n: int = 10,
) -> list[dict]:
    row = matrix.get(anchor_id) or {}
    ranked = []
    for tid, value in row.items():
        if tid == anchor_id or value is None:
            continue
        ranked.append((float(value), tid))
    ranked.sort(key=lambda x: x[0])
    return [{"id": tid, "value": val} for val, tid in ranked[:n]]


def build_payload(towns: list[dict], graph: dict, osm_cache: dict) -> dict:
    geo = compute_geo_matrix(towns, graph)
    poi, poi_counts = compute_poi_matrix(towns, osm_cache)
    text = compute_text_matrix(towns)

    town_rows = []
    for town in towns:
        town_rows.append(
            {
                "id": town["id"],
                "name": town["name"],
                "tagline": town.get("tagline"),
                "flavors": town.get("flavors") or [],
                "lat": town["lat"],
                "lon": town["lon"],
                "hub_node_id": town["hub_node_id"],
                "poi_counts": poi_counts.get(town["id"], {}),
            }
        )

    def example_for(aid: str) -> dict:
        geo_top = top_neighbors(geo, aid, 10)
        poi_top = top_neighbors(poi, aid, 10)
        text_top = top_neighbors(text, aid, 10)
        geo_ids = {x["id"] for x in geo_top}
        return {
            "geo_top10": geo_top,
            "poi_top10": poi_top,
            "text_top10": text_top,
            "poi_not_in_geo_top10": [x for x in poi_top if x["id"] not in geo_ids],
            "text_not_in_geo_top10": [x for x in text_top if x["id"] not in geo_ids],
        }

    preview_ids = [t["id"] for t in towns[:5]]
    if "shimokitazawa" not in preview_ids:
        preview_ids.append("shimokitazawa")
    examples = {aid: example_for(aid) for aid in preview_ids}

    unreachable = sum(
        1
        for src, row in geo.items()
        for dst, minutes in row.items()
        if src != dst and minutes is None
    )

    return {
        "version": "0.1",
        "phase": "A",
        "built_at": date.today().isoformat(),
        "title": "認知距離マップ",
        "tagline": "地図の「近さ」は、測り方で変わる。",
        "sources": {
            "geo": {
                "label": "地理距離（電車・最短所要時間）",
                "file": "rail_graph.json",
                "note": "N02 由来グラフ + 乗換ペナルティ",
            },
            "poi": {
                "label": "機能距離（POI 構成・TF-IDF）",
                "file": "town_osm_cache.json",
                "note": "OpenStreetMap Overpass 半径700m・16カテゴリ",
            },
            "text": {
                "label": "記述距離（tagline + flavors）",
                "file": "data/towns.json",
                "note": "手書きテキストの bag-of-words（探索用）",
            },
        },
        "poi_categories": POI_CATEGORIES,
        "stats": {
            "town_count": len(towns),
            "geo_unreachable_pairs": unreachable,
        },
        "towns": town_rows,
        "geo_minutes": geo,
        "poi_distance": poi,
        "text_distance": text,
        "examples": examples,
    }


def write_js(payload: dict, path: Path) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"const COGNITIVE_MAP_DATA = {body};\n", encoding="utf-8")


def main() -> None:
    towns = load_towns()
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    osm_cache = {}
    if OSM_CACHE_PATH.exists():
        osm_cache = json.loads(OSM_CACHE_PATH.read_text(encoding="utf-8"))

    payload = build_payload(towns, graph, osm_cache)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_js(payload, OUT_JS)

    print(f"towns={payload['stats']['town_count']}")
    print(f"geo_unreachable_pairs={payload['stats']['geo_unreachable_pairs']}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_JS}")

    shimokitazawa = next((t for t in towns if t["id"] == "shimokitazawa"), towns[0])
    aid = shimokitazawa["id"]
    ex = payload["examples"][aid]
    print(f"\nExample anchor: {shimokitazawa['name']}")
    print("  geo top5:", [t["id"] for t in ex["geo_top10"][:5]])
    print("  poi top5:", [t["id"] for t in ex["poi_top10"][:5]])
    print("  poi surprise:", [t["id"] for t in ex["poi_not_in_geo_top10"][:5]])


if __name__ == "__main__":
    main()
