# TD（話題変化率）データガイド

TOKYO CLIMB の主指標 **TD（Topic Delta）** の取得・運用方法です。

---

## B-2a（既定）: Google Trends 自動取得

毎朝の手動作業は不要です。ビルドスクリプトが tier A 37駅（山手線30＋主要分岐7）を自動取得します。

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"
.\.venv\Scripts\python.exe .\build_tokyo_climb.py
```

- **M(駅, d)** = Google Trends の日次関心値（0-100、`geo=JP`、キーワードは `td_queries.yaml`）
- tier A 37駅のみ色付き（山手線全30＋銀座・六本木・表参道・中目黒・豊洲・錦糸町・押上）。tier B 11駅は ❓
- グラフは **48駅**（山手30 + 分岐7 + 東西・副都心・半蔵門 簡略11）
- キャッシュ: `td_trends_cache.json`（取得失敗時に前回値を使用）
- レート制限対策: 駅ごとに約15秒間隔（全37駅で約9〜10分）
- キャッシュのみ使う: `python build_tokyo_climb.py --skip-trends-fetch`

### モードの優先順位（日付ごと）

| 優先 | 条件 | 表示 |
|------|------|------|
| 1 | `td_counts.csv` にその日の行がある | 手動観測 |
| 2 | Trends 取得成功 or キャッシュあり | Google Trends |
| 3 | 上記なし | ダミー |

---

## TD の定義（卒論に書く式）

```text
TD(駅, d) = ( M(駅, d) − M(駅, d−1) ) / max( M(駅, d−1), 1 ) × 100 [%]

M(駅, d) = Google Trends 日次関心（0-100、クエリ Q(駅)、geo=JP）
```

- クエリ集合 Q(駅) は `td_queries.yaml` で定義（変更したら changelog に追記）
- **関心値のみ**を記録。絶対値は駅間で直接比較しない（各駅を個別取得）
- 前日の M がない駅はその日 ❓（運用初日は正常）

### 卒論用：出典・限界（Trends 版）

```text
[話題性] Google Trends 日次関心（trendspy 経由・geo=JP・キーワードは td_queries.yaml）。
         信頼度 low（検索関心は SNS 言及の代理指標。絶対件数ではない）。
```

限界:
- 0-100 の相対スケール（駅ごとに独立取得のため駅間の絶対比較は不可）
- Google のレート制限により取得失敗時はキャッシュに依存
- 当日分は `isPartial` で未確定の場合あり

---

## 型分類（Trends モード）

| 分類 | 条件 |
|------|------|
| 🔴 急上昇 | TD > +8% |
| 🟠 上昇 | +3% < TD ≤ +8% |
| ❓ 横ばい/未知 | −3% ≤ TD ≤ +3%、またはデータなし（tier B 等） |
| 🟢 静か | TD < −3% |

各日の閾値は `stations_daily.json` の `days[].type_thresholds` を参照。

---

## 手動入力（上書き・検証用）

手動観測は **td_counts.csv がある日だけ** Trends より優先されます。通常運用では不要です。

### 毎朝の手順（手動を使う場合）

1. **毎日同じ時刻**に観測する（例: 朝 8:00。ズレると前日比の意味が壊れる）
2. X（旧Twitter）の検索を開き、`td_queries.yaml` の **tier A 37駅** のクエリを順に検索
   - 検索タブは「最新」
   - **直近1時間**に投稿された件数を数える（50件上限）
3. `td_counts.csv` に1駅1行で追記する

```csv
date,station_id,mention_count,note
2026-06-12,shinjuku,34,
2026-06-12,toyosu,22,
```

4. ビルドして push する

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"
.\.venv\Scripts\python.exe .\build_tokyo_climb.py
$git = "C:\Program Files\Git\bin\git.exe"
& $git add td_counts.csv stations_daily.json tokyo_climb_data.js
& $git -c user.name="Cursor Agent" -c user.email="cursor-agent@example.com" commit -m "Daily TD update"
& $git push
```

---

## 運用のコツ

- **最初の2日間**は盤面がほぼ ❓ でも正常（前日比が揃うのは3日目から）
- 毎日全48駅は不要。**tier A の37駅だけ**続けることが大事
- 観測できなかった日は無理に埋めない（欠損は「霧の濃い日」としてゲーム的に意味を持つ）
- クエリを変えたくなったら `td_queries.yaml` の changelog に日付と理由を書いてから変える

---

## 手動観測の限界（参考）

手動で X 検索件数を使う場合の限界:
- 観測窓が1時間のため、窓外のバズは捉えられない
- 件数上限50によりトップ駅同士の差は飽和する
