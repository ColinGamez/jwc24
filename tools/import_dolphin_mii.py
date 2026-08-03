"""Import one real Wii Mii from a Dolphin RFL_DB.dat for JWC24 concierge use."""

from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path

from mii import MiiDatabase, MiiType


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path.home() / "AppData/Roaming/Dolphin Emulator/Wii/shared2/menu/FaceLib/RFL_DB.dat"
OUTPUT = ROOT / "private/wii_no_ma/miis"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--name", default="コリン")
    parser.add_argument("--id", type=int, default=1)
    args = parser.parse_args()

    database = MiiDatabase(args.database, MiiType.WII_PLAZA)
    match = next((mii for mii in database if mii.name == args.name), None)
    if match is None:
        raise SystemExit(f"Mii name not found: {args.name!r}")
    raw = bytes(match.raw_data)
    if len(raw) != 74:
        raise SystemExit(f"expected 74-byte Wii Mii, received {len(raw)}")
    checksum = binascii.crc_hqx(raw, 0).to_bytes(2, "big")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{args.id}.mii").write_bytes(raw + checksum)
    roster = {
        "schema_version": 1,
        "miis": [
            {
                "mii_id": args.id,
                "name": match.name,
                "creator": match.creator_name,
                "favorite_color": match.favorite_color,
                "clothes": 1,
                "color1": "f58220",
                "color2": "ffffff",
                "action": 9,
                "profile": "JWC24の開発者コリンです。日本のWiiConnect24を復活させています！",
                "movie_id": 1,
                "voice": 0,
                "messages": [
                    {"type": 1, "seq": 1, "face": 1, "text": "JWC24へようこそ！"},
                    {"type": 2, "seq": 1, "face": 2, "text": "今日のおすすめを見てね！"},
                    {"type": 3, "seq": 1, "face": 1, "text": "日本の番組を追加中です。"},
                    {"type": 4, "seq": 1, "face": 3, "text": "ショップもチェック！"},
                    {"type": 5, "seq": 1, "face": 1, "text": "天気予報も使えます。"},
                    {"type": 6, "seq": 1, "face": 2, "text": "また遊びに来てね！"},
                    {"type": 7, "seq": 1, "face": 1, "text": "JWC24開発中！"}
                ],
                "source": str(args.database),
                "source_slot_name": match.name
            }
        ]
    }
    (OUTPUT / "roster.json").write_text(
        json.dumps(roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"imported Mii {args.id}; bytes=76 crc={checksum.hex()}")


if __name__ == "__main__":
    main()
