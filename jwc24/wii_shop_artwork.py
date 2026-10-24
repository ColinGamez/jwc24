"""Bind catalog data into locally cached, archived Shop layouts and artwork.

Third-party archived scripts/event handlers are discarded. Unchanged installed
Shop scripts initialize native objects before JWC24's service adapter runs.
Original page bodies, scripts, styles and images remain under private/.
"""
from dataclasses import dataclass, field
from copy import deepcopy
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

# Visible labels corroborated against Nintendo's Japanese Shop home screenshot:
# https://www.nintendo.co.jp/wii/features/shopping_ch/img/screen.jpg
HOME_COPY = {'text01-01': 'バーチャルコンソール', 'text07-01': 'Wiiウェア',
             'text02-01': 'Wiiチャンネル', 'text03-01': 'Wiiポイントの追加',
             'text04-01': 'ご利用記録', 'text05-01': '設定・その他',
             'text06-01': '購入済みソフト'}

# Visible purchase-screen heading in Nintendo's Japanese functions manual,
# printed p.42 (PDF page 44). This corroborates copy, not a v21 template match.
# https://www.nintendo.co.jp/wii/support/pdf/wiimanual_functions.pdf
DETAIL_HEADING = 'ソフトの購入'


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

    def __init__(self, root, title_artwork=None, catalog_digest=None, native_assets=None, captured_scripts=None,
                 captured_catalog=None, captured_titles=None, captured_empty=None, descriptions=None):
        self.native_assets = native_assets
        self.captured_scripts = captured_scripts
        self.captured_catalog = captured_catalog
        self.captured_titles = captured_titles
        self.captured_empty = captured_empty
        self.descriptions = descriptions
        if (captured_catalog or captured_titles or captured_empty or descriptions) and not captured_scripts:
            raise ValueError('Captured pages require their shared resource pack')
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
        if self.descriptions and (path.startswith('/oss/ccs/') or path == '/assets/captured/description-scroll.js'):
            return self.descriptions.asset(path)
        if path == '/assets/captured/controller-mode.js' and self.captured_titles:
            return self.captured_titles.asset(path)
        if path == '/assets/captured/catalog-navigation.js' and self.captured_catalog:
            return self.captured_catalog.asset(path)
        if path.startswith('/assets/captured/') and self.captured_scripts:
            return self.captured_scripts.asset(path)
        if path.startswith('/assets/native/') and self.native_assets:
            return self.native_assets.asset(path)
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

    def _sanitize(self, root, captured=False):
        for node in root.walk():
            for key in list(node.attrs):
                if key.lower().startswith('on'):
                    del node.attrs[key]
            if captured and 'style' in node.attrs:
                node.attrs['style'] = self._captured_css(node.attrs['style'])
            if 'href' in node.attrs:
                node.attrs['href'] = self._route(node.attrs['href'])
                node.attrs['onclick'] = 'snd.playSE(cSE_Decide)'
            if node.tag in ('img', 'input') and 'src' in node.attrs:
                source = posixpath.normpath(node.attrs['src'])
                node.attrs['src'] = (self.captured_scripts.resource_url(source) if captured
                                     else source if source in self.files else '/oss/oss/common/images/spacer.gif')
            for index, child in enumerate(node.children):
                if isinstance(child, str) and not captured:
                    for old, new in (('Virtual Console', 'バーチャルコンソール'),
                                     ('Wii Channels', 'Wiiチャンネル'), ('Add Wii Points', 'Wiiポイントの追加'),
                                     ('Account Activity', 'ご利用記録'), ('Settings and Features', '設定・特典'),
                                     ('Wii Points', 'Wiiポイント'), ('Release Date', '配信日'),
                                     ('Publisher', 'メーカー'), ('Players', 'プレイ人数'),
                                     ('Titles You’ve Downloaded', '購入済みソフト'),
                                     ('Wii Shop Channel', 'Wiiショッピングチャンネル')):
                        child = child.replace(old, new)
                    node.children[index] = child.replace('\ufffd', '・')

    def _captured_css(self, value):
        # Absolute CSS image paths must use the same captured pack validated
        # for this page, rather than the older modified web asset bundle.
        def resource(match):
            path = self.captured_scripts.resource_url(match[2])
            return 'url('+match[1]+path+match[1]+')'
        return re.sub(r'''url\(\s*(["\x27]?)(/oss/oss/common/[^)"\x27\s]+)\1\s*\)''',
                      resource,value,flags=re.I)

    def _base(self, name, legacy=False):
        captured_catalog = name == 'B_04.html' and self.captured_catalog is not None and not legacy
        captured = (name == 'W_03.html' and self.captured_scripts is not None) or captured_catalog
        source = (self.captured_catalog.layout_html.decode('utf-8-sig') if captured_catalog else
                  self.captured_scripts.home_html.decode('utf-8-sig') if captured
                  else self.files['/oss/serv/'+name].decode('utf-8', errors='replace'))
        styles = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', source, re.I | re.S))
        body = source[source.lower().index('<body'):]
        body = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', body, flags=re.I | re.S)
        body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
        body = body[:body.lower().rfind('</body>')]
        root = Tree(body).root
        if captured_catalog:
            root.find('catalogFrame').children = []
        return self._prepare(root,captured),styles

    def _prepare(self, root, captured=False):
        self._sanitize(root, captured=captured)
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
        return root

    def _button_label(self, root, identifier, text):
        node = root.find(identifier)
        if node:
            node.children = [Node('table', {'width': '100%', 'height': '100%', 'cellspacing': '0', 'cellpadding': '0'},
                [Node('tr', {}, [Node('td', {'align': 'center', 'valign': 'middle'}, [text])])])]

    def _finish(self, root, styles, extra='', captured_home=False, captured_catalog=False,
                captured_stylesheets=None, page_script=None):
        if captured_home or captured_catalog or captured_stylesheets:
            styles = self._captured_css(styles)
        css_url = self.captured_scripts.resource_url('/oss/oss/common/css/oss.css') if self.captured_scripts else '/oss/oss/common/css/oss.css'
        css = '<link rel="stylesheet" type="text/css" href="'+css_url+'">'
        if captured_catalog:
            css = ''.join('<link rel="stylesheet" type="text/css" href="'+self.captured_scripts.resource_url(path)+'">'
                          for path in self.captured_catalog.stylesheets)
        if captured_stylesheets:
            css = ''.join('<link rel="stylesheet" type="text/css" href="'+self.captured_scripts.resource_url(path)+'">'
                          for path in captured_stylesheets)
        if root.find('purchasePage') and not captured_stylesheets:
            detail_css = self.captured_scripts.resource_url('/oss/oss/common/css/B_05.css') if self.captured_scripts else '/oss/oss/common/css/B_05.css'
            css += '<link rel="stylesheet" type="text/css" href="'+detail_css+'">'
        scripts = self.native_assets.script_tags() if self.native_assets else ''
        if self.captured_scripts:
            scripts += self.captured_scripts.script_tags()
        if captured_catalog:
            scripts += '<script type="text/javascript" src="/assets/captured/catalog-navigation.js"></script>'
        if page_script:
            scripts += '<script type="text/javascript" src="'+page_script+'"></script>'
        return ('<html lang="ja"><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
                '<title></title>'+css+'<style type="text/css">'+styles+
                '</style>'+scripts+'<script type="text/javascript" src="/assets/shop.js"></script></head>'+
                root.render()+extra+'</html>').encode('utf-8')

    def home(self, _count):
        root, styles = self._base('W_03.html')
        for identifier, label in HOME_COPY.items():
            root.text(identifier, label)
        # The unit shares its container with the native balance slot.
        point = root.find('point')
        if point:
            for node in point.walk():
                node.children = [child.replace('Wii Points', 'Wiiポイント') if isinstance(child, str) else child
                                 for child in node.children]
        root.find('W_03-title').children = [Node('span', {'data-shop-string': 'title'})]
        self._button_label(root, 'underwordL', Node('span', {'data-shop-string': 'menuBtn'}))
        root.find('underlinkL').attrs['onclick'] = 'return leaveShop()'
        # Original three-panel layout, original normal/hover artwork.
        for trigger, image in (('spacer01', 'Image1'), ('spacer07', 'Image7'), ('spacer02', 'Image2'),
                               ('spacer03', 'Image3'), ('spacer04', 'Image4'), ('spacer05', 'Image5'),
                               ('spacer06', 'Image6')):
            self._hover(root, trigger, image)
        return self._finish(root, styles, captured_home=self.captured_scripts is not None)

    def _hover(self, root, trigger, image, hover=None):
        target, picture = root.find(trigger), root.find(image)
        if not target or not picture:
            return
        normal = picture.attrs.get('src', '')
        hover = hover or re.sub(r'_a\.(gif|png)$', r'_b.\1', normal)
        if hover in self.files or self.captured_scripts and self.captured_scripts.has_asset(hover):
            target.attrs['onmouseover'] = 'MM_swapImage('+json.dumps(image)+',"",'+json.dumps(hover)+',1);snd.playSE(cSE_Forcus)'
            target.attrs['onmouseout'] = 'MM_swapImgRestore()'

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
                entry.attrs.update(maxlength='40', onmousedown='typeSearch(this)',
                                   onchange='submitCatalogSearch(this)')
                entry.attrs['data-shop-category'] = category
        return self._finish(root, styles)

    def browse(self, result, options):
        if self.captured_catalog and result['items']:
            return self._captured_browse(result,options)
        if self.captured_empty and result['total'] == 0 and options['q'].strip():
            return self._captured_no_results(options)
        return self._legacy_browse(result,options)

    def _captured_no_results(self, options):
        capture = self.captured_empty
        root = self._prepare(deepcopy(capture.parsed_root),captured=True)
        root.text('listinfo',capture.caption)
        if options['category']:
            root.find('underlinkL').attrs['href'] = '/category/'+('wiiware' if options['category']=='WiiWare' else 'virtual-console')
        styles = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>',capture.layout_html.decode('utf-8-sig'),re.I|re.S))
        return self._finish(root,styles,captured_stylesheets=capture.stylesheets)

    def _legacy_browse(self, result, options):
        # Non-keyword and out-of-range experimental states still lack their
        # original Japanese flow; preserve the existing fallback for those.
        root, styles = self._base('B_04.html',legacy=True)
        root.text('text01-01', {'WiiWare': 'Wiiウェア', 'Virtual Console': 'バーチャルコンソール'}.get(options['category'], 'ソフトカタログ'))
        source = self.files['/oss/serv/B_04.html'].decode('utf-8', errors='replace')
        match = re.search(r'innerHTML\s*\+=\s*`(.*?)`;', source, re.S)
        if not match:
            raise ValueError('Archived catalog row layout missing')
        cards = []
        for index, item in enumerate(result['items']):
            historical = item.get('historical_metadata', {})
            title = historical.get('title', item['names'][0])
            def value(token):
                expression = token[1]
                if expression == 'i + 1': return str(index+1)
                if 'i * 112' in expression: return str(index*112+24)
                if expression == 'isimport': return 'none'
                if '.id' in expression: return item['title_id']
                if '.console' in expression: return escape(item['category'])
                if '.publisher' in expression: return escape(historical.get('publisher') or '')
                if '.title1' in expression: return escape(title[:38])
                if '.title2' in expression: return escape(title[38:76])
                if '.points' in expression: return format(historical['points'], ',') if historical.get('points') is not None else '－'
                raise ValueError('Unsupported archived row data field')
            card = Tree(re.sub(r'\$\{(.*?)\}', value, match[1], flags=re.S)).root
            self._sanitize(card)
            if historical:
                # Localization applies to the template, not captured product names.
                card.text('Publisher', historical.get('publisher') or '')
                card.text('title1_'+str(index+1), title[:38])
                card.text('title2_'+str(index+1), title[38:76])
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

    def _captured_browse(self, result, options):
        root, styles = self._base('B_04.html')
        root.text('listinfo',self.captured_catalog.caption)
        root.attrs['onkeypress'] = 'kdown();'
        root.attrs['onload'] = "initShop();document.getElementById('catalogFrame').focus();"
        cards = []
        context = {key:value for key,value in options.items() if value is not None}
        for index,item in enumerate(result['items']):
            card = self.captured_catalog.card(item,index)
            self._sanitize(card,captured=True)
            image = next(node for node in card.find('ImageforCatalogpage').walk() if node.tag == 'img')
            if self.title_artwork:
                image.attrs['src'] = self.title_artwork.url(item['title_id'])
            for node in card.walk():
                if node.tag == 'a':
                    node.attrs['href'] = '/title/'+item['title_id']+'?'+urlencode(context)
            self._hover(card,'spacer','Image'+str(index+1))
            cards.append(card)
        root.find('catalogFrame').children = cards
        count = max(1,(result['total']+self.page_size-1)//self.page_size)
        current = options['offset']//self.page_size
        # Captured first/last pages wrap around instead of disabling arrows.
        page = root.find('page')
        cell = next(node for node in page.walk() if node.attrs.get('align') == 'center')
        cell.children = [str(current+1)+'/'+str(count)]
        for direction,number in (('L',(current-1)%count),('R',(current+1)%count)):
            arrow = root.find('arrow'+direction)
            anchor = next(node for node in arrow.walk() if node.tag == 'a')
            anchor.attrs['href'] = '/catalog?'+urlencode(dict(context,offset=number*self.page_size))
        if options['category']:
            root.find('underlinkL').attrs['href'] = '/category/'+('wiiware' if options['category'] == 'WiiWare' else 'virtual-console')
        return self._finish(root,styles,captured_catalog=True)

    def detail(self, item, options):
        if self.captured_titles:
            page = self.captured_titles.page(item['title_id'])
            if page:
                return self._captured_detail(item,options,page)
        root, styles = self._base('B_05.html')
        historical = item.get('historical_metadata', {})
        title = historical.get('title', item['names'][0])
        root.text('text01-01', 'ソフトの情報')
        root.display('purchasePage', True)
        root.display('sdbuttons', False)
        root.display('buyButton', False)
        root.display('downloadedMsg', False)
        root.display('notAvailableMsg', True)
        root.text('notAvailableMsg', 'カタログ閲覧プレビューです。ダウンロードは準備中です。')
        for identifier, text in (('Title1', title[:38]), ('Title2', title[38:76]),
                                 ('PublisherName', historical.get('publisher') or '－'), ('ReleaseDate', '－'), ('NumPlayers', '－'),
                                 ('Console', 'Wiiウェア' if item['category'] == 'WiiWare' else 'バーチャルコンソール'),
                                 ('price', format(historical['points'], ',')+' Wiiポイント' if historical.get('points') is not None else '－')):
            root.text(identifier, text)
        thumbnail = root.find('Thumbnail')
        if thumbnail and self.title_artwork:
            thumbnail.attrs['src'] = self.title_artwork.url(item['title_id'], role='detail')
        root.find('underlinkL').attrs['href'] = '/catalog?'+urlencode({k:v for k,v in options.items() if v is not None})
        return self._finish(root, styles)

    def _captured_detail(self, item, options, page):
        root,styles = page
        identifier = item['title_id']
        detail = root.find('details')
        purchase = root.find('purchasePage')
        if detail is None or purchase is None:
            raise ValueError('Original detail structure missing')
        # Only the original information panel is enabled. Captured transaction,
        # storage, gift, balance-error and entitlement states are not current.
        purchase.children = [detail]
        removed = {'sdErrorDiv','warningMsgs','icrWarningPage','icrExpirePage','sdbuttons','sdErrorNoSizeDiv',
                   'buyButton','giftButton','downloadedMsg','notAvailableMsg','noTitleMsg','undeliverableMsg'}
        for node in root.walk():
            node.children = [child for child in node.children if not isinstance(child,Node) or child.attrs.get('id') not in removed]
        photo = detail.find('Photo')
        image = next(node for node in photo.walk() if node.tag == 'img')
        image.attrs['src'] = '/oss/oss/common/images/spacer.gif'
        overlay = root.find('Image2control')
        hover = re.search(r"MM_swapImage\('Image3control','','([^']+)'",overlay.attrs.get('onmouseover','')) if overlay else None
        root = self._prepare(root,captured=True)
        root.text('heading',DETAIL_HEADING)
        self._button_label(root,'underwordL','Back')
        if self.title_artwork:
            image.attrs['src'] = self.title_artwork.url(identifier,role='detail')
        context = urlencode({key:value for key,value in options.items() if value is not None})
        root.find('underlinkL').attrs['href'] = '/catalog?'+context
        anchor = root.find('ControlAnchor')
        if identifier in self.captured_titles.controller_rows:
            anchor.attrs['href'] = '/controller/'+identifier+'?'+context
            if hover:
                self._hover(root,'controllerLink','Image3control',self.captured_scripts.resource_url(hover[1]))
        else:
            root.display('controllerLink',False)
        description = self.descriptions.rows.get(identifier) if self.descriptions else None
        if description and description['detail_proof']['sha256'] == item['historical_metadata']['capture_sha256']:
            root.display('underButtonR',True)
            self._button_label(root,'underwordR','More Details')
            root.find('underlinkR').attrs['href'] = '/description/'+identifier+'?'+context
            self._hover(root,'underspacerR','underImgR')
        return self._finish(root,styles,captured_stylesheets=self.captured_titles.detail_stylesheets)

    def description(self, item, options):
        page = self.descriptions.page(item['title_id']) if self.descriptions else None
        if page is None:
            return None
        root,styles,stylesheets = page
        content_links = [(node,node.attrs['href']) for node in root.find('goodsfree').walk()
                         if node.tag == 'a' and 'href' in node.attrs]
        screenshots = [(node,node.attrs['src']) for node in root.walk()
                       if node.tag == 'img' and node.attrs.get('src','').startswith('/oss/ccs/')]
        for node,_ in screenshots:
            node.attrs['src'] = '/oss/oss/common/images/spacer.gif'
        root = self._prepare(root,captured=True)
        for node,href in content_links:
            node.attrs['href'] = href
        for node,path in screenshots:
            node.attrs['src'] = path
        root.attrs['onkeypress'] = "kdown('goodsfree');"
        root.attrs['onload'] = "initShop();document.getElementById('goodsfree').focus();"
        self._button_label(root,'underwordL','Back')
        context = urlencode({key:value for key,value in options.items() if value is not None})
        root.find('underlinkL').attrs.update(href='/title/'+item['title_id']+'?'+context,
                                           onclick='snd.playSE(cSE_Cancel)')
        return self._finish(root,styles,captured_stylesheets=stylesheets,
                            page_script='/assets/captured/description-scroll.js')

    def controller(self, item, options):
        page = self.captured_titles.page(item['title_id'],'controller') if self.captured_titles else None
        if page is None:
            return None
        root,styles = page
        root = self._prepare(root,captured=True)
        root.text('B08headingMessage',self.captured_titles.controller_caption)
        self._button_label(root,'underwordL','Back')
        root.attrs['onload'] = 'initShop();applyControllerMode();'
        context = urlencode({key:value for key,value in options.items() if value is not None})
        root.find('underlinkL').attrs['href'] = '/title/'+item['title_id']+'?'+context
        return self._finish(root,styles,captured_stylesheets=self.captured_titles.controller_stylesheets,
                            page_script='/assets/captured/controller-mode.js')

    def about(self):
        root, styles = self._base('B_04.html', legacy=True)
        root.text('text01-01', 'このカタログについて')
        for identifier in ('arrowL', 'arrowR', 'arrowLshadow', 'arrowRshadow', 'notFound', 'page'):
            root.display(identifier, False)
        root.find('catalogFrame').children = [Node('div', {'class': 'contentsBlackM', 'style': 'padding:20px'},
            ['MarioCubeの日本向けソフト収録情報を使用した閲覧プレビューです。購入、ポイント、ダウンロードは準備中です。'])]
        return self._finish(root, styles)
