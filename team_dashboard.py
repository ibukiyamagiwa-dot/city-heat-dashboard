from __future__ import annotations

from datetime import datetime
from pathlib import Path
import html

import yaml


BASE_DIR = Path(__file__).resolve().parent
AGENTS_FILE = BASE_DIR / "agents.yaml"
TASKS_FILE = BASE_DIR / "tasks.yaml"
ORG_FILE = BASE_DIR / "org_structure.yaml"
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


def load_yaml_optional(path: Path) -> dict:
    if not path.exists():
        return {}
    return load_yaml(path)


def normalize_progress_markdown(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def build_task_map(tasks: dict) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for task_key, conf in tasks.items():
        if not isinstance(conf, dict):
            continue
        agent_key = conf.get("agent")
        if not agent_key:
            continue
        mapping.setdefault(agent_key, []).append(task_key)
    return mapping


def get_departments(agents: dict, org: dict) -> list[str]:
    explicit = org.get("departments")
    if isinstance(explicit, list) and explicit:
        return [str(v) for v in explicit]

    seen: list[str] = []
    for conf in agents.values():
        if not isinstance(conf, dict):
            continue
        dep = str(conf.get("department", "未分類"))
        if dep not in seen:
            seen.append(dep)
    return seen or ["未分類"]


def build_org_matrix(agents: dict, departments: list[str]) -> str:
    cells = []
    for dep in departments:
        mgmt = None
        exec_ = None
        for key, conf in agents.items():
            if not isinstance(conf, dict):
                continue
            if str(conf.get("department")) != dep:
                continue
            tier = str(conf.get("tier", "execution"))
            role = html.escape(str(conf.get("role", key)))
            key_html = html.escape(key)
            node_html = (
                f'<div class="org-node"><b>{role}</b><br /><span class="muted">{key_html}</span></div>'
            )
            if tier == "management":
                mgmt = node_html
            else:
                exec_ = node_html

        cells.append(
            f"""
            <div class="org-col">
              <div class="dep-title">{html.escape(dep)}</div>
              {mgmt or '<div class="org-node empty">未設定</div>'}
              <div class="v-arrow">↓ 縦連携</div>
              {exec_ or '<div class="org-node empty">未設定</div>'}
            </div>
            """
        )
    return "".join(cells)


def render_links(org: dict, agents: dict, link_key: str, title: str) -> str:
    links = org.get(link_key, [])
    if not isinstance(links, list) or not links:
        return f"<h3>{title}</h3><p class='muted'>リンク未定義</p>"

    rows: list[str] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        src = str(link.get("from", ""))
        dst = str(link.get("to", ""))
        note = str(link.get("note", ""))
        src_role = str(agents.get(src, {}).get("role", src))
        dst_role = str(agents.get(dst, {}).get("role", dst))
        rows.append(
            f"<li><code>{html.escape(src)}</code> ({html.escape(src_role)}) → "
            f"<code>{html.escape(dst)}</code> ({html.escape(dst_role)})"
            + (f" / {html.escape(note)}" if note else "")
            + "</li>"
        )

    return f"<h3>{title}</h3><ul>{''.join(rows)}</ul>"


def create_html(agents: dict, tasks: dict, org: dict, progress_md: str) -> str:
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_map = build_task_map(tasks)
    departments = get_departments(agents, org)

    team_title = html.escape(str(org.get("team_title", "卒業制作 CrewAI 組織図")))
    team_subtitle = html.escape(str(org.get("team_subtitle", "部門構成と進捗確認ビュー")))

    agent_cards: list[str] = []
    for agent_key, conf in agents.items():
        if not isinstance(conf, dict):
            continue
        role = html.escape(str(conf.get("role", "")))
        goal = html.escape(str(conf.get("goal", "")))
        department = html.escape(str(conf.get("department", "未分類")))
        tier = html.escape(str(conf.get("tier", "execution")))
        assigned_tasks = task_map.get(agent_key, [])
        tasks_html = "".join(
            f"<li><code>{html.escape(task_name)}</code></li>" for task_name in assigned_tasks
        ) or "<li>（未割り当て）</li>"

        agent_cards.append(
            f"""
            <section class="card">
              <h3>{role}</h3>
              <p><span class="label">キー:</span> <code>{html.escape(agent_key)}</code></p>
              <p><span class="label">部門:</span> {department}</p>
              <p><span class="label">階層:</span> {tier}</p>
              <p><span class="label">Goal:</span> {goal}</p>
              <p class="label">担当タスク:</p>
              <ul>{tasks_html}</ul>
            </section>
            """
        )

    progress_html = html.escape(progress_md)
    org_matrix_html = build_org_matrix(agents=agents, departments=departments)
    vertical_links_html = render_links(org, agents, "vertical_links", "縦連携（管理→実行）")
    horizontal_links_html = render_links(org, agents, "horizontal_links", "横連携（部門間）")

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{team_title}</title>
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
    body {{ margin: 0; font-family: "Segoe UI","Yu Gothic UI",sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
    .container {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
    h1, h2, h3 {{ margin: 0 0 10px; }}
    .muted {{ color: var(--sub); }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin-bottom: 18px; }}
    .status {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .badge {{ background: #1b243a; border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px; font-size: 14px; }}
    .ok {{ color: var(--good); font-weight: 700; }}
    .org-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .org-col {{ background: #16223a; border: 1px solid #33476f; border-radius: 10px; padding: 12px; }}
    .dep-title {{ font-weight: 700; margin-bottom: 8px; color: #9cc1ff; }}
    .org-node {{ background: #1e2e4a; border: 1px solid #3d5788; border-radius: 8px; padding: 10px; text-align: center; }}
    .org-node.empty {{ opacity: 0.5; }}
    .v-arrow {{ text-align: center; color: var(--sub); font-size: 13px; padding: 6px 0; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .card {{ background: #18233b; border: 1px solid #33476f; border-radius: 10px; padding: 14px; }}
    .label {{ color: var(--sub); font-weight: 600; }}
    code {{ background: #0f1728; border: 1px solid #2a3652; border-radius: 6px; padding: 2px 6px; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; background: #0f1728; border: 1px solid #2a3652; border-radius: 8px; padding: 14px; max-height: 520px; overflow: auto; }}
    ul {{ margin-top: 8px; }}
  </style>
</head>
<body>
  <div class="container">
    <section class="panel">
      <h1>{team_title}</h1>
      <p class="muted">{team_subtitle}</p>
      <div class="status">
        <span class="badge">部門数: <b>{len(departments)}</b></span>
        <span class="badge">エージェント数: <b>{len(agents)}</b></span>
        <span class="badge">タスク数: <b>{len(tasks)}</b></span>
        <span class="badge">最終更新: <b>{updated_at}</b></span>
        <span class="badge ok">progress.md 連携: 有効</span>
      </div>
    </section>

    <section class="panel">
      <h2>組織図（縦連携 + 横連携）</h2>
      <p class="muted">各列が部門、上段が管理、下段が実行です。列内が縦連携です。</p>
      <div class="org-grid">{org_matrix_html}</div>
    </section>

    <section class="panel">
      <h2>連携一覧</h2>
      {vertical_links_html}
      {horizontal_links_html}
    </section>

    <section class="panel">
      <h2>部門設定（agents.yaml）</h2>
      <div class="cards">{''.join(agent_cards)}</div>
    </section>

    <section class="panel">
      <h2>進捗サマリー（progress.md）</h2>
      <pre>{progress_html}</pre>
    </section>
  </div>
</body>
</html>"""


def main() -> None:
    agents = load_yaml(AGENTS_FILE)
    tasks = load_yaml(TASKS_FILE)
    org = load_yaml_optional(ORG_FILE)

    if not PROGRESS_FILE.exists():
        progress_md = "progress.md がまだ作成されていません。まず main.py を実行してください。"
    else:
        progress_md = normalize_progress_markdown(PROGRESS_FILE.read_text(encoding="utf-8"))

    html_text = create_html(agents=agents, tasks=tasks, org=org, progress_md=progress_md)
    OUTPUT_FILE.write_text(html_text, encoding="utf-8")
    INDEX_FILE.write_text(html_text, encoding="utf-8")
    print(f"作成完了: {OUTPUT_FILE}")
    print(f"作成完了: {INDEX_FILE}")


if __name__ == "__main__":
    main()
