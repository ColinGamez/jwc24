"""Summarize a private 7-Zip technical listing without printing captured URLs.

No archive member or script is executed. Query strings and original page bodies
are not included in the public report. This is a collector capture inventory,
not verification of a Nintendo signature or a complete original storefront.
"""
import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote


def listing_rows(lines):
    row = {}
    count = 0
    for line in lines:
        if len(line) > 32768:
            raise ValueError('Oversized archive listing line')
        line = line.rstrip('\r\n').lstrip('\ufeff')
        if not line:
            if row:
                count += 1
                if count > 2000000:
                    raise ValueError('Too many archive entries')
                yield row
                row = {}
            continue
        key, separator, value = line.partition(' = ')
        if separator:
            if key in row:
                raise ValueError('Duplicate archive listing field')
            row[key] = value
    if row:
        yield row


def member_path(value):
    value = value.replace('\\', '/')
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '..' in path.parts
            or re.match(r'^[A-Za-z]:', value) or any(ord(c) < 32 for c in value)):
        raise ValueError('Unsafe archive member path')
    return value


def summarize(rows):
    files = total = 0
    pages, extensions, regions = Counter(), Counter(), Counter()
    for row in rows:
        path = member_path(row.get('Path', ''))
        if row.get('Folder') == '+' or row.get('Attributes', '').startswith('D'):
            continue
        if row.get('Symbolic Link') or row.get('Hard Link'):
            raise ValueError('Archive links are outside capture review scope')
        size = int(row['Size'])
        if size < 0 or size > 256*1024*1024:
            raise ValueError('Unexpected capture member size')
        files += 1
        total += size
        # Decode only for classification. Never use a decoded name for extraction.
        name = unquote(path.rsplit('/', 1)[-1])
        base = name.split('?', 1)[0].split(';', 1)[0]
        extension = PurePosixPath(base).suffix.lower()
        extensions[extension or '(none)'] += 1
        if re.fullmatch(r'(?:[WB]_\d\d|index|CheckRegistered|Register|startup)\.(?:jsp|html?)', base, re.I):
            pages[base] += 1
        for key, value in re.findall(r'(?:[?&])(country|language)=([A-Za-z]{2})(?=[&;]|$)', name):
            regions[key+'='+value.upper()] += 1
    return {'schema_version': 1, 'source': 'https://archive.org/details/WiiShopChannelBackup',
            'capture_files': files, 'declared_uncompressed_bytes': total,
            'extensions': dict(sorted(extensions.items())),
            'navigation_page_basenames': dict(sorted(pages.items())),
            'regional_filename_hints': dict(sorted(regions.items())),
            'query_strings_emitted': False, 'complete_original_storefront_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('listing', type=Path)
    args = parser.parse_args(argv)
    if args.listing.stat().st_size > 512*1024*1024:
        raise ValueError('Oversized listing')
    with args.listing.open(encoding='utf-8-sig') as stream:
        report = summarize(listing_rows(stream))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
