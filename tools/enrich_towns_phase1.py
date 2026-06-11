# -*- coding: utf-8 -*-
"""Phase1: towns.json に trends_query / trends_key / today_hints を付与。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TOWNS_PATH = BASE / "data" / "towns.json"

META = {
    "shimokitazawa": {
        "trends_key": None,
        "trends_query": "下北沢",
        "today_hints": {
            "default": "古着屋とライブハウスを1軒",
            "high_td": "話題のイベント・新店をチェック",
            "low_td": "路地をのんびり散歩",
        },
    },
    "nakano": {
        "trends_key": None,
        "trends_query": "中野",
        "today_hints": {
            "default": "ブックカフェで一冊探す",
            "high_td": "サブカルスポットを1軒回る",
            "low_td": "中野坂上までゆっくり歩く",
        },
    },
    "kichijoji": {
        "trends_key": None,
        "trends_query": "吉祥寺",
        "today_hints": {
            "default": "井の頭公園でひと息",
            "high_td": "話題の雑貨店へ寄る",
            "low_td": "公園ベンチで夕方まで",
        },
    },
    "yanaka": {
        "trends_key": None,
        "trends_query": "谷中",
        "today_hints": {
            "default": "猫の路地を歩く",
            "high_td": "谷中銀座をブラブラ",
            "low_td": "静かな坂道をのんびり",
        },
    },
    "asakusa": {
        "trends_key": "oshiage",
        "trends_query": "浅草",
        "today_hints": {
            "default": "雷門から仲見世を歩く",
            "high_td": "話題のスポットをチェック",
            "low_td": "川沿いを静かに散歩",
        },
    },
    "ueno": {
        "trends_key": "ueno",
        "trends_query": "上野",
        "today_hints": {
            "default": "公園とアメ横を回る",
            "high_td": "話題のイベントを覗く",
            "low_td": "公園でゆっくり過ごす",
        },
    },
    "akihabara": {
        "trends_key": "akihabara",
        "trends_query": "秋葉原",
        "today_hints": {
            "default": "電気街を1周",
            "high_td": "話題のポップカルチャーをチェック",
            "low_td": "混雑前に裏通りを歩く",
        },
    },
    "kagurazaka": {
        "trends_key": None,
        "trends_query": "神楽坂",
        "today_hints": {
            "default": "坂道と小料理屋を1軒",
            "high_td": "話題の店を1軒予約",
            "low_td": "石畳をのんびり歩く",
        },
    },
    "ginza": {
        "trends_key": "ginza",
        "trends_query": "銀座",
        "today_hints": {
            "default": "並木通りを歩く",
            "high_td": "話題のショップを覗く",
            "low_td": "路地裏カフェで一息",
        },
    },
    "nihombashi": {
        "trends_key": None,
        "trends_query": "日本橋",
        "today_hints": {
            "default": "老舗と橋の景色を見る",
            "high_td": "話題のエリアをチェック",
            "low_td": "ビジネス街の静かな路地へ",
        },
    },
    "tokyo": {
        "trends_key": "tokyo",
        "trends_query": "東京駅",
        "today_hints": {
            "default": "赤レンガ駅舎を眺める",
            "high_td": "グランルーフの話題店へ",
            "low_td": "駅周辺を短く散歩",
        },
    },
    "harajuku": {
        "trends_key": "harajuku",
        "trends_query": "原宿",
        "today_hints": {
            "default": "竹下通りと裏原を歩く",
            "high_td": "話題のファッション店へ",
            "low_td": "代々木公園側を散歩",
        },
    },
    "omotesando": {
        "trends_key": "omotesando",
        "trends_query": "表参道",
        "today_hints": {
            "default": "ケヤキ並木を歩く",
            "high_td": "話題のブティックを覗く",
            "low_td": "カフェでゆっくり",
        },
    },
    "shibuya": {
        "trends_key": "shibuya",
        "trends_query": "渋谷",
        "today_hints": {
            "default": "スクランブル周辺を歩く",
            "high_td": "いま話題のスポットへ",
            "low_td": "混雑前に路地を散歩",
        },
    },
    "ebisu": {
        "trends_key": "ebisu",
        "trends_query": "恵比寿",
        "today_hints": {
            "default": "居酒屋横丁で一杯",
            "high_td": "話題のビアホールへ",
            "low_td": "坂道をのんびり歩く",
        },
    },
    "nakameguro": {
        "trends_key": "nakameguro",
        "trends_query": "中目黒",
        "today_hints": {
            "default": "目黒川沿いのカフェへ",
            "high_td": "話題のカフェを1軒",
            "low_td": "川沿いを静かに歩く",
        },
    },
    "roppongi": {
        "trends_key": "roppongi",
        "trends_query": "六本木",
        "today_hints": {
            "default": "美術館か夜景スポットへ",
            "high_td": "話題の展示・夜景をチェック",
            "low_td": "丘の上を短く散歩",
        },
    },
    "yoyogi": {
        "trends_key": "yoyogi",
        "trends_query": "代々木",
        "today_hints": {
            "default": "公園でひと休み",
            "high_td": "話題のライブ・イベントへ",
            "low_td": "公園のベンチで読書",
        },
    },
    "okubo": {
        "trends_key": "shinokubo",
        "trends_query": "大久保",
        "today_hints": {
            "default": "多国籍の食べ歩き",
            "high_td": "話題の韓国街グルメへ",
            "low_td": "路地をのんびり歩く",
        },
    },
    "kinshicho": {
        "trends_key": "kinshicho",
        "trends_query": "錦糸町",
        "today_hints": {
            "default": "下町と映画館を楽しむ",
            "high_td": "話題のエンタメをチェック",
            "low_td": "北口の静かな路地へ",
        },
    },
    "monzen": {
        "trends_key": None,
        "trends_query": "門前仲町",
        "today_hints": {
            "default": "運河沿いの居酒屋へ",
            "high_td": "話題の店を1軒",
            "low_td": "運河を眺めながら散歩",
        },
    },
    "toyosu": {
        "trends_key": "toyosu",
        "trends_query": "豊洲",
        "today_hints": {
            "default": "湾岸を歩く",
            "high_td": "話題の施設をチェック",
            "low_td": "海風を感じて散歩",
        },
    },
    "odaiba": {
        "trends_key": "toyosu",
        "trends_query": "お台場",
        "today_hints": {
            "default": "ベイエリアを散歩",
            "high_td": "話題の夜景スポットへ",
            "low_td": "海辺をゆっくり歩く",
        },
    },
    "ryogoku": {
        "trends_key": None,
        "trends_query": "両国",
        "today_hints": {
            "default": "国技館周辺を歩く",
            "high_td": "相撲・下町の話題をチェック",
            "low_td": "江戸情緒の路地を散歩",
        },
    },
    "daikanyama": {
        "trends_key": "nakameguro",
        "trends_query": "代官山",
        "today_hints": {
            "default": "ブティックとカフェを1軒",
            "high_td": "話題の店を覗く",
            "low_td": "丘の上をのんびり",
        },
    },
    "jiyugaoka": {
        "trends_key": None,
        "trends_query": "自由が丘",
        "today_hints": {
            "default": "スイーツと雑貨を楽しむ",
            "high_td": "話題のスイーツ店へ",
            "low_td": "住宅街を散歩",
        },
    },
    "koenji": {
        "trends_key": None,
        "trends_query": "高円寺",
        "today_hints": {
            "default": "古着屋を1軒回る",
            "high_td": "話題のライブバーへ",
            "low_td": "路地をのんびり歩く",
        },
    },
    "sangenchaya": {
        "trends_key": None,
        "trends_query": "三軒茶屋",
        "today_hints": {
            "default": "三角地帯の居酒屋へ",
            "high_td": "話題の店を1軒",
            "low_td": "坂道を短く散歩",
        },
    },
}

towns = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
towns["note"] = (
    "寄り町マスタ。trends_key は td_trends_cache.json の駅ID（代理）。"
    "today_hints は Google Trends 前日比で切り替え。"
)
for town in towns["towns"]:
    extra = META[town["id"]]
    town.update(extra)

TOWNS_PATH.write_text(json.dumps(towns, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Updated {len(towns['towns'])} towns")
