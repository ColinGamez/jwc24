"""Atomically encode and publish one private JWC24 Wii no Ma theater movie."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "mobipeg-gui/_internal/ffmpeg.exe"
CATALOG = ROOT / "private/wii_no_ma/theater/catalog.json"
MOVIES = ROOT / "private/wii_no_ma/theater/assets/movies"


def validate_mo(path: Path) -> int:
    data = path.read_bytes()
    if data[:4] != b"MOC5" or b"KI" not in data:
        raise ValueError("not a valid MOC5 movie")
    fps = int.from_bytes(data[0xC:0xF], "little") / 256
    frames = int.from_bytes(data[0x10:0x13], "little")
    if fps <= 0 or frames <= 0:
        raise ValueError("movie was not finalized")
    return max(1, round(frames / fps))


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("title")
    parser.add_argument("--category-id", type=int, default=11002)
    parser.add_argument("--category-name", default="日本のテレビアーカイブ")
    parser.add_argument("--note", default="ユーザー提供の日本放送アーカイブです。")
    parser.add_argument("--max-seconds", type=int)
    args = parser.parse_args()

    source = args.source.resolve(strict=True)
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    movie_id = max((int(item["movie_id"]) for item in document["movies"]), default=0) + 1
    bucket = hashlib.md5(str(movie_id).encode(), usedforsecurity=False).hexdigest()[:2]
    output_dir = MOVIES / bucket
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / f".{movie_id}-H.partial.mov"
    final_movie = output_dir / f"{movie_id}-H.mov"
    temporary_thumb = output_dir / f".{movie_id}.partial.jpg"
    final_thumb = output_dir / f"{movie_id}.img"

    command = [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
    if args.max_seconds:
        command += ["-t", str(args.max_seconds)]
    command += [
        "-vf", "scale=624:352:force_original_aspect_ratio=decrease,pad=624:352:(ow-iw)/2:(oh-ih)/2,fps=30000/1001",
        "-c:v", "mobiclip", "-mobiclip", "1", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-g", "90", "-qp", "28",
        "-c:a", "pcm_s16le", "-ar", "32000", "-ac", "2", "-mo_audio", "adpcm",
        "-f", "mobiclip_mo", str(temporary),
    ]
    try:
        run(command)
        duration = validate_mo(temporary)
        run([
            str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-ss", "1",
            "-i", str(source), "-frames:v", "1", "-vf",
            "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2",
            str(temporary_thumb),
        ])
        temporary.replace(final_movie)
        temporary_thumb.replace(final_thumb)
    except Exception:
        temporary.unlink(missing_ok=True)
        temporary_thumb.unlink(missing_ok=True)
        raise

    document["movies"].append({
        "movie_id": movie_id,
        "title": args.title,
        "staff": "JWC24 Theater / Colin collection",
        "note": args.note,
        "category_id": args.category_id,
        "category_name": args.category_name,
        "genre": 1,
        "length_seconds": duration,
        "aspect": 1,
        "source_path": str(source),
        "source_start": "00:00:00",
        "rights_status": "user-supplied-private-archive",
        "distribution_note": "Private JWC24 LAN testing only; no public redistribution authorization recorded.",
        "mobiclip_profile": "Wii MO / 624x352 / 30000/1001 / ADPCM / GOP<=90",
        "published": True,
    })
    CATALOG.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"published movie {movie_id}: {duration}s -> {final_movie}")


if __name__ == "__main__":
    main()
