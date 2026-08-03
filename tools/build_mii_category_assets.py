"""Build private Wii no Ma concierge-category artwork without external renderers."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "private/wii_no_ma/miis/roster.json"
OUTPUT = ROOT / "private/wii_no_ma/miis/assets/categories"


def load_font(size: int):
    for path in (Path("C:/Windows/Fonts/YuGothB.ttc"), Path("C:/Windows/Fonts/meiryob.ttc")):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def main() -> None:
    miis = json.loads(ROSTER.read_text(encoding="utf-8"))["miis"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for mii in miis:
        mii_id = int(mii["mii_id"])
        image = Image.new("RGB", (160, 120), "#fdf6b2")
        draw = ImageDraw.Draw(image)
        draw.ellipse((12, 12, 66, 66), fill="#f5c6a5", outline="#f58220", width=3)
        draw.arc((23, 33, 38, 48), 190, 350, fill="#393939", width=2)
        draw.arc((42, 33, 57, 48), 190, 350, fill="#393939", width=2)
        draw.arc((29, 42, 51, 60), 10, 170, fill="#393939", width=2)
        draw.text((75, 22), str(mii["name"]), font=load_font(22), fill="#5b3a16")
        draw.text((75, 56), "開発者", font=load_font(15), fill="#e05f18")
        draw.text((14, 91), "JWC24 おすすめ", font=load_font(14), fill="#5b3a16")
        image.save(
            OUTPUT / f"{20000 + mii_id}.img",
            "JPEG",
            quality=90,
            subsampling="4:2:0",
            progressive=False,
        )
        print(f"built Mii category {20000 + mii_id}")


if __name__ == "__main__":
    main()
