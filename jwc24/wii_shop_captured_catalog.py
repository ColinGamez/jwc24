"""Index historical catalog panels without enabling captured commerce scripts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs

from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE

LAYOUT_SHA256 = '6a74a12ebbac7e6599295ed7f92f8e0ff0aad3585acdce47723c2e316e44cfec'
NAVIGATION_URL = '/assets/captured/catalog-navigation.js'


def page_tree(data):
    from .wii_shop_artwork import Tree
    source = data.decode('utf-8-sig')
    source = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', source, flags=re.I|re.S)
    source = re.sub(r'<!--.*?-->', '', source, flags=re.S)
    return Tree(source[source.lower().index('<body'):source.lower().rfind('</body>')]).root


def panel_identity(panel):
    targets, images = set(), set()
    for node in panel.walk():
        if node.tag == 'a':
            match = re.search(r'B_05\.jsp\?[^\x27\x22]*?titleId=([A-Fa-f0-9]{16})(?=&|[\x27\x22)]|$)',node.attrs.get('href',''))
            if match:
                targets.add(match[1].upper())
        if node.tag == 'img':
            match = re.fullmatch(r'/oss/ccs/([A-Fa-f0-9]{16})/FFFD[A-Fa-f0-9]{4}',node.attrs.get('src',''))
            if match:
                images.add((match[1].upper(),node.attrs['src']))
    if len(targets) == len(images) == 1 and next(iter(targets)) == next(iter(images))[0]:
        return next(iter(targets))
    return None


class CapturedCatalog:
    def __init__(self, root, title_ids):
        root = Path(root).resolve()
        manifest_path = root/'manifest.private.json'
        if manifest_path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized catalog capture manifest')
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        if (manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1
                or len(manifest['files']) > 200):
            raise ValueError('Unexpected catalog capture source')
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.panels, self.panel_sources, self.layout_html = {}, {}, None
        seen, total = set(), 0
        for row in manifest['files']:
            base, _, query = row['member'].rsplit('/',1)[-1].partition('?')
            if (not row['member'].startswith('oss-auth.shop.wii.com/oss/serv/')
                    or base != 'B_04.jsp' or parse_qs(query).get('country') != ['JP']
                    or row['member'] in seen):
                raise ValueError('Expected distinct Japan-region catalog captures')
            seen.add(row['member'])
            fingerprint = row['sha256']
            if not re.fullmatch('[0-9a-f]{64}',fingerprint) or row['file'] != 'blobs/'+fingerprint:
                raise ValueError('Unexpected catalog capture fingerprint/path')
            local = (root/row['file']).resolve()
            if not local.is_relative_to(root) or not 0 < local.stat().st_size <= 8*1024*1024:
                raise ValueError('Catalog capture outside bounds')
            data = local.read_bytes()
            total += len(data)
            if total > 32*1024*1024 or len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != fingerprint:
                raise ValueError('Catalog capture fingerprint/size differs')
            if fingerprint == LAYOUT_SHA256:
                self.layout_html = data
            # The oversized all-titles duplicate adds no matching IDs. Keep
            # its bytes checked, but index the bounded individual pages.
            if len(data) > 2*1024*1024:
                continue
            for node in page_tree(data).walk():
                if not re.fullmatch(r'panel\d+',node.attrs.get('id','')):
                    continue
                identifier = panel_identity(node)
                if identifier in title_ids and identifier not in self.panels:
                    self.panels[identifier] = node
                    self.panel_sources[identifier] = fingerprint
        if self.layout_html is None:
            raise ValueError('Missing reviewed catalog layout')
        source = self.layout_html.decode('utf-8-sig')
        self.prototype = page_tree(self.layout_html).find('panel01')
        if not self.prototype or not self.prototype.find('regularTitle1'):
            raise ValueError('Original catalog panel structure differs')
        self.stylesheets = re.findall(r'<link\s+href="([^"]+)"\s+rel="stylesheet"',source)
        if self.stylesheets != ['/oss/oss/common/css/oss.css','/oss/oss/common/css/error.css']:
            raise ValueError('Original catalog stylesheets differ')
        self.caption = 'Catalog'
        if 'document.write("Catalog".replace' not in source:
            raise ValueError('Original catalog caption differs')
        start = source.index('var scroll_step = 30;')
        end = source.index('function doPrePost()',start)
        self.navigation_script = source[start:end].encode('utf-8')

    def card(self, item, index):
        """Copy original geometry/title lines; account branches stay inactive."""
        if not 0 <= index < 10:
            raise ValueError('Catalog slot outside captured page size')
        from .wii_shop_artwork import Node
        identifier = item['title_id']
        matched = identifier in self.panels
        panel = deepcopy(self.panels.get(identifier,self.prototype))
        old = int(panel.attrs['id'][5:])
        number = index+1
        panel.attrs['id'] = 'panel0'+str(number)
        panel.attrs['style'] = re.sub(r'top:\s*\d+px', 'top:'+str(24+112*index)+'px',panel.attrs['style'])
        for node in panel.walk():
            for key in ('id','name'):
                value = node.attrs.get(key,'')
                match = re.fullmatch(r'(title[12]_|UPDATE|giftTitle|storedGiftTitle|giftAnchor|regularTitle|scaTitle|ImageB?|purchasePoint|goTitleDetailsLink)(\d+)',value)
                if match and int(match[2]) == old:
                    node.attrs[key] = match[1]+str(number)
        # Captured entitlement, gift, discount and update states cannot be
        # asserted for a preview visitor. Only retain the regular browse branch.
        inactive = {prefix+str(number) for prefix in ('UPDATE','giftTitle','storedGiftTitle','scaTitle')}
        panel.children = [child for child in panel.children if not isinstance(child,Node) or child.attrs.get('id') not in inactive]
        regular = panel.find('regularTitle'+str(number))
        if regular is None:
            raise ValueError('Captured regular title branch missing')
        regular.attrs['style'] = ''
        if not matched:
            historical = item.get('historical_metadata',{})
            panel.text('title1_'+str(number),historical.get('title',item['names'][0]))
            panel.text('Publisher',historical.get('publisher') or '')
            panel.text('Platform',historical.get('captured_platform_text') or '')
        historical = item.get('historical_metadata',{})
        for node in regular.walk():
            if node.attrs.get('name') == 'purchasePoint'+str(number):
                node.children = [format(historical['points'],',')+' Wii Points' if historical.get('points') is not None else '—']
        # The original source image is replaced by the separately verified role
        # cache after shared-resource sanitization.
        picture = panel.find('ImageforCatalogpage')
        if not picture:
            raise ValueError('Captured catalog picture slot missing')
        image = next((node for node in picture.walk() if node.tag == 'img'),None)
        if image is None:
            raise ValueError('Captured catalog image missing')
        image.attrs['src'] = '/oss/oss/common/images/spacer.gif'
        return panel

    def asset(self, path):
        if path == NAVIGATION_URL:
            return 200,'text/javascript; charset=UTF-8',self.navigation_script
        return 404,'text/plain',b'Catalog script not found'
