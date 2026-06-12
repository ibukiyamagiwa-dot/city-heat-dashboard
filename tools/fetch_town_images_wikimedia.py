# -*- coding: utf-8 -*-
"""Fetch town cover images from Wikimedia Commons for curated towns."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
TOWNS_PATH = BASE / "data" / "towns.json"
OUT_DIR = BASE / "assets" / "towns"
CACHE_PATH = BASE / "town_images_cache.json"
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "YorimachiGradProject/1.0 (education; local build script)"
REQUEST_DELAY = 2.5
THUMB_WIDTH = 800

REJECT_LICENSE = re.compile(
    r"nc|non.?commercial|all rights reserved|fair use|copyrighted|unknown",
    re.I,
)
ACCEPT_LICENSE = re.compile(
    r"cc.?by|cc0|public domain|pd-|gfdl|free art",
    re.I,
)


def api_get(params: dict, retries: int = 5) -> dict:
    qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    url = f"{API_URL}?{qs}"
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=45) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            time.sleep(REQUEST_DELAY * (2 ** attempt))
    raise last_exc  # type: ignore[misc]


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"towns": {}}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"towns": {}}


def save_cache(payload: dict) -> None:
    payload["updated_at"] = date.today().isoformat()
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def license_ok(license_short: str) -> bool:
    if not license_short or not license_short.strip():
        return False
    if REJECT_LICENSE.search(license_short):
        return False
    return bool(ACCEPT_LICENSE.search(license_short))


def parse_metadata(info: dict) -> dict:
    meta = info.get("extmetadata") or {}

    def m(key: str) -> str:
        raw = meta.get(key, {}).get("value") or ""
        return re.sub(r"<[^>]+>", "", raw).strip()

    return {
        "license": m("LicenseShortName"),
        "artist": m("Artist") or m("Credit") or "Wikimedia contributor",
        "object_name": m("ObjectName"),
    }


def log(msg: str) -> None:
    line = msg + "\n"
    try:
        sys.stdout.write(line)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
    sys.stdout.flush()


def score_title(title: str, town: dict) -> int:
    name = town.get("name") or ""
    tid = (town.get("id") or "").replace("_", "-")
    query = town.get("trends_query") or ""
    t_lower = title.lower()
    score = 0
    if name and name in title:
        score += 10
    if query and query in title:
        score += 8
    if tid and tid in t_lower:
        score += 8
    if "tokyo" in t_lower or "\u6771\u4eac" in title:
        score += 3
    if "japan" in t_lower or "\u65e5\u672c" in title:
        score += 2
    if "station" in t_lower or "\u99c5" in title:
        score -= 4
    if "map" in t_lower or "\u5730\u56f3" in title:
        score -= 6
    if "logo" in t_lower or "icon" in t_lower:
        score -= 8
    return score


def search_candidates(query: str, limit: int = 10) -> list[dict]:
    data = api_get({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "iiurlwidth": str(THUMB_WIDTH),
    })
    pages = (data.get("query") or {}).get("pages") or {}
    rows = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime") or ""
        if not mime.startswith("image/"):
            continue
        meta = parse_metadata(info)
        if not license_ok(meta["license"]):
            continue
        thumb = info.get("thumburl") or info.get("url")
        if not thumb:
            continue
        title = page.get("title") or ""
        rows.append({
            "title": title,
            "pageid": page.get("pageid"),
            "thumburl": thumb,
            "descriptionurl": info.get("descriptionurl") or "",
            "license": meta["license"],
            "artist": meta["artist"],
            "mime": mime,
        })
    return rows


def pick_image(town: dict) -> dict | None:
    name = town.get("name") or town.get("id") or ""
    tid = town.get("id") or ""
    queries = [
        f"{name} \u6771\u4eac",
        f"{name} \u65e5\u672c",
        f"{tid} tokyo",
        name,
        town.get("trends_query") or "",
    ]
    seen = set()
    best = None
    best_score = -999
    for q in queries:
        q = (q or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        try:
            cands = search_candidates(q)
        except Exception:
            continue
        for c in cands:
            s = score_title(c["title"], town)
            if s > best_score:
                best_score = s
                best = c
        time.sleep(REQUEST_DELAY)
    return best


def download(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        data = resp.read()
    dest.write_bytes(data)


def ext_from_mime(mime: str) -> str:
    if "jpeg" in mime or "jpg" in mime:
        return ".jpg"
    if "png" in mime:
        return ".png"
    if "webp" in mime:
        return ".webp"
    return ".jpg"


def credit_line(meta: dict) -> str:
    artist = (meta.get("artist") or "Wikimedia contributor").replace("\n", " ")[:120]
    lic = meta.get("license") or "See Commons"
    return f"{artist} / Wikimedia Commons / {lic}"


def merge_town_image(town: dict, rel_path: str, meta: dict, source_url: str) -> dict:
    out = dict(town)
    out["image"] = rel_path.replace("\\", "/")
    out["image_credit"] = credit_line(meta)
    out["image_source_url"] = source_url
    return out


def persist_town(towns_data: dict, tid: str, rel: str, meta: dict, source_url: str) -> None:
    idx = next(j for j, t in enumerate(towns_data["towns"]) if t["id"] == tid)
    towns_data["towns"][idx] = merge_town_image(
        towns_data["towns"][idx], rel, meta, source_url,
    )
    note = towns_data.get("note") or ""
    extra = " image=assets/towns/* from Wikimedia Commons (fetch_town_images_wikimedia.py)."
    if extra.strip() not in note:
        towns_data["note"] = (note + extra).strip()
    TOWNS_PATH.write_text(json.dumps(towns_data, ensure_ascii=False, indent=2), encoding="utf-8")


def run(*, force: bool, limit: int | None, dry_run: bool, only_missing: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = load_cache()
    cache_towns: dict = payload.setdefault("towns", {})

    towns_data = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    towns = [t for t in towns_data["towns"] if t.get("tier") != "station"]
    if only_missing:
        towns = [t for t in towns if not t.get("image")]
    if limit:
        towns = towns[:limit]

    ok, skip, fail = 0, 0, 0
    for i, town in enumerate(towns, 1):
        tid = town["id"]
        dest_jpg = OUT_DIR / f"{tid}.jpg"
        rel = f"assets/towns/{tid}.jpg"

        if not force and town.get("image") and dest_jpg.exists():
            log(f"[{i}/{len(towns)}] skip {tid} (already set)")
            skip += 1
            continue

        if not force and dest_jpg.exists() and tid in cache_towns and cache_towns[tid].get("status") == "ok":
            meta = cache_towns[tid]
            if not dry_run:
                persist_town(towns_data, tid, town.get("image") or rel, meta, meta.get("descriptionurl", ""))
            log(f"[{i}/{len(towns)}] cache {tid}")
            ok += 1
            continue

        log(f"[{i}/{len(towns)}] fetch {tid} ({town.get('name')})")
        try:
            picked = pick_image(town)
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            log(f"  ! search failed: {exc}")
            fail += 1
            continue

        if not picked:
            log("  ! no suitable image")
            fail += 1
            cache_towns[tid] = {"status": "not_found"}
            save_cache(payload)
            continue

        if dry_run:
            log(f"  -> {picked['title']} ({picked['license']})")
            ok += 1
            continue

        ext = ext_from_mime(picked.get("mime", "image/jpeg"))
        dest = OUT_DIR / f"{tid}{ext}"
        rel = f"assets/towns/{tid}{ext}"
        try:
            download(picked["thumburl"], dest)
        except Exception as exc:
            log(f"  ! download failed: {exc}")
            fail += 1
            continue

        meta = {
            "title": picked["title"],
            "license": picked["license"],
            "artist": picked["artist"],
            "descriptionurl": picked["descriptionurl"],
            "status": "ok",
        }
        cache_towns[tid] = meta
        persist_town(towns_data, tid, rel, meta, picked["descriptionurl"])
        payload["source"] = "Wikimedia Commons API"
        save_cache(payload)
        log(f"  OK {tid}")
        ok += 1

    payload["stats"] = {"ok": ok, "skip": skip, "fail": fail}
    save_cache(payload)
    log(f"\nDone: ok={ok} skip={skip} fail={fail}")


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch town cover images from Wikimedia Commons")
    p.add_argument("--force", action="store_true", help="Re-fetch even if image exists")
    p.add_argument("--limit", type=int, default=None, help="Process first N towns only")
    p.add_argument("--dry-run", action="store_true", help="Search only, no download")
    p.add_argument("--only-missing", action="store_true", help="Skip towns that already have image")
    args = p.parse_args()
    run(force=args.force, limit=args.limit, dry_run=args.dry_run, only_missing=args.only_missing)


if __name__ == "__main__":
    main()
