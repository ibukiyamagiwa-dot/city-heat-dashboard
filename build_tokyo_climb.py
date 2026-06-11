# -*- coding: utf-8 -*-
"""TOKYO CLIMB の日次データ生成スクリプト（Phase A: ダミーTD版）。

rail_graph.json を読み込み、直近3日分のダミー TD（Topic Delta: 話題の前日比%）を
駅ごとに決定論的（日付＋駅IDシード）に生成する。

出力:
  - stations_daily.json  … パイプライン記録用（最新日＋過去日）
  - tokyo_climb_data.js  … tokyo_climb.html が <script src> で読む
                            （file:// で開いても動くよう JS 変数として埋め込む）

将来 (Phase B/C):
  - TD を SNS API / 検索トレンドの実集計に置き換える
  - 天気を Open-Meteo の実取得に置き換える（build_prototype.py のパターン流用）
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GRAPH_PATH = BASE_DIR / "rail_graph.json"
DAILY_JSON_PATH = BASE_DIR / "stations_daily.json"
DATA_JS_PATH = BASE_DIR / "tokyo_climb_data.js"

DAYS = 3  # 生成する日数（今日を含む直近3日）

# ノードタイプ閾値（卒論で固定する定義。tokyo_climb.html 側と一致させること）
TD_HIGH = 30.0       # TD > +30%        → high
TD_MID = 10.0        # +10% < TD ≤ +30% → mid
TD_LOW = -10.0       # TD < -10%        → low / その間 → mystery
MENTION_MIN = 60     # SNS言及がこの件数未満の駅はデータ薄として mystery 固定

# ダミー天気（Phase B で Open-Meteo に置き換え。雨の日を1日入れて「消耗」をデモ）
DUMMY_WEATHER = [
    {"summary": "晴れ", "temperature_c": 22.0, "precipitation_mm": 0.0, "icon": "☀️"},
    {"summary": "雨",   "temperature_c": 18.0, "precipitation_mm": 4.2, "icon": "🌧️"},
    {"summary": "くもり", "temperature_c": 20.0, "precipitation_mm": 0.0, "icon": "☁️"},
]


def seeded_unit(*parts: str) -> float:
    """文字列シードから [0, 1) の決定論的な値を返す。"""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def node_degree(graph: dict) -> dict[str, int]:
    deg: dict[str, int] = {n["id"]: 0 for n in graph["nodes"]}
    for e in graph["edges"]:
        deg[e["from"]] += 1
        deg[e["to"]] += 1
    return deg


def classify(td: float, mentions: int) -> str:
    if mentions < MENTION_MIN:
        return "mystery"
    if td > TD_HIGH:
        return "high"
    if td > TD_MID:
        return "mid"
    if td < TD_LOW:
        return "low"
    return "mystery"


def build_day(graph: dict, day: date, weather: dict) -> dict:
    """1日分の駅別ダミーTDを生成する。"""
    day_str = day.isoformat()
    deg = node_degree(graph)
    stations = []
    for node in graph["nodes"]:
        sid = node["id"]
        # ハブ駅ほど言及が多い、を接続数で擬似的に表現（実装置き換えまでのダミー）
        base = seeded_unit(day_str, sid, "mentions")
        mentions = int(30 + deg[sid] * 45 + base * 160)
        # TD は -45% 〜 +75% の範囲で日替わり。少数の駅だけ大きく動くよう偏らせる
        roll = seeded_unit(day_str, sid, "td")
        spike = seeded_unit(day_str, sid, "spike")
        td = (roll - 0.45) * 60.0
        if spike > 0.85:
            td += 35.0  # その日の「急上昇駅」
        td = round(max(-45.0, min(75.0, td)), 1)
        stations.append(
            {
                "id": sid,
                "name": node["name"],
                "lat": node["lat"],
                "lon": node["lon"],
                "line": node["line"],
                "outdoor": node.get("outdoor", False),
                "td": td,
                "mention_count": mentions,
                "type": classify(td, mentions),
            }
        )
    return {
        "date": day_str,
        "weather": {
            "summary": weather["summary"],
            "icon": weather["icon"],
            "temperature_c": weather["temperature_c"],
            "precipitation_mm": weather["precipitation_mm"],
            "is_rain": weather["precipitation_mm"] >= 1.0,
            "source": "ダミー値（Phase B で Open-Meteo に置き換え）",
            "trust_level": "low",
        },
        "stations": stations,
    }


def main() -> None:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    today = date.today()
    days = []
    for i in range(DAYS - 1, -1, -1):
        d = today - timedelta(days=i)
        weather = DUMMY_WEATHER[(DAYS - 1 - i) % len(DUMMY_WEATHER)]
        days.append(build_day(graph, d, weather))

    daily_payload = {
        "generated_at": today.isoformat(),
        "td_definition": "TD = 駅別の監査済みクエリによるSNS言及件数の前日比（%）。本ファイルはダミー値。",
        "type_thresholds": {
            "high": f"TD > +{TD_HIGH}%",
            "mid": f"+{TD_MID}% < TD <= +{TD_HIGH}%",
            "mystery": f"-{abs(TD_LOW)}% <= TD <= +{TD_MID}% または言及 {MENTION_MIN} 件未満",
            "low": f"TD < {TD_LOW}%",
        },
        "trust_level": "low",
        "days": days,
    }
    DAILY_JSON_PATH.write_text(
        json.dumps(daily_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    js_payload = {"graph": graph, "daily": daily_payload}
    DATA_JS_PATH.write_text(
        "// TOKYO CLIMB データ（build_tokyo_climb.py が自動生成。手編集しない）\n"
        "window.TOKYO_CLIMB_DATA = "
        + json.dumps(js_payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )

    print(f"OK: {DAILY_JSON_PATH.name} / {DATA_JS_PATH.name} を生成しました")
    print(f"  日付: {days[0]['date']} 〜 {days[-1]['date']}")
    print(f"  駅数: {len(graph['nodes'])} / エッジ数: {len(graph['edges'])}")


if __name__ == "__main__":
    main()
