"""Import a Rakuten Ichiba search into a private JWC24 shop catalog."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from jwc24.rakuten import search, write_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", help="Japanese Rakuten search keyword")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hits", type=int, default=30)
    parser.add_argument("--pages", type=int, default=1, choices=range(1, 101))
    args = parser.parse_args()
    application_id = os.environ.get("JWC24_RAKUTEN_APPLICATION_ID", "")
    access_key = os.environ.get("JWC24_RAKUTEN_ACCESS_KEY", "")
    affiliate_id = os.environ.get("JWC24_RAKUTEN_AFFILIATE_ID", "")
    products = []
    seen = set()
    for page in range(1, args.pages + 1):
        if page > 1:
            time.sleep(1.05)
        fetched = search(
            application_id,
            access_key,
            args.keyword,
            affiliate_id=affiliate_id,
            hits=args.hits,
            page=page,
        )
        for product in fetched:
            if product.item_code not in seen:
                seen.add(product.item_code)
                products.append(product)
        if len(fetched) < args.hits:
            break
    write_catalog(args.output, args.keyword, products)
    print(f"wrote {len(products)} Rakuten products to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
