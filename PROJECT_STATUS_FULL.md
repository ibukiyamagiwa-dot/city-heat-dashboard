# 卒業制作プロジェクト進捗共有ドキュメント

最終更新: 2026-05-15

## 1. プロジェクト概要

本プロジェクトは、CrewAI を用いて「都市の熱狂度」を分析・可視化する卒業制作アプリを開発するものである。完成物の方向性は、派手なエンタメアプリではなく、CITY SONAR のように都市ごとの状態を直感的に比較・確認できるWebダッシュボードである。

研究・制作上の中心テーマは、「複数の都市データを統合し、都市のにぎわい・活動しやすさ・注目度を、非専門家にも分かる形で可視化できるか」である。

## 2. 現在の到達段階

現在は、卒業研究ロードマップ上では Phase 2「データ設計」から Phase 3「α版プロトタイプ初期」へ進み始めた段階である。

完了していること:

- Python 3.12 の仮想環境 `.venv` 構築
- CrewAI 1.14.4 の導入
- CrewAI のエージェント/タスク設定を YAML 化
- GitHub Pages による固定URL公開
- 階層型組織図ダッシュボードの生成
- 都市熱狂度プロトタイプHTMLの生成
- Open-Meteo API から気象データ取得
- データ信頼度ラベル、監査メモ、スコア内訳表示

未完了・注意が必要なこと:

- イベントデータは未接続で、現在は `event_bonus=12.0` の固定仮説値
- 人流データは未接続
- SNS/検索トレンドは未接続
- `progress.md` はCrewAIが生成した文章であり、実装済みでない内容を含む可能性がある
- 現時点のプロトタイプは研究用の初期実証であり、完成アプリではない

## 3. 公開URL

固定公開URL:

https://ibukiyamagiwa-dot.github.io/city-heat-dashboard/

このURLは GitHub Pages で公開されており、今後 `git push` することで同じURLのまま内容が更新される。

## 4. 主要ファイル

- `main.py`
  - CrewAI を実行するメインスクリプト
  - `agents.yaml` と `tasks.yaml` を読み込み、エージェントとタスクを生成する
  - 実行結果を `progress.md` に出力する

- `agents.yaml`
  - CrewAI 上の部門/エージェント定義
  - 各部門は management と execution の二層で構成

- `tasks.yaml`
  - CrewAI の反復改善型タスク定義
  - Round1、α版、フィードバック、改善案、Round2、β版、再開発、Todo整理まで含む

- `org_structure.yaml`
  - 組織図表示用の設定
  - 階層構造、縦連携、横連携、α/β改善ループを定義

- `team_dashboard.py`
  - 組織図・進捗・データ設計をまとめた `index.html` / `team_dashboard.html` を生成

- `build_prototype.py`
  - Open-Meteo API から気象データを取得
  - `prototype_data.json` と `prototype_app.html` を生成

- `data_sources.yaml`
  - データソース定義
  - 実データ、仮説値、未接続データを信頼度付きで整理

- `score_methodology.md`
  - 都市熱狂度スコアの現行設計
  - スコア式、構成要素、監査ルール、次の改善点を記載

- `prototype_app.html`
  - 都市熱狂度の試作画面
  - 都市別スコア、スコア根拠、信頼度、Todo、改善ループを表示

- `prototype_data.json`
  - プロトタイプで使う都市データ
  - 現在は気象データ + 固定イベント補正を含む

## 5. 現在の組織構造

組織は階層型で、上位から以下のように構成されている。

Level 1: 統括

- 統括戦略室
  - `strategy_mgmt`: 統括戦略室マネージャー
  - `strategy_exec`: 統括戦略室実行担当
- PMO部門
  - `pmo_mgmt`: PMOマネージャー
  - `pmo_exec`: PMO実行担当（秘書）

Level 2: 方針・検証・改善

- 企画部門
  - `planner_mgmt`: 企画部門マネージャー
  - `planner_exec`: 企画部門実行担当
- 監査部門
  - `audit_mgmt`: 監査部門マネージャー
  - `audit_exec`: 監査部門実行担当
- 改善解決案部門
  - `solution_mgmt`: 改善解決案部門マネージャー
  - `solution_exec`: 改善解決案部門実行担当
- フィードバック部門
  - `feedback_mgmt`: フィードバック部門マネージャー
  - `feedback_exec`: フィードバック部門実行担当

Level 3: 実行

- データ部門
  - `data_mgmt`: データ部門マネージャー
  - `data_exec`: データ部門実行担当
- 開発部門
  - `dev_mgmt`: 開発部門マネージャー
  - `dev_exec`: 開発部門実行担当

## 6. 連携構造

縦連携:

- 各部門は management が方針・優先度・品質基準を管理し、execution が実作業を担当する
- 組織図では各部門内の「管理 → 実行」として表示される

横連携:

- 企画 → データ: 要件とデータ仕様の同期
- データ → 監査: データ真偽と出典確認
- 監査 → 開発: 監査指摘の実装反映
- 開発 → 企画: 実装制約の企画フィードバック
- フィードバック → 改善解決案: α/β評価を修正案へ変換
- 改善解決案 → 企画/開発: 再企画・再開発へ差し戻し

改善ループ:

- α版改善ループ:
  - 開発 → フィードバック → 改善解決案 → 企画 → データ → 監査 → 開発
- β版改善ループ:
  - 開発 → フィードバック → 改善解決案 → 開発 → 監査

## 7. CrewAIタスクフロー

現在の `tasks.yaml` は、単純な縦流れではなく、反復改善型のタスクフローになっている。

主な流れ:

