"""Minimal boot-safe Wii no Ma v1025 direct HTTP responses."""

from __future__ import annotations

import re
import json
import os
import hashlib
import base64
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _xml(name: str, values: tuple[tuple[str, object], ...]) -> bytes:
    root = ET.Element(name)
    ET.SubElement(root, "ver").text = "399"

    def add(parent: ET.Element, key: str, value: object) -> None:
        if isinstance(value, tuple) and value and isinstance(value[0], tuple):
            child = ET.SubElement(parent, key)
            for nested_key, nested_value in value:
                add(child, nested_key, nested_value)
        elif isinstance(value, bytes):
            ET.SubElement(parent, key).text = base64.b64encode(value).decode("ascii")
        else:
            ET.SubElement(parent, key).text = str(value)

    for key, value in values:
        add(root, key, value)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8") + b"\n"


def _shop_products() -> list[dict[str, object]]:
    path = Path(
        os.environ.get(
            "JWC24_RAKUTEN_CATALOG",
            "private/wii_no_ma/shop/rakuten.json",
        )
    )
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    products = document.get("products", []) if isinstance(document, dict) else []
    return [item for item in products if isinstance(item, dict)]


def _theater_movies() -> list[dict[str, object]]:
    path = Path(
        os.environ.get(
            "JWC24_THEATER_CATALOG",
            "private/wii_no_ma/theater/catalog.json",
        )
    )
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    movies = document.get("movies", []) if isinstance(document, dict) else []
    return [
        item
        for item in movies
        if isinstance(item, dict) and bool(item.get("published", True))
    ]


def _theater_movieinfo(
    movies: list[dict[str, object]],
) -> tuple[tuple[str, object], ...]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    values: list[tuple[str, object]] = []
    for rank, movie in enumerate(movies[:64], 1):
        values.append(
            (
                "movieinfo",
                (
                    ("rank", rank),
                    ("movieid", int(movie.get("movie_id", 0))),
                    ("title", str(movie.get("title", ""))[:96]),
                    ("genre", int(movie.get("genre", 1))),
                    ("strdt", timestamp),
                    ("pop", 0),
                ),
            )
        )
    return tuple(values)


def _all_miis() -> list[dict[str, object]]:
    path = Path(
        os.environ.get(
            "JWC24_MII_ROSTER",
            "private/wii_no_ma/miis/roster.json",
        )
    )
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    miis = document.get("miis", []) if isinstance(document, dict) else []
    return [item for item in miis if isinstance(item, dict)]


def _concierge_miis() -> list[dict[str, object]]:
    return [mii for mii in _all_miis() if not bool(mii.get("parade_only", False))]


def _special_rooms() -> list[dict[str, object]]:
    path = Path("private/wii_no_ma/special/rooms.json")
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rooms = document.get("rooms", []) if isinstance(document, dict) else []
    valid_rooms = [item for item in rooms if isinstance(item, dict)]
    rotations = document.get("rotations", {}) if isinstance(document, dict) else {}
    if not isinstance(rotations, dict) or not rotations:
        return valid_rooms[:30]
    requested = os.environ.get(
        "JWC24_ROOM_ROTATION", str(document.get("default_rotation", "history_early"))
    )
    selected = rotations.get(requested)
    if not isinstance(selected, list):
        selected = rotations.get(str(document.get("default_rotation", "history_early")), [])
    selected_ids = {int(room_id) for room_id in selected}
    return [room for room in valid_rooms if int(room.get("room_id", 0)) in selected_ids][:30]


def _menu_pairs(menu: dict[str, object]) -> tuple[tuple[str, object], ...]:
    menu_type = int(menu.get("type", 3))
    base: list[tuple[str, object]] = [
        ("type", menu_type),
        ("imageid", str(menu.get("imageid", "c1000"))),
    ]
    if menu_type == 2:
        poll_id = int(menu.get("poll_id", 1))
        image_id = str(menu.get("imageid", "b1001"))[1:]
        base.append(
            (
                "enq",
                (
                    ("enqid", poll_id),
                    ("enqq", str(menu.get("question", "どう思いますか？"))),
                    ("enqa", 3),
                    ("enqimgid", f"e{image_id}"),
                    ("enqtitle", str(menu.get("title", "アンケート"))),
                    (
                        "enqmsginfo",
                        (("enqmsgseq", 1), ("enqmsg", str(menu.get("message", "選んでください。")))),
                    ),
                    ("enqmov", 0),
                ),
            )
        )
    elif menu_type == 3:
        base.append(
            (
                "mov",
                (
                    ("movieid", int(menu.get("movie_id", 1))),
                    ("title", str(menu.get("title", "おすすめ映像"))),
                ),
            )
        )
    elif menu_type == 6:
        pictures = menu.get("pictures", [])
        base.append(
            (
                "pic",
                (
                    ("picid", int(menu.get("pic_id", 1))),
                    ("pictitle", str(menu.get("title", "資料"))),
                    ("picmov", 0),
                    ("picnum", len(pictures) if isinstance(pictures, list) else 0),
                    ("picbgm", int(menu.get("bgm", 2))),
                ),
            )
        )
    return tuple(base)


