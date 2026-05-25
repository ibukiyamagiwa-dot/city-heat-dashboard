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
DATA_SOURCES_FILE = BASE_DIR / "data_sources.yaml"
SCORE_METHOD_FILE = BASE_DIR / "score_methodology.md"
OUTPUT_FILE = BASE_DIR / "team_dashboard.html"
INDEX_FILE = BASE_DIR / "index.html"

DEPARTMENT_META = {
    "統括戦略室": {
        "icon": "♕",
        "icon_label": "羅針盤 / 王冠",
        "summary": "全体方針と卒業制作としての到達点を決める司令塔。",
        "role": "研究全体の方向性、評価基準、意思決定をまとめる部門です。",
    },
    "PMO部門": {
        "icon": "✓",
        "icon_label": "カレンダー / チェックリスト",
        "summary": "進捗・連携・提出品質を見守る管理ハブ。",
        "role": "各部門の進捗を整理し、作業が迷子にならないように調整する部門です。",
    },
    "企画部門": {
        "icon": "灯",
        "icon_label": "電球",
        "summary": "都市熱狂度アプリの価値と見せ方を考える部門。",
        "role": "誰に何を伝えるアプリなのかを定義し、改善の方向性を作る部門です。",
    },
    "監査部門": {
        "icon": "盾",
        "icon_label": "虫眼鏡 / 盾",
        "summary": "データの信頼性と説明可能性を確認する部門。",
        "role": "使っているデータやスコア根拠が卒論として説明できるかを確認する部門です。",
    },
    "改善解決案部門": {
        "icon": "工",
        "icon_label": "工具 / スパナ",
        "summary": "指摘や課題を次の改善案に変換する部門。",
        "role": "フィードバックを実装可能な修正案に分解し、次の開発へ渡す部門です。",
    },
    "フィードバック部門": {
        "icon": "吹",
        "icon_label": "吹き出し",
        "summary": "見た人の反応を集め、改善点を見つける部門。",
        "role": "教授・ユーザー・非エンジニア視点の疑問や改善要望を整理する部門です。",
    },
    "データ部門": {
        "icon": "DB",
        "icon_label": "データベース",
        "summary": "気象・人流・施設などの根拠データを扱う部門。",
        "role": "公開データを集め、スコア計算に使える形へ整える部門です。",
    },
    "開発部門": {
        "icon": "</>",
        "icon_label": "ノートPC / コード",
        "summary": "ダッシュボードとプロトタイプを形にする部門。",
        "role": "企画・データ・監査の内容を画面や生成スクリプトとして実装する部門です。",
    },
}


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


