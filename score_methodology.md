# 都市熱狂度スコア設計 v0.3

## 現在のスコア式

```text
heat_score = 52.0 + temp_score + flow_bonus + venue_bonus - precip_penalty - wind_penalty
```

## 構成要素

- `temp_score` — Open-Meteo（high）
- `flow_bonus` — 国交省 駅別乗降客数 → `urban_indicators.csv` の station_users を正規化（4.0〜18.0）
- `venue_bonus` — 文科省 社会教育調査（劇場・音楽堂）→ `event_venues` を正規化（0.5〜6.0）
- `precip_penalty` / `wind_penalty` — Open-Meteo（high）

## 廃止したもの

- 固定 `event_bonus=12.0`（仮説値）→ 廃止
- `event_bonus` 合成フィールド → 廃止（flow + venue を個別表示）

## 将来拡張

- `entertainment_facilities`（遊園地等）— 任意。入力時のみ最大 +3.0
- OpenStreetMap による施設種別の自動取得
