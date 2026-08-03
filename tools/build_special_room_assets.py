"""Build Wii-compatible artwork for JWC24 special/parade rooms."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ROOMS = ROOT / "private/wii_no_ma/special/rooms.json"
OUTPUT = ROOT / "private/wii_no_ma/special/assets"
PICTURES = OUTPUT / "picture"


def font(size: int):
    for path in (Path("C:/Windows/Fonts/YuGothB.ttc"), Path("C:/Windows/Fonts/meiryob.ttc")):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=90, subsampling="4:2:0", progressive=False)


def main() -> None:
    rooms = json.loads(ROOMS.read_text(encoding="utf-8"))["rooms"]
    for room in rooms:
        room_id = int(room["room_id"])
        directory = OUTPUT / str(room_id)

        banner = Image.new("RGB", (184, 80), "#eaf8ff")
        draw = ImageDraw.Draw(banner)
        draw.rounded_rectangle((2, 2, 181, 77), radius=14, fill="#ffffff", outline="#29a9df", width=4)
        title = str(room.get("banner_title", room["news"]))
        draw.text((14, 8), "JWC24", font=font(20), fill="#168fbd")
        draw.text((14, 40), title[:12], font=font(13), fill="#ed6a8a")
        save(banner, directory / "parade_banner.jpg")

        logo = Image.new("RGB", (320, 180), "#eaf8ff")
        draw = ImageDraw.Draw(logo)
        draw.rounded_rectangle((8, 8, 311, 171), radius=24, fill="#ffffff", outline="#29a9df", width=6)
        title = str(room["news"])
        draw.text((34, 36), "JWC24 SPECIAL", font=font(27), fill="#168fbd")
        draw.text((34, 88), title[:18], font=font(18), fill="#ed6a8a")
        label = "JWC24版・現代向け再構成" if room.get("provenance") == "jwc24 revival" else ("歴史資料からの再現" if room.get("provenance") else "非公式ファンプロジェクト")
        draw.text((34, 132), label, font=font(15), fill="#15324a")
        save(logo, directory / "f1234.img")
        for menu in room.get("menus", []):
            image_id = str(menu["imageid"])
            card = Image.new("RGB", (160, 120), "#ffffff")
            card_draw = ImageDraw.Draw(card)
            menu_type = int(menu["type"])
            color = "#ed6a8a" if menu_type == 2 else "#29a9df"
            card_draw.rounded_rectangle((3, 3, 156, 116), radius=13, fill="#f8fcff", outline=color, width=4)
            labels = {2: "アンケート", 3: "映像", 6: ("JWC24版" if room.get("provenance") == "jwc24 revival" else "当時の内容")}
            card_draw.text((14, 17), labels.get(menu_type, "資料"), font=font(16), fill=color)
            card_draw.text((14, 52), str(menu["title"])[:12], font=font(14), fill="#15324a")
            card_draw.text((14, 89), "Aボタンで開く", font=font(12), fill="#5b6b75")
            save(card, directory / f"{image_id}.img")
            if menu_type == 2:
                poll_num = image_id[1:]
                for answer, label in enumerate(("はい", "どちらでも", "いいえ"), 1):
                    answer_card = Image.new("RGB", (832, 456), "#eaf8ff")
                    answer_draw = ImageDraw.Draw(answer_card)
                    answer_draw.rounded_rectangle((30, 30, 801, 425), radius=40, fill="#ffffff", outline=color, width=8)
                    answer_draw.text((90, 80), str(menu["question"]), font=font(30), fill="#15324a")
                    answer_draw.text((330, 220), label, font=font(46), fill=color)
                    save(answer_card, directory / f"e{poll_num}-{answer}.img")
            elif menu_type == 6:
                pic_id = int(menu.get("pic_id", room_id))
                for number, fact in enumerate(menu.get("pictures", []), 1):
                    page = Image.new("RGB", (832, 456), "#eef8fb")
                    page_draw = ImageDraw.Draw(page)
                    page_draw.rounded_rectangle((28, 26, 803, 427), radius=34, fill="#ffffff", outline="#29a9df", width=7)
                    page_draw.text((70, 58), title[:22], font=font(28), fill="#168fbd")
                    words = str(fact).split()
                    lines, current = [], ""
                    for word in words:
                        candidate = f"{current} {word}".strip()
                        if len(candidate) > 34 and current:
                            lines.append(current)
                            current = word
                        else:
                            current = candidate
                    if current:
                        lines.append(current)
                    if not lines:
                        lines = [str(fact)[:34]]
                    for line_no, line in enumerate(lines[:6]):
                        page_draw.text((72, 135 + line_no * 42), line, font=font(23), fill="#15324a")
                    footer = "JWC24版・公式公開情報から再構成" if room.get("provenance") == "jwc24 revival" else "JWC24 歴史資料からの再現"
                    page_draw.text((70, 382), footer, font=font(16), fill="#667985")
                    save(page, PICTURES / f"{pic_id}-{number}.img")
        print(f"built special room {room_id}")


if __name__ == "__main__":
    main()
