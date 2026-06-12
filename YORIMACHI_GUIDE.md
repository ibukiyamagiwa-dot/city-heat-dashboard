# 寄り町（YORIMACHI）ガイド

空いた時間に、ふらっと寄れる**町**を提案する Web アプリ（制作物）。

---

## 名称

| 項目 | 内容 |
|------|------|
| 日本語 | **寄り町** |
| 読み | よりまち |
| 英字 | YORIMACHI |
| タグライン | **空いた時間に、寄れる町を。** |

## コンセプト

- **駅アプリではなく町アプリ** — ユーザーには「下北沢」「中野」など**町の風味**を見せる。鉄道路線・グラフは内部エンジン。
- **ふらっと** — 本題の旅行ではなく、ちょい寄り・小さな旅。
- **研究との関係** — [都市熱狂度ダッシュボード](prototype_app.html)（研究）・[TOKYO CLIMB](tokyo_climb.html)（試作）とは別系統の**制作物**。

## 3ステップ UX

```
Step 1  どこから出る？     検索窓 + 主要5エリア（新宿・渋谷・東京・池袋・品川）
   ↓
Step 2  どのくらい寄れる？  15 / 30 / 45 / 60 分（≒ 移動に使う時間）
   ↓
Step 3  今日の寄り町       おすすめ・近場・のんびり… から候補を選ぶ
   ↓
結果    ルート + 「今日の寄り町：〇〇 → △△（だいたい○分）」
```

## データ

| ファイル | 役割 |
|----------|------|
| `rail_graph.json` | N02 由来の駅グラフ（v0.2+）。ルート計算用 |
| `rail_graph_v01.json` | 旧48駅グラフ（TOKYO CLIMB 用・レガシー） |
| `data/towns.json` | **寄り町**マスタ（町名・風味タグ・代表駅 id） |
| `stations_index.json` | 出発地検索用インデックス |
| `yorimachi_data.js` | ブラウザ用バンドル（`build_yorimachi.py` 生成） |

### 出典（鉄道）

> 国土交通省 国土数値情報 鉄道（N02）／出典：国土交通省

## ビルド

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"

# N02 未取得時は --fetch でダウンロード（要ネット）
.\.venv\Scripts\python.exe .\build_rail_graph.py --fetch

# 寄り町 UI 用 JS 生成
.\.venv\Scripts\python.exe .\build_yorimachi.py

# 手選り町の追加（stations_index から hub を付与）
.\.venv\Scripts\python.exe .\tools\expand_towns_curated.py

# Phase2: 町名の Google Trends 取得（要ネット・約20分）
.\.venv\Scripts\python.exe .\tools\fetch_yorimachi_trends.py --only-missing
.\.venv\Scripts\python.exe .\build_yorimachi.py
```

## 実装状況

| 段階 | 内容 | 状態 |
|------|------|------|
| 0 | 本ガイド・名称 | ✅ |
| 1 | N02 → `rail_graph.json` | ✅（344 nodes / MVP+私鉄拡張） |
| 2 | `data/towns.json`（手選り95町＋駅周辺自動） | ✅ |
| 3 | `yorimachi.html` Step 1 | ✅ |
| 4 | Step 2 時間選択 | ✅ |
| 5 | Step 3 寄り町候補 | ✅ |
| 6 | 路線拡張・距離ベース所要時間・乗換ペナルティ | ✅ |
| 7 | おすすめの時間帯フィルタ（選んだ時間 ±5 分） | ✅ |
| 8 | 結果画面マップ（ルート・町中心） | ✅ |
| 9 | Trends Phase1（いま話題・今日の1町・today_hints） | ✅ |
| 10 | 町拡張（95手選り＋駅周辺 tier）・候補12件＋もっと見る・シャッフル | ✅ |
| 11 | Trends Phase2（町名クエリ取得・いま話題拡充） | ✅ |

### カテゴリ（Step 3）

| 表示名 | 意味 |
|--------|------|
| おすすめ | 選んだ移動時間の前後 ±5 分に収まる町（例: 30 分 → 25〜35 分） |
| いま話題 | Google Trends 前日比（TD）が高い順（`trends_key` がある町のみ） |
| すぐ行ける | 出発地からの移動が短い順（「近場」ではなく移動時間の短さ） |
| のんびり | 風味タグに「のんびり」を含む町 |

### 町マスタ（tier）

| tier | 意味 |
|------|------|
| `curated` | `towns.json` の手選り町（tagline・風味あり） |
| `station` | `build_yorimachi.py` が未カバー駅から自動付与（駅周辺） |

Step 3 は初回 **12 件**表示、「もっと見る」で追加、「候補をシャッフル」で並び替え。手選り町を優先して表示。

### Google Trends（Phase 1）

- `towns.json`: `trends_query`, `trends_key`, `today_hints`
- `build_yorimachi.py`: `td_trends_cache.json` から TD を付与（駅代理）
- UI: 「今日の1町（ふらっと／話題）」、結果の「今日やること」
- 信頼度 low・`trends_key` は駅・近傍の代理指標

### Google Trends（Phase 2）

- `tools/fetch_yorimachi_trends.py`: 手選り町の `trends_query`（町名）を trendspy で取得
- `yorimachi_trends_cache.json`: 町 id キーで日次関心を保存
- `build_yorimachi.py`: **町名（Phase2）→ 駅代理（Phase1）** の順で TD を付与
- UI バッジ: 「町名検索」／「駅代理」でデータ源を表示

### 天気・快適・イベント（Phase 3）

| データ | 取得 | キャッシュ | build 出力 |
|--------|------|------------|------------|
| 天気 | `tools/yorimachi_weather.py`（Open-Meteo） | ビルド時取得 | `weather_today` |
| OSM タグ | `tools/fetch_town_osm.py`（Overpass） | `town_osm_cache.json` | `research_tags`, `rain_score`, `heat_score`, `comfort` |
| 駅乗降 | `data/station_flow.yaml` | 手メンテ | `flow_score`（代表駅 slug で join） |
| イベント | `tools/fetch_tokyo_events.py` | `events_cache.json` | `events_near`, `event_pick` |

イベントソース（`data/config/tokyo_event_apis.yaml`）:

| ソース | 当日向き | 備考 |
|--------|----------|------|
| Doorkeeper API | ◎ | キー不要・`since`/`until` で今日〜7日 |
| connpass v2 | ◎ | `CONNPASS_API_KEY` 環境変数が必要 |
| 区市 OD（中央・文京・墨田） | △ | 更新は区次第・座標は API 次第 |
| 東京ビッグサイト OD | △ | 有明座標を代表点として付与 |

Step 3 タブ: **雨の日**／**暑い日**／**イベント**（2.5km 以内）。結果画面に近傍イベント 1 件＋出典表示。

```bash
python tools/fetch_town_osm.py          # 初回は時間がかかる（95 町 × Overpass）
python tools/fetch_tokyo_events.py      # 毎日実行推奨（Doorkeeper 等）
python build_yorimachi.py
# connpass も使う場合:
# $env:CONNPASS_API_KEY="..."; python tools/fetch_tokyo_events.py
```

## 関連 URL

- アプリ: [yorimachi.html](yorimachi.html)
- 研究概要: [index.html](index.html)
