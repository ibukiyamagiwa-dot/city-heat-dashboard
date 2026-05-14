from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = BASE_DIR / "prototype_data.json"
OUTPUT_HTML = BASE_DIR / "prototype_app.html"

# 試作対象都市（必要ならここへ都市を追加）
CITY_COORDS = {
    "TOKYO": (35.6762, 139.6503),
    "OSAKA": (34.6937, 135.5023),
    "NAGOYA": (35.1815, 136.9066),
    "FUKUOKA": (33.5904, 130.4017),
}

ITERATION_STATE = {
    "version": "β再開発候補",
    "cycle": [
        {"name": "企画", "status": "done", "note": "都市熱狂度の可視化価値を定義"},
        {"name": "データ収集", "status": "done", "note": "Open-Meteoから気象データを取得"},
        {"name": "監査", "status": "doing", "note": "イベント補正が固定値のため改善対象"},
        {"name": "α版開発", "status": "done", "note": "都市カードと詳細表を実装"},
        {"name": "フィードバック", "status": "doing", "note": "見やすさと根拠表示を改善中"},
        {"name": "解決案", "status": "todo", "note": "イベントデータAPIの候補選定"},
        {"name": "β版再開発", "status": "todo", "note": "地図/推移/根拠表示を追加"},
    ],
    "todos": [
        {
            "id": "T-001",
            "title": "イベント補正を固定値から実データへ置き換える",
            "owner": "データ部門",
            "status": "未達",
            "next_action": "自治体イベントAPIまたは公開イベントカレンダーを調査",
        },
        {
            "id": "T-002",
            "title": "スコア根拠をユーザーに分かりやすく表示する",
            "owner": "開発部門",
            "status": "進行中",
            "next_action": "都市カードに計算内訳を追加",
        },
        {
            "id": "T-003",
            "title": "データ真偽監査の結果を画面上に表示する",
            "owner": "監査部門",
            "status": "進行中",
            "next_action": "出典・取得時刻・固定値利用有無を一覧化",
        },
        {
            "id": "T-004",
            "title": "β版で地図表示を追加する",
            "owner": "開発部門",
            "status": "新規",
            "next_action": "Leaflet導入可否を検証",
        },
    ],
    "feedback": [
        "α版は都市ごとの比較は分かりやすいが、スコア根拠の説明が不足している。",
        "イベント補正が固定値のため、現時点では熱狂度の一部が仮説ベースである。",
        "β版では地図・時系列推移・監査ステータスを追加すると説得力が上がる。",
    ],
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def fetch_city_weather(city: str, lat: float, lon: float) -> dict:
    """Open-Meteo から都市の最新気象データを取得する。"""
    params = urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": "Asia/Tokyo",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urlopen(url, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    current = payload.get("current", {})
    temp = float(current.get("temperature_2m", 20.0))
    precip = float(current.get("precipitation", 0.0))
    wind = float(current.get("wind_speed_10m", 3.0))

    # 都市の熱狂度（簡易版）:
    # - 気温が高いほど活動量が上がる前提で加点
    # - 降水/強風は人流抑制要因として減点
    temp_score = clamp((temp - 8.0) * 1.7, 0.0, 32.0)
    precip_penalty = clamp(precip * 5.0, 0.0, 20.0)
    wind_penalty = clamp(wind * 0.9, 0.0, 18.0)
    event_bonus = 12.0  # MVPでは固定値（将来はイベントAPI連携で置き換え）

    heat_score = clamp(52.0 + temp_score + event_bonus - precip_penalty - wind_penalty, 0, 100)

    return {
        "city": city,
        "lat": lat,
        "lon": lon,
        "temperature_c": round(temp, 1),
        "precipitation_mm": round(precip, 1),
        "wind_speed_mps": round(wind, 1),
        "event_bonus": round(event_bonus, 1),
        "heat_score": round(heat_score, 1),
        "source": "Open-Meteo (weather) + prototype fixed bonus (events)",
    }


def fallback_city_data() -> list[dict]:
    """API取得失敗時のフォールバックデータ。"""
    return [
        {
            "city": "TOKYO",
            "lat": 35.6762,
            "lon": 139.6503,
            "temperature_c": 25.2,
            "precipitation_mm": 0.0,
            "wind_speed_mps": 3.9,
            "event_bonus": 12.0,
            "heat_score": 76.4,
            "source": "fallback sample",
        },
        {
            "city": "OSAKA",
            "lat": 34.6937,
            "lon": 135.5023,
            "temperature_c": 24.0,
            "precipitation_mm": 0.4,
            "wind_speed_mps": 4.5,
            "event_bonus": 12.0,
            "heat_score": 69.5,
            "source": "fallback sample",
        },
        {
            "city": "NAGOYA",
            "lat": 35.1815,
            "lon": 136.9066,
            "temperature_c": 23.3,
            "precipitation_mm": 0.0,
            "wind_speed_mps": 2.7,
            "event_bonus": 12.0,
            "heat_score": 72.1,
            "source": "fallback sample",
        },
        {
            "city": "FUKUOKA",
            "lat": 33.5904,
            "lon": 130.4017,
            "temperature_c": 22.7,
            "precipitation_mm": 1.0,
            "wind_speed_mps": 5.0,
            "event_bonus": 12.0,
            "heat_score": 64.8,
            "source": "fallback sample",
        },
    ]


def build_dataset() -> dict:
    records: list[dict] = []
    had_error = False

    for city, (lat, lon) in CITY_COORDS.items():
        try:
            records.append(fetch_city_weather(city, lat, lon))
        except (TimeoutError, URLError, ValueError):
            had_error = True
            break

    if had_error or len(records) != len(CITY_COORDS):
        records = fallback_city_data()

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "records": records,
        "note": "prototype dataset for alpha demo",
        "iteration": ITERATION_STATE,
    }


