# 手動データ入力ガイド

`urban_indicators.csv` の **entertainment_facilities（エンタメ施設数）** だけ、あなたが e-Stat から取得して入力します。  
それ以外（人流・イベント会場）はすでに正式データで更新済みです。

---

## 現在の CSV 状態

| 列 | 状態 | 出典 |
|----|------|------|
| station_users | ✅ 更新済み | 国土交通省 国土数値情報 駅別乗降客数（2023年度） |
| event_venues | ✅ 更新済み | 文部科学省 社会教育調査 令和3年度（劇場・音楽堂） |
| entertainment_facilities | ⏳ **あなたが入力** | 総務省 令和3年経済センサス-活動調査 R92 |

---

## 手順 1：e-Stat を開く

1. ブラウザで以下を開く  
   https://www.e-stat.go.jp/stat-search/database?statdisp_id=0004005687

2. ページ内の **「9-1A 産業(小分類)別全事業所数－全国、都道府県、市区町村」** を探す

3. **「CSV」または「EXCEL」** をクリックしてダウンロード  
   （ファイル名の例: `h29_a0911.csv` や `.xlsx`）

---

## 手順 2：R92「公園，遊園地」の事業所数を探す

1. ダウンロードしたファイルを Excel で開く

2. 次の条件で行を探す  
   - **産業小分類**: `R92` または `公園，遊園地`  
   - **区分**: 事業所数

3. 次の都道府県の数値をメモする

| CSVの city | 探す都道府県 | entertainment_facilities に入れる値 |
|------------|-------------|-------------------------------------|
| TOKYO | 東京都 | （ここに事業所数） |
| OSAKA | 大阪府 | （ここに事業所数） |
| NAGOYA | 愛知県 | （ここに事業所数） |
| FUKUOKA | 福岡県 | （ここに事業所数） |

> ヒント: Excel の「検索」（Ctrl+F）で `公園` または `R92` と都道府県名を探すと早いです。

---

## 手順 3：CSV を編集する

1. `urban_indicators.csv` を Cursor または Excel で開く

2. **entertainment_facilities 列**（現在空白）に、手順2でメモした4つの数値を入力

   例（数値はあなたが取得した正式値に置き換え）:
   ```csv
   TOKYO,東京都,4250258,45,132,...
   OSAKA,大阪府,2028399,28,69,...
   ```

3. 保存する

---

## 手順 4：プロトタイプを再生成する

PowerShell で実行:

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"
.\.venv\Scripts\python.exe .\build_prototype.py
Start-Process .\prototype_app.html
```

画面で確認すること:
- 都市ごとに **人流補正** が異なる（東京 > 大阪 > 名古屋 > 福岡）
- **エンタメ補正** が 0 以外になっている
- 監査メモに「CSV人流データ接続済み」と表示される

---

## 手順 5（任意）：GitHub Pages に公開

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"
$git = "C:\Program Files\Git\bin\git.exe"
& $git add urban_indicators.csv prototype_data.json prototype_app.html MANUAL_DATA_GUIDE.md
& $git commit -m "正式オープンデータでCSVを更新（エンタメ施設数は経済センサス値）"
& $git push
```

---

## 卒論用：出典の書き方

```
[人流] 国土交通省, 国土数値情報 駅別乗降客数（2023年度）, CC BY 4.0
       https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-2024.html

[イベント会場] 文部科学省, 社会教育調査 令和3年度, 劇場・音楽堂施設数
              https://www.e-stat.go.jp/stat-search/files?stat_infid=000040054602

[エンタメ施設] 総務省, 令和3年経済センサス-活動調査, 産業小分類 R92 公園，遊園地
               https://www.e-stat.go.jp/stat-search/database?statdisp_id=0004005687
```

---

## うまくいかないとき

| 症状 | 対処 |
|------|------|
| e-Stat が重い / 英語になる | 右上の言語を「日本語」に |
| R92 が見つからない | 表 9-1A の「小分類名」列をスクロールして `公園` で検索 |
| CSV 保存後に文字化け | UTF-8 で保存（Excel なら「CSV UTF-8」） |
| スコアが変わらない | `build_prototype.py` を再実行したか確認 |

入力が終わったら「入力完了」と送ってください。動作確認と公開まで進めます。
