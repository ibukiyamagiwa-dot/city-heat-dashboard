# -*- coding: utf-8 -*-
"""curated 町を towns.json に追加（既存 id はスキップ）。門前仲町 hub を修正。"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TOWNS_PATH = BASE / "data" / "towns.json"
INDEX_PATH = BASE / "stations_index.json"
TRENDS_PATH = BASE / "td_trends_cache.json"

# (id, display_name, tagline, flavors, station_slug, trends_key or None)
ADDITIONS: list[tuple] = [
    ("ikebukuro", "池袋", "サブカルと百貨店の街", ["サブカル", "ショッピング"], "池袋", "ikebukuro"),
    ("shinagawa", "品川", "港と駅前の街", ["街歩き", "食"], "品川", "shinagawa"),
    ("meguro", "目黒", "坂道とカフェの街", ["カフェ", "のんびり"], "目黒", "meguro"),
    ("gotanda", "五反田", "路地裏グルメの町", ["食", "ナイト"], "五反田", "gotanda"),
    ("kitasenju", "北千住", "下町とアーケード", ["下町", "街歩き"], "北千住", None),
    ("kiyosumi", "清澄白河", "倉庫とカフェの街", ["カフェ", "アート"], "清澄白河", None),
    ("tsukiji", "築地", "市場跡と食べ歩き", ["食", "街歩き"], "築地", None),
    ("shimbashi", "新橋", "ビジネス街と居酒屋", ["食", "ナイト"], "新橋", "shimbashi"),
    ("yurakucho", "有楽町", "高架下とビアホール", ["食", "ナイト"], "有楽町", "yurakucho"),
    ("ochanomizu", "御茶ノ水", "楽器街と坂道", ["サブカル", "街歩き"], "御茶ノ水", None),
    ("kanda", "神田", "古書店と学生街", ["書店", "食"], "神田", "kanda"),
    ("takadanobaba", "高田馬場", "ラーメンと学生の街", ["食", "賑わい"], "高田馬場", "takadanobaba"),
    ("mejiro", "目白", "閑静な住宅街の散歩", ["のんびり", "街歩き"], "目白", "mejiro"),
    ("sugamo", "巣鴨", "地蔵通りと温泉", ["下町", "のんびり"], "巣鴨", "sugamo"),
    ("futakotamagawa", "二子玉川", "河川とモールの街", ["のんびり", "ショッピング"], "二子玉川", None),
    ("ogikubo", "荻窪", "ラーメンと商店街", ["食", "下町"], "荻窪", None),
    ("asagaya", "阿佐ヶ谷", "ジャズとパールロード", ["サブカル", "ライブ"], "阿佐ヶ谷", None),
    ("gakuenmae", "学芸大学", "坂道カフェの街", ["カフェ", "のんびり"], "学芸大学", None),
    ("yutenji", "祐天寺", "坂と小さな店", ["カフェ", "のんびり"], "祐天寺", None),
    ("komazawa", "駒沢大学", "公園と学生の街", ["公園", "のんびり"], "駒沢大学", None),
    ("nishinippori", "西日暮里", "繊維街と坂道", ["街歩き", "下町"], "西日暮里", "nishinippori"),
    ("komagome", "駒込", "庭園と坂道", ["のんびり", "歴史"], "駒込", "komagome"),
    ("yotsuya", "四ツ谷", "路地裏と居酒屋", ["食", "ナイト"], "四ツ谷", None),
    ("sendagaya", "千駄ヶ谷", "国技館と裏路地", ["歴史", "食"], "千駄ヶ谷", None),
    ("toranomon", "虎ノ門", "ビジネス街の高層ビュー", ["街歩き", "夜景"], "虎ノ門", None),
    ("azabujuban", "麻布十番", "商店街とスイーツ", ["食", "街歩き"], "麻布十番", None),
    ("shirokanedai", "白金高輪", "坂道と洋館の街", ["街歩き", "のんびり"], "白金高輪", None),
    ("oimachi", "大井町", "品川寄りの下町", ["下町", "街歩き"], "大井町", None),
    ("osaki", "大崎", "再開発とオフィス街", ["街歩き", "夜景"], "大崎", "osaki"),
    ("ouji", "王子", "荒川と下町", ["下町", "公園"], "王子", None),
    ("nezu", "根津", "神社と谷中近く", ["歴史", "のんびり"], "根津", None),
    ("minowa", "三ノ輪", "浅草の裏手", ["下町", "のんびり"], "三ノ輪", None),
    ("irya", "入谷", "ひょうたん島の路地", ["下町", "のんびり"], "入谷", None),
    ("iidabashi", "飯田橋", "神田川とラーメン", ["食", "街歩き"], "飯田橋", None),
    ("korakuen", "後楽園", "遊園地と大学街", ["エンタメ", "街歩き"], "後楽園", None),
    ("myogadani", "茗荷谷", "坂道と閑静な街", ["のんびり", "街歩き"], "茗荷谷", None),
    ("kojimachi", "麹町", "半蔵門と歴史", ["歴史", "街歩き"], "麹町", None),
    ("ichigaya", "市ヶ谷", "護国神社と坂", ["歴史", "街歩き"], "市ヶ谷", None),
    ("kudanshita", "九段下", "武道館と神楽坂近く", ["歴史", "街歩き"], "九段下", None),
    ("tabata", "田端", "住宅街の坂道", ["のんびり", "街歩き"], "田端", "tabata"),
    ("otsuka", "大塚", "商店街と温泉", ["下町", "食"], "大塚", "otsuka"),
    ("higashinakano", "東中野", "古着とライブバー", ["サブカル", "古着"], "東中野", None),
    ("nakanosakaue", "中野坂上", "ビル街とランチ", ["街歩き", "食"], "中野坂上", None),
    ("shiodome", "汐留", "高層ビューと浜離宮", ["夜景", "街歩き"], "汐留", None),
    ("takanawadai", "高輪台", "坂道と閑静な街", ["のんびり", "街歩き"], "高輪台", None),
    ("shinjuku", "新宿", "摩天楼と歓楽街", ["賑わい", "ナイト"], "新宿", "shinjuku"),
    ("mitaka", "三鷹", "井の頭寄りの街", ["のんびり", "公園"], "三鷹", None),
    ("yoyogihara", "代々木上原", "カフェと住宅街", ["カフェ", "のんびり"], "代々木上原", None),
    ("yoyogikoen", "代々木公園", "公園とカフェ", ["公園", "のんびり"], "代々木公園", None),
    ("hachobori", "八丁堀", "運河とビジネス街", ["街歩き", "歴史"], "八丁堀", None),
    ("kayabacho", "茅場町", "日本橋寄りのオフィス街", ["街歩き", "食"], "茅場町", None),
    ("kasumigaseki", "霞ヶ関", "官公庁と並木", ["街歩き", "歴史"], "霞ヶ関", None),
    ("nagatacho", "永田町", "国会と坂道", ["歴史", "街歩き"], "永田町", None),
    ("shirokanetakanawa", "白金台", "坂と高級住宅街", ["のんびり", "街歩き"], "白金台", None),
    ("yoga", "用賀", "田園都市線の住宅街", ["のんびり", "街歩き"], "用賀", None),
    ("gaiemmae", "外苑前", "競技場と並木", ["街歩き", "公園"], "外苑前", None),
    ("sangubashi", "参宮橋", "小田急沿いの坂", ["のんびり", "街歩き"], "参宮橋", None),
    ("kitasando", "北参道", "裏参道のカフェ", ["カフェ", "街歩き"], "北参道", None),
    ("senzoku", "千石", "文京の静かな坂", ["のんびり", "街歩き"], "千石", None),
    ("sendagi", "千駄木", "谷中に近い下町", ["下町", "のんびり"], "千駄木", None),
    ("asakusabashi", "浅草橋", "問屋街と下町", ["下町", "街歩き"], "浅草橋", None),
    ("kuramae", "蔵前", "職人街とカフェ", ["カフェ", "下町"], "蔵前", None),
    ("ningyocho", "人形町", "老舗と下町", ["歴史", "食"], "人形町", None),
    ("hamadayama", "浜田山", "閑静な坂道", ["のんびり", "街歩き"], "浜田山", None),
    ("nishiogikubo", "西荻窪", "古着とライブ", ["サブカル", "古着"], "西荻窪", None),
    ("seijogakuen", "成城学園前", "緑の住宅街", ["のんびり", "街歩き"], "成城学園前", None),
    ("okachimachi", "御徒町", "アメ横の食べ歩き", ["食", "下町"], "新御徒町", "okachimachi"),
]


def hints_for(name: str, tagline: str) -> dict:
    return {
        "default": tagline.split("と")[0] + "を1軒回る" if "と" in tagline else f"{name}を散歩",
        "high_td": "話題のスポットをチェック",
        "low_td": "路地をのんびり歩く",
    }


def main() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    by_slug = {s["slug"]: s for s in index}
    trends_keys = set()
    if TRENDS_PATH.exists():
        cache = json.loads(TRENDS_PATH.read_text(encoding="utf-8"))
        trends_keys = set((cache.get("stations") or {}).keys())

    towns_data = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    existing_ids = {t["id"] for t in towns_data["towns"]}
    added = 0

    for row in ADDITIONS:
        tid, name, tagline, flavors, slug, trends_key = row
        if tid in existing_ids:
            continue
        st = by_slug.get(slug)
        if not st:
            print(f"SKIP missing station: {slug} ({tid})")
            continue
        if trends_key and trends_key not in trends_keys:
            trends_key = None
        towns_data["towns"].append(
            {
                "id": tid,
                "name": name,
                "tagline": tagline,
                "flavors": flavors,
                "hub_node_id": st["id"],
                "lat": st["lat"],
                "lon": st["lon"],
                "in_graph": True,
                "tier": "curated",
                "trends_key": trends_key,
                "trends_query": name.replace("周辺", "").split("近く")[0],
                "today_hints": hints_for(name, tagline),
            }
        )
        existing_ids.add(tid)
        added += 1

    for town in towns_data["towns"]:
        if "tier" not in town:
            town["tier"] = "curated"
        if town["id"] == "monzen":
            st = by_slug.get("門前仲町")
            if st:
                town["hub_node_id"] = st["id"]

    towns_data["version"] = "0.2"
    towns_data["note"] = (
        "寄り町マスタ。tier=curated は手選り、tier=station は build_yorimachi で自動付与。"
        "trends_key は td_trends_cache.json の駅ID（代理）。"
    )
    TOWNS_PATH.write_text(json.dumps(towns_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Added {added} towns, total curated={len(towns_data['towns'])}")


if __name__ == "__main__":
    main()
