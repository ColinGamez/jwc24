"""Rakuten Ichiba ingestion for the JWC24 Wii no Ma shop."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"


@dataclass(frozen=True)
class Product:
    item_code: str
    name: str
    price_yen: int
    caption: str
    product_url: str
    image_url: str
    shop_name: str
    shop_code: str
    review_count: int
    review_average: float
    available: bool


def _https_url(value: object) -> str:
    text = str(value or "")
    parsed = urlparse(text)
    return text if parsed.scheme == "https" and parsed.netloc else ""


def _first_image(value: object) -> str:
    if not isinstance(value, list):
        return ""
    for entry in value:
        if isinstance(entry, dict):
            entry = entry.get("imageUrl", "")
        result = _https_url(entry)
        if result:
            return result
    return ""


def normalize(document: dict[str, Any]) -> list[Product]:
    raw_items = document.get("items", document.get("Items", []))
    if not isinstance(raw_items, list):
        raise ValueError("Rakuten response has no items array")
    products: list[Product] = []
    for wrapper in raw_items:
        if not isinstance(wrapper, dict):
            continue
        item = wrapper.get("Item", wrapper.get("item", wrapper))
        if not isinstance(item, dict):
            continue
        item_code = str(item.get("itemCode", "")).strip()
        name = str(item.get("itemName", "")).strip()
        product_url = _https_url(item.get("affiliateUrl") or item.get("itemUrl"))
        if not item_code or not name or not product_url:
            continue
        try:
            price = int(item.get("itemPrice", 0))
        except (TypeError, ValueError):
            continue
        if price < 0:
            continue
        products.append(
            Product(
                item_code=item_code,
                name=name,
                price_yen=price,
                caption=str(item.get("itemCaption", "")).strip(),
                product_url=product_url,
                image_url=_first_image(item.get("mediumImageUrls", [])),
                shop_name=str(item.get("shopName", "")).strip(),
                shop_code=str(item.get("shopCode", "")).strip(),
                review_count=int(item.get("reviewCount", 0) or 0),
                review_average=float(item.get("reviewAverage", 0) or 0),
                available=int(item.get("availability", 1) or 0) == 1,
            )
        )
    return products


def search(
    application_id: str,
    access_key: str,
    keyword: str,
    *,
    affiliate_id: str = "",
    hits: int = 30,
    page: int = 1,
    timeout: float = 20,
) -> list[Product]:
    if not application_id or not access_key:
        raise ValueError("Rakuten application ID and access key are required")
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("Rakuten keyword cannot be empty")
    if not 1 <= hits <= 30:
        raise ValueError("Rakuten hits must be between 1 and 30")
    if not 1 <= page <= 100:
        raise ValueError("Rakuten page must be between 1 and 100")
    params = {
        "applicationId": application_id,
        "keyword": keyword,
        "hits": hits,
        "page": page,
        "format": "json",
        "formatVersion": 2,
        "availability": 1,
    }
    if affiliate_id:
        params["affiliateId"] = affiliate_id
    request = Request(
        f"{API_URL}?{urlencode(params)}",
        headers={"accessKey": access_key, "User-Agent": "JWC24/0.1"},
    )
    with urlopen(request, timeout=timeout) as response:
        document = json.loads(response.read().decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Rakuten response is not a JSON object")
    return normalize(document)


def write_catalog(path: Path, keyword: str, products: list[Product]) -> None:
    document = {
        "schema_version": 1,
        "provider": "rakuten_ichiba",
        "keyword": keyword,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "currency": "JPY",
        "products": [asdict(product) for product in products],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
