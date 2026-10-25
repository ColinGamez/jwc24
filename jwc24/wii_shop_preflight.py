"""Offline Shop preview assembly and dependency checks; never opens a listener.

This verifies the current experiment, including its documented fallbacks. Passing
does not establish original Japanese fidelity, native rendering or commerce.
"""
from dataclasses import dataclass, fields
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit


@dataclass(frozen=True)
class PreviewPacks:
    catalog: Path = Path('private/wii_shop/mariocube-catalog-ids.json')
    artwork: Path = Path('private/wii_shop/artwork-v2')
    title_artwork: Path = Path('private/wii_shop/title-artwork-v4')
    native_assets: Path = Path('private/wii_shop/native-assets-v1')
    frontend_capture: Path = Path('private/wii_shop/frontend-capture-v1')
    title_metadata: Path = Path('private/wii_shop/title-metadata-v2/metadata.json')
    catalog_capture: Path = Path('private/wii_shop/frontend-japan-catalog-v2')
    title_support: Path = Path('private/wii_shop/frontend-title-support-v1')
    title_page_index: Path = Path('private/wii_shop/title-pages-v2/index.json')
    catalog_evidence_capture: Path = Path('private/wii_shop/frontend-all-catalog-v1')
    descriptions: Path = Path('private/wii_shop/descriptions-v2')
    navigation_capture: Path = Path('private/wii_shop/frontend-navigation-v1')


def load_preview_application(packs=None):
    """Use the same validated private packs as the server, without TLS or NAND."""
    from .wii_shop_artwork import Artwork
    from .wii_shop_native_assets import NativeAssets
    from .wii_shop_captured_scripts import CapturedScripts
    from .wii_shop_captured_catalog import CapturedCatalog
    from .wii_shop_captured_titles import CapturedTitlePages
    from .wii_shop_captured_empty import CapturedEmpty
    from .wii_shop_descriptions import Descriptions
    from .wii_shop_captured_navigation import CapturedNavigation
    from .wii_shop_server import Application, catalog_from_file

    packs = PreviewPacks() if packs is None else packs
    if type(packs) is not PreviewPacks or any(not isinstance(getattr(packs, f.name), Path)
                                            for f in fields(packs)):
        raise ValueError('Expected explicit Shop pack paths')
    capture = CapturedScripts(packs.frontend_capture)
    catalog, digest = catalog_from_file(packs.catalog, packs.title_metadata, capture.manifest_sha256)
    identifiers = {item['title_id'] for item in catalog.items}
    artwork = Artwork(packs.artwork, packs.title_artwork, digest, NativeAssets(packs.native_assets),
        capture, CapturedCatalog(packs.catalog_capture, identifiers),
        CapturedTitlePages(capture, catalog.title_metadata, packs.title_support,
                           identifiers, packs.title_page_index),
        CapturedEmpty(packs.catalog_evidence_capture, capture),
        Descriptions(packs.descriptions, digest, identifiers, shared_paths=capture.shared),
        CapturedNavigation(packs.navigation_capture, capture))
    return Application(catalog, digest, artwork)


class PreviewPreflightError(ValueError):
    """A bounded offline check failed; diagnostics exclude paths and content."""


_CSS_URL = re.compile(r'''url\(\s*(["']?)([^)"']+)\1\s*\)''', re.I)
_CSS_IMPORT = re.compile(r'''@import\s+(["'])([^"']+)\1''', re.I)


def _css_resources(value):
    # Quoted @import is a distinct valid form, without a surrounding url().
    # Comments must not create requests that the browser would never make.
    value = re.sub(r'/\*.*?\*/', '', value, flags=re.S)
    for pattern in (_CSS_URL, _CSS_IMPORT):
        for match in pattern.finditer(value):
            yield match[2].strip()


