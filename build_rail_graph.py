# -*- coding: utf-8 -*-
"""N02（国土数値情報 鉄道）から rail_graph.json v0.2 を生成する。

入力: data/raw/n02/N02-23_GML/UTF-8/*.geojson（--fetch で ZIP 取得）
出力: rail_graph.json, stations_index.json

依存: pyyaml（.venv）
"""

from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import urlretrieve

import yaml

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw" / "n02"
CONFIG_PATH = BASE_DIR / "data" / "config" / "lines_mvp.yaml"
GRAPH_PATH = BASE_DIR / "rail_graph.json"
INDEX_PATH = BASE_DIR / "stations_index.json"

N02_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-23/N02-23_GML.zip"
N02_VERSION = "N02-2023"
SOURCE_NOTE = (
    "国土交通省 国土数値情報 鉄道（N02-2023）。"
    "出典：国土交通省／加工：build_rail_graph.py"
)

YAMANOTE_CENTER = (139.7300, 35.6762)


def station_point(geom: dict) -> tuple[float, float]:
    coords = geom["coordinates"]
    if geom["type"] == "Point":
        return float(coords[0]), float(coords[1])
    if geom["type"] == "LineString":
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    raise ValueError(f"unsupported geometry: {geom['type']}")


def slugify(name: str) -> str:
    s = re.sub(r"\s+", "", name)
    s = re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff-]", "", s.lower())
    return s or "node"


def in_bbox(lon: float, lat: float, bbox: dict) -> bool:
    return (
        bbox["lon_min"] <= lon <= bbox["lon_max"]
        and bbox["lat_min"] <= lat <= bbox["lat_max"]
    )


def line_matches(line_name: str, patterns: list[str]) -> bool:
    return any(p in line_name for p in patterns)


def fetch_n02() -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "N02-23_GML.zip"
    if not zip_path.exists():
        print(f"Downloading {N02_URL} …")
        urlretrieve(N02_URL, zip_path)
    extract_dir = RAW_DIR / "N02-23_GML"
    station_geojson = extract_dir / "UTF-8" / "N02-23_Station.geojson"
    if not station_geojson.exists():
        print("Extracting …")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    return station_geojson


def load_stops(station_path: Path, cfg: dict) -> list[dict]:
    data = json.loads(station_path.read_text(encoding="utf-8"))
    patterns = cfg["include_line_contains"]
    bbox = cfg["bbox"]
    stops = []
    for feat in data["features"]:
        props = feat["properties"]
        line = props.get("N02_003") or ""
        if not line_matches(line, patterns):
            continue
        lon, lat = station_point(feat["geometry"])
        if not in_bbox(lon, lat, bbox):
            continue
        stops.append({
            "stop_id": props["N02_005c"],
            "group_code": props["N02_005g"],
            "name": props["N02_005"],
            "line": line,
            "operator": props.get("N02_004") or "",
            "lon": round(lon, 6),
            "lat": round(lat, 6),
        })
    return stops


def build_nodes(stops: list[dict]) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in stops:
        groups[s["group_code"]].append(s)

    nodes: dict[str, dict] = {}
    used_slugs: set[str] = set()
    for gcode, items in groups.items():
        name_counts: dict[str, int] = defaultdict(int)
        for it in items:
            name_counts[it["name"]] += 1
        display_name = max(name_counts, key=name_counts.get)
        lon = sum(it["lon"] for it in items) / len(items)
        lat = sum(it["lat"] for it in items) / len(items)
        lines = sorted({it["line"] for it in items})
        node_id = f"g_{gcode}"
        slug = slugify(display_name)
        if slug in used_slugs:
            slug = f"{slug}_{gcode}"
        used_slugs.add(slug)
        nodes[node_id] = {
            "id": node_id,
            "slug": slug,
            "name": display_name,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "group_code": gcode,
            "lines": lines,
            "stops": [
                {
                    "stop_id": it["stop_id"],
                    "line": it["line"],
                    "operator": it["operator"],
                }
                for it in items
            ],
        }
    return nodes


