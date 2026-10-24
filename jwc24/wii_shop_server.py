"""Loopback catalog preview for the original Wii Shop browser; no commerce API."""
import argparse
from collections import deque
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import ssl
import threading
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from .wii_shop_browse import Catalog
from .wii_shop_native import JS


def catalog_from_file(path):
    if path.stat().st_size > 32*1024*1024:
        raise ValueError('Catalog exceeds input bound')
    data = path.read_bytes()
    return Catalog(json.loads(data)['records']), hashlib.sha256(data).hexdigest()


def legacy_tls_context(cert=None, key=None, root=None):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if cert else ssl.PROTOCOL_TLS_CLIENT)
    context.set_ciphers('ALL:@SECLEVEL=0')
    context.minimum_version = ssl.TLSVersion.TLSv1
    if cert:
        context.load_cert_chain(cert, key)
    else:
        context.load_verify_locations(cafile=root)
    return context


class Application:
    def __init__(self, catalog, digest='synthetic', artwork=None):
        if artwork is None:
            raise ValueError('An archived Shop artwork renderer is required')
        self.catalog, self.digest = catalog, digest
        self.pages = artwork
        self.page_size = artwork.page_size
        self.lock = threading.Lock()
        self.events = deque(maxlen=64)
        self.last_ready = None

    def get(self, target, agent='other'):
        if len(target) > 4096:
            raise ValueError('Oversized target')
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            raise ValueError('Expected origin-form request')
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=12)
        if any(len(value) != 1 for value in query.values()):
            raise ValueError('Repeated query field')
        path = parsed.path
        if path == '/healthz':
            with self.lock:
                status = {'service': 'jwc24-wii-shop-preview', 'titles': len(self.catalog.items),
                          'catalog_sha256': self.digest, 'last_ready': self.last_ready,
                          'archived_artwork': True,
                          'native_original_scripts': bool(getattr(self.pages, 'native_assets', None)),
                          'captured_keyboard_script': bool(getattr(self.pages, 'captured_scripts', None)),
                          'category_menus_supported': hasattr(self.pages, 'category'),
                          'title_artwork_titles': len(self.pages.title_artwork.images) if getattr(self.pages, 'title_artwork', None) else 0,
                          'recent_requests': list(self.events), 'downloads_supported': False}
            return 200, 'application/json', json.dumps(status).encode()
        if path == '/ready':
            if set(query) not in ({'w', 'h', 'bridge', 'music'}, {'w', 'h', 'bridge', 'music', 'keyboard'}):
                raise ValueError('Invalid ready report')
            values = {k: int(v[0]) for k, v in query.items()}
            if not (0 < values['w'] <= 8192 and 0 < values['h'] <= 8192
                    and values['bridge'] in (0, 1) and values['music'] in (0, 1)):
                raise ValueError('Invalid ready dimensions or flags')
            if 'keyboard' in values and values['keyboard'] not in (0, 1):
                raise ValueError('Invalid ready keyboard flag')
            with self.lock:
                self.last_ready = dict(values, agent=agent)
            return 204, 'text/plain', b''
        if path == '/assets/shop.js':
            return 200, 'text/javascript', JS
        if path.startswith(('/assets/native/', '/assets/captured/', '/oss/oss/', '/title-artwork/')) and hasattr(self.pages, 'asset'):
            return self.pages.asset(path)
        if path in ('/', '/startup'):
            return 200, 'text/html; charset=utf-8', self.pages.home(len(self.catalog.items))
        if path == '/about':
            return 200, 'text/html; charset=utf-8', self.pages.about()
        if path in ('/category/wiiware', '/category/virtual-console') and hasattr(self.pages, 'category'):
            category = 'WiiWare' if path.endswith('/wiiware') else 'Virtual Console'
            return 200, 'text/html; charset=utf-8', self.pages.category(category)
        if path == '/catalog' or re.fullmatch(r'/title/[0-9A-Fa-f]{16}', path):
            if set(query)-{'offset', 'q', 'category', 'demos'}:
                raise ValueError('Unsupported catalog query')
            options = {k: query.get(k, [default])[0] for k, default in
                       (('q', ''), ('category', None), ('demos', 'all'), ('offset', '0'))}
            options['offset'] = int(options['offset'])
            if not 0 <= options['offset'] <= 0xffffffff:
                raise ValueError('Unsupported offset')
            title_ids = (path.rsplit('/', 1)[1],) if path.startswith('/title/') else ()
            result = self.catalog.query(offset=0 if title_ids else options['offset'], limit=self.page_size,
                                        search=options['q'], category=options['category'],
                                        demos=options['demos'], title_ids=title_ids)
            if title_ids:
                if not result['items']:
                    return 404, 'text/plain', b'Title not found'
                body = self.pages.detail(result['items'][0], options)
            else:
                body = self.pages.browse(result, options)
            return 200, 'text/html; charset=utf-8', body
        return 404, 'text/plain', b'Not found'


