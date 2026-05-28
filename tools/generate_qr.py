from __future__ import annotations

from pathlib import Path

import qrcode


def main() -> None:
    # GitHub Pages: prototype dashboard
    url = "https://ibukiyamagiwa-dot.github.io/city-heat-dashboard/prototype_app.html"

    out_dir = Path(__file__).resolve().parent
    out_path = out_dir / "qr_prototype_app.png"

    img = qrcode.make(url)
    img.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

