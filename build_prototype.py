from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = BASE_DIR / "prototype_data.json"
OUTPUT_HTML = BASE_DIR / "prototype_app.html"
DATA_SOURCES_FILE = BASE_DIR / "data_sources.yaml"
URBAN_CSV = BASE_DIR / "urban_indicators.csv"

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
        {"name": "データ収集", "status": "done", "note": "Open-Meteo + CSV人流データを取得"},
        {"name": "監査", "status": "doing", "note": "CSV出典の正式化と数値検証を継続"},
        {"name": "α版開発", "status": "done", "note": "都市カードと詳細表を実装"},
        {"name": "フィードバック", "status": "doing", "note": "見やすさと根拠表示を改善中"},
        {"name": "解決案", "status": "doing", "note": "劇場・音楽堂データをスコアに接続済み。追加施設は将来拡張"},
        {"name": "β版再開発", "status": "todo", "note": "地図/推移/根拠表示を追加"},
    ],
    "todos": [
        {
            "id": "T-001",
            "title": "CSV人流データをスコア計算に接続する",
            "owner": "データ部門",
            "status": "達成",
            "next_action": "正式なオープンデータ出典へ差し替え",
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
        {
            "id": "T-005",
            "title": "event_venues（劇場・音楽堂）をスコア計算に接続する",
            "owner": "データ部門",
            "status": "達成",
            "next_action": "OpenStreetMap等での施設種別拡張を検討",
        },
    ],
    "feedback": [
        "α版は都市ごとの比較は分かりやすいが、スコア根拠の説明が不足している。",
        "人流と劇場・音楽堂数の接続により、都市間差が公的データベースで説明できる。",
        "β版では地図・時系列推移・監査ステータスを追加すると説得力が上がる。",
    ],
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def normalize_to_range(
    value: float, min_v: float, max_v: float, out_min: float, out_max: float
) -> float:
    if max_v <= min_v:
        return (out_min + out_max) / 2
    ratio = (value - min_v) / (max_v - min_v)
    return out_min + ratio * (out_max - out_min)


def parse_csv_int(value: str | None, default: int = 0) -> int:
    text = (value or "").strip()
    if not text:
        return default
    return int(text)


def load_urban_indicators() -> dict[str, dict]:
    """都市指標CSVを読み込む。"""
    if not URBAN_CSV.exists():
        return {}

    rows: dict[str, dict] = {}
    with URBAN_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row["city"].strip().upper()
            entertainment_raw = (row.get("entertainment_facilities") or "").strip()
            rows[city] = {
                "prefecture": row.get("prefecture", "").strip(),
                "station_users": parse_csv_int(row.get("station_users")),
                "entertainment_facilities": parse_csv_int(row.get("entertainment_facilities")),
                "entertainment_pending": not entertainment_raw,
                "event_venues": parse_csv_int(row.get("event_venues")),
                "source": row.get("source", "").strip(),
                "notes": row.get("notes", "").strip(),
            }
    return rows


def compute_urban_bonuses(indicators: dict[str, dict]) -> dict[str, dict]:
    """駅利用者数・劇場音楽堂数・（任意）エンタメ施設数から都市別補正値を算出する。"""
    if not indicators:
        return {}

    users = [v["station_users"] for v in indicators.values()]
    venues = [v["event_venues"] for v in indicators.values()]
    ents = [v["entertainment_facilities"] for v in indicators.values()]
    min_u, max_u = min(users), max(users)
    min_v, max_v = min(venues), max(venues)
    has_entertainment = any(v > 0 for v in ents)
    min_e, max_e = (min(ents), max(ents)) if has_entertainment else (0, 0)

    result: dict[str, dict] = {}
    for city, data in indicators.items():
        flow_bonus = normalize_to_range(data["station_users"], min_u, max_u, 4.0, 18.0)
        venue_bonus = normalize_to_range(data["event_venues"], min_v, max_v, 0.5, 6.0)
        if has_entertainment and data["entertainment_facilities"] > 0:
            entertainment_bonus = normalize_to_range(
                data["entertainment_facilities"], min_e, max_e, 0.0, 3.0
            )
        else:
            entertainment_bonus = 0.0
        result[city] = {
            **data,
            "flow_bonus": round(flow_bonus, 1),
            "venue_bonus": round(venue_bonus, 1),
            "entertainment_bonus": round(entertainment_bonus, 1),
        }
    return result


def fetch_city_weather(
    city: str, lat: float, lon: float, urban: dict | None = None
) -> dict:
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

    if urban:
        flow_bonus = urban["flow_bonus"]
        venue_bonus = urban["venue_bonus"]
        entertainment_bonus = urban["entertainment_bonus"]
        station_users = urban["station_users"]
        event_venues = urban["event_venues"]
        urban_source = urban["source"]
        audit_status = "CSV接続済み: 人流(国交省) + 劇場・音楽堂(文科省社会教育調査)"
        if urban.get("entertainment_pending"):
            audit_status += " / 遊園地等は未接続（将来拡張）"
        trust_level = "high"
        source = f"Open-Meteo (weather) + {URBAN_CSV.name} (urban indicators)"
        source_mode = "mixed"
    else:
        flow_bonus = 0.0
        venue_bonus = 0.0
        entertainment_bonus = 0.0
        station_users = None
        event_venues = None
        urban_source = "未接続"
        audit_status = "要注意: 人流CSVに該当都市なし"
        trust_level = "medium"
        source = "Open-Meteo (weather) only"
        source_mode = "weather_only"

    heat_score = clamp(
        52.0
        + temp_score
        + flow_bonus
        + venue_bonus
        + entertainment_bonus
        - precip_penalty
        - wind_penalty,
        0,
        100,
    )

    components = {
        "base": {"value": 52.0, "trust_level": "medium", "label": "基準値"},
        "temp_score": {
            "value": round(temp_score, 1),
            "trust_level": "high",
            "label": "気温補正（実データ）",
        },
        "flow_bonus": {
            "value": flow_bonus,
            "trust_level": "medium",
            "label": "人流補正（国交省CSV）",
        },
        "venue_bonus": {
            "value": venue_bonus,
            "trust_level": "medium",
            "label": "劇場・音楽堂補正（文科省調査）",
        },
        "precip_penalty": {
            "value": round(-precip_penalty, 1),
            "trust_level": "high",
            "label": "降水ペナルティ（実データ）",
        },
        "wind_penalty": {
            "value": round(-wind_penalty, 1),
            "trust_level": "high",
            "label": "風速ペナルティ（実データ）",
        },
    }
    if entertainment_bonus > 0:
        components["entertainment_bonus"] = {
            "value": entertainment_bonus,
            "trust_level": "medium",
            "label": "エンタメ施設補正（CSV参照値）",
        }

    return {
        "city": city,
        "lat": lat,
        "lon": lon,
        "temperature_c": round(temp, 1),
        "precipitation_mm": round(precip, 1),
        "wind_speed_mps": round(wind, 1),
        "station_users": station_users,
        "event_venues": event_venues,
        "flow_bonus": flow_bonus,
        "venue_bonus": venue_bonus,
        "entertainment_bonus": entertainment_bonus,
        "heat_score": round(heat_score, 1),
        "urban_source": urban_source,
        "source": source,
        "source_mode": source_mode,
        "trust_level": trust_level,
        "audit_status": audit_status,
        "components": components,
    }


def fallback_city_data(urban_bonuses: dict[str, dict] | None = None) -> list[dict]:
    """API取得失敗時のフォールバックデータ。"""
    samples = [
        ("TOKYO", 35.6762, 139.6503, 25.2, 0.0, 3.9),
        ("OSAKA", 34.6937, 135.5023, 24.0, 0.4, 4.5),
        ("NAGOYA", 35.1815, 136.9066, 23.3, 0.0, 2.7),
        ("FUKUOKA", 33.5904, 130.4017, 22.7, 1.0, 5.0),
    ]
    records: list[dict] = []
    urban_bonuses = urban_bonuses or {}

    for city, lat, lon, temp, precip, wind in samples:
        urban = urban_bonuses.get(city)
        temp_score = clamp((temp - 8.0) * 1.7, 0.0, 32.0)
        precip_penalty = clamp(precip * 5.0, 0.0, 20.0)
        wind_penalty = clamp(wind * 0.9, 0.0, 18.0)
        flow_bonus = urban["flow_bonus"] if urban else 0.0
        venue_bonus = urban["venue_bonus"] if urban else 0.0
        entertainment_bonus = urban["entertainment_bonus"] if urban else 0.0
        heat_score = clamp(
            52.0
            + temp_score
            + flow_bonus
            + venue_bonus
            + entertainment_bonus
            - precip_penalty
            - wind_penalty,
            0,
            100,
        )
        records.append(
            {
                "city": city,
                "lat": lat,
                "lon": lon,
                "temperature_c": temp,
                "precipitation_mm": precip,
                "wind_speed_mps": wind,
                "station_users": urban["station_users"] if urban else None,
                "event_venues": urban["event_venues"] if urban else None,
                "flow_bonus": flow_bonus,
                "venue_bonus": venue_bonus,
                "entertainment_bonus": entertainment_bonus,
                "heat_score": round(heat_score, 1),
                "urban_source": urban["source"] if urban else "未接続",
                "source": "fallback sample",
                "source_mode": "fallback",
                "trust_level": "low",
                "audit_status": "要注意: API取得失敗時のサンプル値",
                "components": {},
            }
        )
    return records


def build_dataset() -> dict:
    urban_bonuses = compute_urban_bonuses(load_urban_indicators())
    records: list[dict] = []
    had_error = False

    for city, (lat, lon) in CITY_COORDS.items():
        try:
            records.append(
                fetch_city_weather(city, lat, lon, urban_bonuses.get(city))
            )
        except (TimeoutError, URLError, ValueError):
            had_error = True
            break

    if had_error or len(records) != len(CITY_COORDS):
        records = fallback_city_data(urban_bonuses)

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "records": records,
        "note": "prototype dataset for alpha demo",
        "iteration": ITERATION_STATE,
        "score_policy": {
            "formula": "52.0 + temp_score + flow_bonus + venue_bonus - precip_penalty - wind_penalty",
            "warning": "flow_bonus=国交省駅乗降客数 / venue_bonus=文科省社会教育調査(劇場・音楽堂)。いずれも urban_indicators.csv 経由。",
            "data_sources_file": DATA_SOURCES_FILE.name,
            "urban_csv": URBAN_CSV.name,
        },
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
    .trust-high {{ color: #77dd77; }}
    .trust-medium {{ color: #ffd166; }}
    .trust-low {{ color: #ff8fa3; }}
    .component-list {{
      margin-top: 8px;
      padding-left: 18px;
      color: #b8c5df;
      font-size: 13px;
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
      <h2>スコア設計と監査メモ</h2>
      <p><strong>計算式:</strong> <code id="formula"></code></p>
      <p class="muted" id="scoreWarning"></p>
      <p class="muted">信頼度: high=実データ / medium=推定含む / low=仮説値・サンプル</p>
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
            <th>駅利用者数</th>
            <th>劇場・音楽堂数</th>
            <th>人流補正</th>
            <th>会場補正</th>
            <th>熱狂度</th>
            <th>信頼度</th>
            <th>監査メモ</th>
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
          <p>β版へ進めるが、<strong>CSV出典の正式化</strong>と<strong>監査結果表示</strong>は継続課題。</p>
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
    document.getElementById("formula").textContent = dataset.score_policy.formula;
    document.getElementById("scoreWarning").textContent = dataset.score_policy.warning;

    dataset.iteration.cycle.forEach((s) => {{
      const div = document.createElement("div");
      div.className = "step " + s.status;
      div.innerHTML = `<strong>${{s.name}}</strong><br><span class="pill">${{s.status}}</span><p class="muted">${{s.note}}</p>`;
      cycle.appendChild(div);
    }});

    dataset.records.forEach((r) => {{
      const card = document.createElement("div");
      card.className = "city";
      const components = Object.values(r.components || {{}})
        .map((c) => `<li>${{c.label}}: <strong>${{c.value}}</strong> <span class="trust-${{c.trust_level}}">(${{c.trust_level}})</span></li>`)
        .join("");
      card.innerHTML = `
        <div><strong>${{r.city}}</strong></div>
        <div class="score">${{r.heat_score}}</div>
        <div class="bar"><div class="fill" style="width:${{r.heat_score}}%"></div></div>
        <div class="muted">source: ${{r.source}}</div>
        <div class="muted">監査: ${{r.audit_status}}</div>
        <ul class="component-list">${{components}}</ul>
      `;
      cards.appendChild(card);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${{r.city}}</td>
        <td>${{r.temperature_c}}</td>
        <td>${{r.precipitation_mm}}</td>
        <td>${{r.wind_speed_mps}}</td>
        <td>${{r.station_users ?? "—"}}</td>
        <td>${{r.event_venues ?? "—"}}</td>
        <td>${{r.flow_bonus}}</td>
        <td>${{r.venue_bonus}}</td>
        <td><strong>${{r.heat_score}}</strong></td>
        <td class="trust-${{r.trust_level}}">${{r.trust_level}}</td>
        <td>${{r.audit_status}}</td>
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
