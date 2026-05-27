# Graduation Project Dashboard

このリポジトリは、CrewAI の設定ファイルから確認用ダッシュボードを生成するためのものです。

## 使い方

1. `main.py` を実行して `progress.md` を更新
2. `team_dashboard.py` を実行して `index.html`（発表用）と `team_dashboard.html`（組織図）を再生成
3. GitHub に push すると GitHub Pages 側の同一URLに反映

## 更新コマンド

```powershell
.\.venv\Scripts\python.exe .\main.py
.\.venv\Scripts\python.exe .\team_dashboard.py
git add .
git commit -m "Update dashboard"
git push
```