1. `program_alignment_task`
   - 統括戦略室がスプリント方針を定義

2. `coordination_task`
   - PMOが未達Todo・差し戻し・フィードバック運用ルールを定義

3. `planning_round1_task`
   - 企画部門が初版企画を作成

4. `data_round1_task`
   - データ部門が必要データと取得計画を作成

5. `audit_round1_task`
   - 監査部門がデータの虚偽、出典、規約、倫理を監査

6. `dev_alpha_task`
   - 開発部門がα版実装計画を作成

7. `alpha_feedback_task`
   - フィードバック部門がα版への改善点を抽出

8. `solution_alpha_task`
   - 改善解決案部門が未達Todoを解決案へ変換

9. `cross_function_review_task`
   - PMOが部門間の矛盾や詰まりを横断レビュー

10. `planning_round2_task`
    - 企画部門が改善点を反映しRound2企画へ更新

11. `data_round2_task`
    - データ部門が真偽確認プロセスと品質KPIを更新

12. `dev_beta_task`
    - 開発部門がβ版改善計画を作成

13. `beta_feedback_task`
    - フィードバック部門がβ版の未達Todoを再抽出

14. `redevelopment_task`
    - 開発部門が再開発計画を作成

15. `todo_iteration_task`
    - PMOがTodoを達成済み、継続、新規に分類

16. `management_gate_task`
    - 監査管理側が提出可否を判定

17. `secretary_task`
    - PMO実行担当が `progress.md` を生成

## 8. データ設計

現在接続済みの実データ:

- Open-Meteo 現在気象データ
  - 気温
  - 降水量
  - 風速
  - 信頼度: high

未接続のデータ:

- 都市イベントデータ
  - 現在は `event_bonus=12.0` の固定仮説値
  - 信頼度: low

- 人流・混雑データ
  - 現在未使用
  - 候補: 公開統計、駅利用者数、混雑指標など

- SNS/検索トレンド
  - 現在未使用
  - 利用規約確認が必要

## 9. 現在のスコア式

```text
heat_score = 52.0 + temp_score + event_bonus - precip_penalty - wind_penalty
```

構成:

- `52.0`: 基準値、信頼度 medium
- `temp_score`: Open-Meteo の気温から算出、信頼度 high
- `event_bonus`: 固定仮説値、信頼度 low
- `precip_penalty`: Open-Meteo の降水量から算出、信頼度 high
- `wind_penalty`: Open-Meteo の風速から算出、信頼度 high

監査上の重要点:

- 現在の熱狂度は完全な実測値ではない
- `event_bonus` が固定値であるため、スコアの一部は仮説である
- 画面上では `audit_status` と `trust_level` で明示している

## 10. 現在のプロトタイプ

`prototype_app.html` で確認できる内容:

- 都市別スコア
- スコアバー
- データ出典
- 監査メモ
- スコア構成要素
- 信頼度ラベル
- Todo達成状況
- フィードバック
- 再開発方針
- α/β改善サイクル

現在の対象都市:

- TOKYO
- OSAKA
- NAGOYA
- FUKUOKA

## 11. 実装済みと未実装の区別

実装済み:

- CrewAI実行基盤
- YAMLによる部門/タスク設定
- 階層型組織図ダッシュボード
- GitHub Pages固定URL公開
- Open-Meteoからの気象データ取得
- 都市別スコア算出
- 信頼度ラベル表示
- スコア内訳表示
- 監査メモ表示
- Todo/フィードバック/再開発方針の表示

未実装:

- 実イベントデータ連携
- 人流データ連携
- SNS/検索トレンド連携
- 地図表示
- 時系列グラフ
- 実ユーザーフィードバックの収集
- 研究評価実験
- 卒論本文
- 発表スライド

## 12. 重要な注意点

`progress.md` は CrewAI により生成された進捗文書である。  
したがって、文中に「実装完了」とある場合でも、実際のファイル実装と一致しているとは限らない。  
実装状況の確認は `build_prototype.py`、`prototype_app.html`、`prototype_data.json`、`team_dashboard.py` を基準に行うべきである。

## 13. 次にやるべきこと

優先度A:

1. `event_bonus` を固定値から実データへ置き換える
2. イベントデータ候補を調査する
3. 人流の代替指標を決める
4. 地図表示を追加する
5. 時系列推移を追加する

優先度B:

1. 都市を増やす
2. スコア式を改善する
3. データ品質KPIを定義する
4. β版UIへ改善する

優先度C:

1. 発表用の構成図を作る
2. 卒論の研究背景を書く
3. 先行事例を整理する

## 14. 実行コマンド

ローカル確認:

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"
start .\index.html
start .\prototype_app.html
```

通常更新:

```powershell
Set-Location "C:\Users\ibuki\OneDrive\デスクトップ\卒業制作"

.\.venv\Scripts\python.exe .\main.py
.\.venv\Scripts\python.exe .\team_dashboard.py
.\.venv\Scripts\python.exe .\build_prototype.py
```

公開URLへ反映:

```powershell
$git = "C:\Program Files\Git\bin\git.exe"
& $git add .
& $git commit -m "Update project status"
& $git push
```

## 15. 現在の結論

このプロジェクトは、単なるアイデア段階ではなく、以下の実体を持つ段階まで進んでいる。

- マルチエージェント組織設計
- 反復改善型タスクフロー
- データ監査ルール
- 初期プロトタイプ
- 固定URL公開環境
- データ信頼度表示

一方で、研究として説得力を高めるには、イベントデータ・人流代替指標・時系列表示・地図表示が次の重要課題である。