def build_html(dataset: dict) -> str:
    data_json = json.dumps(dataset, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>都市熱狂度プロトタイプ（α/β改善ループ）</title>
  <style>
    body {{
      margin: 0;
      font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
      background: #0b1020;
      color: #e7eefc;
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 20px;
    }}
    .panel {{
      background: #141d33;
      border: 1px solid #2a3a63;
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 14px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .loop {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: stretch;
    }}
    .step {{
      flex: 1 1 135px;
      background: #1a2742;
      border: 1px solid #334b78;
      border-radius: 10px;
      padding: 10px;
    }}
    .done {{ border-color: #77dd77; }}
    .doing {{ border-color: #ffd166; }}
    .todo {{ border-color: #ff6b6b; }}
    .pill {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      background: #0f1a32;
      font-size: 12px;
      color: #b8c5df;
    }}
    .city {{
      background: #1a2742;
      border: 1px solid #334b78;
      border-radius: 10px;
      padding: 12px;
    }}
    .score {{
      font-size: 28px;
      font-weight: 800;
      margin: 6px 0;
      color: #75b7ff;
    }}
    .bar {{
      height: 10px;
      background: #0f1a32;
      border-radius: 999px;
      overflow: hidden;
    }}
    .fill {{
      height: 100%;
      background: linear-gradient(90deg, #4facfe, #00f2fe);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid #2a3a63;
      padding: 8px;
      text-align: left;
      font-size: 14px;
    }}
    .muted {{ color: #b8c5df; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="panel">
      <h1>都市熱狂度プロトタイプ（α/β改善ループ）</h1>
      <p class="muted">データ収集、監査、α版、フィードバック、解決案、β版再開発までを確認する試作画面です。</p>
      <p class="muted" id="updatedAt"></p>
    </section>

    <section class="panel">
      <h2>改善サイクル</h2>
      <div class="loop" id="cycle"></div>
    </section>

    <section class="panel">
      <h2>都市別スコア</h2>
      <div class="cards" id="cards"></div>
    </section>

    <section class="panel">
      <h2>データ詳細</h2>
      <table>
        <thead>
          <tr>
            <th>都市</th>
            <th>気温(℃)</th>
            <th>降水(mm)</th>
            <th>風速(m/s)</th>
            <th>イベント補正</th>
            <th>熱狂度</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Todo達成状況</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Todo</th>
            <th>担当</th>
            <th>状態</th>
            <th>次アクション</th>
          </tr>
        </thead>
        <tbody id="todoBody"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>フィードバックと再開発方針</h2>
      <div class="grid2">
        <div>
          <h3>フィードバック</h3>
          <ul id="feedbackList"></ul>
        </div>
        <div>
          <h3>現在の判定</h3>
          <p>β版へ進めるが、<strong>イベント補正の実データ化</strong>と<strong>監査結果表示</strong>は未達。</p>
          <p class="muted">未達Todoは次ループで解決案部門→企画/データ/開発へ差し戻す。</p>
        </div>
      </div>
    </section>
  </div>

  <script>
    const dataset = {data_json};
    const cards = document.getElementById("cards");
    const tableBody = document.getElementById("tableBody");
    const cycle = document.getElementById("cycle");
    const todoBody = document.getElementById("todoBody");
    const feedbackList = document.getElementById("feedbackList");
    document.getElementById("updatedAt").textContent = "更新時刻: " + dataset.generated_at;

    dataset.iteration.cycle.forEach((s) => {{
      const div = document.createElement("div");
      div.className = "step " + s.status;
      div.innerHTML = `<strong>${{s.name}}</strong><br><span class="pill">${{s.status}}</span><p class="muted">${{s.note}}</p>`;
      cycle.appendChild(div);
    }});

    dataset.records.forEach((r) => {{
      const card = document.createElement("div");
      card.className = "city";
      card.innerHTML = `
        <div><strong>${{r.city}}</strong></div>
        <div class="score">${{r.heat_score}}</div>
        <div class="bar"><div class="fill" style="width:${{r.heat_score}}%"></div></div>
        <div class="muted">source: ${{r.source}}</div>
      `;
      cards.appendChild(card);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${{r.city}}</td>
        <td>${{r.temperature_c}}</td>
        <td>${{r.precipitation_mm}}</td>
        <td>${{r.wind_speed_mps}}</td>
        <td>${{r.event_bonus}}</td>
        <td><strong>${{r.heat_score}}</strong></td>
      `;
      tableBody.appendChild(tr);
    }});

    dataset.iteration.todos.forEach((t) => {{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${{t.id}}</td>
        <td>${{t.title}}</td>
        <td>${{t.owner}}</td>
        <td><strong>${{t.status}}</strong></td>
        <td>${{t.next_action}}</td>
      `;
      todoBody.appendChild(tr);
    }});

    dataset.iteration.feedback.forEach((f) => {{
      const li = document.createElement("li");
      li.textContent = f;
      feedbackList.appendChild(li);
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    dataset = build_dataset()
    OUTPUT_JSON.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUTPUT_HTML.write_text(build_html(dataset), encoding="utf-8")
    print(f"作成完了: {OUTPUT_JSON}")
    print(f"作成完了: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
