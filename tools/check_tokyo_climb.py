# -*- coding: utf-8 -*-
"""tokyo_climb.html のボス決定・DAG生成ロジックの検証（JS実装のPython移植）。

全37駅をスタートにした場合に:
  - ボスが必ず決まるか
  - DAG が必ず生成できるか（経路1本以上）
  - 各層の候補数・分岐の量
を確認する。
"""

import json
import random
from collections import deque
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
graph = json.loads((BASE / "rail_graph_v01.json").read_text(encoding="utf-8"))
daily = json.loads((BASE / "stations_daily.json").read_text(encoding="utf-8"))

adj: dict[str, list[str]] = {n["id"]: [] for n in graph["nodes"]}
for e in graph["edges"]:
    adj[e["from"]].append(e["to"])
    adj[e["to"]].append(e["from"])

RUN_HOPS = 12

day = daily["days"][-1]
# 手動モードの未入力駅は td が None になるため、ボス候補から実質除外する
td = {s["id"]: (s["td"] if s["td"] is not None else -999) for s in day["stations"]}


def bfs(src):
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def pick_boss(start):
    dist = bfs(start)
    for lo, hi in [
        (RUN_HOPS, RUN_HOPS),
        (RUN_HOPS - 1, RUN_HOPS + 1),
        (RUN_HOPS - 2, RUN_HOPS + 2),
        (RUN_HOPS - 3, RUN_HOPS + 3),
        (6, 99),
    ]:
        cands = [i for i in adj if i != start and lo <= dist.get(i, 999) <= hi]
        if cands:
            return max(cands, key=lambda i: td[i]), dist
    return None, dist


def build_dag(S, B):
    for extra in (2, 4, 6, 8):
        dag = build_dag_with_slack(S, B, extra)
        if dag:
            n_branch = sum(1 for l in dag["layers"] if len(l) >= 2)
            if n_branch >= 2 or extra == 8:
                return dag
    return None


def build_dag_with_slack(S, B, extra):
    dB = bfs(B)
    L = bfs(S)[B]
    maxlen = L + extra

    rng = random.Random(f"{day['date']}|{S}|{B}")
    paths, steps = [], [0]
    in_path = {S}

    def dfs(u, path):
        if len(paths) >= 60 or steps[0] > 20000:
            return
        steps[0] += 1
        if u == B:
            paths.append(path[:])
            return
        nexts = [v for v in adj[u] if v not in in_path and len(path) + dB[v] <= maxlen]
        rng.shuffle(nexts)
        for v in nexts:
            in_path.add(v)
            path.append(v)
            dfs(v, path)
            path.pop()
            in_path.discard(v)

    dfs(S, [S])
    if not paths:
        return None

    groups: dict[int, list] = {}
    for p in paths:
        groups.setdefault(len(p) - 1, []).append(p)
    best_len = max(groups, key=lambda ln: (min(len(groups[ln]), 8), -abs(ln - RUN_HOPS)))
    ps = groups[best_len]
    T = best_len

    layers = [set() for _ in range(T + 1)]
    chosen = 0
    for p in ps:
        if all(p[k] in layers[k] or len(layers[k]) < 3 for k in range(T + 1)):
            chosen += 1
            for k in range(T + 1):
                layers[k].add(p[k])
        if chosen >= 10:
            break
    if not chosen:
        for k in range(T + 1):
            layers[k].add(ps[0][k])

    edges = set()
    for k in range(T):
        for u in layers[k]:
            for v in layers[k + 1]:
                if v in adj[u]:
                    edges.add((u, v))
    return {"L": T, "layers": [sorted(s) for s in layers], "edges": edges, "n_paths": len(paths)}


ok = True
widths = []
for node in graph["nodes"]:
    s = node["id"]
    boss, dist = pick_boss(s)
    if boss is None:
        print(f"NG: {s} ボスなし")
        ok = False
        continue
    dag = build_dag(s, boss)
    if dag is None:
        print(f"NG: {s} -> {boss} DAG生成失敗")
        ok = False
        continue
    w = [len(l) for l in dag["layers"]]
    n_branch = sum(1 for x in w if x >= 2)
    widths.append(n_branch)
    if n_branch <= 1:
        print(f"  低分岐: {s} -> {boss} (L={dag['L']}, 層幅={w}, 経路数={dag['n_paths']})")
    # 全ノードが次層への辺を持つか（行き止まりがないか）
    for k in range(dag["L"]):
        for u in dag["layers"][k]:
            if not any((u, v) in dag["edges"] for v in dag["layers"][k + 1]):
                print(f"NG: {s}->{boss} layer{k} の {u} が行き止まり")
                ok = False

print()
print(f"スタート駅 {len(graph['nodes'])} 件すべて検証")
print(f"分岐あり層数（width>=2）の平均: {sum(widths)/len(widths):.1f}")
print(f"最小: {min(widths)} / 最大: {max(widths)}")
print("結果:", "OK（全スタートでボス決定・DAG生成・行き止まりなし）" if ok else "NG あり")
