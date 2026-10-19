"""Conservative decimal area-code policy from native state-file consumers.

This validates representation, not geographic identity or delivery coverage.
"""
import re

MAX_AREA_CODE = 99_999_999_999


def normalize_area_code(value):
    """Match the native minimum-width formatter within its state-reader cap."""
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,11}', value):
        raise ValueError('Area code requires one to eleven ASCII decimal digits')
    number = int(value)
    if number > MAX_AREA_CODE:
        raise ValueError('Area code exceeds the native state-reader limit')
    return f'{number:011d}'
