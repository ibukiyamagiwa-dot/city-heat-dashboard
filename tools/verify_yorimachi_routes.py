# -*- coding: utf-8 -*-
"""寄り町ルート検証（簡易）。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
graph = json.loads((BASE / "rail_graph.json").read_text(encoding="utf-8"))
towns = json.loads((BASE / "data" / "towns.json").read_text(encoding="utf-8"))
routing = graph.get("routing") or {}
TRANSFER = routing.get("transfer_penalty_minutes", 5)
FIT = routing.get("time_fit_margin_minutes", 5)

adj: dict[str, list] = {}
for e in graph["edges"]:
    adj.setdefault(e["from"], []).append(e)


def shortest(from_id: str, to_id: str) -> tuple[int, int] | None:
    if from_id == to_id:
        return 0, 0
    dist: dict[str, int] = {}
    prev: dict[str, tuple[str, dict | None]] = {}
    heap: list[tuple[str, str | None, int, str]] = []

    sk = f"{from_id}|"
    dist[sk] = 0
    prev[sk] = (None, None)
    heap.append((from_id, None, 0, sk))

    while heap:
        heap.sort(key=lambda x: x[2])
        node, line, cost, key = heap.pop(0)
        if cost > dist.get(key, 10**9):
            continue
        for edge in adj.get(node, []):
            transfer = TRANSFER if line and edge["line"] != line else 0
            new_cost = cost + edge["minutes"] + transfer
            nk = f"{edge['to']}|{edge['line']}"
            if new_cost < dist.get(nk, 10**9):
                dist[nk] = new_cost
                prev[nk] = (key, edge)
                heap.append((edge["to"], edge["line"], new_cost, nk))

    best = None
    for k, c in dist.items():
        if k.startswith(f"{to_id}|") and (best is None or c < best):
            best = c
    if best is None:
        return None

    best_key = min(
        [k for k in dist if k.startswith(f"{to_id}|")],
        key=lambda k: dist[k],
    )
    edges_used = []
    k = best_key
    while prev[k][0]:
        pk, edge = prev[k]
        if edge:
            edges_used.insert(0, edge)
        k = pk
    transfers = sum(
        1 for i in range(1, len(edges_used)) if edges_used[i]["line"] != edges_used[i - 1]["line"]
    )
    return best, transfers


from_id = "g_003700"  # 新宿
selected = 30
lo, hi = selected - FIT, selected + FIT
print(f"Graph: nodes={graph['stats']['nodes']} edges={graph['stats']['edges']}")
print(f"Shinjuku recommend window: {lo}-{hi} min")

off = [t for t in towns["towns"] if not t["in_graph"]]
print(f"off_graph towns: {len(off)}")
if off:
    print("  ", [t["name"] for t in off])

fitted = []
for t in towns["towns"]:
    if not t.get("in_graph") or not t.get("hub_node_id"):
        continue
    if t["hub_node_id"] == from_id:
        continue
    r = shortest(from_id, t["hub_node_id"])
    if not r:
        print(f"  NO ROUTE: {t['name']}")
        continue
    mins, tr = r
    if lo <= mins <= hi:
        fitted.append((t["name"], mins, tr))

print(f"Recommend count ({lo}-{hi}): {len(fitted)}")
for name, mins, tr in sorted(fitted, key=lambda x: x[1])[:10]:
    print(f"  {name}: {mins} min, transfers={tr}")
