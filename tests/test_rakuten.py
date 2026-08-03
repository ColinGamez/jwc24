from __future__ import annotations

import unittest

from jwc24.rakuten import normalize


class RakutenTests(unittest.TestCase):
    def test_normalizes_format_version_two(self) -> None:
        products = normalize(
            {
                "items": [
                    {
                        "itemCode": "jwc24:1",
                        "itemName": "Wii用リモコン",
                        "itemPrice": 1980,
                        "itemCaption": "テスト商品",
                        "itemUrl": "https://example.rakuten.co.jp/item/1",
                        "mediumImageUrls": [{"imageUrl": "https://example.invalid/1.jpg"}],
                        "shopName": "JWC24商店",
                        "shopCode": "jwc24",
                        "reviewCount": 12,
                        "reviewAverage": 4.5,
                        "availability": 1,
                    }
                ]
            }
        )
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].price_yen, 1980)
        self.assertEqual(products[0].name, "Wii用リモコン")

    def test_rejects_non_https_product_links(self) -> None:
        products = normalize(
            {"items": [{"itemCode": "x:1", "itemName": "bad", "itemPrice": 1, "itemUrl": "http://bad"}]}
        )
        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