def sort_stops_on_line(line_stops: list[dict], line_name: str, ring_lines: list[str]) -> list[dict]:
    if any(r in line_name for r in ring_lines):
        cx, cy = YAMANOTE_CENTER
        return sorted(
            line_stops,
            key=lambda s: math.atan2(s["lat"] - cy, s["lon"] - cx),
        )
    lons = [s["lon"] for s in line_stops]
    lats = [s["lat"] for s in line_stops]
    if max(lons) - min(lons) >= max(lats) - min(lats):
        return sorted(line_stops, key=lambda s: s["lon"])
    return sorted(line_stops, key=lambda s: s["lat"])


def build_edges(stops: list[dict], nodes: dict[str, dict], cfg: dict) -> list[dict]:
    g2n = {n["group_code"]: nid for nid, n in nodes.items()}

    by_line: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for s in stops:
        key = (s["line"], s["group_code"])
        if key in seen:
            continue
        seen.add(key)
        by_line[s["line"]].append(s)

    edges: dict[tuple[str, str, str], dict] = {}
    ring_lines = cfg.get("ring_lines") or []

    for line_name, line_stops in by_line.items():
        ordered = sort_stops_on_line(line_stops, line_name, ring_lines)
        node_ids: list[str] = []
        for s in ordered:
            nid = g2n.get(s["group_code"])
            if nid and (not node_ids or node_ids[-1] != nid):
                node_ids.append(nid)
        for i in range(len(node_ids) - 1):
            a, b = node_ids[i], node_ids[i + 1]
            edges[(a, b, line_name)] = {
                "from": a, "to": b, "line": line_name, "kind": "ride", "minutes": 3,
            }
            edges[(b, a, line_name)] = {
                "from": b, "to": a, "line": line_name, "kind": "ride", "minutes": 3,
            }
        if any(r in line_name for r in ring_lines) and len(node_ids) >= 3:
            a, b = node_ids[-1], node_ids[0]
            edges[(a, b, line_name)] = {
                "from": a, "to": b, "line": line_name, "kind": "ride", "minutes": 3,
            }
            edges[(b, a, line_name)] = {
                "from": b, "to": a, "line": line_name, "kind": "ride", "minutes": 3,
            }

    return list(edges.values())


def build_index(nodes: dict[str, dict]) -> list[dict]:
    index = []
    for node in nodes.values():
        index.append({
            "id": node["id"],
            "slug": node["slug"],
            "name": node["name"],
            "lat": node["lat"],
            "lon": node["lon"],
            "lines": node["lines"],
        })
    index.sort(key=lambda x: x["name"])
    return index


def build_graph(fetch: bool = False) -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    station_path = (
        fetch_n02() if fetch
        else RAW_DIR / "N02-23_GML" / "UTF-8" / "N02-23_Station.geojson"
    )
    if not station_path.exists():
        raise SystemExit(
            "N02 GeoJSON がありません。python build_rail_graph.py --fetch を実行してください。"
        )

    stops = load_stops(station_path, cfg)
    if not stops:
        raise SystemExit("フィルタ後の stop が 0 件です。config/lines_mvp.yaml を確認してください。")

    nodes_map = build_nodes(stops)
    edges = build_edges(stops, nodes_map, cfg)
    return {
        "version": "0.2",
        "source": N02_VERSION,
        "source_note": SOURCE_NOTE,
        "note": (
            "N02 駅 stop を group_code で物理ノード化。"
            "路線内エッジは同一 N02_003 上の stop を並べて隣接接続（簡略）。"
        ),
        "filters": {
            "bbox": cfg["bbox"],
            "lines": cfg["include_line_contains"],
        },
        "stats": {
            "stops": len(stops),
            "nodes": len(nodes_map),
            "edges": len(edges),
        },
        "nodes": list(nodes_map.values()),
        "edges": edges,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build rail_graph.json from N02")
    parser.add_argument("--fetch", action="store_true", help="Download N02 zip if missing")
    args = parser.parse_args()

    graph = build_graph(fetch=args.fetch)
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    index = build_index({n["id"]: n for n in graph["nodes"]})
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = graph["stats"]
    print(f"Wrote {GRAPH_PATH} - nodes={stats['nodes']} edges={stats['edges']} stops={stats['stops']}")
    print(f"Wrote {INDEX_PATH} — {len(index)} entries")


if __name__ == "__main__":
    main()
