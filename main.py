"""
卒業制作向け CrewAI 初期チーム実行スクリプト

この版では、設定を YAML に外出ししています。
- エージェント設定: agents.yaml
- タスク設定: tasks.yaml

実行前に同じフォルダへ .env ファイルを作成し、最低限以下を設定してください。
OPENAI_API_KEY=your_api_key_here

任意でモデル名を切り替えたい場合:
OPENAI_MODEL=gpt-4o-mini
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
AGENTS_FILE = BASE_DIR / "agents.yaml"
TASKS_FILE = BASE_DIR / "tasks.yaml"


def load_yaml(path: Path) -> dict:
    """YAML ファイルを読み込む。"""
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path.name}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} の形式が不正です（辞書形式が必要です）。")
    return data


def build_agents(model_name: str, agents_config: dict) -> dict[str, Agent]:
    """agents.yaml の内容から Agent を生成する。"""
    agents: dict[str, Agent] = {}

    # キー名（planner / critic / secretary）をそのまま識別子として使う。
    for agent_key, conf in agents_config.items():
        if not isinstance(conf, dict):
            raise ValueError(f"agents.yaml の {agent_key} は辞書形式で定義してください。")

        role = conf.get("role")
        goal = conf.get("goal")
        backstory = conf.get("backstory")
        verbose = conf.get("verbose", True)

        if not role or not goal or not backstory:
            raise ValueError(
                f"agents.yaml の {agent_key} には role/goal/backstory が必要です。"
            )

        agents[agent_key] = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=model_name,
            verbose=bool(verbose),
        )

    return agents


def build_tasks(tasks_config: dict, agents: dict[str, Agent]) -> list[Task]:
    """tasks.yaml の内容から Task を順番に生成する。"""
    tasks: list[Task] = []
    tasks_by_key: dict[str, Task] = {}

    # Python 3.7+ では dict は挿入順を保持する。
    # つまり、tasks.yaml の記載順が実行順になる。
    for task_key, conf in tasks_config.items():
        if not isinstance(conf, dict):
            raise ValueError(f"tasks.yaml の {task_key} は辞書形式で定義してください。")

        agent_key = conf.get("agent")
        if not agent_key or agent_key not in agents:
            raise ValueError(
                f"tasks.yaml の {task_key}.agent が不正です。"
                "agents.yaml に存在するキーを指定してください。"
            )

        description = conf.get("description")
        expected_output = conf.get("expected_output")
        if not description or not expected_output:
            raise ValueError(
                f"tasks.yaml の {task_key} には description / expected_output が必要です。"
            )

        # context は「前のタスク結果を参照したい時」に使う。
        context_keys = conf.get("context", [])
        if context_keys is None:
            context_keys = []
        if not isinstance(context_keys, list):
            raise ValueError(f"tasks.yaml の {task_key}.context は配列で指定してください。")

        context_tasks: list[Task] = []
        for ctx_key in context_keys:
            if ctx_key not in tasks_by_key:
                raise ValueError(
                    f"tasks.yaml の {task_key}.context に未定義または後続タスク"
                    f" '{ctx_key}' が指定されています。"
                )
            context_tasks.append(tasks_by_key[ctx_key])

        task = Task(
            description=str(description).strip(),
            expected_output=str(expected_output).strip(),
            agent=agents[agent_key],
            context=context_tasks or None,
            markdown=bool(conf.get("markdown", True)),
            output_file=conf.get("output_file"),
        )

        tasks.append(task)
        tasks_by_key[task_key] = task

    return tasks


def main() -> None:
    """Crew 実行のエントリーポイント。"""
    # .env を読み込み、OPENAI_API_KEY などの環境変数を有効化する。
    load_dotenv()

    # APIキー必須チェック: 未設定時にエラー理由を明確化する。
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY が見つかりません。.env を作成して設定してください。"
        )

    # モデル名は環境変数で差し替え可能。
    # 非エンジニアでも .env を編集するだけで設定変更できる。
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    agents_config = load_yaml(AGENTS_FILE)
    tasks_config = load_yaml(TASKS_FILE)

    agents = build_agents(model_name=model_name, agents_config=agents_config)
    tasks = build_tasks(tasks_config=tasks_config, agents=agents)

    # 今回は依存関係が明確なため sequential を採用。
    # tasks.yaml の記載順で実行される。
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    print("\n=== Crew 実行完了 ===")
    print("progress.md を更新しました。")
    print("\n--- 最終出力（秘書班） ---")
    print(result)


if __name__ == "__main__":
    main()