def create_server(address, application, *, cert=None, key=None):
    if address[0] != '127.0.0.1':
        raise ValueError('Preview listener must bind IPv4 loopback')

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_args):
            pass  # Never persist query strings, identifiers, headers or bodies.

        def respond(self, head=False):
            agent = 'opera' if 'Opera' in self.headers.get('User-Agent', '') else 'other'
            try:
                status, content_type, body = application.get(self.path, agent)
            except (ValueError, UnicodeError, OverflowError):
                status, content_type, body = 400, 'text/plain', b'Invalid request'
            try:
                route = urlsplit(self.path).path
            except ValueError:
                route = ''
            safe_route = route if route in ('/', '/startup', '/catalog', '/about', '/ready') else 'asset' if route.startswith(('/assets/', '/oss/oss/', '/title-artwork/')) else 'category' if route.startswith('/category/') else 'title' if re.fullmatch('/title/[0-9A-Fa-f]{16}', route) else 'other'
            if route != '/healthz':
                with application.lock:
                    application.events.append({'route': safe_route, 'status': status, 'agent': agent,
                                               'method': self.command, 'bytes': len(body),
                                               'tls': self.connection.version() if isinstance(self.connection, ssl.SSLSocket) else None})
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def do_GET(self):
            self.respond()

        def do_HEAD(self):
            self.respond(head=True)

        def do_POST(self):
            self.send_response(405)
            self.send_header('Allow', 'GET, HEAD')
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True

    server = ThreadingHTTPServer(address, Handler)
    server.daemon_threads = True
    if cert:
        server.socket = legacy_tls_context(cert, key).wrap_socket(server.socket, server_side=True)
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=Path('private/wii_shop/mariocube-catalog-ids.json'))
    parser.add_argument('--port', type=int, default=18443)
    parser.add_argument('--cert', type=Path)
    parser.add_argument('--key', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--root', type=Path)
    parser.add_argument('--artwork', type=Path, default=Path('private/wii_shop/artwork-v2'))
    parser.add_argument('--title-artwork', type=Path, default=Path('private/wii_shop/title-artwork-v1'))
    parser.add_argument('--native-assets', type=Path, default=Path('private/wii_shop/native-assets-v1'))
    parser.add_argument('--frontend-capture', type=Path, default=Path('private/wii_shop/frontend-capture-v1'))
    args = parser.parse_args(argv)
    if args.check:
        context = legacy_tls_context(root=args.root)
        with urlopen(f'https://127.0.0.1:{args.port}/healthz', context=context, timeout=3) as response:
            status = json.load(response)
        if status.get('service') != 'jwc24-wii-shop-preview' or status.get('titles', 0) < 1:
            raise ValueError('Unexpected preview service')
        print(json.dumps(status))
        return
    if bool(args.cert) != bool(args.key):
        parser.error('Both TLS certificate and key are required')
    catalog, digest = catalog_from_file(args.catalog)
    from .wii_shop_artwork import Artwork
    from .wii_shop_native_assets import NativeAssets
    from .wii_shop_captured_scripts import CapturedScripts
    artwork = Artwork(args.artwork, args.title_artwork, digest, NativeAssets(args.native_assets),
                      CapturedScripts(args.frontend_capture))
    server = create_server(('127.0.0.1', args.port), Application(catalog, digest, artwork), cert=args.cert, key=args.key)
    print(f'JWC24 Shop preview ready: {len(catalog.items)} titles', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
