# -*- coding: utf-8 -*-
"""TOKYO CLIMB の日次データ生成スクリプト。

rail_graph.json を読み込み、直近3日分のデータを生成する。
  - 天気: Open-Meteo の日別データ（過去2日＋今日）。取得失敗時はダミーにフォールバック
  - TD（Topic Delta: 話題の前日比%）: 日付ごとに自動でモードを切り替える
      manual … td_counts.csv にその日の行がある（手動観測の実データ。手順は TD_DATA_GUIDE.md）
                入力済み駅は実TD、未入力駅は ❓（td なし）
      dummy  … その日の行がない（日付＋駅IDシードのダミー値）

出力:
  - stations_daily.json  … パイプライン記録用（最新日＋過去日）
  - tokyo_climb_data.js  … tokyo_climb.html が <script src> で読む
                            （file:// で開いても動くよう JS 変数として埋め込む）

将来 (Phase C):
  - TD を SNS API / 検索トレンドの自動集計に置き換える
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE_DIR = Path(__file__).resolve().parent
GRAPH_PATH = BASE_DIR / "rail_graph.json"
DAILY_JSON_PATH = BASE_DIR / "stations_daily.json"
DATA_JS_PATH = BASE_DIR / "tokyo_climb_data.js"
TD_CSV_PATH = BASE_DIR / "td_counts.csv"

DAYS = 3  # 生成する日数（今日を含む直近3日）

# ノードタイプ閾値（卒論で固定する定義。tokyo_climb.html 側と一致させること）
TD_HIGH = 30.0       # TD > +30%        → high
TD_MID = 10.0        # +10% < TD ≤ +30% → mid
TD_LOW = -10.0       # TD < -10%        → low / その間 → mystery
MENTION_MIN_DUMMY = 60   # ダミーTD: 言及がこの件数未満の駅は mystery 固定
MENTION_MIN_MANUAL = 5   # 手動TD: 観測窓1時間・上限50件のスケールに合わせた下限

# 天気の取得地点（東京駅周辺。山手線圏の代表値として1地点で足りる）
TOKYO_LAT, TOKYO_LON = 35.685, 139.74

# Open-Meteo 取得失敗時のフォールバック（雨の日を1日入れて「消耗」をデモ可能に）
DUMMY_WEATHER = [
    {"summary": "晴れ", "temperature_c": 22.0, "precipitation_mm": 0.0, "icon": "☀️"},
    {"summary": "雨",   "temperature_c": 18.0, "precipitation_mm": 4.2, "icon": "🌧️"},
    {"summary": "くもり", "temperature_c": 20.0, "precipitation_mm": 0.0, "icon": "☁️"},
]

# WMO weather code → 表示用の要約とアイコン
WMO_CODES = [
    ({0, 1}, "晴れ", "☀️"),
    ({2}, "晴れ時々くもり", "🌤️"),
    ({3}, "くもり", "☁️"),
    ({45, 48}, "霧", "🌫️"),
    (set(range(51, 68)) | set(range(80, 83)), "雨", "🌧️"),
    (set(range(71, 78)) | {85, 86}, "雪", "❄️"),
    ({95, 96, 99}, "雷雨", "⛈️"),
]


def describe_wmo(code: int) -> tuple[str, str]:
    for codes, summary, icon in WMO_CODES:
        if code in codes:
            return summary, icon
    return "不明", "🌡️"


def fetch_weather_days(n_days: int) -> dict[str, dict]:
    """Open-Meteo から「過去 n_days-1 日＋今日」の日別天気を取得する。

    戻り値: {"YYYY-MM-DD": weather_dict} 。失敗時は例外を投げる（呼び出し側でフォールバック）。
    """
    params = urlencode(
        {
            "latitude": TOKYO_LAT,
            "longitude": TOKYO_LON,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
            "past_days": n_days - 1,
            "forecast_days": 1,
            "timezone": "Asia/Tokyo",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    last_exc: Exception | None = None
    for attempt in range(3):  # 回線が不安定でも毎朝の運用が止まらないように
        try:
            with urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except Exception as exc:
            last_exc = exc
            print(f"  リトライ {attempt + 1}/3: {exc}")
    else:
        raise last_exc  # type: ignore[misc]

    daily = payload["daily"]
    result: dict[str, dict] = {}
    for i, day_str in enumerate(daily["time"]):
        code = int(daily["weather_code"][i])
        t_max = float(daily["temperature_2m_max"][i])
        t_min = float(daily["temperature_2m_min"][i])
        precip = float(daily["precipitation_sum"][i] or 0.0)
        summary, icon = describe_wmo(code)
        result[day_str] = {
            "summary": summary,
            "icon": icon,
            "temperature_c": round((t_max + t_min) / 2, 1),
            "temperature_max_c": round(t_max, 1),
            "precipitation_mm": round(precip, 1),
            "source": "Open-Meteo（日別・東京駅周辺）",
            "trust_level": "high",
        }
    return result


def load_weather_cache() -> dict[str, dict]:
    """前回生成した stations_daily.json から実取得済みの天気を回収する。

    Open-Meteo がネットワーク要因で落ちている日でも、過去日の天気は変わらないため
    前回の取得結果をそのまま使える（trust_level=high のものだけをキャッシュ扱いにする）。
    """
    try:
        prev = json.loads(DAILY_JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cache: dict[str, dict] = {}
    for d in prev.get("days", []):
        w = dict(d.get("weather", {}))
        w.pop("is_rain", None)
        if w.get("trust_level") == "high":
            if "キャッシュ" not in w.get("source", ""):
                w["source"] = f"{w.get('source', 'Open-Meteo')}（前回取得キャッシュ）"
            cache[d["date"]] = w
    return cache


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


def classify(td: float | None, mentions: int, mention_min: int) -> str:
    if td is None or mentions < mention_min:
        return "mystery"
    if td > TD_HIGH:
        return "high"
    if td > TD_MID:
        return "mid"
    if td < TD_LOW:
        return "low"
    return "mystery"


def load_td_counts(path: Path) -> dict[tuple[str, str], int]:
    """td_counts.csv を {(date, station_id): mention_count} に読み込む。"""
    counts: dict[tuple[str, str], int] = {}
    if not path.exists():
        return counts
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            day = (row.get("date") or "").strip()
            sid = (row.get("station_id") or "").strip()
            raw = (row.get("mention_count") or "").strip()
            if not day or not sid or not raw:
                continue
            counts[(day, sid)] = int(raw)
    return counts


def dummy_td(day_str: str, sid: str, degree: int) -> tuple[float, int]:
    """日付＋駅IDシードで決定論的なダミー (td, mentions) を返す。"""
    base = seeded_unit(day_str, sid, "mentions")
    mentions = int(30 + degree * 45 + base * 160)
    roll = seeded_unit(day_str, sid, "td")
    spike = seeded_unit(day_str, sid, "spike")
    td = (roll - 0.45) * 60.0
    if spike > 0.85:
        td += 35.0  # その日の「急上昇駅」
    td = round(max(-45.0, min(75.0, td)), 1)
    return td, mentions


def build_day(graph: dict, day: date, weather: dict, counts: dict) -> dict:
    """1日分の駅別TDを生成する。CSVにその日の行があれば手動モード。"""
    day_str = day.isoformat()
    prev_str = (day - timedelta(days=1)).isoformat()
    deg = node_degree(graph)
    manual = any(key[0] == day_str for key in counts)

    stations = []
    for node in graph["nodes"]:
        sid = node["id"]
        if manual:
            c = counts.get((day_str, sid))
            prev = counts.get((prev_str, sid))
            if c is None:
                td, mentions, source = None, 0, "none"
            elif prev is None:
                td, mentions, source = None, c, "manual"  # 前日比の基準がない
            else:
                td = round((c - prev) / max(prev, 1) * 100.0, 1)
                mentions, source = c, "manual"
            node_type = classify(td, mentions, MENTION_MIN_MANUAL)
        else:
            td, mentions = dummy_td(day_str, sid, deg[sid])
            source = "dummy"
            node_type = classify(td, mentions, MENTION_MIN_DUMMY)
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
                "td_source": source,
                "type": node_type,
            }
        )
    return {
        "date": day_str,
        "td_mode": "manual" if manual else "dummy",
        "weather": {
            **weather,
            "is_rain": weather["precipitation_mm"] >= 1.0,
        },
        "stations": stations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TOKYO CLIMB 日次データ生成")
    parser.add_argument(
        "--td-csv", type=Path, default=TD_CSV_PATH,
        help="手動TD入力CSVのパス（既定: td_counts.csv）",
    )
    args = parser.parse_args()

    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    counts = load_td_counts(args.td_csv)
    today = date.today()

    try:
        weather_by_date = fetch_weather_days(DAYS)
        weather_mode = "open-meteo"
    except Exception as exc:  # ネットワーク断などはキャッシュ → ダミーの順で継続
        weather_by_date = load_weather_cache()
        weather_mode = "cache" if weather_by_date else "dummy"
        print(f"WARN: Open-Meteo 取得失敗（{exc}）。{weather_mode} 天気で生成します。")

    days = []
    for i in range(DAYS - 1, -1, -1):
        d = today - timedelta(days=i)
        weather = weather_by_date.get(d.isoformat())
        if weather is None:
            weather = {
                **DUMMY_WEATHER[(DAYS - 1 - i) % len(DUMMY_WEATHER)],
                "source": "ダミー値（Open-Meteo 取得失敗時のフォールバック）",
                "trust_level": "low",
            }
        days.append(build_day(graph, d, weather, counts))

    daily_payload = {
        "generated_at": today.isoformat(),
        "weather_mode": weather_mode,
        "td_definition": (
            "TD = 駅別の監査済みクエリ（td_queries.yaml）によるSNS言及件数の前日比（%）。"
            "td_mode=manual の日は td_counts.csv の手動観測値、dummy の日はシード生成のダミー値。"
        ),
        "type_thresholds": {
            "high": f"TD > +{TD_HIGH}%",
            "mid": f"+{TD_MID}% < TD <= +{TD_HIGH}%",
            "mystery": (
                f"-{abs(TD_LOW)}% <= TD <= +{TD_MID}% "
                f"または言及不足（manual: {MENTION_MIN_MANUAL}件未満 / dummy: {MENTION_MIN_DUMMY}件未満）"
                "またはデータなし"
            ),
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
    print(f"  天気: {weather_mode}")
    for d in days:
        w = d["weather"]
        n_manual = sum(1 for s in d["stations"] if s["td_source"] == "manual")
        td_info = f"manual（入力 {n_manual} 駅）" if d["td_mode"] == "manual" else "dummy"
        print(
            f"    {d['date']}: {w['summary']} {w['temperature_c']}°C / "
            f"降水 {w['precipitation_mm']}mm / TD: {td_info}"
        )
    print(f"  駅数: {len(graph['nodes'])} / エッジ数: {len(graph['edges'])}")


if __name__ == "__main__":
    main()
