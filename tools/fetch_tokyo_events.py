# -*- coding: utf-8 -*-
"""東京都オープンデータ API からイベント取得 → events_cache.json"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

BASE = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE / "data" / "config" / "tokyo_event_apis.yaml"
CACHE_PATH = BASE / "events_cache.json"
API_BASE = "https://service.api.metro.tokyo.lg.jp/api"

FIELD_MAP = {
    "イベント名": "event_name",
    "event_name": "event_name",
    "開始日": "start_date",
    "start_date": "start_date",
    "終了日": "end_date",
    "end_date": "end_date",
    "場所名称": "place_name",
    "place_name": "place_name",
    "緯度": "latitude",
    "latitude": "latitude",
    "経度": "longitude",
    "longitude": "longitude",
    "コンテンツURL": "content_url",
    "content_url": "content_url",
    "URL": "url",
    "概要": "summary",
    "summary": "summary",
}


def parse_date(text: str | None) -> date | None:
    if not text or not str(text).strip():
        return None
    s = str(text).strip().replace("-", "/")
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def normalize_hit(hit: dict, org: str) -> dict | None:
    row: dict = {}
    for key, val in hit.items():
        if key == "row":
            continue
        mapped = FIELD_MAP.get(key)
        if mapped:
            row[mapped] = val
    name = (row.get("event_name") or "").strip()
    if not name:
        return None
    lat = row.get("latitude")
    lon = row.get("longitude")
    try:
        lat_f = float(lat) if lat not in (None, "") else None
        lon_f = float(lon) if lon not in (None, "") else None
    except (TypeError, ValueError):
        lat_f, lon_f = None, None
    start = parse_date(row.get("start_date"))
    end = parse_date(row.get("end_date")) or start
    url = row.get("content_url") or row.get("url") or ""
    return {
        "event_name": name,
        "start_date": start.isoformat() if start else row.get("start_date"),
        "end_date": end.isoformat() if end else row.get("end_date"),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "place_name": (row.get("place_name") or "").strip(),
        "lat": lat_f,
        "lon": lon_f,
        "url": str(url).strip(),
        "summary": (row.get("summary") or "").strip(),
        "org": org,
        "source": "東京都オープンデータ API",
        "trust_level": "medium",
    }


def fetch_api(api_id: str, limit: int = 1000) -> list[dict]:
    url = f"{API_BASE}/{api_id}/json?limit={limit}"
    req = Request(
        url,
        data=b"{}",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "yorimachi/phase3",
        },
        method="POST",
    )
    with urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("hits") or []


def event_in_window(ev: dict, start: date, end: date) -> bool:
    es = ev.get("start")
    ee = ev.get("end") or es
    if not es:
        return False
    try:
        d_start = date.fromisoformat(es)
        d_end = date.fromisoformat(ee) if ee else d_start
    except ValueError:
        return False
    return d_start <= end and d_end >= start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="今日から何日先まで")
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    if args.skip_fetch and CACHE_PATH.exists():
        print(f"Cache exists: {CACHE_PATH}")
        return

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    sources = cfg.get("sources") or []
    all_events: list[dict] = []
    for src in sources:
        api_id = src["api_id"]
        org = src.get("org", "")
        try:
            hits = fetch_api(api_id)
            print(f"  {org}: {len(hits)} rows", flush=True)
            for h in hits:
                ev = normalize_hit(h, org)
                if ev:
                    all_events.append(ev)
        except Exception as exc:
            print(f"  WARN {org} ({api_id}): {exc}", flush=True)

    today = date.today()
    window_end = today + timedelta(days=args.days)
    filtered = [e for e in all_events if event_in_window(e, today, window_end)]

    payload = {
        "updated_at": today.isoformat(),
        "window_start": today.isoformat(),
        "window_end": window_end.isoformat(),
        "source": "東京都オープンデータ API（区市イベント一覧）",
        "trust_level": "medium",
        "license": "CC BY",
        "events": filtered,
        "events_all": all_events,
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {CACHE_PATH} window={len(filtered)} total={len(all_events)}")


if __name__ == "__main__":
    main()
