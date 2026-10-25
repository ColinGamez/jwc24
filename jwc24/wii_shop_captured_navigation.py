"""Read pinned captured VC navigation without enabling account/commerce scripts.

The captured English menu is not a recovered Japanese localization. Destination
metadata preserves original meanings; it does not supply popularity/new-release
data or the missing B_23 category gateway.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs

from .wii_shop_captured_catalog import page_tree
from .wii_shop_captured_empty import STYLESHEETS, _resource_path
from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE

PAGE_PINS = {
    'B_01.jsp': ('da03f9e6de729ad6763e71c2e83ea0e2a4c62d6e2df50dd76321440d1c86c854', 32496),
    'B_03.jsp': ('db6afe02557b35e38d4e5507e710bc51ce07f40ac342b8def274cbbd91360651', 48365),
}
MEMBER_PINS = {
    'B_01.jsp': 'a3c4b749ef84012fcd5a7450a288b5368080281e41ed5df829f79c7337aac048',
    'B_03.jsp': 'fcbf3675f86faf44fd1a56375ba1e68f8c0d6a09ead08b7484a7907c9cdabee3',
}
SYSTEM_CODES = ('WII', 'FC/NES', 'SFC/SNES', 'N64', 'PCE/TG16', 'MD/GEN',
                'NEOGEO', 'MASTER', 'VCA', 'WIIWARE')
SYSTEM_SCROLL_SHA256 = '858edbc75a11a52196ef379a2cffcf6fe26810e51955d41fbeeb9b120c746b22'


def _text(node):
    from .wii_shop_artwork import Node
    if node is None or node.tag in ('script', 'style'):
        return ''
    return ''.join(_text(c) if isinstance(c, Node) else c for c in node.children).strip()


def _destination(value):
    match = re.search(r"([WB]_\d\d\.jsp)(?:\?([^\x27\x22)]*))?", value)
    if not match:
        raise ValueError('Captured control has no reviewed destination')
    fields = parse_qs(match[2] or '')
    if not set(fields).issubset({'p', 'vc', 'popular', 'order', 'platform'}):
        raise ValueError('Unexpected captured navigation destination parameters')
    if any(len(v) != 1 or not re.fullmatch(r'[A-Za-z0-9_/-]{1,40}', v[0]) for v in fields.values()):
        raise ValueError('Unexpected captured navigation parameter value')
    return {'page': match[1], 'query': {k: v[0] for k, v in fields.items()}}


@dataclass
class NavigationPage:
    page: str
    layout_html: bytes
    parsed_root: object
    stylesheets: tuple
    styles: str
    controls: tuple
    display_dependencies: tuple
    missing_dependencies: tuple
    back_page: str
    navigation_script: bytes = b''

    @property
    def ready_for_display(self):
        return not self.missing_dependencies


class CapturedNavigation:
    def __init__(self, root, shared):
        self.root = Path(root).resolve()
        path = self.root/'manifest.private.json'
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized navigation capture manifest')
        raw = path.read_bytes()
        self.manifest = json.loads(raw)
        if (self.manifest.get('source') != SOURCE or self.manifest.get('archive_sha1') != ARCHIVE_SHA1
                or len(self.manifest.get('files', [])) > 1000):
            raise ValueError('Unexpected navigation capture source')
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.shared = shared
        vc = self._load('B_01.jsp')
        self.vc_root = vc.parsed_root
        self.vc_layout_html = vc.layout_html
        self.vc_stylesheets = vc.stylesheets
        self.vc_styles = vc.styles
        self.vc_controls = vc.controls
        self.vc_back_page = vc.back_page
        self.vc_dependencies = vc.display_dependencies
        field = vc.parsed_root.find('Image04s')
        if field is None:
            raise ValueError('Captured VC title-search field missing')
        match = re.search(r'kbd\.call\(\s*(cKT_\w+)\s*,\s*(\d+)', field.attrs.get('onmousedown', ''))
        if (not match or match.groups() != ('cKT_PredictNoLF', '5')
                or field.attrs.get('maxlength') != '40'
                or "'title', searchValue" not in field.attrs.get('onchange', '')):
            raise ValueError('Captured VC keyboard binding differs')
        self.vc_search = {'keyboard_mode': match[1], 'keyboard_rows': int(match[2]),
                          'maximum_characters': 40, 'query_parameter': 'title',
                          'destination': {'page': 'B_04.jsp', 'query': {'p': '1', 'vc': 'true'}}}
        self.original_japanese_navigation_verified = False
        self.popular_new_release_data_verified = False
        self.category_gateway_recovered = False

    def _load(self, page, *, allow_incomplete=False):
        from .wii_shop_artwork import Tree
        fingerprint, size = PAGE_PINS[page]
        member = 'oss-auth.shop.wii.com/oss/serv/'+page
        rows = [r for r in self.manifest['files'] if r.get('member', '').partition('?')[0] == member]
        if len(rows) != 1:
            raise ValueError('Missing or ambiguous pinned navigation page')
        row = rows[0]
        # Pin the recorded title-ID selector without emitting its full query.
        # No account/locale-scoped capture can acquire this page's attribution.
        if (set(parse_qs(row['member'].partition('?')[2])) != {'titleId'}
                or hashlib.sha256(row['member'].encode('utf-8')).hexdigest() != MEMBER_PINS[page]
                or row.get('sha256') != fingerprint or row.get('bytes') != size
                or row.get('file') != 'blobs/'+fingerprint):
            raise ValueError('Unexpected navigation page fingerprint/member/path')
        local = (self.root/row['file']).resolve()
        if not local.is_relative_to(self.root) or local.stat().st_size != size:
            raise ValueError('Navigation page outside review bounds')
        data = local.read_bytes()
        if hashlib.sha256(data).hexdigest() != fingerprint:
            raise ValueError('Navigation page fingerprint differs')
        source = data.decode('utf-8-sig')
        tree = Tree(source).root
        stylesheets = tuple(n.attrs.get('href') for n in tree.walk()
                            if n.tag == 'link' and n.attrs.get('rel') == 'stylesheet')
        if stylesheets != STYLESHEETS:
            raise ValueError('Navigation stylesheets differ')
        styles = '\n'.join(''.join(c for c in n.children if isinstance(c, str))
                           for n in tree.walk() if n.tag == 'style')
        # Include original visible, hover and preloaded images. Script bodies
        # are inspected as text only; no captured script is evaluated here.
        dependencies = set(stylesheets)
        dependencies.update(n.attrs['src'] for n in tree.walk()
                            if n.tag == 'img' and n.attrs.get('src'))
        dependencies.update(m[1] for m in re.findall(r'''(["'])(/oss/[^"']+\.(?:gif|png|jpe?g))\1''', source, re.I))
        for stylesheet in stylesheets:
            normalized = _resource_path(stylesheet)
            if normalized not in self.shared.shared:
                raise ValueError('Missing navigation stylesheet dependency')
            mime, body = self.shared.shared[normalized]
            css = body.decode('utf-8-sig' if 'UTF-8' in mime else 'cp932')
            dependencies.update(_resource_path(ref.strip(), normalized) for ref in
                                re.findall(r'url\(\s*[\x22\x27]?([^\x22\x27)]+)', css))
        dependencies.update(ref.strip() for ref in re.findall(r'url\(\s*[\x22\x27]?([^\x22\x27)]+)', styles))
        normalized = tuple(sorted({_resource_path(p) for p in dependencies}))
        missing = tuple(p for p in normalized if p not in self.shared.shared)
        if missing and not allow_incomplete:
            raise ValueError('Missing captured navigation display dependencies: '+', '.join(missing))
        for path in normalized:
            if path not in missing:
                self.shared.resource_url(path)
        parsed = page_tree(data)
        controls = []
        for number in range(1, (4 if page == 'B_01.jsp' else 10)+1):
            suffix = '0'+str(number)
            slot = parsed.find('spacer'+suffix)
            if slot is None:
                raise ValueError('Captured navigation control missing')
            label = _text(parsed.find(('text' if page == 'B_01.jsp' else 'word')+suffix))
            link = next((n for n in slot.walk() if n.tag == 'a'), None)
            if link is not None:
                binding = _destination(link.attrs.get('href', ''))
            else:
                field = next((n for n in slot.walk() if n.tag == 'input'), None)
                if field is None or number != 4 or page != 'B_01.jsp':
                    raise ValueError('Captured navigation link missing')
                binding = _destination(field.attrs.get('onchange', ''))
                binding['input_parameter'] = 'title'
            controls.append({'slot': suffix, 'label': label, **binding})
        back = re.search(r'setUnderButtonL\(true,.*?showPage\(\x27([WB]_\d\d\.jsp)', source)
        expected_back = 'W_03.jsp' if page == 'B_01.jsp' else 'B_23.jsp'
        if not back or back[1] != expected_back:
            raise ValueError('Captured navigation back destination differs')
        script = b''
        if page == 'B_03.jsp':
            if tuple(c['query'].get('platform') for c in controls) != SYSTEM_CODES:
                raise ValueError('Captured system codes differ')
            start = source.index('var scroll_step = 30;')
            script = source[start:source.index('</script>', start)].encode('utf-8')
            if hashlib.sha256(script).hexdigest() != SYSTEM_SCROLL_SHA256:
                raise ValueError('Captured system scrolling subset differs')
        return NavigationPage(page, data, parsed, stylesheets, styles, tuple(controls),
                              normalized, missing, expected_back, script)

    def review_systems(self, *, allow_incomplete=False):
        """Read B_03; incomplete mode is for offline evidence, never a ready view."""
        return self._load('B_03.jsp', allow_incomplete=allow_incomplete)