SHOP_CATEGORIES = (
    (10001, "Wii本体"),
    (10002, "Wiiソフト"),
    (10003, "コントローラー"),
    (10004, "アクセサリー"),
    (10005, "その他"),
)


def _shop_category(product: dict[str, object]) -> int:
    name = str(product.get("name", "")).casefold()
    if any(word in name for word in ("本体", "console", "すぐ遊べるセット")):
        return 10001
    if any(word in name for word in ("リモコン", "コントローラ", "ヌンチャク", "controller")):
        return 10003
    if any(word in name for word in ("ケーブル", "アダプタ", "センサー", "スタンド", "ケース", "バッテリー")):
        return 10004
    if any(word in name for word in ("ソフト", "ゲーム", "game")):
        return 10002
    return 10005


def _indexed_products() -> list[tuple[int, dict[str, object]]]:
    return list(enumerate(_shop_products(), 1))


def _shop_movieinfo(
    products: list[tuple[int, dict[str, object]]],
) -> tuple[tuple[str, object], ...]:
    values: list[tuple[str, object]] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    for rank, (movie_id, product) in enumerate(products[:64], 1):
        item_code = str(product.get("item_code", ""))
        refid = hashlib.md5(item_code.encode("utf-8"), usedforsecurity=False).hexdigest()
        values.append(
            (
                "movieinfo",
                (
                    ("rank", rank),
                    ("movieid", movie_id),
                    ("title", str(product.get("name", ""))[:96]),
                    ("kana", "12345678"),
                    ("refid", refid),
                    ("strdt", timestamp),
                    ("pop", 1),
                    ("released", 1),
                    ("term", 1),
                    ("price", int(product.get("price_yen", 0) or 0)),
                ),
            )
        )
    return tuple(values)


