"""Build rotating JWC24 historical-recreation room metadata from the audit CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research/wii_no_ma_special_rooms/rooms.csv"
ROOMS = ROOT / "private/wii_no_ma/special/rooms.json"
REVIVALS = ROOT / "private/wii_no_ma/special/jwc24_revivals.json"


def main() -> None:
    document = json.loads(ROOMS.read_text(encoding="utf-8"))
    originals = [room for room in document.get("rooms", []) if int(room["room_id"]) < 100]

    with AUDIT.open("r", encoding="utf-8-sig", newline="") as handle:
        audited = list(csv.DictReader(handle))
    revivals = json.loads(REVIVALS.read_text(encoding="utf-8"))["rooms"]

    # Annual Lucky Bag entries share one parade identity. Keep the best-supported
    # record as its metadata seed while retaining all editions in the research CSV.
    unique: dict[str, dict[str, str]] = {}
    grade_rank = {"A": 3, "B": 2, "C": 1, "D": 0}
    for entry in audited:
        name = entry["canonical_jp_name"]
        current = unique.get(name)
        if current is None or grade_rank.get(entry["evidence_grade"], 0) > grade_rank.get(
            current["evidence_grade"], 0
        ):
            unique[name] = entry

    historical = []
    for index, entry in enumerate(unique.values(), 0):
        room_id = 101 + index
        mii_id = 12 + index
        name = entry["canonical_jp_name"]
        partner = entry["partner"] or "Wiiの間"
        facts = [fact.strip() for fact in entry["known_features"].split(";") if fact.strip()]
        revival = revivals.get(name)
        display_facts = facts or (revival["features"] if revival else [])
        menus = []
        if display_facts:
            menus.append(
                {
                    "type": 6,
                    "imageid": f"i{room_id}0",
                    "pic_id": room_id,
                    "title": "JWC24版" if revival and not facts else "当時の内容",
                    "bgm": 2 + index % 7,
                    "pictures": display_facts,
                }
            )
        historical.append(
            {
                "room_id": room_id,
                "news": name,
                "banner_title": name,
                "level": 1,
                "bgm": 2 + index % 7,
                "mascot": 0,
                "parade_mii": mii_id,
                "mii_name": (partner if partner != "Wii no Ma" else name.replace("の間", ""))[:10],
                "provenance": "jwc24 revival" if revival and not facts else "historical recreation",
                "replacement_sources": revival["sources"] if revival and not facts else [],
                "evidence_grade": entry["evidence_grade"],
                "research_status": entry["status"],
                "historical_start": entry["start_date"],
                "historical_end": entry["end_date"],
                "intro_messages": (
                    [
                        f"{name}を現代向けに再構成したJWC24版です。",
                        "内容は各社の公式公開情報をもとにした新しい展示です。",
                    ]
                    if revival and not facts
                    else [
                        f"{name}の歴史資料をもとにしたJWC24再現です。",
                        "Miiと画像は再制作物で、当時の原本ではありません。",
                    ]
                ),
                "miis": [
                    {
                        "mii_id": mii_id,
                        "message": f"{partner}に関する当時の部屋を紹介します。",
                    }
                ],
                "menus": menus,
            }
        )

    original_ids = [int(room["room_id"]) for room in originals]
    # Keep the startup listing comfortably below the stock client's apparent
    # 8 KiB receive/parse boundary. The former 27-room payload was 9.2 KiB.
    historical_ids = [int(room["room_id"]) for room in historical]
    groups = [historical_ids[index::3] for index in range(3)]
    rotations = {
        "history_early": original_ids + groups[0],
        "history_middle": original_ids + groups[1],
        "history_late": original_ids + groups[2],
    }
    if any(len(ids) > 20 for ids in rotations.values()):
        raise SystemExit("rotation exceeds the stock client's safe 20-room startup payload")

    output = {
        "schema_version": 2,
        "default_rotation": "history_early",
        "rotations": rotations,
        "rooms": originals + historical,
    }
    ROOMS.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"built {len(historical)} historical rooms across {len(rotations)} rotations")
    for name, ids in rotations.items():
        print(f"{name}: {len(ids)} rooms")


if __name__ == "__main__":
    main()
