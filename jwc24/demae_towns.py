"""Lossless public town candidates with stable experimental native identifiers."""
import hashlib
import re

from .japan_post import areas


def town_candidates(database, municipality):
    if not isinstance(municipality, str) or not re.fullmatch(r'[0-9]{5}', municipality):
        raise ValueError('Town navigation requires a municipality JIS code')
    rows = areas(database, municipality)
    result = []
    seen = set()
    for row in rows:
        # Include the complete name and municipality: a postcode is not unique.
        identity = '\0'.join((municipality, row['postal'], row['name']))
        code = 'T-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:13]
        if code in seen:
            raise ValueError('Experimental town identifier collision')
        seen.add(code)
        units = len(row['name'].encode('utf-16-be')) // 2
        try:
            row['name'].encode('shift_jis', errors='strict')
            encodable = True
        except UnicodeEncodeError:
            encodable = False
        selectable = row['kind'] == 'town' and units <= 31 and encodable
        result.append({**row, 'municipality': municipality, 'experimental_code': code,
                       'native_label_units': units, 'label_eligible': selectable,
                       'strict_shift_jis_encodable': encodable,
                       'native_selectable': False,
                       'review_reason': ('municipality_default' if row['kind'] != 'town'
                                         else 'label_exceeds_capacity' if units > 31
                                         else 'shift_jis_unrepresentable' if not encodable else None)})
    return result