def get_response(route: str, base_url: str = "http://127.0.0.1") -> bytes | None:
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")
    date = now.strftime("%Y-%m-%d")
    if route == "/url2/reginfo.cgi":
        return _xml(
            "RegionInfo",
            (("sdt", timestamp), ("cdt", timestamp), ("limited", "0")),
        )
    if route == "/url1/conf/datetime.xml":
        return _xml("DateTime", (("upddt", timestamp),))
    if route == "/url1/conf/eula.xml":
        return _xml(
            "LicenseAgree",
            (("agree", "Wiiの間へようこそ。JWC24テストサービスをご利用いただけます。"),),
        )
    calendar_match = re.fullmatch(r"/url1/cal/(\d{8}|\d{4}-\d{2}-\d{2})\.xml", route)
    if calendar_match:
        try:
            raw_date = calendar_match.group(1)
            start = datetime.strptime(raw_date, "%Y%m%d" if "-" not in raw_date else "%Y-%m-%d")
        except ValueError:
            return None
        values: list[tuple[str, object]] = []
        for offset in range(7):
            day = start + timedelta(days=offset)
            values.append(
                (
                    "dayinfo",
                    (
                        ("date", day.strftime("%Y-%m-%d")),
                        ("wday", day.strftime("%a").upper()[:2]),
                        ("holiday", 0),
                        ("thead", 0),
                    ),
                )
            )
        return _xml("Calendar", tuple(values))
    daily_match = re.fullmatch(r"/url1/caldaily/(\d{8}|\d{4}-\d{2}-\d{2})\.xml", route)
    if daily_match:
        try:
            raw_date = daily_match.group(1)
            day = datetime.strptime(raw_date, "%Y%m%d" if "-" not in raw_date else "%Y-%m-%d")
        except ValueError:
            return None
        return _xml(
            "CalDaily",
            (
                ("date", day.strftime("%Y-%m-%d")),
                ("wday", day.strftime("%a").upper()[:2]),
                ("holiday", 0),
            ),
        )
    if route == "/url1/event/today.xml":
        posters = tuple(
            (
                "posterinfo",
                (
                    ("seq", sequence),
                    ("posterid", int(movie.get("movie_id", 0))),
                ),
            )
            for sequence, movie in enumerate(_theater_movies()[:20], 1)
        )
        miis = tuple(
            (
                "miiinfo",
                (("seq", sequence), ("miiid", int(mii.get("mii_id", 0)))),
            )
            for sequence, mii in enumerate(_concierge_miis()[:20], 1)
        )
        return _xml(
            "Event",
            (
                ("date", date),
                ("frameid", 1000001),
                ("color", "000000"),
                ("postertime", 5),
                ("adinfo", (("pref", 2), ("adid", 1), ("pref", 1), ("adid", 1))),
                *posters,
                (
                    "introinfo",
                    (
                        ("seq", 1),
                        ("cntid", 1),
                        ("cnttype", 1),
                        ("random", 0),
                        ("linktype", 2),
                        ("dispsec", 8),
                        ("dimg", 1),
                        ("linkid", 11002),
                        ("catname", "アニマックス"),
                    ),
                ),
                (
                    "newsinfo",
                    (("page", 1), ("news", "JWC24へようこそ！日本の番組とCMをお楽しみください。")),
                ),
                *miis,
            ),
        )
    if route == "/url1/conf2/paylink.xml":
        return _xml("MovieLink", (("linkinfo", (("movieid", 2), ("categid", 11111))),))
    if route == "/url1/special/all.xml":
        pages: list[tuple[str, object]] = []
        roster = {int(mii.get("mii_id", 0)): mii for mii in _all_miis()}
        for room in _special_rooms():
            mii_id = int(room.get("parade_mii", 1))
            mii = roster.get(mii_id, {})
            pages.append(
                (
                    "pageinfo",
                    (
                        ("sppageid", int(room.get("room_id", 1))),
                        ("name", str(mii.get("name", "JWC24"))),
                        ("level", int(room.get("level", 1))),
                        ("miiid", mii_id),
                        ("color1", str(mii.get("color1", "f58220"))),
                        ("color2", str(mii.get("color2", "ffffff"))),
                        ("logo1id", "g1234"),
                        ("news", str(room.get("news", "JWC24の間"))),
                        ("valid", 1),
                        ("pref", "1" * 47),
                    ),
                )
            )
        return _xml("SpPageList", (*pages, ("upddt", timestamp)))
    if route == "/url1/special/allbin.xml":
        bins: list[tuple[str, object]] = []
        for room in _special_rooms()[:30]:
            room_id = int(room.get("room_id", 1))
            mii_id = int(room.get("parade_mii", 1))
            mii_path = Path(f"private/wii_no_ma/miis/{mii_id}.mii")
            banner_path = Path(f"private/wii_no_ma/special/assets/{room_id}/parade_banner.jpg")
            if not mii_path.is_file() or not banner_path.is_file():
                continue
            bins.append(
                (
                    "bininfo",
                    (
                        ("sppageid", room_id),
                        ("miiid", mii_id),
                        ("miibin", mii_path.read_bytes()),
                        ("logo1id", "g1234"),
                        ("logobin", banner_path.read_bytes()),
                    ),
                )
            )
        return _xml("SpPageBin", tuple(bins))
    if route == "/url3/pay/list/new/all.xml":
        return _xml("New", _shop_movieinfo(_indexed_products()))
    if route == "/url1/list/new/all.xml":
        return _xml("New", _theater_movieinfo(_theater_movies()))
    if route == "/url3/pay/list/popular/all.xml":
        products = sorted(
            _indexed_products(),
            key=lambda entry: int(entry[1].get("review_count", 0) or 0),
            reverse=True,
        )
        return _xml("Popular", _shop_movieinfo(products))
    if route == "/url1/list/popular/all.xml" or re.fullmatch(
        r"/url1/list/popular/\d{2}\.xml", route
    ):
        return _xml("Popular", _theater_movieinfo(_theater_movies()))
    normal_category_list = re.fullmatch(r"/url1/list/category/(\d{2})\.xml", route)
    if normal_category_list:
        list_id = normal_category_list.group(1)
        categories: list[tuple[str, object]] = [("type", 3), ("img", 0)]
        if list_id == "01":
            seen: set[int] = set()
            for movie in _theater_movies():
                category_id = int(movie.get("category_id", 11001))
                if category_id in seen:
                    continue
                seen.add(category_id)
                categories.append(
                    (
                        "categinfo",
                        (
                            ("place", len(seen)),
                            ("categid", category_id),
                            ("name", str(movie.get("category_name", "JWC24 Theater"))),
                        ),
                    )
                )
        elif list_id == "02":
            categories[1] = ("img", 1)
            for place, mii in enumerate(_concierge_miis(), 1):
                categories.append(
                    (
                        "categinfo",
                        (
                            ("place", place),
                            ("categid", 20000 + int(mii.get("mii_id", 0))),
                            ("name", str(mii.get("name", ""))[:10]),
                            ("sppageid", 0),
                            ("splinktext", "おすすめ"),
                        ),
                    )
                )
        return _xml("CategoryList", tuple(categories))
    if route == "/url3/pay/list/category/header.xml":
        return _xml(
            "PayCategoryHeader",
            (("img", 0), ("listinfo", (("place", 1), ("type", 10), ("text", "Rakuten Ichiba")))),
        )
    if re.fullmatch(r"/url3/pay/list/category/\d{2}\.xml", route):
        categories: list[tuple[str, object]] = [("type", 3), ("img", 1)]
        populated = {_shop_category(product) for _, product in _indexed_products()}
        for place, (category_id, name) in enumerate(SHOP_CATEGORIES, 1):
            if category_id in populated:
                categories.append(
                    ("categinfo", (("place", place), ("categid", category_id), ("name", name)))
                )
        return _xml(
            "PayCategoryList",
            tuple(categories),
        )
    if route == "/url3/pay/event/today.xml":
        products = _indexed_products()
        posters = tuple(
            (
                "posterinfo",
                (
                    ("seq", sequence),
                    ("posterid", movie_id),
                    ("geofilter", 0),
                ),
            )
            for sequence, (movie_id, _) in enumerate(products[:20], 1)
        )
        first_category = _shop_category(products[0][1]) if products else 10001
        return _xml(
            "Event",
            (
                ("date", date),
                ("postertime", 5),
                *posters,
                (
                    "introinfo",
                    (
                        ("seq", 1),
                        ("cntid", 1),
                        ("cnttype", 1),
                        ("dispsec", 5),
                        ("dimg", 1),
                        ("random", 0),
                        ("linktype", 5),
                        ("linkid", first_category),
                    ),
                ),
            ),
        )
    pay_wall = re.fullmatch(r"/url3/pay/wall/(\d+)\.met", route)
    if pay_wall:
        movie_id = int(pay_wall.group(1))
        products = _shop_products()
        if not 1 <= movie_id <= len(products):
            return None
        product = products[movie_id - 1]
        return _xml(
            "PosterMeta",
            (
                ("posterid", movie_id),
                ("msg", str(product.get("caption", "JWC24ショップ"))[:160]),
                ("movieid", movie_id),
                ("title", str(product.get("name", "商品"))[:96]),
                ("type", 1),
                ("aspect", 1),
            ),
        )
    pay_meta = re.fullmatch(r"/url3/pay/movie/[^/]+/\d+/(\d+)\.met", route)
    if pay_meta:
        movie_id = int(pay_meta.group(1))
        products = _shop_products()
        if not 1 <= movie_id <= len(products):
            return None
        product = products[movie_id - 1]
        item_code = str(product.get("item_code", ""))
        return _xml(
            "PayMovies",
            (
                ("movieid", movie_id),
                ("title", str(product.get("name", ""))[:96]),
                ("kana", "12345678"),
                ("len", 0),
                ("aspect", 1),
                ("dsdist", 0),
                ("staff", str(product.get("shop_name", ""))[:64]),
                ("note", str(product.get("caption", ""))[:512]),
                ("dimg", 1),
                ("eval", 0),
                ("refid", hashlib.md5(item_code.encode("utf-8"), usedforsecurity=False).hexdigest()),
                ("pricecd", 0),
                ("term", 1),
                ("price", int(product.get("price_yen", 0) or 0)),
                ("sample", 0),
                ("smpap", 0),
                ("released", 1),
                ("encrypt", 0),
                ("geofilter", 0),
            ),
        )
    simple_routes = {
        "/url2/search.cgi": ("SearchMovies", (("num", 1), ("categid", 12345))),
        "/url2/pay/psearch.cgi": ("PaySearchMovies", (("num", 1), ("categid", 12345))),
        "/url2/miiinfo.cgi": ("MiiInfo", (("code", 0), ("msg", "thanks"))),
        "/url2/related.cgi": ("RelatedMovies", (("leftmovieinfo", ""), ("rightmovieinfo", ""))),
        "/url2/pay/prelated.cgi": ("PayRelatedMovies", (("movieinfo", ""),)),
        "/url2/evaluate.cgi": ("Evaluate", (("code", 1), ("msg", "thanks"))),
        "/url2/pay/pevaluate.cgi": ("PayEvaluate", (("code", 1), ("msg", "thanks"))),
        "/url2/enquete.cgi": ("Enquete", (("code", 2), ("msg", "Vote recorded."))),
        "/url2/piceval.cgi": ("PicEval", (("code", 1), ("msg", "Vote recorded."))),
        "/url2/smp.cgi": ("Delivery", (("code", 1), ("msg", "Accepted."))),
        "/url2/pay/rivtoken.cgi": ("RIVToken", (("code", 1), ("token", 1), ("msg", "Accepted."))),
        "/url2/pay/title.cgi": ("PayTitle", (("movieinfo", ""),)),
        "/url2/pay/challenge.cgi": (
            "Challenge",
            (("code", 1), ("cblob", "SldDMjQ="), ("channelid", 1), ("msg", "Accepted.")),
        ),
        "/url2/pay/verify.cgi": (
            "Verify",
            (
                ("code", 1),
                ("url", f"{base_url.rstrip('/')}/url3/"),
                ("cookie", "jwc24"),
                ("key", "5ab362aa57dbb1dc16849e3e2d1cf2ff"),
                ("msg", "Accepted."),
            ),
        ),
        "/url2/pay/support.cgi": (
            "Support",
            (("code", 1), ("supportid", "JWC24"), ("msg", "Accepted.")),
        ),
    }
    if route in simple_routes:
        name, values = simple_routes[route]
        return _xml(name, values)
    normal_category = re.fullmatch(r"/url1/list/category/search/(\d+)", route)
    if normal_category:
        category_id = int(normal_category.group(1))
        if 20000 <= category_id <= 29999:
            mii_id = category_id - 20000
            mii = next(
                (item for item in _concierge_miis() if int(item.get("mii_id", 0)) == mii_id),
                None,
            )
            recommended_id = int(mii.get("movie_id", 0)) if mii else 0
            movies = [
                movie
                for movie in _theater_movies()
                if int(movie.get("movie_id", 0)) == recommended_id
            ]
        else:
            movies = [
                movie
                for movie in _theater_movies()
                if int(movie.get("category_id", 11001)) == category_id
            ]
        return _xml(
            "SearchMovies",
            (("num", 1), ("categid", category_id), *_theater_movieinfo(movies)),
        )
    category_search = re.fullmatch(r"/url3/pay/list/category/search/(\d+)", route)
    if category_search:
        category_id = int(category_search.group(1))
        products = [
            entry for entry in _indexed_products() if _shop_category(entry[1]) == category_id
        ]
        return _xml(
            "SearchMovies",
            (("num", 1), ("categid", category_id), *_shop_movieinfo(products)),
        )
    if re.fullmatch(r"/url1/(delivery|coupon)/[^/]+\.xml", route):
        return _xml("DeliveryAgree", (("agree", "1"),))
    if re.fullmatch(r"/url1/special/\d+/contact\.xml", route):
        return _xml("SpContact", (("contact", ""),))
    special_page = re.fullmatch(r"/url1/special/(\d+)/page\.xml", route)
    if special_page:
        room_id = int(special_page.group(1))
        room = next(
            (item for item in _special_rooms() if int(item.get("room_id", 0)) == room_id),
            None,
        )
        if room is None:
            return None
        roster = {int(mii.get("mii_id", 0)): mii for mii in _all_miis()}
        room_miis: list[tuple[str, object]] = []
        for sequence, entry in enumerate(room.get("miis", []), 1):
            if not isinstance(entry, dict):
                continue
            mii_id = int(entry.get("mii_id", 0))
            mii = roster.get(mii_id, {})
            room_miis.append(
                (
                    "miiinfo",
                    (
                        ("seq", sequence),
                        ("miiid", mii_id),
                        ("color1", str(mii.get("color1", "ffffff"))),
                        ("color2", str(mii.get("color2", "ffffff"))),
                        ("msginfo", (("msgseq", 1), ("msg", str(entry.get("message", ""))))),
                    ),
                )
            )
        intro = tuple(
            ("inmsginfo", (("inmsgseq", sequence), ("inmsg", line)))
            for sequence, line in enumerate(room.get("intro_messages", []), 1)
        )
        menus = tuple(
            ("menu", (("place", place), *_menu_pairs(menu)))
            for place, menu in enumerate(room.get("menus", []), 1)
            if isinstance(menu, dict)
        )
        return _xml(
            "SpPage",
            (
                ("sppageid", room_id),
                ("strdt", timestamp),
                ("enddt", (now + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("name", str(room.get("news", "JWC24の間"))),
                ("stopflag", 0),
                ("level", int(room.get("level", 1))),
                ("bgm", int(room.get("bgm", 2))),
                ("mascot", int(room.get("mascot", 0))),
                ("contact", 0),
                ("intro", intro),
                *room_miis,
                *menus,
                ("logo", (("logo1id", "g1234"), ("logo2id", "f1234"))),
            ),
        )
    if re.fullmatch(r"/url1/beacon/[^/]+", route):
        return _xml("SampleRequest", (("code", 1), ("msg", "JWC24")))
    if re.fullmatch(r"/url1/movie/[^/]+/\d+\.stf", route):
        return _xml("MovieStaff", (("staff", ""),))
    movie_meta = re.fullmatch(r"/url1/movie/[^/]+/(\d+)\.met", route)
    if movie_meta:
        movie_id = int(movie_meta.group(1))
        movie = next(
            (item for item in _theater_movies() if int(item.get("movie_id", 0)) == movie_id),
            None,
        )
        if movie is None:
            return None
        return _xml(
            "MovieMeta",
            (
                ("movieid", movie_id),
                ("title", str(movie.get("title", ""))[:96]),
                ("len", int(movie.get("length_seconds", 0))),
                ("aspect", int(movie.get("aspect", 1))),
                ("genre", int(movie.get("genre", 1))),
                ("sppageid", 0),
                ("dsdist", 0),
                ("staff", str(movie.get("staff", ""))[:96]),
            ),
        )
    wall_meta = re.fullmatch(r"/url1/wall/(\d+)\.met", route)
    if wall_meta:
        poster_id = int(wall_meta.group(1))
        movie = next(
            (item for item in _theater_movies() if int(item.get("movie_id", 0)) == poster_id),
            None,
        )
        if movie is None:
            return None
        return _xml(
            "PosterMeta",
            (
                ("posterid", poster_id),
                ("msg", str(movie.get("note", "JWC24 Theater"))[:160]),
                ("movieid", int(movie.get("movie_id", 0))),
                ("title", str(movie.get("title", ""))[:96]),
            ),
        )
    mii_meta = re.fullmatch(r"/url1/mii/(\d+)\.met", route)
    if mii_meta:
        mii_id = int(mii_meta.group(1))
        mii = next(
            (item for item in _all_miis() if int(item.get("mii_id", 0)) == mii_id),
            None,
        )
        if mii is None:
            return None
        messages: list[tuple[str, object]] = []
        grouped: dict[int, list[dict[str, object]]] = {}
        for message in mii.get("messages", []):
            if isinstance(message, dict):
                grouped.setdefault(int(message.get("type", 1)), []).append(message)
        for message_type in sorted(grouped):
            msglists: list[tuple[str, object]] = []
            for message in sorted(grouped[message_type], key=lambda item: int(item.get("seq", 1))):
                msglists.append(
                    (
                        "msglist",
                        (
                            ("seq", int(message.get("seq", 1))),
                            ("msg", str(message.get("text", ""))),
                            ("face", int(message.get("face", 1))),
                        ),
                    )
                )
            messages.append(("msginfo", (("type", message_type), *msglists)))
        return _xml(
            "ConciergeMii",
            (
                ("miiid", mii_id),
                ("clothes", int(mii.get("clothes", 1))),
                ("color1", str(mii.get("color1", "f58220"))),
                ("color2", str(mii.get("color2", "ffffff"))),
                ("action", int(mii.get("action", 1))),
                ("prof", str(mii.get("profile", ""))),
                ("name", str(mii.get("name", ""))[:10]),
                *messages,
                ("movieid", int(mii.get("movie_id", 1))),
                ("voice", int(mii.get("voice", 0))),
            ),
        )
    return None
