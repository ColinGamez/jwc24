"""Read category/search capture evidence without executing or publishing page bodies.

This reports collector observations, not Nintendo provenance or Japanese UI
verification. Captured query strings and non-category query values stay private.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote

from jwc24.wii_shop_artwork import Node, Tree
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from tools.inspect_wii_shop_frontend_backup import listing_rows, member_path

PAGES = {'B_01.jsp', 'B_03.jsp', 'B_04.jsp', 'B_16.jsp'}
MISSING = ('B_17.jsp', 'B_23.jsp', 'B_27.jsp')
FILTER_KEYS = ('genre', 'publisher', 'platform', 'title', 'search', 'key', 'sort',
               'category', 'subCat', 'vc')


def visible_text(node):
    if node is None or node.tag in ('script', 'style'):
        return ''
    return ''.join(visible_text(c) if isinstance(c, Node) else c
                   for c in node.children).strip()


def target(href):
    """Return only a page and bounded category codes; never serialize a full URL."""
    match = re.search(r'(?<![A-Za-z0-9_])(B_\d\d\.jsp)(?:\?([^\x27\x22\s)]*))?', href)
    if not match:
        return None
    fields = parse_qs(match[2] or '')
    # Publisher/search values can contain private free text. Presence alone is
    # useful evidence; the fixed-code fields below are sufficient for this audit.
    codes = {k: fields[k] for k in ('genre', 'platform', 'vc') if k in fields
             and all(re.fullmatch(r'[A-Za-z0-9_/-]{1,40}', v) for v in fields[k])}
    return {'page': match[1], 'category_codes': codes}


def inspect_html(source, page):
    tree = Tree(source).root
    controls = []
    for slot in tree.walk():
        match = re.fullmatch(r'spacer(0\d+)', slot.attrs.get('id', ''))
        if not match:
            continue
        number = match[1]
        link = next((n for n in slot.walk() if n.tag == 'a'), None)
        route = target(link.attrs.get('href', '')) if link else None
        label = tree.find('word'+number) or tree.find('text'+number)
        if route:
            controls.append({'slot': number, 'label': visible_text(label), **route})
        else:
            field = next((n for n in slot.walk() if n.tag == 'input'), None)
            if field is not None:
                route = target(field.attrs.get('onchange', ''))
                keyboard = re.search(r'kbd\.call\(\s*(cKT_\w+)\s*,\s*(\d+)', field.attrs.get('onmousedown', ''))
                if route and keyboard:
                    controls.append({'slot': number, 'label': visible_text(label), **route,
                                     'keyboard_mode': keyboard[1], 'keyboard_rows': int(keyboard[2]),
                                     'maximum_characters': field.attrs.get('maxlength')})
    frame = tree.find('catalogFrame')
    heading = tree.find('text01-01')
    result = {'page': page, 'controls': controls}
    if page == 'B_04.jsp':
        panels = [n for n in frame.walk() if re.fullmatch(r'panel\d+', n.attrs.get('id', ''))] if frame else []
        heading_script = ''.join(c for n in heading.walk() if n.tag == 'script'
                                 for c in n.children if isinstance(c, str)) if heading else ''
        captions = {'Catalog': 'catalog', 'Catalogue': 'catalogue',
                    '\uc18c\ud504\ud2b8\uc6e8\uc5b4 \uce74\ud0c8\ub85c\uadf8': 'korean_catalog',
                    'Recommended Titles': 'recommended_titles'}
        caption = next((kind for literal, kind in captions.items()
                        if 'document.write("'+literal+'".replace' in heading_script), None)
        result['catalog_state'] = {
            'catalog_frame_present': frame is not None,
            'panel_count': len(panels), 'heading_text': visible_text(heading),
            'heading_link_present': bool(heading and any(n.tag == 'a' for n in heading.walk())),
            'heading_input_present': bool(heading and any(n.tag == 'input' for n in heading.walk())),
            'heading_caption_kind': caption,
            'captured_english_no_results_notice_present': visible_text(tree.find('text02-01')).startswith('Your search did not return any results.'),
            'not_found_element_present': tree.find('notFound') is not None,
        }
    return result


def inspect_manifest(root):
    root = Path(root).resolve()
    manifest_bytes = (root/'manifest.private.json').read_bytes()
    if len(manifest_bytes) > 16*1024*1024:
        raise ValueError('Oversized capture manifest')
    manifest = json.loads(manifest_bytes.decode('utf-8-sig'))
    if (manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1
            or len(manifest.get('files', [])) > 4000):
        raise ValueError('Unexpected category capture source')
    pages = []
    for row in manifest['files']:
        name = unquote(member_path(row['member']).rsplit('/', 1)[-1])
        base, _, query = name.partition('?')
        if base not in PAGES:
            continue
        if row['member'].partition('?')[0] != 'oss-auth.shop.wii.com/oss/serv/'+base:
            raise ValueError('Unexpected category capture member host/path')
        relative = member_path(row['file'])
        path = (root/relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Capture blob escapes manifest root')
        if not 0 < row['bytes'] <= 8*1024*1024:
            raise ValueError('Capture page exceeds review bounds')
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Capture page checksum/size differs from manifest')
        fields = parse_qs(query)
        result = inspect_html(data.decode('utf-8-sig'), base)
        result.update(bytes=len(data), sha256=row['sha256'])
        result['request_region_hints'] = {k: v for k in ('country', 'language', 'region')
                                         if (v := fields.get(k)) and
                                         all(re.fullmatch('[A-Za-z0-9]{1,8}', x) for x in v)}
        result['request_page_number'] = int(fields['p'][0]) if fields.get('p', [''])[0].isdigit() else None
        pages.append(result)
    return {'capture_name': root.name,
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'pages': pages}


def inspect_listing(rows):
    missing = Counter({k: 0 for k in MISSING})
    page_count = 0
    filter_counts = Counter({k: 0 for k in FILTER_KEYS})
    for row in rows:
        path = member_path(row['Path'])
        if row.get('Folder') == '+' or row.get('Attributes', '').startswith('D'):
            continue
        name = unquote(path.rsplit('/', 1)[-1])
        base, _, query = name.partition('?')
        base = base.split(';', 1)[0]
        for missing_page in MISSING:
            if base.casefold() == missing_page.casefold():
                missing[missing_page] += 1
        if '/oss/serv/' not in path or base.casefold() != 'b_04.jsp':
            continue
        page_count += 1
        fields = parse_qs(query)
        filter_counts.update(k for k in FILTER_KEYS if k in fields)
    return {'missing_page_filename_hits': dict(missing), 'B_04_request_entries': page_count,
            'B_04_requests_with_filter_key': dict(filter_counts)}


def summarize_capture(capture):
    pages = capture['pages']
    catalog = [p for p in pages if p['page'] == 'B_04.jsp']
    states, captions, representatives = Counter(), Counter(), {}
    blank_frames = []
    for page in catalog:
        state = page['catalog_state']
        kind = ('no_results_notice' if state['captured_english_no_results_notice_present'] else
                'populated_catalog' if state['panel_count'] else
                'empty_catalog_frame' if state['catalog_frame_present'] else 'other')
        states[kind] += 1
        captions[state['heading_caption_kind'] or 'unrecognized'] += 1
        key = (kind, state['heading_caption_kind'])
        representatives.setdefault(key, page)
        if kind == 'empty_catalog_frame':
            blank_frames.append({k: page[k] for k in ('sha256', 'bytes', 'request_page_number', 'request_region_hints')})
    return {k: capture[k] for k in ('capture_name', 'manifest_sha256')} | {
        'reviewed_pages': len(pages), 'unique_page_hashes': len({p['sha256'] for p in pages}),
        'declared_reviewed_page_bytes': sum(p['bytes'] for p in pages),
        'original_controls': [p for p in pages if p['page'] != 'B_04.jsp'],
        'catalog_state_counts': dict(states), 'catalog_caption_counts': dict(captions),
        'catalog_interactive_headings': sum(bool(p['catalog_state']['heading_link_present'] or
                                               p['catalog_state']['heading_input_present']) for p in catalog),
        'representative_catalog_pages': list(representatives.values()),
        'empty_catalog_frame_observations': blank_frames,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, action='append', required=True)
    parser.add_argument('--listing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--detailed-private-output', type=Path)
    args = parser.parse_args(argv)
    if args.listing.stat().st_size > 512*1024*1024:
        raise ValueError('Oversized archive listing')
    captures = [inspect_manifest(root) for root in args.capture]
    with args.listing.open(encoding='utf-8-sig') as stream:
        listing = inspect_listing(listing_rows(stream))
    report = {'schema_version': 1, 'source': SOURCE,
              'listing_sha256': hashlib.sha256(args.listing.read_bytes()).hexdigest(),
              'listing': listing, 'captures': [summarize_capture(c) for c in captures],
              'query_strings_emitted': False, 'scripts_executed': False,
              'canonical_genre_title_mapping_recovered': False,
              'original_japanese_picker_verified': False,
              'original_search_empty_state_verified': False,
              'complete_original_storefront_verified': False}
    if args.detailed_private_output:
        private = Path(__file__).resolve().parents[1]/'private'
        target_path = args.detailed_private_output.resolve()
        if not target_path.is_relative_to(private.resolve()):
            raise ValueError('Detailed observations must stay beneath private/')
        target_path.write_text(json.dumps(captures, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'capture_pages_reviewed': sum(len(c['pages']) for c in captures), **listing}))


if __name__ == '__main__':
    main()