def read_text_optional(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    return path.read_text(encoding="utf-8")


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


def format_task_list(task_names: list[str]) -> str:
    if not task_names:
        return "<li>（未割り当て）</li>"
    return "".join(f"<li><code>{html.escape(task_name)}</code></li>" for task_name in task_names)


def find_department_agents(agents: dict, dep: str) -> dict[str, tuple[str, dict]]:
    found: dict[str, tuple[str, dict]] = {}
    for key, conf in agents.items():
        if not isinstance(conf, dict) or str(conf.get("department")) != dep:
            continue
        tier = str(conf.get("tier", "execution"))
        found[tier] = (key, conf)
    return found


def agent_department_map(agents: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key, conf in agents.items():
        if isinstance(conf, dict):
            mapping[key] = str(conf.get("department", "未分類"))
    return mapping


def render_related_links(
    dep: str, org: dict, agents: dict, link_key: str, title: str
) -> str:
    links = org.get(link_key, [])
    if not isinstance(links, list):
        links = []
    dep_by_agent = agent_department_map(agents)
    rows: list[str] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        src = str(link.get("from", ""))
        dst = str(link.get("to", ""))
        if dep_by_agent.get(src) != dep and dep_by_agent.get(dst) != dep:
            continue
        note = html.escape(str(link.get("note", "")))
        src_role = html.escape(str(agents.get(src, {}).get("role", src)))
        dst_role = html.escape(str(agents.get(dst, {}).get("role", dst)))
        rows.append(
            f"<li><code>{html.escape(src)}</code> {src_role} → "
            f"<code>{html.escape(dst)}</code> {dst_role}"
            + (f"<br /><span class='muted'>{note}</span>" if note else "")
            + "</li>"
        )
    if not rows:
        return f"<div class='dept-links'><h4>{html.escape(title)}</h4><p class='muted'>関連連携なし</p></div>"
    return f"<div class='dept-links'><h4>{html.escape(title)}</h4><ul>{''.join(rows)}</ul></div>"


def render_agent_detail(
    title: str, item: tuple[str, dict] | None, task_map: dict[str, list[str]]
) -> str:
    if item is None:
        return f"""
        <div class="dept-agent empty">
          <h4>{html.escape(title)}</h4>
          <p class="muted">未設定</p>
        </div>
        """

    key, conf = item
    role = html.escape(str(conf.get("role", key)))
    goal = html.escape(str(conf.get("goal", "")))
    tasks_html = format_task_list(task_map.get(key, []))
    return f"""
    <div class="dept-agent">
      <h4>{html.escape(title)}</h4>
      <p><b>{role}</b><br /><code>{html.escape(key)}</code></p>
      <p class="muted">{goal}</p>
      <p class="label">担当タスク</p>
      <ul>{tasks_html}</ul>
    </div>
    """


def build_department_card(dep: str, agents: dict, task_map: dict[str, list[str]], org: dict) -> str:
    meta = DEPARTMENT_META.get(
        dep,
        {
            "icon": dep[:1],
            "icon_label": "部門",
            "summary": "この部門の役割を確認できます。",
            "role": "プロジェクト内の担当範囲を整理する部門です。",
        },
    )
    dep_agents = find_department_agents(agents, dep)
    management_html = render_agent_detail("管理担当", dep_agents.get("management"), task_map)
    execution_html = render_agent_detail("実行担当", dep_agents.get("execution"), task_map)
    vertical_html = render_related_links(dep, org, agents, "vertical_links", "関連する縦連携")
    horizontal_html = render_related_links(dep, org, agents, "horizontal_links", "関連する横連携")
    return f"""
    <details class="dept-card">
      <summary>
        <span class="dept-icon" aria-label="{html.escape(str(meta["icon_label"]))}">
          {html.escape(str(meta["icon"]))}
        </span>
        <span class="dept-summary-text">
          <strong>{html.escape(dep)}</strong>
          <small>{html.escape(str(meta["summary"]))}</small>
          <em>{html.escape(str(meta["icon_label"]))}</em>
        </span>
        <span class="tap-hint">クリックで詳細</span>
      </summary>
      <div class="dept-detail">
        <p class="dept-role">{html.escape(str(meta["role"]))}</p>
        <div class="dept-agent-grid">
          {management_html}
          {execution_html}
        </div>
        <div class="dept-link-grid">
          {vertical_html}
          {horizontal_html}
        </div>
      </div>
    </details>
    """


def build_department_overview(
    agents: dict, departments: list[str], task_map: dict[str, list[str]], org: dict
) -> str:
    cards: list[str] = []
    for dep in departments:
        cards.append(build_department_card(dep, agents, task_map, org))
    return "".join(cards)


def build_department_pyramid(agents: dict, org: dict, task_map: dict[str, list[str]]) -> str:
    layers = org.get("hierarchy_layers", [])
    if not isinstance(layers, list) or not layers:
        return f"<div class='dept-grid'>{build_department_overview(agents, get_departments(agents, org), task_map, org)}</div>"

    html_layers: list[str] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        name = html.escape(str(layer.get("name", "階層")))
        departments = layer.get("departments", [])
        if not isinstance(departments, list):
            departments = []
        cards = "".join(build_department_card(str(dep), agents, task_map, org) for dep in departments)
        html_layers.append(
            f"""
            <section class="pyramid-layer">
              <div class="pyramid-title">{name}</div>
              <div class="pyramid-row">{cards}</div>
            </section>
            """
        )
    return f"<div class='pyramid'>{''.join(html_layers)}</div>"


def build_department_column(agents: dict, dep: str) -> str:
    nodes: dict[str, str] = {}
    for key, conf in agents.items():
        if not isinstance(conf, dict) or str(conf.get("department")) != dep:
            continue
        tier = str(conf.get("tier", "execution"))
        role = html.escape(str(conf.get("role", key)))
        nodes[tier] = (
            f'<div class="org-node {html.escape(tier)}">'
            f"<b>{role}</b><br /><span class='muted'>{html.escape(key)}</span></div>"
        )

    return f"""
    <div class="hierarchy-dep">
      <div class="dep-title">{html.escape(dep)}</div>
      {nodes.get("management", '<div class="org-node empty">管理: 未設定</div>')}
      <div class="v-arrow">↓ 管理から実行へ</div>
      {nodes.get("execution", '<div class="org-node empty">実行: 未設定</div>')}
    </div>
    """


def build_hierarchy_view(agents: dict, org: dict) -> str:
    layers = org.get("hierarchy_layers", [])
    if not isinstance(layers, list) or not layers:
        return "<p class='muted'>階層設定が未定義です。</p>"

    html_layers: list[str] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        name = html.escape(str(layer.get("name", "階層")))
        departments = layer.get("departments", [])
        if not isinstance(departments, list):
            departments = []
        columns = "".join(build_department_column(agents, str(dep)) for dep in departments)
        html_layers.append(
            f"""
            <section class="hierarchy-layer">
              <h3>{name}</h3>
              <div class="hierarchy-grid">{columns}</div>
            </section>
            """
        )
    return "".join(html_layers)


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


def render_iteration_loops(org: dict, agents: dict) -> str:
    loops = org.get("iteration_loops", [])
    if not isinstance(loops, list) or not loops:
        return "<p class='muted'>改善ループ未定義</p>"

    cards = []
    for loop in loops:
        if not isinstance(loop, dict):
            continue
        name = html.escape(str(loop.get("name", "改善ループ")))
        flow = loop.get("flow", [])
        if not isinstance(flow, list):
            flow = []
        steps = []
        for key in flow:
            key_str = str(key)
            role = html.escape(str(agents.get(key_str, {}).get("role", key_str)))
            steps.append(f"<span class='loop-step'>{role}<small>{html.escape(key_str)}</small></span>")
        cards.append(f"<div class='loop-card'><h3>{name}</h3><div class='loop-flow'>{' → '.join(steps)}</div></div>")
    return "".join(cards)


def create_html(
    agents: dict,
    tasks: dict,
    org: dict,
    progress_md: str,
    data_sources_text: str,
    score_method_text: str,
) -> str:
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
    data_sources_html = html.escape(data_sources_text)
    score_method_html = html.escape(score_method_text)
    org_matrix_html = build_org_matrix(agents=agents, departments=departments)
    hierarchy_html = build_hierarchy_view(agents=agents, org=org)
    department_pyramid_html = build_department_pyramid(agents=agents, org=org, task_map=task_map)
    vertical_links_html = render_links(org, agents, "vertical_links", "縦連携（管理→実行）")
    horizontal_links_html = render_links(org, agents, "horizontal_links", "横連携（部門間）")
    iteration_loops_html = render_iteration_loops(org=org, agents=agents)

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{team_title}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --panel: #ffffff;
      --panel-soft: #fff7ed;
      --line: #e5e7eb;
      --text: #1f2937;
      --sub: #64748b;
      --accent: #f39800;
      --accent-strong: #e60012;
      --accent-yellow: #fff100;
      --good: #059669;
      --shadow: 0 12px 30px rgba(15, 23, 42, .08);
      --brand-gradient: linear-gradient(90deg, #e60012, #f39800, #fff100);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI","Yu Gothic UI",sans-serif;
      background:
        radial-gradient(circle at top left, rgba(255, 241, 0, .18), transparent 30%),
        linear-gradient(180deg, #ffffff 0%, var(--bg) 45%, #f1f5f9 100%);
      color: var(--text);
      line-height: 1.6;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
    h1, h2, h3 {{ margin: 0 0 10px; }}
    .muted {{ color: var(--sub); }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 18px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .panel::before {{
      content: "";
      display: block;
      height: 4px;
      margin: -18px -18px 14px;
      background: var(--brand-gradient);
    }}
    .status {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .badge {{ background: #fff7ed; border: 1px solid #fed7aa; border-radius: 999px; padding: 6px 12px; font-size: 14px; color: #9a3412; font-weight: 700; }}
    .ok {{ color: var(--good); font-weight: 700; }}
    .pyramid {{ display: grid; gap: 18px; }}
    .pyramid-layer {{ display: grid; gap: 10px; }}
    .pyramid-title {{
      justify-self: center;
      color: #9a3412;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      border-radius: 999px;
      padding: 6px 14px;
      font-weight: 900;
      box-shadow: 0 6px 16px rgba(243, 152, 0, .10);
    }}
    .pyramid-row {{
      display: grid;
      grid-template-columns: repeat(var(--cols, auto-fit), minmax(250px, 1fr));
      gap: 14px;
      justify-content: center;
      align-items: start;
    }}
    .pyramid-layer:nth-child(1) .pyramid-row {{ max-width: 620px; margin: 0 auto; --cols: 2; }}
    .pyramid-layer:nth-child(2) .pyramid-row {{ max-width: 1120px; margin: 0 auto; --cols: 4; }}
    .pyramid-layer:nth-child(3) .pyramid-row {{ max-width: 620px; margin: 0 auto; --cols: 2; }}
    @media (max-width: 760px) {{
      .pyramid-row,
      .pyramid-layer:nth-child(1) .pyramid-row,
      .pyramid-layer:nth-child(2) .pyramid-row,
      .pyramid-layer:nth-child(3) .pyramid-row {{
        grid-template-columns: 1fr;
        max-width: none;
      }}
    }}
    .dept-card {{
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, .07);
      overflow: hidden;
    }}
    .dept-card[open] {{ border-color: #fed7aa; box-shadow: 0 14px 30px rgba(243, 152, 0, .16); }}
    .dept-card summary {{
      list-style: none;
      cursor: pointer;
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 12px;
      align-items: center;
      padding: 14px;
      position: relative;
    }}
    .dept-card summary::-webkit-details-marker {{ display: none; }}
    .dept-card summary::before {{
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 4px;
      background: var(--brand-gradient);
    }}
    .dept-icon {{
      width: 48px;
      height: 48px;
      display: inline-grid;
      place-items: center;
      border-radius: 16px;
      background: linear-gradient(135deg, #e60012, #f39800 70%, #fff100);
      color: #ffffff;
      font-weight: 900;
      font-size: 19px;
      box-shadow: 0 8px 18px rgba(230, 0, 18, .18);
    }}
    .dept-summary-text strong {{ display: block; font-size: 1.02rem; }}
    .dept-summary-text small {{ display: block; color: var(--sub); line-height: 1.45; }}
    .dept-summary-text em {{ display: block; color: #c2410c; font-style: normal; font-size: 12px; margin-top: 3px; }}
    .tap-hint {{ color: #c2410c; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 800; white-space: nowrap; }}
    .dept-detail {{ border-top: 1px solid var(--line); padding: 14px; background: #fffdf8; }}
    .dept-role {{ margin: 0 0 12px; color: var(--text); }}
    .dept-agent-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .dept-agent {{ background: #ffffff; border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
    .dept-agent h4 {{ margin: 0 0 8px; color: var(--accent-strong); }}
    .dept-agent.empty {{ opacity: .65; }}
    .dept-link-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 12px; }}
    .dept-links {{ background: #ffffff; border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
    .dept-links h4 {{ margin: 0 0 8px; color: #9a3412; }}
    .dept-links ul {{ padding-left: 18px; }}
    .compact-section summary {{
      cursor: pointer;
      color: #9a3412;
      font-weight: 800;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      border-radius: 999px;
      padding: 8px 12px;
      display: inline-block;
      margin-top: 8px;
    }}
    .compact-section[open] summary {{ margin-bottom: 14px; }}
    .org-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .org-col {{ background: var(--panel-soft); border: 1px solid #fed7aa; border-radius: 12px; padding: 12px; }}
    .hierarchy-layer {{ margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); }}
    .hierarchy-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }}
    .hierarchy-dep {{ background: var(--panel-soft); border: 1px solid #fed7aa; border-radius: 12px; padding: 12px; }}
    .dep-title {{ font-weight: 800; margin-bottom: 8px; color: var(--accent-strong); }}
    .org-node {{ background: #ffffff; border: 1px solid var(--line); border-radius: 10px; padding: 10px; text-align: center; box-shadow: 0 6px 16px rgba(15, 23, 42, .05); }}
    .org-node.management {{ border-color: var(--accent-strong); }}
    .org-node.execution {{ border-color: var(--good); }}
    .org-node.empty {{ opacity: 0.5; }}
    .v-arrow {{ text-align: center; color: var(--sub); font-size: 13px; padding: 6px 0; }}
    .loop-card {{ background: var(--panel-soft); border: 1px solid #fed7aa; border-radius: 12px; padding: 12px; margin-top: 12px; }}
    .loop-flow {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .loop-step {{ background: #ffffff; border: 1px solid var(--line); border-radius: 999px; padding: 8px 10px; box-shadow: 0 4px 12px rgba(15, 23, 42, .05); }}
    .loop-step small {{ display: block; color: var(--sub); font-size: 11px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .card {{ background: #ffffff; border: 1px solid var(--line); border-radius: 12px; padding: 14px; box-shadow: 0 8px 22px rgba(15, 23, 42, .06); overflow: hidden; }}
    .card::before {{ content: ""; display: block; height: 4px; margin: -14px -14px 12px; background: var(--brand-gradient); }}
    .label {{ color: var(--sub); font-weight: 600; }}
    code {{ background: #fffbeb; border: 1px solid #fde68a; color: #7c2d12; border-radius: 6px; padding: 2px 6px; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; background: #fffbeb; border: 1px solid #fde68a; color: #1f2937; border-radius: 10px; padding: 14px; max-height: 520px; overflow: auto; }}
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
      <h2>ピラミッド型の階層組織図</h2>
      <p class="muted">上から統括、方針・検証・改善、実行へ降りるCrewAI組織です。部門カードを開くと、管理担当・実行担当・Goal・担当タスク・関連連携を確認できます。</p>
      {department_pyramid_html}
    </section>

    <section class="panel">
      <h2>詳しい組織図</h2>
      <p class="muted">発表時は必要に応じて開けるように、詳細な組織図は折りたたみ表示にしています。</p>
      <details class="compact-section">
        <summary>階層型組織図を開く</summary>
        <p class="muted">Level 1からLevel 3へ降りる階層構造です。各部門内は管理担当と実行担当の二台体制です。</p>
        {hierarchy_html}
      </details>
      <details class="compact-section">
        <summary>部門別二台体制を開く</summary>
        <p class="muted">各列が部門、上段が管理、下段が実行です。列内が縦連携です。</p>
        <div class="org-grid">{org_matrix_html}</div>
      </details>
    </section>

    <section class="panel">
      <h2>連携一覧</h2>
      {vertical_links_html}
      {horizontal_links_html}
    </section>

    <section class="panel">
      <h2>改善ループ（α/β → フィードバック → 解決案 → 再開発）</h2>
      {iteration_loops_html}
    </section>

    <section class="panel">
      <h2>データ設計フェーズ</h2>
      <p class="muted">実データ・仮説値・未接続データを分け、卒業研究として説明できる状態にする段階です。</p>
      <div class="cards">
        <section class="card">
          <h3>データソース定義</h3>
          <pre>{data_sources_html}</pre>
        </section>
        <section class="card">
          <h3>スコア設計</h3>
          <pre>{score_method_html}</pre>
        </section>
      </div>
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
    data_sources_text = read_text_optional(
        DATA_SOURCES_FILE,
        "data_sources.yaml がまだ作成されていません。",
    )
    score_method_text = read_text_optional(
        SCORE_METHOD_FILE,
        "score_methodology.md がまだ作成されていません。",
    )

    html_text = create_html(
        agents=agents,
        tasks=tasks,
        org=org,
        progress_md=progress_md,
        data_sources_text=data_sources_text,
        score_method_text=score_method_text,
    )
    OUTPUT_FILE.write_text(html_text, encoding="utf-8")
    INDEX_FILE.write_text(html_text, encoding="utf-8")
    print(f"作成完了: {OUTPUT_FILE}")
    print(f"作成完了: {INDEX_FILE}")


if __name__ == "__main__":
    main()
