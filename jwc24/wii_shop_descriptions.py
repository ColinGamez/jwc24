"""Read private, title-bound original B_06 descriptions and screenshot bytes.

Collector hashes establish capture consistency, not Nintendo provenance or an
exact installed-client match. No commerce script, account or network is used.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import parse_qs

from .wii_shop_captured_catalog import page_tree
from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from .wii_shop_title_metadata import parse_detail

ARCHIVE_SHA256 = 'f7f349b8baf06f0f77ba6d413ed87e535378bc746084e24c7d5f59273acacda0'
SCROLL_SHA256 = 'e3c84935e0f4f13d0e6376a1bae14d54154f42fd402822547994838d23c429ae'
SCROLL_SCRIPT_URL = '/assets/captured/description-scroll.js'
REFERENCE_PAGE_SHA256 = 'f72fd8ed3b3cf41d686dc21c7d3f1834b4cedf96377f8c4759fefe9c3e335d22'
VALIDATION_REVISION = 2
HOST = 'oss-auth.shop.wii.com'
MAX_TITLES = 1000
MAX_FILES = 4000
MAX_BYTES = 192 * 1024 * 1024
STYLESHEETS = ['/oss/oss/common/css/oss.css', '/oss/oss/common/css/error.css']
_SHA = r'[0-9a-f]{64}'
_ID = r'[0-9A-F]{16}'
_SCREENSHOT = r'/oss/ccs/([A-Fa-f0-9]{16})/(FFFD[0-9A-F]{4})'


class _ContentActivities(HTMLParser):
    """Inventory original active elements before page_tree removes scripts."""
    active_tags = {'a', 'form', 'input', 'button', 'textarea', 'select', 'iframe',
                   'frame', 'object', 'embed', 'audio', 'video', 'script', 'style'}
    void = {'img', 'input', 'br', 'hr', 'meta', 'link', 'area', 'base', 'wbr', 'source', 'embed'}

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack, self.rows = [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        selected = attrs.get('id') == 'goodsfree'
        inside = selected or any(marker for _, marker in self.stack)
        if inside and (tag in self.active_tags or any(key.startswith('on') for key in attrs)):
            self.rows.append({'tag': tag, 'attrs': attrs})
        if tag not in self.void:
            self.stack.append((tag, selected))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break


def page_identity(member):
    """Recognize only a single canonical Japan B05/B06 request identity."""
    match = re.fullmatch(re.escape(HOST) + r'/oss/serv/(B_0[56]\.jsp)\?([^#]+)', member)
    if not match:
        return None
    query = parse_qs(match[2], keep_blank_values=True)
    ids = query.get('titleId', [])
    if (query.get('country') != ['JP'] or len(ids) != 1
            or not re.fullmatch(r'[A-Fa-f0-9]{16}', ids[0])):
        return None
    return match[1], ids[0].upper()


def _text(node):
    return ''.join(child for item in node.walk() for child in item.children
                   if isinstance(child, str)) if node else ''


def b05_description_link(data, identifier):
    """Require the captured B05's actual false branch; never infer a manual link."""
    metadata = parse_detail(data, identifier)
    source = data.decode('utf-8-sig')
    flags = re.findall(r'\bvar\s+isFreeIntroEnabled\s*=\s*["\x27]([^"\x27]*)["\x27]\s*;', source)
    branch = (r'if\s*\(\s*isFreeIntroEnabled\s*==\s*"true"\s*\)\s*'
              r'setUnderButtonR\(true,\s*"More Details",\s*'
              r'"javascript:showPage\(\x27ext/B_30\.jsp\?titleId=([A-Fa-f0-9]{16})\x27\)",\s*'
              r'"wiiSelectSound\(\)"\);\s*else\s*'
              r'setUnderButtonR\(true,\s*"More Details",\s*'
              r'"javascript:showPage\(\x27B_06\.jsp\?titleId=([A-Fa-f0-9]{16})\x27\)",\s*'
              r'"wiiSelectSound\(\)"\);')
    targets = re.findall(branch, source)
    if flags != ['false'] or len(targets) != 1 or any(value.upper() != identifier for value in targets[0]):
        raise ValueError('B05 does not prove a same-title B06 footer target')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'flag': 'false',
            'target': 'B_06.jsp?titleId=' + identifier, 'title': metadata['title']}


