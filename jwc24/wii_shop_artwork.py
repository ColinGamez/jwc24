"""Bind catalog data into locally cached, archived Shop layouts and artwork.

Archived scripts/event handlers are discarded. Only JWC24's small native-bridge
adapter runs. Original page bodies, styles and images remain under private/.
"""
from dataclasses import dataclass, field
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import mimetypes
from pathlib import Path
import posixpath
import re
from urllib.parse import urlencode
from .wii_shop_title_artwork import TitleArtwork

VOID = {'img', 'input', 'br', 'hr', 'meta', 'link', 'area', 'base', 'wbr', 'source'}


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def find(self, identifier):
        return next((n for n in self.walk() if n.attrs.get('id') == identifier), None)

    def text(self, identifier, value):
        node = self.find(identifier)
        if node:
            node.children = [value]

    def display(self, identifier, visible):
        node = self.find(identifier)
        if node:
            node.attrs['style'] = node.attrs.get('style', '')+';display:'+('block' if visible else 'none')

    def render(self):
        attrs = ''.join(' '+k+'="'+escape(v or '', quote=True)+'"' for k, v in self.attrs.items())
        result = '<'+self.tag+attrs+'>'
        if self.tag not in VOID:
            result += ''.join(c.render() if isinstance(c, Node) else escape(c) for c in self.children)
            result += '</'+self.tag+'>'
        return result


class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node('body')
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.root.attrs.update(dict(attrs))
            return
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


