"""Read official menu evidence without inferring orderability or exact prices."""
from html.parser import HTMLParser
import hashlib
import re
from urllib.parse import urljoin, urlsplit

SOURCE_URL = 'https://www.dominos.jp/menu'


class _Index(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.current = None
        self.products = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'div' and 'product-container' in classes:
            if self.current is not None:
                raise ValueError('Nested product container')
            self.current = {'name': [], 'description': [], 'advertised_prices': [], 'url': None}
            self.product_depth = len(self.stack)
        if self.current is not None and tag == 'a' and 'product-page-link' in classes:
            href = attrs.get('href', '')
            if href.startswith('/menu-pizza/') and not re.fullmatch(r'/menu-pizza/[A-Za-z0-9.\-]+', href):
                raise ValueError('Unexpected official product link')
            if re.fullmatch(r'/menu-pizza/[A-Za-z0-9.\-]+', href):
                self.current['url'] = urljoin(SOURCE_URL, href)
        field = ('name' if 'menu-entry' in classes else
                 'description' if 'menu-page-product-description' in classes else
                 'advertised_prices' if 'size-price' in classes else None)
        if field and self.current is not None:
            self.current[field].append([])
        if tag not in ('img', 'br', 'hr', 'input', 'meta', 'link', 'source', 'area', 'wbr'):
            self.stack.append((tag, field))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            # Optional HTML closing tags outside product blocks need no repair.
            if self.current is not None:
                raise ValueError('Malformed product markup')
            return
        self.stack.pop()
        if self.current is not None and len(self.stack) == self.product_depth:
            if self.current['url']:
                self.products.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            field = next((field for _, field in reversed(self.stack) if field), None)
            if field:
                self.current[field][-1].append(data)


def parse_official_menu(data, *, source_url=SOURCE_URL):
    """Return source-backed names and price labels, never a checkout quote."""
    if source_url != SOURCE_URL or len(data) > 3_000_000:
        raise ValueError('Unexpected menu source or oversized document')
    text = data.decode('utf-8', errors='strict')
    if '\ufffd' in text:
        raise ValueError('Corrupted menu text')
    parser = _Index()
    parser.feed(text)
    parser.close()
    if parser.current is not None:
        raise ValueError('Truncated product markup')
    products = {}
    for raw in parser.products:
        clean = lambda field: [' '.join(''.join(parts).split()) for parts in raw[field]]
        names = clean('name')
        if len(names) != 1 or not names[0]:
            raise ValueError('Missing or ambiguous official product name')
        product = {'source_url': raw['url'], 'name': names[0],
                   'description': ' '.join(clean('description')),
                   'advertised_price_labels': clean('advertised_prices'),
                   'exact_price_yen': None, 'delivery_eligibility': None,
                   'orderable': False}
        key = urlsplit(raw['url']).path.rsplit('/', 1)[-1]
        if key in products and products[key] != product:
            raise ValueError('Conflicting duplicate official product')
        products[key] = product
    if not 1 <= len(products) <= 500:
        raise ValueError('No usable menu products or excessive product count')
    return {'source_url': source_url, 'source_sha256': hashlib.sha256(data).hexdigest(),
            'scope': 'official menu evidence; not a local delivery or checkout quote',
            'products': products}