def parse_description(data, identifier):
    """Validate title/CCS association and preserve the original body and styles."""
    if (not isinstance(identifier, str) or not re.fullmatch(_ID, identifier)
            or not 0 < len(data) <= 2 * 1024 * 1024):
        raise ValueError('Description page identity or size outside bounds')
    source = data.decode('utf-8-sig')
    if '\ufffd' in source:
        raise ValueError('Description contains decoding substitutions')
    tree = page_tree(data)
    required = ('goodsfree', 'text', 'goodsdetails', 'TitleName1stline', 'Platform')
    if any(sum(node.attrs.get('id') == name for node in tree.walk()) != 1 for name in required):
        raise ValueError('Description layout is missing or ambiguous')
    title = ' '.join((_text(tree.find('TitleName1stline')) + ' ' +
                      _text(tree.find('TitleName2stline'))).split())
    commentary = _text(tree.find('text')).strip()
    if not title or len(title) > 512 or not commentary or len(commentary) > 32768:
        raise ValueError('Description title or commentary missing/outside bounds')
    links = re.findall(r'<link\s+href="([^"]+)"\s+rel="stylesheet"', source)
    if links != STYLESHEETS:
        raise ValueError('Unreviewed description stylesheet set')
    styles = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', source, re.I | re.S))
    if not styles.strip() or len(styles) > 64 * 1024:
        raise ValueError('Description inline styles absent or oversized')
    inline_css = styles + '\n' + '\n'.join(node.attrs.get('style', '') for node in tree.walk())
    css_matches = re.findall(r'url\(\s*(?:"([^"]*)"|\x27([^\x27]*)\x27|([^\s)]+))\s*\)',
                             inline_css, re.I)
    css_urls = [next((value for value in match if value), '') for match in css_matches]
    if (any(not url for url in css_urls)
            or len(css_matches) != len(re.findall(r'url\s*\(', inline_css, re.I))
            or re.search(r'@import\b', inline_css, re.I)):
        raise ValueError('Unreviewed description inline CSS dependency')
    if (tree.attrs.get('onkeypress') != "kdown('goodsfree');"
            or tree.attrs.get('onload') != 'initPage(); goodsfree.focus()'):
        raise ValueError('Unreviewed description body events')
    start = source.find('var scroll_step = 30;')
    end = source.find('//-->', start)
    script = source[start:end].encode('utf-8') if start >= 0 and end > start else b''
    if hashlib.sha256(script).hexdigest() != SCROLL_SHA256:
        raise ValueError('Unreviewed description scrolling handler')
    back = re.findall(r'setUnderButtonL\(true,\s*"Back",\s*"javascript:showBack\(\)",\s*'
                      r'"snd\.playSE\(cSE_Cancel\)"\);', source)
    if len(back) != 1:
        raise ValueError('Unreviewed description back-button behavior')
    references = set(re.findall(r'/oss/ccs/[^\s"\x27<>]+', source))
    references = {path[:-1] if path.endswith(')') and path[:-1] in css_urls else path for path in references}
    if not 1 <= len(references) <= 2:
        raise ValueError('Description screenshot count outside reviewed bounds')
    for path in references:
        match = re.fullmatch(_SCREENSHOT, path)
        if not match or match[1].upper() != identifier:
            raise ValueError('Description CCS reference differs from requested title')
    screenshot_nodes = {node.attrs['src'] for node in tree.find('goodsfree').walk()
                        if node.tag == 'img' and node.attrs.get('src', '').startswith('/oss/ccs/')}
    if screenshot_nodes | {url for url in css_urls if url.startswith('/oss/ccs/')} != references:
        raise ValueError('Description screenshot references are outside scrolling content')
    resources = set(links)
    for url in css_urls:
        if url in references:
            continue
        path = posixpath.normpath(url)
        if not path.startswith('/oss/oss/common/'):
            raise ValueError('Description inline CSS resource outside reviewed namespaces')
        resources.add(path)
    for node in tree.walk():
        if node.tag in ('img', 'input') and 'src' in node.attrs:
            path = node.attrs['src']
            if path not in references:
                normalized = posixpath.normpath(path)
                if not normalized.startswith('/oss/oss/common/'):
                    raise ValueError('Description resource outside reviewed namespaces')
                resources.add(normalized)
    return {'tree': tree, 'styles': styles, 'stylesheets': links, 'title': title,
            'screenshots': sorted(references), 'shared_paths': sorted(resources),
            'scroll_script': script, 'content_activities': _ContentActivities(source).rows,
            'inline_css_urls': css_urls,
            'back_button': {'label': 'Back', 'target': 'javascript:showBack()',
                            'sound': 'snd.playSE(cSE_Cancel)'}}


