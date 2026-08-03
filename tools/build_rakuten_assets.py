"""Build Wii-readable JPEG product artwork from a cached Rakuten catalog."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFile
import qrcode


def encode_artwork(payload: bytes, size: tuple[int, int]) -> bytes:
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    source = Image.open(io.BytesIO(payload)).convert("RGB")
    source.thumbnail((size[0] - 24, size[1] - 24), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    result = io.BytesIO()
    canvas.save(result, "JPEG", quality=88, subsampling="4:2:0", progressive=False)
    return result.getvalue()


def category_artwork() -> bytes:
    canvas = Image.new("RGB", (160, 120), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 159, 119), outline=(190, 0, 0), width=6)
    draw.text((26, 43), "Rakuten", fill=(190, 0, 0))
    result = io.BytesIO()
    canvas.save(result, "JPEG", quality=90, subsampling="4:2:0", progressive=False)
    return result.getvalue()


def encode_checkout_card(payload: bytes, product_url: str) -> bytes:
    source = Image.open(io.BytesIO(payload)).convert("RGB")
    source.thumbnail((400, 400), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (832, 456), "white")
    canvas.paste(source, ((420 - source.width) // 2, (456 - source.height) // 2))
    qr = qrcode.make(product_url).convert("RGB").resize((320, 320), Image.Resampling.NEAREST)
    canvas.paste(qr, (472, 38))
    draw = ImageDraw.Draw(canvas)
    draw.text((533, 375), "Open on Rakuten", fill=(190, 0, 0))
    draw.text((545, 397), "Scan with phone", fill=(40, 40, 40))
    result = io.BytesIO()
    canvas.save(result, "JPEG", quality=94, subsampling="4:4:4", progressive=False)
    return result.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.catalog.read_text(encoding="utf-8"))
    products = document.get("products", [])
    args.output.mkdir(parents=True, exist_ok=True)
    category_dir = args.output / "pay-category"
    category_dir.mkdir(parents=True, exist_ok=True)
    for category_id in range(10001, 10006):
        (category_dir / f"{category_id}.img").write_bytes(category_artwork())
    built = 0
    for movie_id, product in enumerate(products[:64], 1):
        image_url = str(product.get("image_url", ""))
        product_url = str(product.get("product_url", ""))
        item_code = str(product.get("item_code", ""))
        if not image_url or not item_code or not product_url.startswith("https://"):
            continue
        request = Request(image_url, headers={"User-Agent": "JWC24/0.1"})
        with urlopen(request, timeout=20) as response:
            payload = response.read(8 * 1024 * 1024 + 1)
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError(f"Rakuten image exceeds 8 MiB: {item_code}")
        bucket = hashlib.md5(str(movie_id).encode("ascii"), usedforsecurity=False).hexdigest()[:2]
        product_dir = args.output / "pay-movie" / bucket / str(movie_id)
        product_dir.mkdir(parents=True, exist_ok=True)
        (product_dir / f"D_{movie_id}-1.img").write_bytes(
            encode_checkout_card(payload, product_url)
        )
        (product_dir / f"{movie_id}.img").write_bytes(encode_artwork(payload, (320, 456)))
        built += 1
    print(f"built Wii artwork for {built}/{min(len(products), 64)} Rakuten products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
