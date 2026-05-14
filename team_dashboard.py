from __future__ import annotations

from datetime import datetime
from pathlib import Path
import html

import yaml


BASE_DIR = Path(__file__).resolve().parent
AGENTS_FILE = BASE_DIR / "agents.yaml"
TASKS_FILE = BASE_DIR / "tasks.yaml"
PROGRESS_FILE = BASE_DIR / "progress.md"
OUTPUT_FILE = BASE_DIR / "team_dashboard.html"
INDEX_FILE = BASE_DIR / "index.html"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path.name} が見つかりません。")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} の形式が不正です。")
    return data


def normalize_progress_markdown(text: str) -> str:
    """progress.md の先頭末尾にある ```markdown フェンスを除去する。"""
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def build_task_map(tasks: dict) -> dict[str, list[str]]:
    """agent_key -> その担当タスク名一覧 に変換する。"""
    mapping: dict[str, list[str]] = {}
    for task_key, conf in tasks.items():
        if not isinstance(conf, dict):
            continue
        agent_key = conf.get("agent")
        if not agent_key:
            continue
        mapping.setdefault(agent_key, []).append(task_key)
    return mapping


def create_html(agents: dict, tasks: dict, progress_md: str) -> str:
    task_map = build_task_map(tasks)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 部門カードを動的生成
    agent_cards: list[str] = []
    for agent_key, conf in agents.items():
        role = html.escape(str(conf.get("role", "")))
        goal = html.escape(str(conf.get("goal", "")))
        backstory = html.escape(str(conf.get("backstory", "")))
        verbose = "有効" if conf.get("verbose", True) else "無効"
        assigned_tasks = task_map.get(agent_key, [])
        tasks_html = "".join(
            f"<li><code>{html.escape(task_name)}</code></li>" for task_name in assigned_tasks
        ) or "<li>（未割り当て）</li>"

        agent_cards.append(
            f"""
            <section class="card">
              <h3>{role}</h3>
              <p><span class="label">キー:</span> <code>{html.escape(agent_key)}</code></p>
              <p><span class="label">Goal:</span> {goal}</p>
              <p><span class="label">Backstory:</span> {backstory}</p>
              <p><span class="label">Verboseログ:</span> {verbose}</p>
              <p class="label">担当タスク:</p>
              <ul>{tasks_html}</ul>
            </section>
            """
        )

    # 組織図ノードを agents.yaml の定義から動的生成
    org_nodes: list[str] = []
    for agent_key, conf in agents.items():
        role = html.escape(str(conf.get("role", agent_key)))
        org_nodes.append(
            f'<div class="org-node"><b>{role}</b><br /><span class="muted">{html.escape(agent_key)}</span></div>'
        )

    progress_html = html.escape(progress_md)

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CrewAI 初期チーム確認画面</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #131a2a;
      --line: #2f3b59;
      --text: #e8edf7;
      --sub: #b7c1d9;
      --accent: #6ea8fe;
      --good: #77dd77;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1, h2, h3 {{ margin: 0 0 10px; }}
    .muted {{ color: var(--sub); }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 18px;
    }}
    .status {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .badge {{
      background: #1b243a;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 14px;
    }}
    .org {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      justify-items: center;
      margin-top: 10px;
    }}
    .org-row {{
      width: 100%;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
    }}
    .org-node {{
      background: #18233b;
      border: 1px solid #3b4b70;
      border-radius: 10px;
      padding: 12px;
      text-align: center;
      min-height: 74px;
    }}
    .org-main {{
      width: min(420px, 100%);
      border-color: var(--accent);
    }}
    .line {{
      width: 2px;
      height: 24px;
      background: var(--line);
    }}
    .line-h {{
      width: calc(100% - 120px);
      height: 2px;
      background: var(--line);
      margin-bottom: 6px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: #18233b;
      border: 1px solid #33476f;
      border-radius: 10px;
      padding: 14px;
    }}
    .label {{
      color: var(--sub);
      font-weight: 600;
    }}
    code {{
      background: #0f1728;
      border: 1px solid #2a3652;
      border-radius: 6px;
      padding: 2px 6px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #0f1728;
      border: 1px solid #2a3652;
      border-radius: 8px;
      padding: 14px;
      max-height: 520px;
      overflow: auto;
    }}
    .ok {{ color: var(--good); font-weight: 700; }}
  </style>
</head>
<body>
  <div class="container">
    <section class="panel">
      <h1>CrewAI 初期チーム確認画面</h1>
      <p class="muted">卒業制作向けの部門構成と進捗を確認するビューです。</p>
      <div class="status">
        <span class="badge">エージェント数: <b>{len(agents)}</b></span>
        <span class="badge">タスク数: <b>{len(tasks)}</b></span>
        <span class="badge">最終更新: <b>{updated_at}</b></span>
        <span class="badge ok">progress.md 連携: 有効</span>
      </div>
    </section>

    <section class="panel">
      <h2>組織図（確認用）</h2>
      <div class="org">
        <div class="org-node org-main">
          <b>卒業制作 CrewAI チーム</b><br />
          <span class="muted">都市の熱狂度分析 × エンタメアプリ開発</span>
        </div>
        <div class="line"></div>
        <div class="line-h"></div>
        <div class="org-row">
          {''.join(org_nodes)}
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>部門設定（agents.yaml）</h2>
      <div class="cards">
        {''.join(agent_cards)}
      </div>
    </section>

    <section class="panel">
      <h2>進捗サマリー（progress.md）</h2>
      <pre>{progress_html}</pre>
    </section>
  </div>
</body>
</html>
"""


def main() -> None:
    agents = load_yaml(AGENTS_FILE)
    tasks = load_yaml(TASKS_FILE)
    if not PROGRESS_FILE.exists():
        progress_md = "progress.md がまだ作成されていません。まず main.py を実行してください。"
    else:
        progress_md = normalize_progress_markdown(
            PROGRESS_FILE.read_text(encoding="utf-8")
        )

    html_text = create_html(agents=agents, tasks=tasks, progress_md=progress_md)
    OUTPUT_FILE.write_text(html_text, encoding="utf-8")
    # GitHub Pages でルートURL表示できるように index.html も同時更新する
    INDEX_FILE.write_text(html_text, encoding="utf-8")
    print(f"作成完了: {OUTPUT_FILE}")
    print(f"作成完了: {INDEX_FILE}")


if __name__ == "__main__":
    main()