def image_info(data):
    """Verify screenshot bytes, decoded format and bounded dimensions, not a URL suffix."""
    from PIL import Image
    if not 0 < len(data) <= 512 * 1024:
        raise ValueError('Screenshot exceeds byte bounds')
    with Image.open(BytesIO(data)) as image:
        if image.format not in ('GIF', 'PNG', 'JPEG', 'BMP') or not (
                0 < image.width <= 1024 and 0 < image.height <= 1024):
            raise ValueError('Unexpected screenshot format/dimensions')
        result = {'format': image.format, 'width': image.width, 'height': image.height,
                  'mime': {'GIF': 'image/gif', 'PNG': 'image/png', 'JPEG': 'image/jpeg',
                           'BMP': 'image/bmp'}[image.format]}
        image.verify()
    return result


def read_blob(root, row, stage):
    digest = row.get('sha256', '')
    if (not re.fullmatch(_SHA, digest) or row.get('file') != stage + '/blobs/' + digest
            or type(row.get('bytes')) is not int):
        raise ValueError('Description capture fingerprint/path differs')
    local = (root / row['file']).resolve()
    bound = 512 * 1024 if stage == 'screenshots' else 2 * 1024 * 1024
    if not local.is_relative_to(root) or not 0 < local.stat().st_size <= bound:
        raise ValueError('Description capture outside private cache bounds')
    data = local.read_bytes()
    if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Description capture fingerprint/size differs')
    return data


