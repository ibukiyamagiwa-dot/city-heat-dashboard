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
    }


def build_html(dataset: dict) -> str:
    data_json = json.dumps(dataset, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>都市熱狂度プロトタイプ（α版）</title>
  <style>
    body {{
      margin: 0;
      font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
      background: #0b1020;
      color: #e7eefc;
    }}
    .wrap {{
      max-width: 980px;
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
      <h1>都市熱狂度プロトタイプ（α版）</h1>
      <p class="muted">最低限のデータ収集 + 可視化を確認するための実働サンプルです。</p>
      <p class="muted" id="updatedAt"></p>
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
  </div>

  <script>
    const dataset = {data_json};
    const cards = document.getElementById("cards");
    const tableBody = document.getElementById("tableBody");
    document.getElementById("updatedAt").textContent = "更新時刻: " + dataset.generated_at;

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
