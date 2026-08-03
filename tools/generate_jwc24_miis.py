"""Generate a deterministic batch of original, valid Wii-format JWC24 Miis."""

from __future__ import annotations

import binascii
import json
from pathlib import Path

from mii import MiiParser


ROOT = Path(__file__).resolve().parents[1]
MII_DIR = ROOT / "private/wii_no_ma/miis"
ROOMS = ROOT / "private/wii_no_ma/special/rooms.json"

GUESTS = (
    # name, gender, color, face, skin, feature, hair, hair color, eye, lip, glasses, action
    ("ヒカリ", 1, 2, 1, 1, 1, 18, 1, 4, 5, 0, 16),
    ("ソラ", 0, 6, 2, 0, 4, 32, 2, 10, 1, 1, 18),
    ("ミドリ", 1, 3, 0, 2, 6, 45, 3, 15, 8, 0, 6),
    ("アカネ", 1, 0, 3, 1, 2, 8, 1, 22, 10, 3, 7),
    ("タクミ", 0, 5, 4, 3, 8, 52, 0, 28, 2, 2, 14),
    ("ユメ", 1, 7, 5, 0, 10, 65, 4, 34, 14, 4, 19),
    ("ハル", 0, 8, 6, 2, 3, 70, 5, 40, 6, 5, 20),
)

TRIBUTES = (
    ("岩田聡", 0, 5, 2, 1, 5, 30, 1, 8, 1, 2, 14),
    ("宮本茂", 0, 3, 1, 1, 3, 25, 1, 12, 2, 1, 15),
    ("横井軍平", 0, 8, 4, 1, 7, 42, 1, 18, 3, 3, 20),
)


def set_be_field(data: bytearray, offset: int, size: int, shift: int, width: int, value: int) -> None:
    mask = ((1 << width) - 1) << shift
    current = int.from_bytes(data[offset : offset + size], "big")
    current = (current & ~mask) | ((value << shift) & mask)
    data[offset : offset + size] = current.to_bytes(size, "big")


def write_utf16(data: bytearray, offset: int, units: int, value: str) -> None:
    encoded = value.encode("utf-16be")[: units * 2]
    data[offset : offset + units * 2] = encoded.ljust(units * 2, b"\0")