class Descriptions:
    """Expose eligible source rows, copied original trees and exact screenshot bytes.

    Startup validates the builder's manifest bindings without rereading every
    payload. First use rechecks original B05/B06 proofs and image fingerprints;
    bounded caches retain eight parsed pages and sixteen verified images.
    A caller must provide its shared original resource paths. Missing resources
    and unreviewed embedded active content stay excluded.
    """
    def __init__(self, root, catalog_digest, title_ids, *, shared_paths):
        self.root = Path(root).resolve()
        path = self.root / 'manifest.private.json'
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Oversized description manifest')
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if (manifest.get('schema_version') != 1 or manifest.get('validation_revision') != VALIDATION_REVISION
                or manifest.get('source') != SOURCE
                or manifest.get('archive_sha1') != ARCHIVE_SHA1
                or manifest.get('archive_sha256') != ARCHIVE_SHA256
                or manifest.get('selection') != 'japan-b06-descriptions'
                or manifest.get('catalog_sha256') != catalog_digest
                or not re.fullmatch(_SHA, manifest.get('listing_sha256', ''))):
            raise ValueError('Description source/catalog binding differs')
        rows, files = manifest.get('titles'), manifest.get('files')
        if (not isinstance(rows, dict) or len(rows) > MAX_TITLES
                or not set(rows) <= set(title_ids)
                or any(not re.fullmatch(_ID, identifier) for identifier in rows)
                or not isinstance(files, list) or len(files) > MAX_FILES):
            raise ValueError('Description count or catalog identity outside bounds')
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.rows, self.excluded, self.images = {}, dict(manifest.get('excluded', {})), {}
        self.scroll_script = None
        self._files = {}
        total = 0
        shared_paths = set(shared_paths)
        for row in files:
            member = row.get('member', '')
            identity = page_identity(member)
            stage = 'source-pages' if identity else 'screenshots'
            image_match = re.fullmatch(re.escape(HOST) + _SCREENSHOT, member)
            if (member in self._files or (identity and identity[1] not in title_ids)
                    or (not identity and (not image_match or image_match[1].upper() not in title_ids))):
                raise ValueError('Unexpected or duplicate description capture member')
            bound = 512 * 1024 if stage == 'screenshots' else 2 * 1024 * 1024
            digest = row.get('sha256', '')
            if (not re.fullmatch(_SHA, digest) or row.get('file') != stage + '/blobs/' + digest
                    or type(row.get('bytes')) is not int or not 0 < row['bytes'] <= bound):
                raise ValueError('Description capture fingerprint/path/size differs')
            total += row['bytes']
            if total > MAX_BYTES:
                raise ValueError('Description cache exceeds total byte bound')
            self._files[member] = row
        for identifier, row in rows.items():
            detail = self._files.get(row.get('detail_member'))
            description = self._files.get(row.get('description_member'))
            if (not detail or not description or page_identity(detail['member']) != ('B_05.jsp', identifier)
                    or page_identity(description['member']) != ('B_06.jsp', identifier)):
                raise ValueError('Description source page association differs')
            proof = row.get('detail_proof', {})
            screenshots, resources = row.get('screenshots'), row.get('shared_paths')
            activities = row.get('content_activities')
            if (proof.get('sha256') != detail['sha256'] or proof.get('flag') != 'false'
                    or proof.get('target') != 'B_06.jsp?titleId=' + identifier
                    or not isinstance(proof.get('title'), str) or not proof['title'].strip()
                    or len(proof['title']) > 512 or '\ufffd' in proof['title']
                    or type(row.get('display_title_differs')) is not bool
                    or description['sha256'] != row.get('description_sha256')
                    or not isinstance(screenshots, list) or not 1 <= len(screenshots) <= 2
                    or len(set(screenshots)) != len(screenshots)
                    or any(not isinstance(p, str) or not (match := re.fullmatch(_SCREENSHOT, p))
                           or match[1].upper() != identifier for p in screenshots)
                    or not isinstance(resources, list) or not set(STYLESHEETS) <= set(resources)
                    or len(resources) > 64
                    or any(not isinstance(p, str) or not p.startswith('/oss/oss/common/') for p in resources)
                    or not isinstance(activities, list) or len(activities) > 128
                    or any(not isinstance(a, dict) or not isinstance(a.get('tag'), str)
                           or not isinstance(a.get('attrs'), dict) for a in activities)
                    or row.get('back_button') != {'label': 'Back', 'target': 'javascript:showBack()',
                                                  'sound': 'snd.playSE(cSE_Cancel)'}):
                raise ValueError('Description title/source evidence differs')
            if any(a['tag'] != 'a' or any(k.startswith('on') for k in a['attrs'])
                   or not re.match(r'https?://', a['attrs'].get('href', '')) for a in activities):
                self.excluded[identifier] = {'reason': 'unreviewed-description-active-content'}
                continue
            missing = set(resources) - shared_paths
            title_images = {}
            for resource in screenshots:
                image_row = self._files.get(HOST + resource)
                if not image_row:
                    missing.add(resource)
                    continue
                info = image_row.get('image_info', {})
                mimes = {'GIF': 'image/gif', 'PNG': 'image/png', 'JPEG': 'image/jpeg', 'BMP': 'image/bmp'}
                if (info.get('format') not in mimes or info.get('mime') != mimes[info['format']]
                        or any(type(info.get(k)) is not int or not 0 < info[k] <= 1024
                               for k in ('width', 'height'))):
                    raise ValueError('Description screenshot MIME/dimensions differ')
                title_images[resource] = image_row
            if missing:
                self.excluded[identifier] = {'reason': 'missing-description-resources', 'paths': sorted(missing)}
                continue
            self.rows[identifier] = deepcopy(row)
            self.images.update(title_images)

    @lru_cache(maxsize=8)
    def _page(self, identifier):
        row = self.rows.get(identifier)
        if row is None:
            return None
        proof = b05_description_link(read_blob(self.root, self._files[row['detail_member']], 'source-pages'), identifier)
        parsed = parse_description(read_blob(self.root, self._files[row['description_member']], 'source-pages'), identifier)
        if (proof != row['detail_proof'] or parsed['screenshots'] != row['screenshots']
                or parsed['shared_paths'] != row['shared_paths']
                or parsed['content_activities'] != row['content_activities']
                or parsed['back_button'] != row['back_button']
                or (parsed['title'] != proof['title']) != row['display_title_differs']):
            raise ValueError('Description original-page evidence changed')
        self.scroll_script = parsed['scroll_script']
        return parsed['tree'], parsed['styles'], parsed['stylesheets']

    def page(self, identifier):
        return deepcopy(self._page(identifier))

    def asset(self, path):
        if path == SCROLL_SCRIPT_URL and self.rows:
            if self.scroll_script is None:
                self._page(next(iter(self.rows)))
            return 200, 'text/javascript; charset=UTF-8', self.scroll_script
        if path in self.images:
            return self._image(path)
        return 404, 'text/plain', b'Description asset not found'

    @lru_cache(maxsize=16)
    def _image(self, path):
        identifier = path.split('/')[3].upper()
        self._page(identifier)
        row = self.images[path]
        data = read_blob(self.root, row, 'screenshots')
        try:
            info = image_info(data)
        except OSError:
            raise ValueError('Invalid original description screenshot') from None
        if info != row['image_info']:
            raise ValueError('Description screenshot MIME/dimensions differ')
        return 200, row['image_info']['mime'], data
