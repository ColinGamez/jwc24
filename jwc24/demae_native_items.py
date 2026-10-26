"""Structural preflight for an offline native action-10 item candidate.

No provider menu, variant identity, price, stock observation or image is inferred.
Passing this check does not establish freshness, availability, native rendering,
basket acceptance or an order. A publisher still needs independent current
branch/provider evidence and the remaining native image/shop/basket contracts.
"""
from dataclasses import dataclass, field
import re
from xml.etree import ElementTree as ET
from xml.parsers import expat


MAX_XML_BYTES = 65536
MAX_ITEMS = 32
MAX_VARIANTS = 32
MAX_TEXT = 128


class NativeItemShapeError(ValueError):
    """Incomplete/unsupported candidate; diagnostics never echo source values."""


@dataclass(frozen=True)
class NativeItemShape:
    menu_code: str = field(repr=False)
    item_codes: tuple[str, ...] = field(repr=False)
    items: int
    variants: int
    provider_evidence_verified: bool = field(default=False, init=False)
    current_orderability_verified: bool = field(default=False, init=False)
    native_rendering_verified: bool = field(default=False, init=False)


def _scalar(node):
    if node is None or node.attrib or len(node):
        raise NativeItemShapeError('Missing or nonscalar native item field')
    value = node.text or ''
    if (not value or value != value.strip() or len(value) > MAX_TEXT
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise NativeItemShapeError('Unsupported or empty native item text')
    try:
        value.encode('cp932')
    except UnicodeError:
        raise NativeItemShapeError('Native item text cannot be represented by CP932') from None
    return value


def _fields(node, expected):
    if node is None or node.attrib or (node.text or '').strip():
        raise NativeItemShapeError('Missing or malformed native item container')
    children = list(node)
    if (len(children) != len(expected) or {n.tag for n in children} != set(expected)
            or any((n.tail or '').strip() for n in children)):
        raise NativeItemShapeError('Missing, repeated or unsupported native item fields')
    return {child.tag: child for child in children}


def _price(node):
    value = _scalar(node)
    if not re.fullmatch(r'0|[1-9][0-9]{0,6}', value) or int(value) > 1_000_000:
        raise NativeItemShapeError('Expected an explicit canonical listed yen amount')


def inspect_native_item_candidate(data: bytes, *, menu_code: str) -> NativeItemShape:
    """Validate a conservative subset before any native publication.

    Required nonempty fields, exact 0/1 stock, canonical prices, unique item and
    per-item variant IDs and local count/text bounds are producer safeguards.
    Some malformed native responses are partially accepted; this gate rejects
    them instead of silently losing later rows. No menu source is verified here.
    """
    if not isinstance(menu_code, str) or not menu_code or len(menu_code) > MAX_TEXT:
        raise NativeItemShapeError('An explicit selected menu code is required')
    if (not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES
            or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper()):
        raise NativeItemShapeError('Invalid or oversized native item XML')
    lexical = re.sub(br'<!\[CDATA\[.*?\]\]>', b'', data, flags=re.S)
    if re.search(br'<[^>]*?/\s*>', lexical):
        raise NativeItemShapeError('Native item XML requires explicit closing tags')
    in_cdata = False

    def start_cdata():
        nonlocal in_cdata
        in_cdata = True

    def end_cdata():
        nonlocal in_cdata
        in_cdata = False

    def character_data(value):
        if value.strip() and not in_cdata:
            raise NativeItemShapeError('Nonempty native scalar text must use CDATA')

    try:
        text = data.decode('utf-8-sig')
        parser = expat.ParserCreate()
        parser.StartCdataSectionHandler = start_cdata
        parser.EndCdataSectionHandler = end_cdata
        parser.CharacterDataHandler = character_data
        parser.Parse(data, True)
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError, expat.ExpatError):
        raise NativeItemShapeError('Malformed native item XML') from None
    if root.tag != 'response':
        raise NativeItemShapeError('Expected a native response root')
    pending = [(root, 1)]
    elements = 0
    while pending:
        node, depth = pending.pop()
        elements += 1
        if elements > 512 or depth > 10:
            raise NativeItemShapeError('Native item XML exceeds local structure bound')
        pending.extend((child, depth+1) for child in node)
    fields = _fields(root, ('Count', 'List', 'apiStatus'))
    if list(root)[-1].tag != 'apiStatus':
        raise NativeItemShapeError('Native item status must remain last')
    status = _fields(fields['apiStatus'], ('code',))
    if _scalar(status['code']) != '0':
        raise NativeItemShapeError('Candidate does not report zero status')
    count = _scalar(fields['Count'])
    if not re.fullmatch(r'[1-9][0-9]?', count) or not 1 <= int(count) <= MAX_ITEMS:
        raise NativeItemShapeError('Native item count exceeds local candidate bound')
    listing = fields['List']
    if listing.attrib or (listing.text or '').strip() or any((n.tail or '').strip() for n in listing):
        raise NativeItemShapeError('Malformed native item list')
    if [n.tag for n in listing] != ['container'+str(i) for i in range(int(count))]:
        raise NativeItemShapeError('Native item container names/count/order differ')
    item_codes, variants = [], 0
    for container in listing:
        entry = _fields(container, ('name', 'item'))
        _scalar(entry['name'])
        row = _fields(entry['item'], ('menuCode', 'itemCode', 'price', 'info', 'size',
                                      'image', 'isSoldout', 'sizeList'))
        if _scalar(row['menuCode']) != menu_code:
            raise NativeItemShapeError('Native item belongs to a different selected menu')
        code = _scalar(row['itemCode'])
        if code in item_codes:
            raise NativeItemShapeError('Duplicate native item identity')
        item_codes.append(code)
        _price(row['price'])
        for name in ('info', 'size', 'image'):
            _scalar(row[name])
        if _scalar(row['isSoldout']) not in ('0', '1'):
            raise NativeItemShapeError('Native item stock requires explicit zero/one text')
        sizes = row['sizeList']
        if (sizes.attrib or (sizes.text or '').strip() or not 1 <= len(sizes) <= MAX_VARIANTS
                or any((n.tail or '').strip() for n in sizes)):
            raise NativeItemShapeError('Native item requires a bounded nonempty variant list')
        seen = set()
        for variant in sizes:
            values = _fields(variant, ('itemCode', 'size', 'price', 'isSoldout'))
            code = _scalar(values['itemCode'])
            if code in seen:
                raise NativeItemShapeError('Duplicate variant identity makes basket selection ambiguous')
            seen.add(code)
            _scalar(values['size'])
            _price(values['price'])
            if _scalar(values['isSoldout']) not in ('0', '1'):
                raise NativeItemShapeError('Native variant stock requires explicit zero/one text')
            variants += 1
    return NativeItemShape(menu_code, tuple(item_codes), len(item_codes), variants)
