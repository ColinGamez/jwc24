"""Read-only MarioCube directory metadata for Shop catalog research."""
import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urljoin, urlsplit

BASE = 'https://repo.mariocube.com/WADs/_WiiWare%2C%20VC%2C%20DLC%2C%20Channels%20%26%20IOS/'
BUCKETS = ('0-9', *'ABCDEFGHIJKLMNOPQRSTUVWXYZ')


class Listing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.rows = []
        self.cells = None
        self.cell = None
        self.href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table' and attrs.get('id') == 'files':
            self.active = True
        elif self.active and tag == 'tr':
            self.cells, self.href = [], None
        elif self.active and tag == 'td':
            self.cell = []
        elif self.active and tag == 'a' and self.cell is not None:
            self.href = attrs.get('href')

    def handle_data(self, data):
        if self.active and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None and self.cells is not None:
            self.cells.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.cells is not None:
            if self.active and self.href and len(self.cells) >= 6:
                self.rows.append((self.href, self.cells))
            self.cells = None
        elif tag == 'table':
            self.active = False


def parse_listing(html, bucket):
    if bucket not in BUCKETS or not isinstance(html, str) or len(html) > 2*1024*1024:
        raise ValueError('Invalid bounded catalog listing')
    parser = Listing()
    parser.feed(html)
    if not parser.rows:
        raise ValueError('No directory rows found; listing format may have changed')
    records = {}
    page = BASE+bucket+'/'
    for href, cells in parser.rows:
        filename = cells[1]
        if not filename.lower().endswith('.wad'):
            continue
        url = urljoin(page, href)
        parsed = urlsplit(url)
        directory = unquote(urlsplit(page).path)
        path = unquote(parsed.path)
        linked_name = path[len(directory):] if path.startswith(directory) else ''
        if (parsed.scheme != 'https' or parsed.netloc != 'repo.mariocube.com'
                or parsed.query or parsed.fragment or linked_name.strip() != filename
                or not linked_name or '/' in linked_name or '\\' in linked_name):
            raise ValueError('Unexpected catalog file link')
        filename = linked_name
        if not cells[2].isdigit():
            raise ValueError('Catalog file size is not an integer')
        tags = re.findall(r'\(([^()]+)\)', filename[:-4])
        kind = 'WiiWare' if 'WiiWare' in tags else 'Virtual Console' if 'Virtual Console' in tags else None
        region = next((tag for tag in tags if tag in ('Japan', 'USA', 'Europe', 'Korea', 'World', 'France', 'Germany')), None)
        dlc, demo = 'DLC' in tags, 'Demo' in tags
        records[url] = {'catalog_id': 'mariocube:'+hashlib.sha256(url.encode()).hexdigest()[:24],
                        'name': filename.split(' (', 1)[0].strip(), 'filename': filename,
                        'region_label': region, 'category_label': kind,
                        'is_demo': demo, 'is_dlc': dlc, 'filename_tags': tags,
                        'listed_bytes': int(cells[2]), 'listed_modified': cells[5],
                        'source_page': page, 'source_url': url,
                        'japan_browse_candidate': region == 'Japan' and kind is not None and not dlc,
                        'title_id': None, 'price': None, 'publisher': None,
                        'tmd_verified': False, 'install_supported': False}
    return sorted(records.values(), key=lambda record: record['filename'])
