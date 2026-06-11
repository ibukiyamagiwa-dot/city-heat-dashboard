# -*- coding: utf-8 -*-
"""寄り町（YORIMACHI）ブラウザ用データを生成する。"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GRAPH_PATH = BASE_DIR / "rail_graph.json"
TOWNS_PATH = BASE_DIR / "data" / "towns.json"
INDEX_PATH = BASE_DIR / "stations_index.json"
OUT_PATH = BASE_DIR / "yorimachi_data.js"


def main() -> None:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    towns = json.loads(TOWNS_PATH.read_text(encoding="utf-8"))
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    graph_edges = [
        {
            "from": e["from"],
            "to": e["to"],
            "minutes": e["minutes"],
            "line": e.get("line"),
        }
        for e in graph["edges"]
    ]

    payload = {
        "generated_at": __import__("datetime").date.today().isoformat(),
        "app": {
            "name": "寄り町",
            "name_en": "YORIMACHI",
            "tagline": "空いた時間に、寄れる町を。",
        },
        "graph_meta": {
            "version": graph.get("version"),
            "source": graph.get("source"),
            "stats": graph.get("stats"),
        },
        "graph_edges": graph_edges,
        "departure_shortcuts": towns["departure_shortcuts"],
        "stations": index,
        "towns": towns["towns"],
    }

    js = "// 寄り町データ（build_yorimachi.py が自動生成。手編集しない）\n"
    js += "window.YORIMACHI_DATA = "
    js += json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js += ";\n"
    OUT_PATH.write_text(js, encoding="utf-8")
    print(f"Wrote {OUT_PATH} - stations={len(index)} towns={len(towns['towns'])}")


if __name__ == "__main__":
    main()
