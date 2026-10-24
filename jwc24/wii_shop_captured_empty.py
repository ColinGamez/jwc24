"""Read the pinned historical generic no-results view for review/integration.

The collector captured this English notice through title-ID queries. It is not
evidence of the complete Japanese keyword-search or search-again interaction.
Original scripts/account branches are not enabled by this reader.
"""
import hashlib
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from .wii_shop_captured_catalog import page_tree
from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE

LAYOUT_SHA256 = '96015418f17ae2072be5b909699ab2df90e2c50a38e28322541c56316862b6e9'
LAYOUT_BYTES = 34978
STYLESHEETS = ('/oss/oss/common/css/oss.css', '/oss/oss/common/css/error.css')


def _resource_path(reference, base='/'):
    resolved = urlsplit(urljoin('https://capture.invalid'+base, reference))
    if (resolved.hostname != 'capture.invalid' or resolved.scheme != 'https'
            or resolved.query or resolved.fragment):
        raise ValueError('Captured display dependency is not a local resource')
    return posixpath.normpath(resolved.path)


class CapturedEmpty:
    def __init__(self, root, shared):
        from .wii_shop_artwork import Tree
        root = Path(root).resolve()
        manifest_path = root/'manifest.private.json'
        if manifest_path.stat().st_size > 16*1024*1024:
            raise ValueError('Oversized no-results capture manifest')
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        if (manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1
                or len(manifest.get('files', [])) > 4000):
            raise ValueError('Unexpected no-results capture source')
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        rows = [r for r in manifest['files'] if r.get('sha256') == LAYOUT_SHA256]
        if not rows:
            raise ValueError('Missing pinned no-results capture')
        seen = set()
        for row in rows:
            prefix = 'oss-auth.shop.wii.com/oss/serv/B_04.jsp?'
            member = row.get('member', '')
            fields = parse_qs(member.partition('?')[2])
            if (not member.startswith(prefix) or member in seen or 'titleId' not in fields
                    or not set(fields).issubset({'titleId', 'country'})
                    or row.get('bytes') != LAYOUT_BYTES
                    or row.get('file') != 'blobs/'+LAYOUT_SHA256):
                raise ValueError('Unexpected no-results capture selector/path')
            seen.add(member)
        local = (root/'blobs'/LAYOUT_SHA256).resolve()
        if not local.is_relative_to(root) or local.stat().st_size != LAYOUT_BYTES:
            raise ValueError('No-results capture outside review bounds')
        data = local.read_bytes()
        if hashlib.sha256(data).hexdigest() != LAYOUT_SHA256:
            raise ValueError('No-results capture fingerprint differs')
        source = data.decode('utf-8-sig')
        tree = Tree(source).root
        stylesheets = [n.attrs.get('href') for n in tree.walk()
                       if n.tag == 'link' and n.attrs.get('rel') == 'stylesheet']
        if tuple(stylesheets) != STYLESHEETS:
            raise ValueError('No-results capture stylesheets differ')
        self.parsed_root = page_tree(data)
        notice = self.parsed_root.find('text02-01')
        if (notice is None or self.parsed_root.find('catalogFrame') is not None
                or 'Your search did not return any results.' not in notice.render()
                or 'document.write("Catalog".replace' not in source):
            raise ValueError('No-results capture structure differs')
        dependencies = set(stylesheets)
        dependencies.update(n.attrs['src'] for n in tree.walk()
                            if n.tag == 'img' and n.attrs.get('src'))
        # Display CSS/images are required. Captured external script tags and the
        # browser favicon are intentionally outside this script-free view.
        for path in stylesheets:
            normalized = _resource_path(path)
            if normalized not in shared.shared:
                raise ValueError('Missing no-results stylesheet dependency')
            mime, body = shared.shared[normalized]
            css = body.decode('utf-8-sig' if 'UTF-8' in mime else 'cp932')
            for reference in re.findall(r'url\(\s*[\x22\x27]?([^\x22\x27)]+)', css):
                dependencies.add(_resource_path(reference.strip(), normalized))
        for node in tree.walk():
            for reference in re.findall(r'url\(\s*[\x22\x27]?([^\x22\x27)]+)', node.attrs.get('style', '')):
                dependencies.add(reference.strip())
            if node.tag == 'style':
                css = ''.join(c for c in node.children if isinstance(c, str))
                dependencies.update(re.findall(r'url\(\s*[\x22\x27]?([^\x22\x27)]+)', css))
        normalized = tuple(sorted({_resource_path(p) for p in dependencies}))
        for path in normalized:
            shared.resource_url(path)  # Raises for any uncaptured display asset.
        self.layout_html = data
        self.stylesheets = list(STYLESHEETS)
        self.display_dependencies = normalized
        self.caption = 'Catalog'
        self.layout_sha256 = LAYOUT_SHA256
        self.capture_request_count = len(rows)
        self.original_japanese_keyword_empty_state_verified = False
        self.original_search_again_verified = False
