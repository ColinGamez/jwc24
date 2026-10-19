"""Shared stable shop identifiers and native-compatible row eligibility."""
import re

MAX_MOVIE_ID = 999999999


def indexed_shop_products(products):
    rows = [row for row in products if isinstance(row, dict)]
    seen = set()
    result = []
    for ordinal, row in enumerate(rows, 1):
        identity = row.get("movie_id", ordinal)
        if type(identity) is not int or not 1 <= identity <= MAX_MOVIE_ID or identity in seen:
            continue
        seen.add(identity)
        values = []
        for key in ("price_yen", "review_count"):
            value = row.get(key, 0)
            if type(value) is not int and (not isinstance(value, str) or len(value) > 20 or re.fullmatch(r"[+-]?[0-9]+", value) is None):
                break
            values.append(int(value))
        if len(values) == 2 and 0 <= values[0] <= 10000 and values[1] >= 0:
            result.append((identity, row))
    return result


def assign_identities(previous, products):
    """Retain retired identities as tombstones; never reuse their numbers."""
    if not isinstance(previous, dict):
        raise ValueError("previous shop catalog must be an object")
    if not isinstance(previous.get("products", []), list):
        raise ValueError("previous shop products must be an array")
    if not isinstance(previous.get("identity_registry", {}), dict):
        raise ValueError("shop identity registry must be an object")
    registry = dict(previous.get("identity_registry", {}))
    if any(not isinstance(code, str) or type(identity) is not int or not 1 <= identity <= MAX_MOVIE_ID
           for code, identity in registry.items()) or len(set(registry.values())) != len(registry):
        raise ValueError("invalid shop identity registry")
    prior_rows = [row for row in previous.get("products", []) if isinstance(row, dict)]
    for ordinal, row in enumerate(prior_rows, 1):
        code = row.get("item_code")
        identity = row.get("movie_id", ordinal)
        if not isinstance(code, str) or not code or type(identity) is not int or not 1 <= identity <= MAX_MOVIE_ID:
            raise ValueError("invalid previous shop identity")
        if code in registry and registry[code] != identity:
            raise ValueError("conflicting previous shop identity")
        if code not in registry and identity in registry.values():
            raise ValueError("duplicate previous shop identity")
        registry[code] = identity
    high = previous.get("movie_id_high_water", 0)
    if type(high) is not int or not 0 <= high <= MAX_MOVIE_ID:
        raise ValueError("invalid shop identity high-water mark")
    high = max([high, len(prior_rows), *registry.values()])
    rows = []
    seen = set()
    for row in products:
        code = row["item_code"]
        if code in seen:
            continue
        seen.add(code)
        if code not in registry:
            high += 1
            if high > MAX_MOVIE_ID:
                raise ValueError("shop movie identifiers exhausted")
            registry[code] = high
        rows.append(dict(row, movie_id=registry[code]))
    return rows, registry, high
