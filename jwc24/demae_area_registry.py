"""Stable decimal identities for replacement-service areas, not original IDs."""
import json

from .demae_area_code import MAX_AREA_CODE, normalize_area_code

FIRST_LOCAL_CODE = 10_000_000_000


def area_identity(municipality, postal, town):
    if not all(isinstance(value, str) and value for value in (municipality, postal, town)):
        raise ValueError('Area identity requires nonempty source fields')
    return json.dumps([municipality, postal, town], ensure_ascii=False, separators=(',', ':'))


def assign_area_codes(previous, identities):
    """Keep retired entries reserved; never renumber when source data changes."""
    if not isinstance(previous, dict):
        raise ValueError('Area registry must be an object')
    registry = dict(previous)
    seen = set()
    for identity, code in registry.items():
        if not isinstance(identity, str) or not identity:
            raise ValueError('Invalid source identity')
        canonical = normalize_area_code(code)
        if canonical != code or int(code) < FIRST_LOCAL_CODE or code in seen:
            raise ValueError('Invalid or duplicate replacement area code')
        seen.add(code)
    requested = list(identities)
    if any(not isinstance(identity, str) or not identity for identity in requested):
        raise ValueError('Invalid source identity')
    next_code = max([FIRST_LOCAL_CODE - 1, *map(int, registry.values())]) + 1
    for identity in sorted(set(requested) - registry.keys()):
        if next_code > MAX_AREA_CODE:
            raise ValueError('Replacement area-code space exhausted')
        registry[identity] = normalize_area_code(str(next_code))
        next_code += 1
    return registry


class AreaRegistry:
    """Validated bidirectional snapshot; source identities remain explicit."""
    def __init__(self, registry):
        self._codes = assign_area_codes(registry, [])
        self._areas = {}
        for identity, code in self._codes.items():
            try:
                fields = json.loads(identity)
            except ValueError:
                raise ValueError('Malformed registry source identity') from None
            if (not isinstance(fields, list) or len(fields) != 3
                    or any(not isinstance(value, str) or not value for value in fields)
                    or area_identity(*fields) != identity):
                raise ValueError('Malformed registry source identity')
            self._areas[code] = tuple(fields)

    def code_for(self, municipality, postal, town):
        identity = area_identity(municipality, postal, town)
        if identity not in self._codes:
            raise ValueError('Town is missing from the replacement registry')
        return self._codes[identity]

    def resolve(self, code):
        fields = self._areas.get(normalize_area_code(code))
        return None if fields is None else dict(zip(('municipality', 'postal', 'town'), fields))
