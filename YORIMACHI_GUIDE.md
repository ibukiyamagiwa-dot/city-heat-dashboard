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
```

## 実装状況

| 段階 | 内容 | 状態 |
|------|------|------|
| 0 | 本ガイド・名称 | ✅ |
| 1 | N02 → `rail_graph.json` | ✅（213 nodes / MVP路線） |
| 2 | `data/towns.json`（28町） | ✅ |
| 3 | `yorimachi.html` Step 1 | ✅ |
| 4 | Step 2 時間選択 | ✅ |
| 5 | Step 3 寄り町候補 | ✅ |

## 関連 URL

- アプリ: [yorimachi.html](yorimachi.html)
- 研究概要: [index.html](index.html)
