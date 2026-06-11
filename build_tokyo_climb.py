# -*- coding: utf-8 -*-
"""TOKYO CLIMB の日次データ生成スクリプト。

rail_graph.json を読み込み、直近3日分のデータを生成する。
  - 天気: Open-Meteo の日別データ（過去2日＋今日）。取得失敗時はダミーにフォールバック
  - TD（Topic Delta: 話題の前日比%）: 日付ごとに自動でモードを切り替える
      trends … Google Trends 日次関心（tier A 15駅を trendspy で自動取得。既定）
      manual … td_counts.csv にその日の行がある（手動観測。TD_DATA_GUIDE.md）
      dummy  … trends 取得失敗かつキャッシュなし（日付＋駅IDシードのダミー値）

出力:
  - stations_daily.json  … パイプライン記録用（最新日＋過去日）
  - tokyo_climb_data.js  … tokyo_climb.html が <script src> で読む
  - td_trends_cache.json … Trends 取得キャッシュ（再取得失敗時のフォールバック）

依存: trendspy, pyyaml（.venv に pip install trendspy pyyaml）
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import yaml
from requests.exceptions import HTTPError
from trendspy import Trends

BASE_DIR = Path(__file__).resolve().parent
GRAPH_PATH = BASE_DIR / "rail_graph.json"
DAILY_JSON_PATH = BASE_DIR / "stations_daily.json"
DATA_JS_PATH = BASE_DIR / "tokyo_climb_data.js"
TD_CSV_PATH = BASE_DIR / "td_counts.csv"
QUERIES_PATH = BASE_DIR / "td_queries.yaml"
TRENDS_CACHE_PATH = BASE_DIR / "td_trends_cache.json"

DAYS = 3  # 生成する日数（今日を含む直近3日）
TRENDS_REQUEST_DELAY = 15.0  # Google Trends レート制限対策（秒。15駅で約4分）
TRENDS_TIMEFRAME = "today 1-m"
TRENDS_GEO = "JP"

# ノードタイプ閾値（卒論で固定する定義。tokyo_climb.html 側と一致させること）
TD_HIGH = 30.0       # TD > +30%        → high
TD_MID = 10.0        # +10% < TD ≤ +30% → mid
TD_LOW = -10.0       # TD < -10%        → low / その間 → mystery
MENTION_MIN_DUMMY = 60   # ダミーTD: 言及がこの件数未満の駅は mystery 固定
MENTION_MIN_MANUAL = 5   # 手動TD: 観測窓1時間・上限50件のスケールに合わせた下限
MENTION_MIN_TRENDS = 1   # Trends: 関心値0はデータ薄として mystery

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


def load_td_queries() -> tuple[dict[str, str], list[str]]:
    """td_queries.yaml から tier A 駅 {id: keyword} と tier A id 一覧を返す。"""
    if not QUERIES_PATH.exists():
        return {}, []
    cfg = yaml.safe_load(QUERIES_PATH.read_text(encoding="utf-8"))
    tier_a: dict[str, str] = {}
    for sid, meta in (cfg.get("stations") or {}).items():
        if str(meta.get("tier", "")).upper() != "A":
            continue
        queries = meta.get("queries") or []
        if queries:
            tier_a[sid] = str(queries[0])
    return tier_a, list(tier_a.keys())


def load_trends_cache(path: Path = TRENDS_CACHE_PATH) -> dict[str, dict[str, int]]:
    """キャッシュを {station_id: {date: interest}} で返す。"""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, int]] = {}
    for sid, days in (payload.get("stations") or {}).items():
        out[sid] = {str(d): int(v) for d, v in days.items()}
    return out


def save_trends_cache(
    stations: dict[str, dict[str, int]],
    path: Path = TRENDS_CACHE_PATH,
    *,
    fetch_status: str,
) -> None:
    payload = {
        "updated_at": date.today().isoformat(),
        "source": f"Google Trends（trendspy・geo={TRENDS_GEO}・日次関心0-100）",
        "fetch_status": fetch_status,
        "stations": stations,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_trends_interest(
    tier_a: dict[str, str],
    *,
    delay: float = TRENDS_REQUEST_DELAY,
    skip_fetch: bool = False,
) -> tuple[dict[str, dict[str, int]], str]:
    """tier A 各駅の Google Trends 日次関心を取得しキャッシュにマージする。

    戻り値: (stations_data, status)
      status … live | partial | cache | empty
    """
    cached = load_trends_cache()
    if skip_fetch:
        return cached, "cache" if cached else "empty"

    if not tier_a:
        return cached, "cache" if cached else "empty"

    merged = {sid: dict(days) for sid, days in cached.items()}
    client = Trends(request_delay=delay)
    fetched, failed = 0, []

    for sid, keyword in tier_a.items():
        ok = False
        for attempt in range(3):
            try:
                df = client.interest_over_time(
                    [keyword], timeframe=TRENDS_TIMEFRAME, geo=TRENDS_GEO
                )
                col = next(c for c in df.columns if c != "isPartial")
                station_days = merged.setdefault(sid, {})
                for idx, row in df.iterrows():
                    station_days[idx.strftime("%Y-%m-%d")] = int(row[col])
                fetched += 1
                ok = True
                print(f"  Trends OK: {sid} ({keyword})")
                break
            except HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else None
                if code == 429 and attempt < 2:
                    wait = 30 * (attempt + 1)
                    print(f"  WARN: 429 {keyword} → {wait}s 待機して再試行")
                    time.sleep(wait)
                else:
                    print(f"  WARN: Trends 失敗 {sid} ({keyword}): {exc}")
                    break
            except Exception as exc:
                print(f"  WARN: Trends 失敗 {sid} ({keyword}): {exc}")
                break
        if not ok:
            failed.append(sid)

    if fetched:
        status = "live" if not failed else "partial"
        save_trends_cache(merged, fetch_status=status)
        return merged, status
    if merged:
        print("  WARN: 今回の Trends 取得は全滅。キャッシュを使用します。")
        return merged, "cache"
    return {}, "empty"


def day_has_trends(
    trends: dict[str, dict[str, int]], day_str: str, tier_a_ids: list[str]
) -> bool:
    return any(trends.get(sid, {}).get(day_str) is not None for sid in tier_a_ids)


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


def build_day(
    graph: dict,
    day: date,
    weather: dict,
    counts: dict,
    trends: dict[str, dict[str, int]] | None,
    tier_a_ids: list[str],
) -> dict:
    """1日分の駅別TDを生成する。優先: manual > trends > dummy。"""
    day_str = day.isoformat()
    prev_str = (day - timedelta(days=1)).isoformat()
    deg = node_degree(graph)
    manual = any(key[0] == day_str for key in counts)
    use_trends = (
        not manual
        and trends is not None
        and day_has_trends(trends, day_str, tier_a_ids)
    )
    td_mode = "manual" if manual else ("trends" if use_trends else "dummy")
    tier_a_set = set(tier_a_ids)

    stations = []
    for node in graph["nodes"]:
        sid = node["id"]
        if manual:
            c = counts.get((day_str, sid))
            prev = counts.get((prev_str, sid))
            if c is None:
                td, mentions, source = None, 0, "none"
            elif prev is None:
                td, mentions, source = None, c, "manual"
            else:
                td = round((c - prev) / max(prev, 1) * 100.0, 1)
                mentions, source = c, "manual"
            node_type = classify(td, mentions, MENTION_MIN_MANUAL)
        elif use_trends and sid in tier_a_set:
            cur = trends.get(sid, {}).get(day_str) if trends else None
            prev_val = trends.get(sid, {}).get(prev_str) if trends else None
            if cur is None:
                td, mentions, source = None, 0, "none"
            elif prev_val is None:
                td, mentions, source = None, cur, "trends"
            else:
                td = round((cur - prev_val) / max(prev_val, 1) * 100.0, 1)
                mentions, source = cur, "trends"
            node_type = classify(td, mentions, MENTION_MIN_TRENDS)
        elif use_trends:
            td, mentions, source = None, 0, "none"
            node_type = "mystery"
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
        "td_mode": td_mode,
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
    parser.add_argument(
        "--td-mode",
        choices=("auto", "trends", "manual", "dummy"),
        default="auto",
        help="TD生成モード（既定: auto = manual行があればmanual、なければtrends）",
    )
    parser.add_argument(
        "--skip-trends-fetch",
        action="store_true",
        help="Google Trends の再取得をスキップしキャッシュのみ使う",
    )
    args = parser.parse_args()

    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    counts = load_td_counts(args.td_csv)
    tier_a, tier_a_ids = load_td_queries()
    today = date.today()

    trends_data: dict[str, dict[str, int]] | None = None
    trends_fetch_status = "skipped"
    if args.td_mode in ("auto", "trends"):
        print(f"Trends: tier A {len(tier_a)} 駅を取得します（delay={TRENDS_REQUEST_DELAY}s）…")
        trends_data, trends_fetch_status = fetch_trends_interest(
            tier_a, skip_fetch=args.skip_trends_fetch
        )
        print(f"  Trends 状態: {trends_fetch_status}")
    elif args.td_mode == "dummy":
        trends_data = None

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
        days.append(build_day(graph, d, weather, counts, trends_data, tier_a_ids))

    daily_payload = {
        "generated_at": today.isoformat(),
        "weather_mode": weather_mode,
        "td_fetch_status": trends_fetch_status,
        "td_definition": (
            "TD = 駅別クエリ（td_queries.yaml）の日次関心 M の前日比（%）。"
            "trends: M=Google Trends 日次関心（0-100・geo=JP）。"
            "manual: M=X検索件数（td_counts.csv）。"
            "dummy: シード生成のダミー値。"
        ),
        "type_thresholds": {
            "high": f"TD > +{TD_HIGH}%",
            "mid": f"+{TD_MID}% < TD <= +{TD_HIGH}%",
            "mystery": (
                f"-{abs(TD_LOW)}% <= TD <= +{TD_MID}% "
                f"またはデータ薄（trends: 関心0 / manual: {MENTION_MIN_MANUAL}件未満 / "
                f"dummy: {MENTION_MIN_DUMMY}件未満）またはデータなし"
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
        n_trends = sum(1 for s in d["stations"] if s["td_source"] == "trends")
        n_manual = sum(1 for s in d["stations"] if s["td_source"] == "manual")
        if d["td_mode"] == "manual":
            td_info = f"manual（入力 {n_manual} 駅）"
        elif d["td_mode"] == "trends":
            td_info = f"trends（{n_trends} 駅・{trends_fetch_status}）"
        else:
            td_info = "dummy"
        print(
            f"    {d['date']}: {w['summary']} {w['temperature_c']}°C / "
            f"降水 {w['precipitation_mm']}mm / TD: {td_info}"
        )
    print(f"  駅数: {len(graph['nodes'])} / エッジ数: {len(graph['edges'])}")


if __name__ == "__main__":
    main()