class Artwork:
    page_size = 10

    def __init__(self, root, title_artwork=None, catalog_digest=None):
        self.title_artwork = TitleArtwork(title_artwork, catalog_digest) if title_artwork else None
        root = Path(root).resolve()
        manifest_path = root/'manifest.json'
        if manifest_path.stat().st_size > 200000:
            raise ValueError('Oversized artwork manifest')
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('source') != 'https://wiishopchannel.net' or len(manifest['files']) > 200:
            raise ValueError('Unexpected artwork source/size')
        self.files = {}
        for path, row in manifest['files'].items():
            local = (root/path.lstrip('/')).resolve()
            if not local.is_relative_to(root) or local.stat().st_size > 2*1024*1024:
                raise ValueError('Artwork outside pack bounds')
            data = local.read_bytes()
            if hashlib.sha256(data).hexdigest() != row['sha256'] or len(data) != row['bytes']:
                raise ValueError('Artwork fingerprint mismatch')
            self.files[path] = data
        for name in ('W_03.html', 'B_01.html', 'B_27.html', 'B_04.html', 'B_05.html'):
            if '/oss/serv/'+name not in self.files:
                raise ValueError('Missing archived layout')

    def asset(self, path):
        if path.startswith('/title-artwork/') and self.title_artwork:
            return self.title_artwork.asset(path)
        normalized = posixpath.normpath(path)
        if normalized.startswith('/oss/oss/') and normalized in self.files:
            return 200, mimetypes.guess_type(normalized)[0] or 'application/octet-stream', self.files[normalized]
        return 404, 'text/plain', b'Artwork not found'

    def _route(self, href):
        if 'B_01' in href:
            return '/category/virtual-console'
        if 'B_27' in href:
            return '/category/wiiware'
        if 'B_05' in href:
            match = re.search(r'titleId=([0-9A-Fa-f]{16})', href)
            return '/title/'+match[1] if match else '/about'
        if 'W_01' in href or 'W_03' in href:
            return '/'
        return '/about'

    def _sanitize(self, root):
        for node in root.walk():
            for key in list(node.attrs):
                if key.lower().startswith('on'):
                    del node.attrs[key]
            if 'href' in node.attrs:
                node.attrs['href'] = self._route(node.attrs['href'])
                node.attrs['onclick'] = 'soundEffect(3)'
            if node.tag in ('img', 'input') and 'src' in node.attrs:
                source = posixpath.normpath(node.attrs['src'])
                node.attrs['src'] = source if source in self.files else '/oss/oss/common/images/spacer.gif'
            for index, child in enumerate(node.children):
                if isinstance(child, str):
                    for old, new in (('Virtual Console', 'バーチャルコンソール'),
                                     ('Wii Channels', 'Wiiチャンネル'), ('Add Wii Points', 'Wiiポイントの追加'),
                                     ('Account Activity', 'ご利用記録'), ('Settings and Features', '設定・特典'),
                                     ('Wii Points', 'Wiiポイント'), ('Release Date', '配信日'),
                                     ('Publisher', 'メーカー'), ('Players', 'プレイ人数'),
                                     ('Titles You’ve Downloaded', '購入済みソフト'),
                                     ('Wii Shop Channel', 'Wiiショッピングチャンネル')):
                        child = child.replace(old, new)
                    node.children[index] = child.replace('\ufffd', '・')

    def _base(self, name):
        source = self.files['/oss/serv/'+name].decode('utf-8', errors='replace')
        styles = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', source, re.I | re.S))
        body = source[source.lower().index('<body'):]
        body = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', body, flags=re.I | re.S)
        body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
        body = body[:body.lower().rfind('</body>')]
        root = Tree(body).root
        self._sanitize(root)
        root.attrs['onload'] = 'initShop()'
        root.text('currentBalance', '－')
        for suffix in ('', 'L', 'R'):
            root.display('underButton'+suffix, suffix == 'L')
        self._button_label(root, 'underwordL', 'もどる')
        anchor = root.find('underlinkL')
        if anchor:
            anchor.attrs['href'] = '/'
        for trigger, image in (('underspacerL', 'underImgL'), ('arrowL', 'arrowLImg'),
                               ('arrowR', 'arrowRImg'), ('top', 'TopImageID'), ('help', 'ManualImageID')):
            self._hover(root, trigger, image)
        for target in ('MainSpacer', 'goTop'):
            node = root.find(target)
            if node:
                node.attrs['onclick'] = "window.location.href='/'"
        return root, styles

    def _button_label(self, root, identifier, text):
        node = root.find(identifier)
        if node:
            node.children = [Node('table', {'width': '100%', 'height': '100%', 'cellspacing': '0', 'cellpadding': '0'},
                [Node('tr', {}, [Node('td', {'align': 'center', 'valign': 'middle'}, [text])])])]

    def _finish(self, root, styles, extra=''):
        css = '<link rel="stylesheet" type="text/css" href="/oss/oss/common/css/oss.css">'
        if root.find('purchasePage'):
            css += '<link rel="stylesheet" type="text/css" href="/oss/oss/common/css/B_05.css">'
        return ('<html lang="ja"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
                '<title>Wiiショッピングチャンネル</title>'+css+'<style type="text/css">'+styles+
                '</style><script type="text/javascript" src="/assets/shop.js"></script></head>'+
                root.render()+extra+'</html>').encode('utf-8')

    def home(self, _count):
        root, styles = self._base('W_03.html')
        root.text('W_03-title', 'Wiiショッピングチャンネル')
        self._button_label(root, 'underwordL', 'Wiiメニューへ')
        root.find('underlinkL').attrs['onclick'] = 'return leaveShop()'
        # Original three-panel layout, original normal/hover artwork.
        for trigger, image in (('spacer01', 'Image1'), ('spacer07', 'Image7'), ('spacer02', 'Image2'),
                               ('spacer03', 'Image3'), ('spacer04', 'Image4'), ('spacer05', 'Image5'),
                               ('spacer06', 'Image6')):
            self._hover(root, trigger, image)
        return self._finish(root, styles)

    def _hover(self, root, trigger, image):
        target, picture = root.find(trigger), root.find(image)
        if not target or not picture:
            return
        normal = picture.attrs.get('src', '')
        hover = re.sub(r'_a\.(gif|png)$', r'_b.\1', normal)
        if hover in self.files:
            target.attrs['onmouseover'] = 'previewHover('+json.dumps(image)+','+json.dumps(hover)+');soundEffect(2)'
            target.attrs['onmouseout'] = 'previewHover('+json.dumps(image)+','+json.dumps(normal)+')'

    def category(self, category):
        root, styles = self._base('B_27.html' if category == 'WiiWare' else 'B_01.html')
        root.text('text00-01', 'Wiiウェア' if category == 'WiiWare' else 'バーチャルコンソール')
        root.text('text00-02', 'Wiiならではのオリジナルソフト。' if category == 'WiiWare' else '懐かしいゲームをWiiで。')
        root.text('text01', '人気のソフト')
        root.text('text02', '新着ソフト')
        root.text('text03', 'ソフト一覧')
        root.text('text04', 'ソフト名でさがす')
        root.text('text05', '体験版')
        for number in ('01', '02', '03', '04', '05'):
            self._hover(root, 'spacer'+number, 'Image'+number)
        for identifier, filters in (('spacer03', {'category': category}),
                                     ('spacer05', {'category': category, 'demos': 'only'})):
            node = root.find(identifier)
            if node:
                anchor = next((n for n in node.walk() if n.tag == 'a'), None)
                if anchor:
                    anchor.attrs['href'] = '/catalog?'+urlencode(filters)
        # The original search banner contains an invisible keyboard input.
        slot = root.find('spacer04')
        if slot:
            entry = next((n for n in slot.walk() if n.tag == 'input'), None)
            if entry:
                entry.attrs.update(name='q', maxlength='40', onmousedown='typeSearch()',
                                   onchange='submitCatalogSearch(this)')
                hidden = Node('input', {'type': 'hidden', 'name': 'category', 'value': category})
                slot.children = [Node('form', {'action': '/catalog', 'method': 'get', 'style': 'margin:0'}, [hidden, entry])]
        return self._finish(root, styles)

    def browse(self, result, options):
        root, styles = self._base('B_04.html')
        root.text('text01-01', {'WiiWare': 'Wiiウェア', 'Virtual Console': 'バーチャルコンソール'}.get(options['category'], 'ソフトカタログ'))
        source = self.files['/oss/serv/B_04.html'].decode('utf-8', errors='replace')
        match = re.search(r'innerHTML\s*\+=\s*`(.*?)`;', source, re.S)
        if not match:
            raise ValueError('Archived catalog row layout missing')
        cards = []
        for index, item in enumerate(result['items']):
            def value(token):
                expression = token[1]
                if expression == 'i + 1': return str(index+1)
                if 'i * 112' in expression: return str(index*112+24)
                if expression == 'isimport': return 'none'
                if '.id' in expression: return item['title_id']
                if '.console' in expression: return escape(item['category'])
                if '.publisher' in expression: return ''
                if '.title1' in expression: return escape(item['names'][0][:38])
                if '.title2' in expression: return escape(item['names'][0][38:76])
                if '.points' in expression: return '－'
                raise ValueError('Unsupported archived row data field')
            card = Tree(re.sub(r'\$\{(.*?)\}', value, match[1], flags=re.S)).root
            self._sanitize(card)
            picture = card.find('ImageforCatalogpage')
            if picture and self.title_artwork:
                image = next((n for n in picture.walk() if n.tag == 'img'), None)
                if image:
                    image.attrs['src'] = self.title_artwork.url(item['title_id'])
            self._hover(card, 'spacer', 'Image'+str(index+1))
            for node in card.walk():
                if node.tag == 'a':
                    node.attrs['href'] = '/title/'+item['title_id']+'?'+urlencode({k:v for k,v in options.items() if v is not None})
            cards.extend(card.children)
        root.find('catalogFrame').children = cards
        if options['category']:
            root.find('underlinkL').attrs['href'] = '/category/'+('wiiware' if options['category'] == 'WiiWare' else 'virtual-console')
        root.display('notFound', not bool(cards))
        if not cards:
            root.text('notFound', '該当するソフトがありません。')
        size = self.page_size
        root.text('pageNum', str(options['offset']//size+1)+'/'+str(max(1, (result['total']+size-1)//size)))
        for direction, offset in (('L', options['offset']-size if options['offset'] else None),
                                  ('R', result['next_offset'])):
            root.display('arrow'+direction, offset is not None)
            root.display('arrow'+direction+'shadow', offset is not None)
            node = root.find('backArrow' if direction == 'L' else 'nextArrow')
            if node and offset is not None:
                node.attrs['href'] = '/catalog?'+urlencode(dict({k:v for k,v in options.items() if v is not None}, offset=offset))
        return self._finish(root, styles)

    def detail(self, item, options):
        root, styles = self._base('B_05.html')
        root.text('text01-01', 'ソフトの情報')
        root.display('purchasePage', True)
        root.display('sdbuttons', False)
        root.display('buyButton', False)
        root.display('downloadedMsg', False)
        root.display('notAvailableMsg', True)
        root.text('notAvailableMsg', 'カタログ閲覧プレビューです。ダウンロードは準備中です。')
        for identifier, text in (('Title1', item['names'][0][:38]), ('Title2', item['names'][0][38:76]),
                                 ('PublisherName', '－'), ('ReleaseDate', '－'), ('NumPlayers', '－'),
                                 ('Console', 'Wiiウェア' if item['category'] == 'WiiWare' else 'バーチャルコンソール'), ('price', '－')):
            root.text(identifier, text)
        thumbnail = root.find('Thumbnail')
        if thumbnail and self.title_artwork:
            thumbnail.attrs['src'] = self.title_artwork.url(item['title_id'])
        root.find('underlinkL').attrs['href'] = '/catalog?'+urlencode({k:v for k,v in options.items() if v is not None})
        return self._finish(root, styles)

    def about(self):
        root, styles = self._base('B_04.html')
        root.text('text01-01', 'このカタログについて')
        for identifier in ('arrowL', 'arrowR', 'arrowLshadow', 'arrowRshadow', 'notFound', 'page'):
            root.display(identifier, False)
        root.find('catalogFrame').children = [Node('div', {'class': 'contentsBlackM', 'style': 'padding:20px'},
            ['MarioCubeの日本向けソフト収録情報を使用した閲覧プレビューです。購入、ポイント、ダウンロードは準備中です。'])]
        return self._finish(root, styles)
