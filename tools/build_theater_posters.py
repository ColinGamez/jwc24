"""Build Wii no Ma room-wall posters from the private theater catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "private/wii_no_ma/theater/catalog.json"
MOVIES = ROOT / "private/wii_no_ma/theater/assets/movies"
OUTPUT = ROOT / "private/wii_no_ma/theater/assets/normal-wall"
INTRO_OUTPUT = ROOT / "private/wii_no_ma/theater/assets/normal-intro"
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/YuGothB.ttc"),
    Path("C:/Windows/Fonts/meiryob.ttc"),
    Path("C:/Windows/Fonts/msgothic.ttc"),
)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def movie_bucket(movie_id: int) -> str:
    return hashlib.md5(str(movie_id).encode(), usedforsecurity=False).hexdigest()[:2]


def wrap_title(draw: ImageDraw.ImageDraw, title: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in title:
        candidate = current + char
        if current and draw.textbbox((0, 0), candidate, font=font(18))[2] > width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:4]


def main() -> None:
    movies = json.loads(CATALOG.read_text(encoding="utf-8"))["movies"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for movie in movies:
        if not movie.get("published", True):
            continue
        movie_id = int(movie["movie_id"])
        thumbnail = MOVIES / movie_bucket(movie_id) / f"{movie_id}.img"
        if not thumbnail.is_file():
            raise FileNotFoundError(thumbnail)
        canvas = Image.new("RGB", (256, 360), "#f7f4ea")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((8, 8, 247, 351), radius=16, fill="#ffffff", outline="#72b7dc", width=4)
        image = Image.open(thumbnail).convert("RGB").resize((224, 168))
        canvas.paste(image, (16, 24))
        draw.rectangle((16, 192, 239, 196), fill="#29a9df")
        y = 210
        for line in wrap_title(draw, str(movie["title"]), 216):
            draw.text((20, y), line, font=font(18), fill="#15324a")
            y += 25
        draw.text((20, 326), "JWC24 おすすめ", font=font(14), fill="#168fbd")
        canvas.save(OUTPUT / f"{movie_id}.img", "JPEG", quality=90, subsampling="4:2:0", progressive=False)
        print(f"built poster {movie_id}")

    INTRO_OUTPUT.mkdir(parents=True, exist_ok=True)
    intro = Image.new("RGB", (832, 456), "#eaf8ff")
    draw = ImageDraw.Draw(intro)
    draw.rounded_rectangle((20, 20, 811, 435), radius=34, fill="#ffffff", outline="#29a9df", width=8)
    featured = Image.open(MOVIES / movie_bucket(4) / "4.img").convert("RGB").resize((480, 360))
    intro.paste(featured, (40, 48))
    draw.text((548, 74), "JWC24", font=font(42), fill="#168fbd")
    draw.text((548, 145), "今日の", font=font(30), fill="#15324a")
    draw.text((548, 190), "おすすめ", font=font(30), fill="#15324a")
    draw.text((548, 260), "アニマックス", font=font(23), fill="#ed6a8a")
    draw.text((548, 350), "クリックして見る", font=font(18), fill="#168fbd")
    intro.save(INTRO_OUTPUT / "1-1.img", "JPEG", quality=90, subsampling="4:2:0", progressive=False)
    print("built intro 1")


if __name__ == "__main__":
    main()
