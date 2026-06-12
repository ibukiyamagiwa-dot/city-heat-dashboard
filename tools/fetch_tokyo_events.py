# -*- coding: utf-8 -*-
"""複数ソースからイベント取得 → events_cache.json

ソース:
  - 東京都オープンデータ（区市・Big Sight）
  - Doorkeeper 公開 API（当日向き・キー不要）
  - connpass v2（CONNPASS_API_KEY がある場合）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

BASE = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE / "data" / "config" / "tokyo_event_apis.yaml"
CACHE_PATH = BASE / "events_cache.json"
METRO_API_BASE = "https://service.api.metro.tokyo.lg.jp/api"
DOORKEEPER_BASE = "https://api.doorkeeper.jp/events"
CONNPASS_BASE = "https://connpass.com/api/v2/events/"

TOKYO_LAT_MIN = 35.45
TOKYO_LAT_MAX = 35.85
TOKYO_LON_MIN = 139.35
TOKYO_LON_MAX = 140.0

FIELD_MAP = {
    "イベント名": "event_name",
    "event_name": "event_name",
    "展示会名": "event_name",
    "開始日": "start_date",
    "start_date": "start_date",
    "会期(開始)": "start_date",
    "終了日": "end_date",
    "end_date": "end_date",
    "会期(終了)": "end_date",
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
    "内容": "summary",
    "説明": "summary",
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


def parse_iso_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_jst_date(dt: datetime) -> date:
    jst = timezone(timedelta(hours=9))
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(jst).date()


def float_or_none(val) -> float | None:
    if val in (None, ""):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def in_tokyo_bbox(lat: float, lon: float) -> bool:
    return TOKYO_LAT_MIN <= lat <= TOKYO_LAT_MAX and TOKYO_LON_MIN <= lon <= TOKYO_LON_MAX


def accept_tokyo_event(lat: float | None, lon: float | None, address: str) -> bool:
    addr = address or ""
    if lat is not None and lon is not None:
        if not in_tokyo_bbox(lat, lon):
            return False
        if "東京" not in addr and lon < 139.68:
            return False
        return True
    return "東京" in addr


def event_record(
    *,
    event_name: str,
    start: date | None,
    end: date | None,
    place_name: str = "",
    lat: float | None = None,
    lon: float | None = None,
    url: str = "",
    summary: str = "",
    org: str = "",
    source: str = "",
    source_kind: str = "",
    trust_level: str = "medium",
    event_id: str | None = None,
) -> dict:
    end_d = end or start
    return {
        "id": event_id,
        "event_name": event_name.strip(),
        "start_date": start.isoformat() if start else None,
        "end_date": end_d.isoformat() if end_d else None,
        "start": start.isoformat() if start else None,
        "end": end_d.isoformat() if end_d else None,
        "place_name": place_name.strip(),
        "lat": lat,
        "lon": lon,
        "url": url.strip(),
        "summary": (summary or "").strip()[:500],
        "org": org,
        "source": source,
        "source_kind": source_kind,
        "trust_level": trust_level,
    }


def dedupe_key(ev: dict) -> str:
    name = (ev.get("event_name") or "").lower()
    start = ev.get("start") or ""
    url = ev.get("url") or ""
    if url:
        return f"url:{url}"
    lat = ev.get("lat")
    lon = ev.get("lon")
    geo = ""
    if lat is not None and lon is not None:
        geo = f"{round(lat, 3)}:{round(lon, 3)}"
    return f"{name}|{start}|{geo}"


def merge_events(events: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for ev in events:
        key = dedupe_key(ev)
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


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


def http_get_json(url: str, headers: dict | None = None, timeout: int = 60) -> object:
    req = Request(url, headers=headers or {"User-Agent": "yorimachi/events"}, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url: str, body: bytes = b"{}", timeout: int = 60) -> object:
    req = Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "yorimachi/events",
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_ward_hit(hit: dict, org: str) -> dict | None:
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
    lat_f = float_or_none(row.get("latitude"))
    lon_f = float_or_none(row.get("longitude"))
    start = parse_date(row.get("start_date"))
    end = parse_date(row.get("end_date")) or start
    url = row.get("content_url") or row.get("url") or ""
    return event_record(
        event_name=name,
        start=start,
        end=end,
        place_name=(row.get("place_name") or "").strip(),
        lat=lat_f,
        lon=lon_f,
        url=str(url).strip(),
        summary=(row.get("summary") or "").strip(),
        org=org,
        source="東京都オープンデータ API",
        source_kind="ward_od",
        trust_level="medium",
    )


def fetch_metro_api(api_id: str, limit: int = 1000) -> list[dict]:
    url = f"{METRO_API_BASE}/{api_id}/json?limit={limit}"
    payload = http_post_json(url)
    return payload.get("hits") or []


def fetch_ward_sources(sources: list[dict]) -> list[dict]:
    out: list[dict] = []
    for src in sources:
        api_id = src["api_id"]
        org = src.get("org", "")
        try:
            hits = fetch_metro_api(api_id)
            print(f"  ward {org}: {len(hits)} rows", flush=True)
            for h in hits:
                ev = normalize_ward_hit(h, org)
                if ev:
                    out.append(ev)
        except Exception as exc:
            print(f"  WARN ward {org}: {exc}", flush=True)
    return out


def fetch_bigsight_sources(sources: list[dict]) -> list[dict]:
    out: list[dict] = []
    for src in sources:
        api_id = src["api_id"]
        org = src.get("org", "東京ビッグサイト")
        lat = float_or_none(src.get("lat"))
        lon = float_or_none(src.get("lon"))
        place = src.get("place_name") or org
        try:
            hits = fetch_metro_api(api_id)
            print(f"  bigsight {org}: {len(hits)} rows", flush=True)
            for h in hits:
                ev = normalize_ward_hit(h, org)
                if not ev:
                    continue
                if lat is not None and lon is not None:
                    ev["lat"] = lat
                    ev["lon"] = lon
                if not ev.get("place_name"):
                    ev["place_name"] = place
                ev["source_kind"] = "bigsight"
                ev["source"] = "東京都オープンデータ API（東京ビッグサイト）"
                out.append(ev)
        except Exception as exc:
            print(f"  WARN bigsight {org}: {exc}", flush=True)
    return out


def fetch_doorkeeper(
    since: date,
    until: date,
    prefecture_name: str = "東京都",
    max_pages: int = 8,
) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        params = urlencode(
            {
                "prefecture_name": prefecture_name,
                "sort": "starts_at",
                "since": since.isoformat(),
                "until": until.isoformat(),
                "page": page,
                "locale": "ja",
            }
        )
        url = f"{DOORKEEPER_BASE}?{params}"
        try:
            rows = http_get_json(
                url,
                headers={"User-Agent": "yorimachi/events", "Accept": "application/json"},
            )
        except Exception as exc:
            print(f"  WARN doorkeeper page {page}: {exc}", flush=True)
            break
        if not rows:
            break
        print(f"  doorkeeper page {page}: {len(rows)} rows", flush=True)
        for row in rows:
            ev = row.get("event") or {}
            title = (ev.get("title") or "").strip()
            if not title:
                continue
            starts = parse_iso_datetime(ev.get("starts_at"))
            ends = parse_iso_datetime(ev.get("ends_at"))
            start_d = to_jst_date(starts) if starts else None
            end_d = to_jst_date(ends) if ends else start_d
            lat_f = float_or_none(ev.get("lat"))
            lon_f = float_or_none(ev.get("long"))
            address = (ev.get("address") or "").strip()
            if not accept_tokyo_event(lat_f, lon_f, address):
                continue
            place = (ev.get("venue_name") or "").strip() or address
            out.append(
                event_record(
                    event_name=title,
                    start=start_d,
                    end=end_d,
                    place_name=place,
                    lat=lat_f,
                    lon=lon_f,
                    url=(ev.get("public_url") or "").strip(),
                    summary="",
                    org="Doorkeeper",
                    source="Doorkeeper API",
                    source_kind="doorkeeper",
                    trust_level="medium",
                    event_id=str(ev.get("id")),
                )
            )
        if len(rows) < 20:
            break
        time.sleep(1.0)
    return out


def fetch_connpass_day(api_key: str, ymd: str, prefecture: str = "tokyo") -> list[dict]:
    params = urlencode(
        {
            "prefecture": prefecture,
            "ymd": ymd,
            "count": 100,
            "order": 2,
        }
    )
    url = f"{CONNPASS_BASE}?{params}"
    req = Request(
        url,
        headers={
            "User-Agent": "yorimachi/events",
            "Accept": "application/json",
            "X-API-Key": api_key,
        },
        method="GET",
    )
    with urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("events") or []


def fetch_connpass(
    api_key: str,
    since: date,
    until: date,
) -> list[dict]:
    out: list[dict] = []
    day = since
    while day <= until:
        ymd = day.strftime("%Y%m%d")
        try:
            rows = fetch_connpass_day(api_key, ymd)
            print(f"  connpass {ymd}: {len(rows)} rows", flush=True)
            for ev in rows:
                title = (ev.get("title") or "").strip()
                if not title:
                    continue
                starts = parse_iso_datetime(ev.get("started_at"))
                ends = parse_iso_datetime(ev.get("ended_at"))
                start_d = to_jst_date(starts) if starts else day
                end_d = to_jst_date(ends) if ends else start_d
                lat_f = float_or_none(ev.get("lat"))
                lon_f = float_or_none(ev.get("lon"))
                if not accept_tokyo_event(lat_f, lon_f, place):
                    continue
                place = (ev.get("place") or ev.get("address") or "").strip()
                out.append(
                    event_record(
                        event_name=title,
                        start=start_d,
                        end=end_d,
                        place_name=place,
                        lat=lat_f,
                        lon=lon_f,
                        url=(ev.get("url") or "").strip(),
                        summary=(ev.get("description") or "")[:500],
                        org="connpass",
                        source="connpass API",
                        source_kind="connpass",
                        trust_level="medium",
                        event_id=str(ev.get("id")),
                    )
                )
        except Exception as exc:
            print(f"  WARN connpass {ymd}: {exc}", flush=True)
        day += timedelta(days=1)
        time.sleep(1.1)
    return out


def count_by_kind(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in events:
        kind = ev.get("source_kind") or "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="今日から何日先まで")
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    if args.skip_fetch and CACHE_PATH.exists():
        print(f"Cache exists: {CACHE_PATH}")
        return

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    today = date.today()
    window_end = today + timedelta(days=args.days)

    all_parts: list[dict] = []
    fetch_log: dict[str, int] = {}

    ward = fetch_ward_sources(cfg.get("ward_sources") or [])
    fetch_log["ward_od"] = len(ward)
    all_parts.extend(ward)

    bigsight = fetch_bigsight_sources(cfg.get("bigsight_sources") or [])
    fetch_log["bigsight"] = len(bigsight)
    all_parts.extend(bigsight)

    dk_cfg = cfg.get("doorkeeper") or {}
    if dk_cfg.get("enabled", True):
        dk = fetch_doorkeeper(
            today,
            window_end,
            prefecture_name=dk_cfg.get("prefecture_name", "東京都"),
            max_pages=int(dk_cfg.get("max_pages", 8)),
        )
        fetch_log["doorkeeper"] = len(dk)
        all_parts.extend(dk)
    else:
        fetch_log["doorkeeper"] = 0

    cp_cfg = cfg.get("connpass") or {}
    api_key = (cp_cfg.get("api_key") or os.environ.get("CONNPASS_API_KEY") or "").strip()
    if cp_cfg.get("enabled", True) and api_key:
        cp = fetch_connpass(api_key, today, window_end)
        fetch_log["connpass"] = len(cp)
        all_parts.extend(cp)
    else:
        fetch_log["connpass"] = 0
        if cp_cfg.get("enabled", True):
            print("  connpass: skipped (set CONNPASS_API_KEY)", flush=True)

    merged = merge_events(all_parts)
    filtered = [e for e in merged if event_in_window(e, today, window_end)]
    with_coords = [e for e in filtered if e.get("lat") is not None and e.get("lon") is not None]

    payload = {
        "updated_at": today.isoformat(),
        "window_start": today.isoformat(),
        "window_end": window_end.isoformat(),
        "source": "複数ソース（区市OD・Doorkeeper・connpass・Big Sight）",
        "trust_level": "medium",
        "license": "各ソースのライセンスに準拠（CC BY 等）",
        "fetch_log": fetch_log,
        "events": filtered,
        "events_with_coords": len(with_coords),
        "events_all": merged,
        "source_counts": count_by_kind(merged),
        "window_source_counts": count_by_kind(filtered),
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {CACHE_PATH} window={len(filtered)} "
        f"(coords={len(with_coords)}) total={len(merged)} log={fetch_log}",
        flush=True,
    )


if __name__ == "__main__":
    main()