def make_guest(template: bytes, guest_id: int, spec: tuple[object, ...]) -> bytes:
    name, girl, color, face, skin, feature, hair, hair_color, eye, lip, glasses, _action = spec
    data = bytearray(template[:74])
    set_be_field(data, 0x00, 2, 14, 1, int(girl))
    set_be_field(data, 0x00, 2, 1, 4, int(color))
    set_be_field(data, 0x00, 2, 0, 1, 0)
    write_utf16(data, 0x02, 10, str(name))
    # Keep deterministic body dimensions inside the one-byte Wii Mii fields,
    # even when the historical catalog uses IDs beyond the original batch.
    data[0x16] = 48 + (guest_id * 7) % 160
    data[0x17] = 42 + (guest_id * 6) % 170
    # Bit 7 clear means a special/gold-pants Mii. Bits 6 and 5 remain clear.
    data[0x18:0x1C] = bytes((guest_id & 0x1F, 0x4A, 0x57, 0x43))
    set_be_field(data, 0x20, 2, 13, 3, int(face))
    set_be_field(data, 0x20, 2, 10, 3, int(skin))
    set_be_field(data, 0x20, 2, 6, 4, int(feature))
    set_be_field(data, 0x22, 2, 9, 7, int(hair))
    set_be_field(data, 0x22, 2, 6, 3, int(hair_color))
    set_be_field(data, 0x24, 4, 27, 5, (guest_id * 3) % 24)
    set_be_field(data, 0x24, 4, 22, 4, 6 + guest_id % 5)
    set_be_field(data, 0x24, 4, 13, 3, int(hair_color))
    set_be_field(data, 0x28, 4, 26, 6, int(eye))
    set_be_field(data, 0x28, 4, 21, 3, guest_id % 7)
    set_be_field(data, 0x28, 4, 13, 3, guest_id % 6)
    set_be_field(data, 0x2C, 2, 12, 4, guest_id % 12)
    set_be_field(data, 0x2E, 2, 11, 5, int(lip))
    set_be_field(data, 0x2E, 2, 9, 2, guest_id % 3)
    set_be_field(data, 0x30, 2, 12, 4, int(glasses))
    set_be_field(data, 0x32, 2, 14, 2, guest_id % 4)
    set_be_field(data, 0x32, 2, 12, 2, (guest_id // 2) % 4)
    set_be_field(data, 0x34, 2, 15, 1, guest_id % 2)
    write_utf16(data, 0x36, 10, "JWC24")
    checksum = binascii.crc_hqx(data, 0).to_bytes(2, "big")
    return bytes(data) + checksum


def main() -> None:
    template = (MII_DIR / "1.mii").read_bytes()
    if len(template) != 76:
        raise SystemExit("developer Mii must be generated first")
    roster_path = MII_DIR / "roster.json"
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    developer = next(mii for mii in roster["miis"] if int(mii["mii_id"]) == 1)
    generated = [developer]
    colors = (
        "f2cf32", "55bde9", "59a84b", "dc3f3f", "397bd1", "e77da8", "8259a8",
        "397bd1", "59a84b", "8259a8",
    )
    all_specs = (*GUESTS, *TRIBUTES)
    for index, spec in enumerate(all_specs, 2):
        raw = make_guest(template, index, spec)
        parsed = MiiParser.parse(raw[:74])
        if parsed.name != spec[0] or len(raw) != 76:
            raise SystemExit(f"validation failed for generated Mii {index}")
        (MII_DIR / f"{index}.mii").write_bytes(raw)
        is_tribute = index > len(GUESTS) + 1
        generated.append(
            {
                "mii_id": index,
                "name": spec[0],
                "creator": "JWC24",
                "favorite_color": parsed.favorite_color,
                "clothes": 1,
                "color1": colors[index - 2],
                "color2": "ffffff",
                "action": int(spec[-1]),
                "profile": (
                    f"{spec[0]}さんをイメージしたJWC24非公式トリビュートMiiです。"
                    if is_tribute
                    else f"JWC24オリジナルゲストの{spec[0]}です。"
                ),
                "movie_id": ((index - 2) % 4) + 1,
                "voice": 0,
                "messages": [
                    {"type": kind, "seq": 1, "face": (kind + index) % 3 + 1, "text": text}
                    for kind, text in enumerate(
                        (
                            "JWC24へようこそ！",
                            "今日のおすすめを紹介します。",
                            "日本の番組を楽しんでね！",
                            "新しい映像をチェック！",
                            "お天気も見ていってね。",
                            "また会いましょう！",
                            "みんなでWiiの間！",
                        ),
                        1,
                    )
                ],
                "source": "JWC24 unofficial tribute likeness" if is_tribute else "JWC24 generated original",
                "source_slot_name": None,
                "special_mii": True,
                "unofficial_likeness": is_tribute,
            }
        )
        print(f"generated Mii {index}")
    rooms = json.loads(ROOMS.read_text(encoding="utf-8")).get("rooms", [])
    historical = [room for room in rooms if int(room.get("room_id", 0)) >= 100]
    for offset, room in enumerate(historical):
        index = int(room["parade_mii"])
        name = str(room.get("mii_name", "案内Mii"))[:10]
        spec = (
            name,
            offset % 2,
            offset % 12,
            offset % 7,
            offset % 4,
            offset % 12,
            (offset * 11 + 7) % 72,
            offset % 6,
            (offset * 5 + 3) % 48,
            offset % 16,
            offset % 6,
            6 + offset % 15,
        )
        raw = make_guest(template, index, spec)
        parsed = MiiParser.parse(raw[:74])
        if parsed.name != name or len(raw) != 76:
            raise SystemExit(f"validation failed for historical Mii {index}")
        (MII_DIR / f"{index}.mii").write_bytes(raw)
        generated.append(
            {
                "mii_id": index,
                "name": name,
                "creator": "JWC24",
                "favorite_color": parsed.favorite_color,
                "clothes": 1,
                "color1": colors[offset % len(colors)],
                "color2": "ffffff",
                "action": int(spec[-1]),
                "profile": f"{room['news']}用に生成したJWC24歴史再現Miiです。原本ではありません。",
                "movie_id": offset % 4 + 1,
                "voice": 0,
                "messages": [
                    {"type": kind, "seq": 1, "face": (kind + offset) % 3 + 1, "text": text}
                    for kind, text in enumerate(
                        (
                            f"{room['news']}へようこそ！",
                            "歴史資料をもとに再現しています。",
                            "このMiiはJWC24の再制作物です。",
                            "関連映像をチェック！",
                            "復刻アンケートにも参加してね。",
                            "また遊びに来てください！",
                            "みんなでWiiの間！",
                        ),
                        1,
                    )
                ],
                "source": "JWC24 generated historical recreation",
                "source_slot_name": None,
                "special_mii": True,
                "unofficial_likeness": False,
                "parade_only": True,
            }
        )
        print(f"generated historical Mii {index}")
    roster["miis"] = generated
    roster_path.write_text(
        json.dumps(roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"roster size={len(generated)}")


if __name__ == "__main__":
    main()
