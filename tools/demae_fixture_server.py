"""Local-only offline Demae fixture harness; never a production service.

Supports startup fixtures and optional postal-directory municipality lists.
No restaurant orders, personal credentials or upstream requests are performed.
"""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_demae_area_fixture import build_root_fixture, build_postal_fallback_fixture, build_auth_fixture, build_document_fixture
from jwc24.demae_response import inspect_area_response
from tools.build_demae_municipality_fixtures import build_municipalities
from tools.build_demae_town_fixture import build_towns
from jwc24.demae_area_registry import AreaRegistry
from jwc24.japan_post import areas
from jwc24.demae_directory import DirectoryCategories
from tools.build_demae_category_fixture import build_categories
from tools.build_demae_directory_shops import build_directory_shops
from jwc24.demae_menu_directory import MenuDirectory


def create_server(port=0, *, postal_database=None, town_registry=None, directory_catalogs=None,
                  directory_shop_previews=None, directory_images=None, directory_image_cache=None,
                  directory_all_shops=False, directory_database=None, menu_directory=None):
    if menu_directory is not None and not isinstance(menu_directory, MenuDirectory):
        raise ValueError('Menu preview requires a validated menu directory')
    if directory_database is not None:
        if directory_catalogs is not None or menu_directory is not None or not Path(directory_database).is_file():
            raise ValueError('Directory database must exist and excludes separate catalog inputs')
        from jwc24.demae_database import DemaeDatabase
        archive = DemaeDatabase(directory_database)
        directory_catalogs = archive.catalogs()
        menu_directory = archive.menu_directory()
    payload = build_root_fixture(postal_database)
    inspect_area_response(payload, variant='root')
    postal_payload = build_postal_fallback_fixture()
    auth_payload = build_auth_fixture()
    document_payload = build_document_fixture()
    municipalities = {}
    town_responses = {}
    directory = None
    category_responses = {}
    shop_responses = {}
    preview_category_codes = {}
    images = {}
    image_store = None
    if directory_catalogs is not None:
        if postal_database is None or town_registry is None:
            raise ValueError('Directory categories require postal data and an area registry')
        directory = DirectoryCategories(directory_catalogs, town_registry, postal_database)
        category_responses[()] = build_categories([], allow_empty=True)
        for codes in set(directory.categories.values()):
            category_responses[codes] = build_categories(codes)
    if directory_all_shops:
        if directory is None or directory_shop_previews is not None:
            raise ValueError('All-directory mode requires catalogs and excludes a preview selection')
        for municipality, groups in directory.restaurants.items():
            for category, rows in groups.items():
                shop_responses[(municipality, category)] = build_directory_shops(
                    rows, category, max_restaurants=1000)
    if directory_shop_previews is not None:
        if directory is None or not isinstance(directory_shop_previews, list) or not 1 <= len(directory_shop_previews) <= 50:
            raise ValueError('Shop previews require directory data and a bounded explicit manifest')
        for preview in directory_shop_previews:
            if not isinstance(preview, dict) or set(preview) != {'municipality', 'category_code', 'restaurant_ids'}:
                raise ValueError('Invalid shop preview manifest entry')
            municipality, category = preview['municipality'], preview['category_code']
            if (not isinstance(municipality, str) or not re.fullmatch(r'[0-9]{5}', municipality)
                    or not isinstance(category, str)):
                raise ValueError('Invalid shop preview location or category')
            key = (municipality, category)
            if key in shop_responses:
                raise ValueError('Duplicate shop preview location/category')
            rows = {row['id']: row for row in directory.restaurants.get(municipality, {}).get(category, ())}
            selected = preview['restaurant_ids']
            if (not isinstance(selected, list) or not 1 <= len(selected) <= 25
                    or any(not isinstance(identifier, str) or identifier not in rows for identifier in selected)):
                raise ValueError('Shop preview restaurant is absent from this municipality/category')
            shop_responses[key] = build_directory_shops([rows[identifier] for identifier in selected], category)
        # A staged preview must not advertise a category whose shop-list route
        # is unavailable. Keep the complete source directory snapshot intact.
        for municipality, codes in directory.categories.items():
            available = tuple(code for code in codes if (municipality, code) in shop_responses)
            preview_category_codes[municipality] = available
            if available not in category_responses:
                category_responses[available] = build_categories(available, allow_empty=True)
    if directory_images is not None:
        if directory_shop_previews is None:
            raise ValueError('Directory images require an explicit shop preview selection')
        from tools.cache_demae_directory_images import load_images
        allowed = {identifier for preview in directory_shop_previews for identifier in preview['restaurant_ids']}
        images = load_images(directory_images, allowed)
    if directory_image_cache is not None:
        if directory_catalogs is None:
            raise ValueError('Catalog image caching requires source directory catalogs')
        from tools.demae_directory_image_store import DirectoryImageStore
        image_store = DirectoryImageStore(directory_catalogs, directory_image_cache)
    if town_registry is not None and (postal_database is None or not isinstance(town_registry, AreaRegistry)):
        raise ValueError('Town routes require a postal database and validated registry')
    if postal_database is not None:
        # Validate and snapshot before listening; no database reads per request.
        for number in range(1, 48):
            identity = f'JP-{number:02d}'
            municipalities['TEST-' + identity] = build_municipalities(postal_database, identity)[0]
            if town_registry is not None:
                for city in areas(postal_database, identity):
                    town_responses['M' + city['id']] = build_towns(postal_database, city['id'], registry=town_registry)[0]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # URL query values can contain personal data.

        def reply(self, status, data=b'Unsupported offline fixture request', *, content_type=None):
            self.send_response(status)
            self.send_header('Content-Type', content_type or ('application/xml; charset=utf-8' if status == 200 else 'text/plain; charset=utf-8'))
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-JWC24-Scope', 'synthetic-offline-fixture')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if len(self.path) > 2048:
                return self.reply(414)
            url = urlsplit(self.path)
            if url.path.startswith('/logoimg2/'):
                match = re.fullmatch(r'/logoimg2/(hotpepper:J[0-9]{9})\.jpg', url.path)
                data = images.get(match[1]) if match and not url.query else None
                if data is None and match and not url.query and image_store is not None:
                    try:
                        data = image_store.get(match[1])
                    except (ValueError, OSError):
                        print('Directory source image unavailable (details withheld)', flush=True)
                        return self.reply(502)
                return self.reply(200, data, content_type='image/jpeg') if data else self.reply(404)
            if url.path == '/health' and not url.query:
                capabilities = {'service': 'jwc24-demae-fixture', 'schema_version': 1,
                                'municipality_prefectures': len(municipalities),
                                'town_navigation': bool(town_responses), 'restaurant_navigation': False,
                                'directory_categories': directory is not None,
                                'directory_shop_preview': bool(shop_responses),
                                'directory_all_shops': directory_all_shops,
                                'directory_restaurants': sum(len(rows) for groups in directory.restaurants.values()
                                                             for rows in groups.values()) if directory_all_shops else 0,
                                'directory_image_sources': len(image_store.index) if image_store else len(images),
                                'menu_preview': menu_directory is not None,
                                'basket_preview': menu_directory is not None,
                                'native_menu_integrated': False,
                                'ordering_supported': False}
                return self.reply(200, json.dumps(capabilities).encode('utf-8'),
                                  content_type='application/json; charset=utf-8')
            try:
                query = parse_qs(url.query, strict_parsing=True, max_num_fields=8, keep_blank_values=True)
            except ValueError:
                return self.reply(400)
            if url.path == '/preview/menu':
                # Read-only JSON for integration work, not the native XML API.
                if menu_directory is None:
                    return self.reply(404)
                if (not {'restaurant_id'} <= set(query) <= {'restaurant_id', 'page', 'page_size', 'category'}
                        or any(len(values) != 1 or not values[0] for values in query.values())):
                    return self.reply(400)
                identifier = query['restaurant_id'][0]
                if not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier):
                    return self.reply(400)
                if identifier not in menu_directory.restaurants:
                    return self.reply(404)
                for key in ('page', 'page_size'):
                    if key in query and not re.fullmatch(r'[1-9][0-9]{0,3}', query[key][0]):
                        return self.reply(400)
                try:
                    result = menu_directory.menu_page(identifier,
                        page=int(query.get('page', ['1'])[0]),
                        page_size=int(query.get('page_size', ['6'])[0]),
                        category=query.get('category', [None])[0])
                except ValueError:
                    return self.reply(409, b'Verified menu unavailable or page/category invalid')
                return self.reply(200, json.dumps({**result, 'native_menu_integrated': False},
                    ensure_ascii=False).encode('utf-8'), content_type='application/json; charset=utf-8')
            expected = {'action': ['webApi_area_list'], 'platform': ['wii'], 'areaCode': ['0']}
            auth = {'action': ['webApi_Authkey'], 'platform': ['wii']}
            documents = {'action': ['webApi_document_template'], 'platform': ['wii'], 'version': ['00000']}
            if (shop_responses and url.path == '/nwapi.php'
                    and set(query) == {'action', 'platform', 'areaCode', 'categoryCode', 'isReservation', 'selectType'}
                    and query['action'] == ['webApi_shop_list'] and query['platform'] == ['wii']
                    and query['isReservation'] == ['0'] and query['selectType'] == ['1']
                    and len(query['areaCode']) == len(query['categoryCode']) == 1):
                try:
                    area = town_registry.resolve(query['areaCode'][0])
                except ValueError:
                    area = None
                body = shop_responses.get((area['municipality'], query['categoryCode'][0])) if area else None
                if body is not None:
                    print('Fixture served: directory shops (ordering unavailable)', flush=True)
                    return self.reply(200, body)
                return self.reply(400)
            if (directory is not None and url.path == '/nwapi.php'
                    and set(query) == {'action', 'platform', 'areaCode', 'reservationType'}
                    and query['action'] == ['webApi_category_list'] and query['platform'] == ['wii']
                    and query['reservationType'] == ['0'] and len(query['areaCode']) == 1):
                try:
                    area = town_registry.resolve(query['areaCode'][0])
                    codes = directory.codes_for(query['areaCode'][0])
                    if area is not None and directory_shop_previews is not None:
                        codes = preview_category_codes.get(area['municipality'], ())
                except ValueError:
                    area = None
                    codes = ()
                if area is not None:
                    print('Fixture served: directory categories (no delivery claim)', flush=True)
                    return self.reply(200, category_responses[codes])
                return self.reply(400)
            if url.path == '/nwapi.php' and query == documents:
                print('Fixture served: documents', flush=True)
                return self.reply(200, document_payload)
            if url.path == '/nwapi.php' and query == auth:
                print('Fixture served: auth', flush=True)
                return self.reply(200, auth_payload)
            if (url.path == '/nwapi.php' and set(query) == {'action', 'platform', 'zipCode'}
                    and query['action'] == ['webApi_area_list'] and query['platform'] == ['wii']
                    and len(query['zipCode']) == 1 and re.fullmatch(r'[0-9]{7}', query['zipCode'][0])):
                # Lookup-to-native selection is unresolved. Status 13 takes the
                # traced manual-selection fallback without inventing an address.
                print('Fixture served: postal manual-selection fallback', flush=True)
                return self.reply(200, postal_payload)
            if url.path == '/nwapi.php' and set(query) == {'action', 'platform', 'areaCode'}:
                code = query['areaCode']
                if (query['action'] == ['webApi_area_list'] and query['platform'] == ['wii']
                        and len(code) == 1 and code[0] in municipalities):
                    print('Fixture served: municipalities', flush=True)
                    return self.reply(200, municipalities[code[0]])
                if (query['action'] == ['webApi_area_list'] and query['platform'] == ['wii']
                        and len(code) == 1 and code[0] in town_responses):
                    print('Fixture served: experimental decimal towns', flush=True)
                    return self.reply(200, town_responses[code[0]])
            if url.path != '/nwapi.php' or query != expected:
                known = {'webApi_area_list', 'webApi_Authkey', 'webApi_document_template',
                         'webApi_category_list', 'webApi_area_one', 'webApi_area_shopinfo',
                         'webApi_shop_list', 'webApi_shop_one', 'webApi_menu_list',
                         'webApi_item_list', 'webApi_item_one'}
                action = query.get('action', [])
                label = action[0] if len(action) == 1 and action[0] in known else '[withheld]'
                print(f'Fixture rejected: {label} (query values withheld)', flush=True)
                return self.reply(400)
            print('Fixture served: root areas', flush=True)
            self.reply(200, payload)

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path == '/preview/basket':
                self.close_connection = True
                if menu_directory is None:
                    return self.reply(404)
                if url.query:
                    return self.reply(400)
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if (self.headers.get('Transfer-Encoding') or not 1 <= length <= 16384
                            or self.headers.get_content_type() != 'application/json'):
                        raise ValueError('Invalid basket payload')

                    def unique_object(pairs):
                        result = {}
                        for key, value in pairs:
                            if key in result:
                                raise ValueError('Duplicate JSON field')
                            result[key] = value
                        return result

                    body = json.loads(self.rfile.read(length).decode('utf-8'),
                                      object_pairs_hook=unique_object)
                    if not isinstance(body, dict) or set(body) != {'restaurant_id', 'selections'}:
                        raise ValueError('Invalid basket fields')
                    identifier = body['restaurant_id']
                    if not isinstance(identifier, str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier):
                        raise ValueError('Invalid restaurant identity')
                except (ValueError, UnicodeError, RecursionError):
                    return self.reply(400)
                # Consume the bounded request before rejecting its origin so
                # closing on Windows does not reset an unread request body.
                origin = self.headers.get('Origin')
                try:
                    if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                        return self.reply(403)
                except ValueError:
                    return self.reply(403)
                if identifier not in menu_directory.restaurants:
                    return self.reply(404)
                try:
                    result = menu_directory.plan(identifier, body['selections'])
                except ValueError:
                    return self.reply(409, b'Verified basket unavailable or selections invalid')
                # Calculate a plan only. No handoff token, confirmation or mail.
                return self.reply(200, json.dumps({**result, 'native_menu_integrated': False},
                    ensure_ascii=False).encode('utf-8'), content_type='application/json; charset=utf-8')
            # Native area navigation can submit the same lookup as a form.
            # Admit only the exact read-only area queries supported by GET.
            stage = 'headers'
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 2048 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid form size')
                url = urlsplit(self.path)
                stage = 'form decoding'
                body = self.rfile.read(length).decode('ascii')
                # Some native callers keep action/platform in the URL even
                # when selecting POST. Parse both without losing duplicates.
                encoded = '&'.join(part for part in (url.query, body) if part)
                query = parse_qs(encoded, strict_parsing=True, max_num_fields=8)
                if (url.path == '/nwapi.php'
                        and query.get('action') == ['webApi_inquiry_done']
                        and query.get('platform') == ['wii']):
                    # The native error reporter (0x800EA644) uses inquiry_done.
                    # Extract only its labeled numeric error; discard all report
                    # text, identifiers and URL data instead of forwarding it.
                    report = parse_qs(encoded, strict_parsing=True, max_num_fields=8,
                                      encoding='cp932').get('message', [''])[0]
                    match = re.search(r'エラーコード[：:]\s*([0-9]{6})(?![0-9])', report)
                    if match is None:
                        report = query.get('message', [''])[0]
                        match = re.search(r'エラーコード[：:]\s*([0-9]{6})(?![0-9])', report)
                    code = match[1] if match else '[unavailable]'
                    print(f'Fixture received native diagnostic: code={code}; report discarded', flush=True)
                    self.close_connection = True
                    return self.reply(200, b'<?xml version="1.0" encoding="UTF-8"?>'
                                      b'<response><apiStatus><code><![CDATA[0]]></code>'
                                      b'</apiStatus></response>')
                stage = 'route or fields'
                if (url.path != '/nwapi.php'
                        or query.get('action') != ['webApi_area_list']
                        or query.get('platform') != ['wii']
                        or set(query) != {'action', 'platform', 'areaCode'}
                        or len(query['areaCode']) != 1
                        or query['areaCode'][0] not in {'0', *municipalities, *town_responses}):
                    raise ValueError('Unsupported form lookup')
            except (ValueError, UnicodeError):
                # Report structure only, never URL/body values or arbitrary keys.
                known_fields = {'action', 'platform', 'areaCode', 'zipCode'}
                fields = sorted(k for k in locals().get('query', {}) if k in known_fields)
                action_values = locals().get('query', {}).get('action', [])
                action = action_values[0] if len(action_values) == 1 and re.fullmatch(
                    r'webApi_[A-Za-z_]{1,48}', action_values[0]) else '[withheld]'
                print(f'Fixture rejected: POST stage={stage}; known fields={fields}; '
                      f'action={action}; '
                      f'api_path={urlsplit(self.path).path == "/nwapi.php"}; '
                      f'url_query={bool(urlsplit(self.path).query)}; '
                      f'form_type={self.headers.get_content_type() == "application/x-www-form-urlencoded"} '
                      '(values withheld)', flush=True)
                self.close_connection = True
                return self.reply(405)
            self.path = '/nwapi.php?' + encoded
            self.do_GET()
            self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18085)
    parser.add_argument('--postal-database', type=Path,
                        help='Enable experimental prefecture-to-municipality navigation')
    parser.add_argument('--town-registry', type=Path,
                        help='Opt in to experimental decimal town lists; requires postal database')
    parser.add_argument('--directory-catalogs', type=Path,
                        help='Opt in to municipality-filtered Hot Pepper categories; rows require an explicit preview manifest')
    parser.add_argument('--directory-database', type=Path,
                        help='Use retained restaurant records from the persistent Demae database')
    parser.add_argument('--directory-shop-previews', type=Path,
                        help='Explicit read-only shop selection manifest; requires the directory client candidate')
    parser.add_argument('--directory-all-shops', action='store_true',
                        help='Serve every geographically matched catalog restaurant; directory client required')
    parser.add_argument('--directory-images', type=Path,
                        help='Validated private source JPEG cache for explicit preview restaurants')
    parser.add_argument('--directory-image-cache', type=Path,
                        help='On-demand unmodified JPEG cache for all source directory restaurants')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    registry = AreaRegistry(json.loads(args.town_registry.read_text(encoding='utf-8'))) if args.town_registry else None
    catalogs = None
    if args.directory_catalogs and args.directory_database:
        parser.error('Choose directory catalogs or the persistent database')
    if args.directory_catalogs or args.directory_database:
        if not args.postal_database or registry is None:
            parser.error('Directory categories require --postal-database and --town-registry')
        if args.directory_catalogs:
            paths = sorted(args.directory_catalogs.glob('JP-*-catalog.json'))
            if not paths:
                parser.error('No directory catalogs found')
            catalogs = [json.loads(path.read_bytes()) for path in paths]
    if args.directory_shop_previews and catalogs is None and not args.directory_database:
        parser.error('Shop previews require --directory-catalogs')
    shop_previews = json.loads(args.directory_shop_previews.read_bytes()) if args.directory_shop_previews else None
    with create_server(args.port, postal_database=args.postal_database, town_registry=registry,
                       directory_catalogs=catalogs, directory_shop_previews=shop_previews,
                       directory_images=args.directory_images,
                       directory_all_shops=args.directory_all_shops,
                       directory_database=args.directory_database,
                       directory_image_cache=args.directory_image_cache) as server:
        print(f'Offline synthetic fixture on 127.0.0.1:{server.server_port}; not native compatibility', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
