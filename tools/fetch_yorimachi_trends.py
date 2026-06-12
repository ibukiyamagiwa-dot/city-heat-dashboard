# -*- coding: utf-8 -*-
"""Phase 2: 寄り町の trends_query（町名）を Google Trends で取得しキャッシュする。"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from requests.exceptions import HTTPError
from trendspy import Trends

BASE = Path(__file__).resolve().parent.parent
TOWNS_PATH = BASE / "data" / "towns.json"
CACHE_PATH = BASE / "yorimachi_trends_cache.json"

TRENDS_REQUEST_DELAY = 12.0
TRENDS_TIMEFRAME = "today 1-m"
TRENDS_GEO = "JP"


def load_cache() -> dict[str, dict[str, int]]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, int]] = {}
    for tid, days in (payload.get("towns") or {}).items():
        out[tid] = {str(d): int(v) for d, v in days.items()}
    return out


def save_cache(towns: dict[str, dict[str, int]], *, fetch_status: str) -> None:
    payload = {
        "updated_at": date.today().isoformat(),
        "source": f"Google Trends（trendspy・geo={TRENDS_GEO}・町名クエリ・日次関心0-100）",
        "fetch_status": fetch_status,
        "phase": 2,
        "towns": towns,
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def curated_queries(only_missing: bool) -> list[tuple[str, str]]:
    towns_data = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    cached = load_cache() if only_missing else {}
    rows: list[tuple[str, str]] = []
    for town in towns_data["towns"]:
        if town.get("tier") == "station":
            continue
        tid = town["id"]
        query = (town.get("trends_query") or town.get("name") or "").strip()
        if not query:
            continue
        if only_missing and tid in cached and cached[tid]:
            continue
        rows.append((tid, query))
    return rows


def fetch_trends(
    queries: list[tuple[str, str]],
    *,
    delay: float,
    skip_fetch: bool,
) -> tuple[dict[str, dict[str, int]], str]:
    merged = load_cache()
    if skip_fetch:
        return merged, "cache" if merged else "empty"
    if not queries:
        return merged, "cache" if merged else "empty"

    client = Trends(request_delay=delay)
    fetched, failed = 0, []

    for tid, keyword in queries:
        ok = False
        for attempt in range(3):
            try:
                df = client.interest_over_time(
                    [keyword], timeframe=TRENDS_TIMEFRAME, geo=TRENDS_GEO
                )
                col = next(c for c in df.columns if c != "isPartial")
                station_days = merged.setdefault(tid, {})
                for idx, row in df.iterrows():
                    station_days[idx.strftime("%Y-%m-%d")] = int(row[col])
                fetched += 1
                ok = True
                save_cache(merged, fetch_status="partial")
                print(f"  OK: {tid} ({keyword})", flush=True)
                break
            except HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else None
                if code == 429 and attempt < 2:
                    wait = 30 * (attempt + 1)
                    print(f"  WARN: 429 {keyword} → {wait}s 待機")
                    time.sleep(wait)
                else:
                    print(f"  WARN: 失敗 {tid} ({keyword}): {exc}")
                    break
            except Exception as exc:
                print(f"  WARN: 失敗 {tid} ({keyword}): {exc}")
                break
        if not ok:
            failed.append(tid)

    if fetched:
        status = "live" if not failed else "partial"
        save_cache(merged, fetch_status=status)
        return merged, status
    if merged:
        print("  WARN: 今回の取得は全滅。既存キャッシュを使用します。")
        return merged, "cache"
    return {}, "empty"


def main() -> None:
    parser = argparse.ArgumentParser(description="寄り町 Phase2 Trends 取得")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="キャッシュにない町だけ取得（既定: 全手選り町）",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="ネット取得せずキャッシュのみ確認",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=TRENDS_REQUEST_DELAY,
        help=f"リクエスト間隔秒（既定 {TRENDS_REQUEST_DELAY}）",
    )
    args = parser.parse_args()

    queries = curated_queries(only_missing=args.only_missing)
    print(f"Phase2 Trends: {len(queries)} 町（only_missing={args.only_missing}）", flush=True)
    data, status = fetch_trends(
        queries,
        delay=args.delay,
        skip_fetch=args.skip_fetch,
    )
    print(f"Cache: {CACHE_PATH} status={status} towns={len(data)}")


if __name__ == "__main__":
    main()
