from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
import json
import os
import tempfile
import binascii
from pathlib import Path

from jwc24.lz11 import decode_lz11, encode_lz11
from tools.build_wii_no_ma_bootstrap import config_xml, encrypt_cbc
from jwc24.wii_no_ma import get_response


class WiiNoMaTests(unittest.TestCase):
    def test_lz11_round_trip(self) -> None:
        payload = (b"Wii no Ma/JWC24/" * 2048) + bytes(range(256))
        compressed = encode_lz11(payload)
        self.assertEqual(compressed[0], 0x11)
        self.assertLess(len(compressed), len(payload))
        self.assertEqual(decode_lz11(compressed), payload)

    def test_builds_v1025_encrypted_bootstrap(self) -> None:
        key = bytes.fromhex("943b13dd87468ba5d9b7a8b899f91803")
        iv = bytes.fromhex("66b33fc1373fe506ec2b59fb6b977c82")
        xml = config_xml("http://192.168.2.16", "2026-08-02T00:00:00")
        encrypted = encrypt_cbc(xml, key, iv)
        self.assertEqual(len(encrypted) % 16, 0)
        self.assertIn(b"<ver>399</ver>", xml)
        self.assertIn(b"http://192.168.2.16/url1/", xml)
        self.assertNotIn(xml, encrypted)

    def test_boot_routes_return_v1025_xml(self) -> None:
        routes = (
            "/url2/reginfo.cgi",
            "/url1/conf/datetime.xml",
            "/url1/conf/eula.xml",
            "/url1/event/today.xml",
            "/url1/list/new/all.xml",
            "/url1/list/popular/all.xml",
            "/url1/list/category/01.xml",
            "/url1/special/all.xml",
            "/url1/conf2/paylink.xml",
            "/url3/pay/event/today.xml",
            "/url3/pay/list/new/all.xml",
            "/url3/pay/list/category/header.xml",
            "/url2/search.cgi",
            "/url2/miiinfo.cgi",
            "/url2/evaluate.cgi",
            "/url2/enquete.cgi",
            "/url2/piceval.cgi",
            "/url2/smp.cgi",
            "/url2/pay/title.cgi",
            "/url2/pay/challenge.cgi",
            "/url2/pay/verify.cgi",
            "/url2/pay/support.cgi",
            "/url2/pay/rivtoken.cgi",
            "/url1/beacon/boot",
            "/url1/movie/00/1.stf",
        )
        for route in routes:
            with self.subTest(route=route):
                response = get_response(route)
                self.assertIsNotNone(response)
                document = ET.fromstring(response)
                self.assertEqual(document.findtext("ver"), "399")

    def test_fresh_install_bandwidth_movie_is_valid(self) -> None:
        movie = Path("private/wii_no_ma/theater/assets/movies/c8/2-H.mov").read_bytes()
        self.assertEqual(movie[:4], b"MOC5")
        self.assertIn(b"KI", movie)
        self.assertGreater(int.from_bytes(movie[0x10:0x13], "little"), 0)

    def test_calendar_routes_are_valid_empty_metadata(self) -> None:
        calendar = ET.fromstring(get_response("/url1/cal/20260802.xml"))
        self.assertEqual(calendar.tag, "Calendar")
        self.assertEqual(len(calendar.findall("dayinfo")), 7)
        self.assertEqual(calendar.findtext("dayinfo/wday"), "SU")
        daily = ET.fromstring(get_response("/url1/caldaily/20260802.xml"))
        self.assertEqual(daily.tag, "CalDaily")
        self.assertEqual(daily.findtext("date"), "2026-08-02")

    def test_rakuten_catalog_populates_paid_theater(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rakuten.json"
            path.write_text(
                json.dumps(
                    {
                        "products": [
                            {
                                "item_code": "shop:1",
                                "name": "Wiiリモコン",
                                "price_yen": 1980,
                                "review_count": 20,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            previous = os.environ.get("JWC24_RAKUTEN_CATALOG")
            os.environ["JWC24_RAKUTEN_CATALOG"] = str(path)
            try:
                new = ET.fromstring(get_response("/url3/pay/list/new/all.xml"))
                popular = ET.fromstring(get_response("/url3/pay/list/popular/all.xml"))
                metadata = ET.fromstring(get_response("/url3/pay/movie/c4/1/1.met"))
            finally:
                if previous is None:
                    os.environ.pop("JWC24_RAKUTEN_CATALOG", None)
                else:
                    os.environ["JWC24_RAKUTEN_CATALOG"] = previous
            self.assertEqual(new.findtext("movieinfo/title"), "Wiiリモコン")
            self.assertEqual(new.findtext("movieinfo/price"), "1980")
            self.assertEqual(popular.findtext("movieinfo/movieid"), "1")
            self.assertEqual(metadata.findtext("price"), "1980")

    def test_paid_event_has_v1025_intro_and_posters(self) -> None:
        event = ET.fromstring(get_response("/url3/pay/event/today.xml"))
        self.assertGreater(len(event.findall("posterinfo")), 0)
        self.assertEqual(event.findtext("posterinfo/geofilter"), "0")
        self.assertEqual(event.findtext("introinfo/cnttype"), "1")
        self.assertEqual(event.findtext("introinfo/linktype"), "5")
        self.assertIsNotNone(event.findtext("introinfo/linkid"))
        poster_id = event.findtext("posterinfo/posterid")
        metadata = ET.fromstring(get_response(f"/url3/pay/wall/{poster_id}.met"))
        self.assertEqual(metadata.findtext("posterid"), poster_id)
        self.assertEqual(metadata.findtext("type"), "1")

    def test_private_theater_catalog_populates_normal_theater(self) -> None:
        new = ET.fromstring(get_response("/url1/list/new/all.xml"))
        category = ET.fromstring(get_response("/url1/list/category/01.xml"))
        search = ET.fromstring(get_response("/url1/list/category/search/11001"))
        metadata = ET.fromstring(get_response("/url1/movie/c4/1.met"))
        self.assertEqual(new.findtext("movieinfo/movieid"), "1")
        self.assertEqual(category.findtext("categinfo/categid"), "11001")
        self.assertEqual(search.findtext("movieinfo/movieid"), "1")
        self.assertEqual(metadata.findtext("len"), "30")
        self.assertEqual(metadata.findtext("dsdist"), "0")

    def test_room_poster_wall_features_theater_movies(self) -> None:
        event = ET.fromstring(get_response("/url1/event/today.xml"))
        tags = [child.tag for child in event]
        self.assertLess(tags.index("adinfo"), tags.index("posterinfo"))
        posters = event.findall("posterinfo")
        catalog = json.loads(
            Path("private/wii_no_ma/theater/catalog.json").read_text(encoding="utf-8")
        )
        published = [movie for movie in catalog["movies"] if movie.get("published", True)]
        self.assertEqual(len(posters), min(20, len(published)))
        self.assertEqual(posters[0].findtext("posterid"), "1")
        metadata = ET.fromstring(get_response("/url1/wall/1.met"))
        self.assertEqual(metadata.findtext("movieid"), "1")
        self.assertIn("1996", metadata.findtext("title"))
        self.assertEqual(event.findtext("introinfo/linktype"), "2")
        self.assertEqual(event.findtext("introinfo/linkid"), "11002")
        self.assertIn("JWC24", event.findtext("newsinfo/news"))
        new_movie = ET.fromstring(get_response("/url1/movie/e4/5.met"))
        self.assertEqual(new_movie.findtext("title"), "アニマックス 番組スポット（0210_025420）")
        self.assertEqual(new_movie.findtext("len"), "10")

    def test_developer_concierge_mii_metadata_and_binary(self) -> None:
        event = ET.fromstring(get_response("/url1/event/today.xml"))
        self.assertEqual(event.findtext("miiinfo/miiid"), "1")
        metadata = ET.fromstring(get_response("/url1/mii/1.met"))
        self.assertEqual(metadata.findtext("name"), "コリン")
        self.assertEqual(metadata.findtext("action"), "9")
        self.assertEqual(len(metadata.findall("msginfo")), 7)
        raw = Path("private/wii_no_ma/miis/1.mii").read_bytes()
        self.assertEqual(len(raw), 76)
        self.assertEqual(raw[74:], binascii.crc_hqx(raw[:74], 0).to_bytes(2, "big"))
        category = ET.fromstring(get_response("/url1/list/category/02.xml"))
        self.assertEqual(category.findtext("categinfo/categid"), "20001")
        recommended = ET.fromstring(get_response("/url1/list/category/search/20001"))
        self.assertEqual(recommended.findtext("movieinfo/movieid"), "1")

    def test_jwc24_special_mii_batch_and_parade_room(self) -> None:
        event = ET.fromstring(get_response("/url1/event/today.xml"))
        self.assertEqual(len(event.findall("miiinfo")), 11)
        for mii_id in range(1, 12):
            raw = Path(f"private/wii_no_ma/miis/{mii_id}.mii").read_bytes()
            self.assertEqual(len(raw), 76)
            self.assertEqual(raw[74:], binascii.crc_hqx(raw[:74], 0).to_bytes(2, "big"))
        special = ET.fromstring(get_response("/url1/special/all.xml"))
        self.assertEqual(special.findtext("pageinfo/sppageid"), "1")
        binary = ET.fromstring(get_response("/url1/special/allbin.xml"))
        self.assertGreater(len(binary.findtext("bininfo/miibin")), 90)
        page = ET.fromstring(get_response("/url1/special/1/page.xml"))
        self.assertEqual(len(page.findall("miiinfo")), 8)
        self.assertEqual(page.findtext("miiinfo/miiid"), "1")
        self.assertEqual(len(page.findall("menu")), 2)
        self.assertEqual(page.findtext("menu/mov/movieid"), "1")
        tribute = ET.fromstring(get_response("/url1/special/2/page.xml"))
        self.assertEqual(tribute.findtext("miiinfo/miiid"), "9")
        self.assertEqual(tribute.findtext("menu[2]/enq/enqid"), "2")

    def test_historical_room_rotations_are_complete_and_wii_safe(self) -> None:
        room_document = json.loads(
            Path("private/wii_no_ma/special/rooms.json").read_text(encoding="utf-8")
        )
        historical = [room for room in room_document["rooms"] if int(room["room_id"]) >= 100]
        self.assertEqual(len(historical), 46)
        covered: set[int] = set()
        previous = os.environ.get("JWC24_ROOM_ROTATION")
        try:
            for rotation in ("history_early", "history_middle", "history_late"):
                os.environ["JWC24_ROOM_ROTATION"] = rotation
                listing = ET.fromstring(get_response("/url1/special/all.xml"))
                binaries = ET.fromstring(get_response("/url1/special/allbin.xml"))
                ids = {int(node.findtext("sppageid")) for node in listing.findall("pageinfo")}
                self.assertLessEqual(len(ids), 20)
                self.assertEqual(len(ids), len(binaries.findall("bininfo")))
                self.assertTrue({1, 2, 3, 4}.issubset(ids))
                covered.update(room_id for room_id in ids if room_id >= 100)
        finally:
            if previous is None:
                os.environ.pop("JWC24_ROOM_ROTATION", None)
            else:
                os.environ["JWC24_ROOM_ROTATION"] = previous
        self.assertEqual(covered, {int(room["room_id"]) for room in historical})
        sample = historical[-1]
        metadata = ET.fromstring(get_response(f"/url1/mii/{sample['parade_mii']}.met"))
        self.assertIn("再現Mii", metadata.findtext("prof"))

    def test_historical_rooms_do_not_use_generic_video_or_poll_placeholders(self) -> None:
        room_document = json.loads(
            Path("private/wii_no_ma/special/rooms.json").read_text(encoding="utf-8")
        )
        historical = [room for room in room_document["rooms"] if int(room["room_id"]) >= 100]
        menu_types = {
            int(menu["type"])
            for room in historical
            for menu in room.get("menus", [])
        }
        self.assertNotIn(2, menu_types)
        self.assertNotIn(3, menu_types)
        self.assertEqual(menu_types, {6})
        nagatanien = next(room for room in historical if room["news"] == "永谷園生姜部の間")
        page = ET.fromstring(get_response(f"/url1/special/{nagatanien['room_id']}/page.xml"))
        self.assertEqual(page.findtext("menu/type"), "6")
        self.assertGreaterEqual(int(page.findtext("menu/pic/picnum")), 5)

    def test_missing_historical_rooms_have_labeled_jwc24_revivals(self) -> None:
        room_document = json.loads(
            Path("private/wii_no_ma/special/rooms.json").read_text(encoding="utf-8")
        )
        expected = {"ロッテ ガーナの間", "日本郵便の間", "くもんの間"}
        revivals = {
            room["news"]: room
            for room in room_document["rooms"]
            if room.get("provenance") == "jwc24 revival"
        }
        self.assertEqual(set(revivals), expected)
        for room in revivals.values():
            self.assertGreaterEqual(len(room["replacement_sources"]), 3)
            self.assertEqual(room["menus"][0]["type"], 6)
            self.assertEqual(room["menus"][0]["title"], "JWC24版")
            self.assertEqual(len(room["menus"][0]["pictures"]), 4)
            self.assertTrue(all("JWC24版" in fact for fact in room["menus"][0]["pictures"]))


if __name__ == "__main__":
    unittest.main()
