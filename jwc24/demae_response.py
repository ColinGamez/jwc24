"""Conservative offline inspection of partially traced HCHJ area XML.

Tool limits and stricter XML/numeric checks are not native capacity claims.
No native acceptance, complete row schema, or authenticity is asserted.
"""
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat

# Explicit empty tags make the complete Minato town list 265,605 bytes.
# This is an offline inspection ceiling, not a native network capacity claim.
MAX_XML_BYTES = 320 * 1024
MAX_NODES = 16384
MAX_DEPTH = 32


class ResponseFormatError(ValueError):
    pass


def _child(parent, name):
    matches = [node for node in parent if node.tag == name]
    if len(matches) != 1:
        raise ResponseFormatError(f'Expected exactly one direct {name} element')
    return matches[0]


def _integer(node, field):
    text = (node.text or '').strip()
    if len(node) or not re.fullmatch(r'[0-9]{1,10}', text):
        raise ResponseFormatError(f'Invalid {field} integer')
    value = int(text)
    if value > 0x7fffffff:
        raise ResponseFormatError(f'{field} exceeds inspector integer limit')
    return value


def inspect_area_response(data: bytes, *, http_status: int = 200,
                          variant: str = 'address') -> dict:
    """Check proven hierarchy only; return metadata without address strings."""
    if http_status != 200:
        raise ResponseFormatError('Native status validation requires HTTP 200')
    if variant not in ('address', 'list', 'root', 'postal-fallback', 'auth', 'documents', 'categories'):
        raise ResponseFormatError('Unknown area response variant')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise ResponseFormatError('XML exceeds inspector byte limit or is empty')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise ResponseFormatError('Inspector requires UTF-8 XML') from None
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
        raise ResponseFormatError('DTD and entity declarations are not allowed')
    if re.search(r'<[A-Za-z_][^<>]*?/\s*>', text):
        raise ResponseFormatError('Native XML requires explicit closing tags for empty elements')
    state = {'cdata': False}
    lexical = expat.ParserCreate()
    lexical.StartCdataSectionHandler = lambda: state.update(cdata=True)
    lexical.EndCdataSectionHandler = lambda: state.update(cdata=False)
    def check_text(value):
        if not state['cdata'] and value.strip():
            raise ResponseFormatError('Native scalar values require CDATA')
    lexical.CharacterDataHandler = check_text
    try:
        lexical.Parse(text, True)
        root = ET.fromstring(text)
    except ResponseFormatError:
        raise
    except (ET.ParseError, ValueError, expat.ExpatError):
        raise ResponseFormatError('Invalid XML') from None
    stack = [(root, 1)]
    nodes = []
    while stack:
        node, depth = stack.pop()
        nodes.append(node)
        if depth > MAX_DEPTH or len(nodes) > MAX_NODES:
            raise ResponseFormatError('XML exceeds inspector structural limits')
        stack.extend((child, depth + 1) for child in reversed(node))
    if root.tag != 'response':
        raise ResponseFormatError('Native document requires response as its XML root')
    statuses = [node for node in nodes if node.tag == 'apiStatus']
    if len(statuses) != 1:
        raise ResponseFormatError('Expected one apiStatus element')
    if variant == 'postal-fallback':
        response = root
        status = _child(response, 'apiStatus')
        code = _integer(_child(status, 'code'), 'postal status code')
        if code not in (13, 14):
            raise ResponseFormatError('Postal fallback requires status 13 or 14')
        return {'byte_length': len(data), 'node_count': len(nodes),
                'variant': variant, 'api_code': code,
                'scope': 'traced postal fallback branch; transport and native acceptance unverified'}
    # Native status navigation is recursive; do not invent a wrapper hierarchy.
    codes = [node for node in statuses[0].iter() if node.tag == 'code']
    if len(codes) != 1 or _integer(codes[0], 'status code') != 0:
        raise ResponseFormatError('Missing or unsuccessful API status code')
    if variant == 'root':
        area = _child(root, 'areaList')
        if not len(area):
            raise ResponseFormatError('Root area selection requires rows')
        seen = set()
        for row in area:
            if row.tag in seen or len(row.tag.encode('cp932')) > 15:
                raise ResponseFormatError('Duplicate or oversized root selection code')
            seen.add(row.tag)
            segment = _child(row, 'segment')
            if len(segment) or not segment.text:
                raise ResponseFormatError('Root selection requires direct segment text')
            lists = [node for node in row if node.tag == 'list']
            if len(lists) > 1:
                raise ResponseFormatError('Duplicate root municipality list')
            if lists:
                if not len(lists[0]):
                    raise ResponseFormatError('Empty root municipality list')
                codes = set()
                for city in lists[0]:
                    name, code = _child(city, 'areaName'), _child(city, 'areaCode')
                    if (len(name) or not name.text or len(code) or not code.text
                            or len(code.text.encode('ascii')) > 10 or code.text in codes):
                        raise ResponseFormatError('Invalid root municipality row')
                    codes.add(code.text)
        return {'byte_length': len(data), 'node_count': len(nodes), 'variant': variant,
                'row_count': len(area), 'scope': 'traced root selection; native display unverified'}
    if variant == 'documents':
        response = root
        status = _child(response, 'apiStatus')
        if status is not statuses[0]:
            raise ResponseFormatError('Document status must be beneath response')
        version = _integer(_child(response, 'version'), 'document version')
        for number in range(3):
            contents = _child(_child(response, f'container{number}'), 'contents')
            if len(contents) or not contents.text:
                raise ResponseFormatError('Missing plain document contents')
            if len(contents.text.encode('utf-8')) > 4096:
                raise ResponseFormatError('Document exceeds conservative fixture text limit')
        return {'byte_length': len(data), 'node_count': len(nodes), 'variant': variant,
                'version': version, 'document_count': 3,
                'scope': 'traced template framing; document semantics and native acceptance unverified'}
    if variant == 'auth':
        keys = [node for node in nodes if node.tag == 'authKey']
        if len(keys) != 1 or len(keys[0]) or not keys[0].text:
            raise ResponseFormatError('Expected one nonempty plain authKey')
        return {'byte_length': len(data), 'node_count': len(nodes), 'variant': variant,
                'scope': 'traced auth-key response fields; native acceptance unverified'}
    if variant == 'categories':
        # Native consumer visits every response child except the last one.
        # Keep status last so it is not misread as a category group.
        if len(root) < 2 or root[-1] is not statuses[0]:
            raise ResponseFormatError('Category fixture requires final apiStatus child')
        seen = set()
        for group in list(root)[:-1]:
            label = _child(group, 'LargeCategoryName')
            if len(label) or label.text != '食事':
                raise ResponseFormatError('Unsupported category fixture group')
            categories = _child(group, 'CategoryList')
            for row in categories:
                code = _child(row, 'CategoryCode')
                if len(code) or not code.text or code.text in seen:
                    raise ResponseFormatError('Missing or duplicate category code')
                seen.add(code.text)
        return {'byte_length': len(data), 'node_count': len(nodes), 'variant': variant,
                'category_count': len(seen),
                'scope': 'offline category framing; encoding and native acceptance unverified'}
    response = root
    area = _child(response, 'areaList')
    fields = ('kanji1', 'kanji2', 'kanji3') if variant == 'address' else ('kanji1',)
    for field in fields:
        matches = [node for node in area.iter() if node is not area and node.tag == field]
        if len(matches) != 1:
            raise ResponseFormatError(f'Expected one unambiguous descendant {field}')
        node = matches[0]
        if len(node) or not node.text:
            raise ResponseFormatError(f'Missing plain text for {field}')
    counts = [node for node in response if node.tag == 'areaCount']
    count = None
    if counts:
        if len(counts) != 1:
            raise ResponseFormatError('Duplicate areaCount')
        count = _integer(counts[0], 'areaCount')
    row_count = 0
    truncated_codes = 0
    if variant == 'list':
        if count is None or count == 0:
            raise ResponseFormatError('List display requires positive areaCount')
        for container in area:
            if container.tag != 'container0':
                segment = _child(container, 'segment')
                if len(segment) or not segment.text:
                    raise ResponseFormatError('Missing segment text')
            for row in _child(container, 'list'):
                primary = _child(row, 'kanji2')
                if len(primary):
                    raise ResponseFormatError('Nested primary row label')
                if primary.text:
                    secondary = _child(row, 'kanji3')
                    if len(secondary):
                        raise ResponseFormatError('Nested secondary row label')
                    if secondary.text:
                        tertiary = _child(row, 'kanji4')
                        if len(tertiary):
                            raise ResponseFormatError('Nested tertiary row label')
                code = _child(row, 'areaCode')
                if len(code) or not code.text:
                    raise ResponseFormatError('Missing plain areaCode text')
                postcodes = [child for child in row if child.tag == 'zipCode']
                if postcodes and (len(postcodes) != 1 or len(postcodes[0])
                                  or not re.fullmatch(r'[0-9]{7}', postcodes[0].text or '')):
                    raise ResponseFormatError('Native postcode fallback requires seven digits')
                # Source code-page handling remains unknown; report UTF-8 risk
                # rather than silently inventing numeric IDs or truncating.
                truncated_codes += len(code.text.encode('utf-8')) > 15
                for field in ('isNextArea', 'display'):
                    _integer(_child(row, field), field)
                row_count += 1
        if count != row_count:
            raise ResponseFormatError('areaCount must equal total list rows for safe allocation')
    return {'byte_length': len(data), 'node_count': len(nodes),
            'variant': variant, 'declared_area_count': count,
            'row_count': row_count, 'area_codes_over_15_utf8_bytes': truncated_codes,
            'scope': 'traced variant-2 fields with safe count equality; encoding and native acceptance unverified'}
