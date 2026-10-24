"""Offline, read-only catalog queries; not a native SOAP or storefront route."""
from collections import defaultdict
from copy import deepcopy
import re
import unicodedata


def folded(value):
    return unicodedata.normalize('NFKC', value).casefold()


class Catalog:
    def __init__(self, records, *, title_metadata=None):
        self.title_metadata = title_metadata
        if not isinstance(records, list) or len(records) > 20000:
            raise ValueError('Catalog records exceed browse bounds')
        groups = defaultdict(list)
        seen_listings = set()
        self.unresolved = 0
        for record in records:
            if not isinstance(record, dict):
                raise ValueError('Catalog record must be an object')
            if not record.get('japan_browse_candidate'):
                continue
            identifier = record.get('title_id')
            if identifier is None:
                self.unresolved += 1
                continue
            version = record.get('title_version')
            if (not isinstance(identifier, str) or not re.fullmatch(r'[0-9A-Fa-f]{16}', identifier)
                    or record.get('title_id_status') != 'source_metadata'
                    or record.get('region_label') != 'Japan'
                    or record.get('category_label') not in ('WiiWare', 'Virtual Console')
                    or type(record.get('is_demo')) is not bool or record.get('is_dlc') is not False
                    or type(version) is not int or not 0 <= version <= 65535
                    or not isinstance(record.get('name'), str) or not record['name'].strip()
                    or not isinstance(record.get('catalog_id'), str)
                    or not isinstance(record.get('title_id_evidence'), dict)):
                raise ValueError('Mapped catalog record lacks browse metadata/provenance')
            if record['catalog_id'] in seen_listings:
                raise ValueError('Duplicate source listing identifier')
            seen_listings.add(record['catalog_id'])
            groups[identifier.upper()].append(record)
        self.items = []
        self.conflicting_ids = []
        for identifier, variants in groups.items():
            if len({(r['category_label'], r['is_demo']) for r in variants}) != 1:
                self.conflicting_ids.append(identifier)
                continue
            if len({r['catalog_id'] for r in variants}) != len(variants):
                raise ValueError('Duplicate source listing identifier')
            variants = sorted(variants, key=lambda r: (r['title_version'], r['catalog_id']))
            names = sorted({r['name'] for r in variants}, key=lambda name: (folded(name), name))
            historical = title_metadata.get(identifier) if title_metadata else None
            if historical:
                names = sorted(set(names+[historical['title']]), key=lambda name: (folded(name), name))
            self.items.append({'title_id': identifier, 'names': names,
                               'category': variants[0]['category_label'], 'is_demo': variants[0]['is_demo'],
                               'versions': sorted({r['title_version'] for r in variants}),
                               'source_listing_count': len(variants),
                               'variant_selection_required': len(variants) > 1,
                               'listings': [{'catalog_id': r['catalog_id'], 'name': r['name'],
                                             'version': r['title_version'], 'evidence': dict(r['title_id_evidence'])}
                                            for r in variants],
                               'title_id_status': 'source_metadata', 'tmd_verified': False,
                               'owned': None, 'price': None, 'install_supported': False})
            if historical:
                self.items[-1]['historical_metadata'] = historical
        self.items.sort(key=lambda r: (folded(r['names'][0]), r['title_id']))

    def query(self, *, offset=0, limit=20, search='', category=None, demos='all', title_ids=()):
        if (type(offset) is not int or not 0 <= offset <= 0xffffffff
                or type(limit) is not int or not 1 <= limit <= 50
                or not isinstance(search, str) or len(search) > 120
                or category not in (None, 'WiiWare', 'Virtual Console')
                or demos not in ('all', 'exclude', 'only')
                or not isinstance(title_ids, (tuple, list)) or len(title_ids) > 100
                or any(not isinstance(t, str) or not re.fullmatch(r'[0-9A-Fa-f]{16}', t) for t in title_ids)):
            raise ValueError('Unsupported catalog query')
        wanted = {t.upper() for t in title_ids}
        needle = folded(search)
        matches = [r for r in self.items
                   if (not category or r['category'] == category)
                   and (demos == 'all' or r['is_demo'] == (demos == 'only'))
                   and (not wanted or r['title_id'] in wanted)
                   and (not needle or any(needle in folded(name) for name in r['names']))]
        total = len(matches)
        return {'total': total, 'offset': offset, 'limit': limit,
                'next_offset': offset+limit if offset+limit < total else None,
                'items': deepcopy(matches[offset:offset+limit]), 'unresolved_japan_listings': self.unresolved,
                'conflicting_title_ids': sorted(self.conflicting_ids),
                'offline_preview': True, 'native_catalog_verified': False}