class _Dependencies(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.resources, self.styles = [], []
        self.in_style = False
        self.feed(body.decode('utf-8-sig'))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'style':
            self.in_style = True
        if tag in ('img', 'input', 'script') and attrs.get('src'):
            self.resources.append(attrs['src'])
        if tag == 'link' and attrs.get('href') and 'stylesheet' in attrs.get('rel', '').lower().split():
            self.resources.append(attrs['href'])
        if attrs.get('style'):
            self.styles.append(attrs['style'])

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False

    def handle_data(self, value):
        if self.in_style:
            self.styles.append(value)


def preflight_preview(application, *, progress=None):
    """Render every retained title/support page and resolve display dependencies.

    Only Application.get is called: no socket, HTTP client, browser, original
    executable, device state or credential is needed. Script execution, dynamic
    resources, anchors and native object behavior are deliberately not claimed.
    """
    if progress is not None and not callable(progress):
        raise PreviewPreflightError('Expected an offline progress callback')
    items = application.catalog.items
    if not 0 < len(items) <= 10000 or not 0 < application.page_size <= 100:
        raise PreviewPreflightError('Preview catalog outside preflight bounds')
    identifiers = {item['title_id'] for item in items}
    if len(identifiers) != len(items) or any(not re.fullmatch('[0-9A-Fa-f]{16}', i)
                                          for i in identifiers):
        raise PreviewPreflightError('Invalid preview title identifiers')
    pages = application.pages
    support = getattr(pages, 'captured_titles', None)
    controllers = set(getattr(support, 'controller_rows', {})) & identifiers
    details = set(getattr(support, 'detail_rows', {})) & identifiers
    descriptions = set(getattr(getattr(pages, 'descriptions', None), 'rows', {})) & identifiers
    routes = ['/', '/startup', '/about', '/category/wiiware', '/category/virtual-console']
    routes += ['/catalog?offset='+str(offset) for offset in range(0, len(items), application.page_size)]
    routes += ['/title/'+identifier for identifier in sorted(identifiers)]
    routes += ['/controller/'+identifier for identifier in sorted(controllers)]
    routes += ['/description/'+identifier for identifier in sorted(descriptions)]
    assets, asset_bytes, html_bytes = set(), 0, 0
    failures = {'html_routes': 0, 'display_dependencies': 0, 'external_display_dependencies': 0}

    def get(target, kind):
        try:
            status, mime, body = application.get(target)
        except (ValueError, KeyError, TypeError, UnicodeError, OSError):
            failures[kind] += 1
            return None
        if (status != 200 or not isinstance(mime, str) or not isinstance(body, bytes)
                or not body or len(body) > 8*1024*1024):
            failures[kind] += 1
            return None
        return mime, body

    def resource(value, base, depth=0):
        nonlocal asset_bytes
        if len(value) > 4096 or depth > 32:
            raise PreviewPreflightError('Preview dependency outside preflight bounds')
        try:
            parsed = urlsplit(value.strip())
            if parsed.scheme or parsed.netloc:
                failures['external_display_dependencies'] += 1
                return
            target = urlsplit(urljoin(base, value.strip())).path
        except ValueError:
            raise PreviewPreflightError('Invalid preview dependency') from None
        if not target.startswith('/') or target in assets:
            return
        if len(assets) >= 20000:
            raise PreviewPreflightError('Preview dependency count exceeds preflight bound')
        assets.add(target)
        result = get(target, 'display_dependencies')
        if result is None:
            return
        mime, body = result
        asset_bytes += len(body)
        if mime.split(';', 1)[0].strip().lower() == 'text/css':
            # CSS URL spelling is ASCII; source CSS may contain Japanese comments.
            for value in _css_resources(body.decode('latin-1')):
                resource(value, target, depth+1)

    for index, target in enumerate(routes):
        if progress is not None and index % 100 == 0:
            progress(index, len(routes))
        result = get(target, 'html_routes')
        if result is None:
            continue
        mime, body = result
        if mime.split(';', 1)[0].strip().lower() != 'text/html':
            failures['html_routes'] += 1
            continue
        html_bytes += len(body)
        try:
            parser = _Dependencies(body)
        except (ValueError, UnicodeError):
            raise PreviewPreflightError('Invalid preview HTML') from None
        for value in parser.resources:
            resource(value, target)
        for style in parser.styles:
            for value in _css_resources(style):
                resource(value, target)
    if progress is not None:
        progress(len(routes), len(routes))
    return {'schema_version': 1, 'offline_preview_passed': not any(failures.values()),
            'titles': len(items), 'html_routes_checked': len(routes),
            'display_dependencies_checked': len(assets), 'html_bytes_checked': html_bytes,
            'display_dependency_bytes_checked': asset_bytes,
            'failures': failures,
            'captured_detail_titles': len(details), 'captured_controller_titles': len(controllers),
            'captured_description_titles': len(descriptions),
            'missing_captured_detail_titles': len(identifiers-details),
            'missing_captured_controller_titles': len(identifiers-controllers),
            'missing_captured_description_titles': len(identifiers-descriptions),
            'http_tls_checked': False, 'scripts_executed': False, 'native_rendering_checked': False,
            'commerce_supported': False, 'complete_original_japanese_experience': False}
