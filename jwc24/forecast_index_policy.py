"""Projections of pinned HAFJ index consumers, not a weather-provider adapter.

All table rows and control words are explicit caller inputs.  An FF code skips
membership validation but can still match an explicit FF dictionary row.
"""
from __future__ import annotations

from dataclasses import dataclass


def _unsigned(value: int, bits: int) -> int:
    if type(value) is not int or not 0 <= value < (1 << bits):
        raise ValueError(f'Expected an unsigned {bits}-bit integer')
    return value


@dataclass(frozen=True)
class IndexRow:
    code: int
    text_pointer_present: bool

    def __post_init__(self):
        _unsigned(self.code, 8)
        if type(self.text_pointer_present) is not bool:
            raise ValueError('Text pointer presence must be explicit boolean state')


@dataclass(frozen=True)
class IndexProjection:
    validation_word: int
    first_matches: tuple[int | None, int | None, int | None]
    any_available: bool
    uv_available: bool
    combined_helper_calls: tuple[bool, bool, bool]
    combined_value_modes: tuple[str, str, str]
    uv_only_helper_call: bool
    uv_only_value_mode: str


def project_indices(codes: tuple[int, int, int],
                    tables: tuple[tuple[IndexRow, ...], tuple[IndexRow, ...],
                                  tuple[IndexRow, ...]], *,
                    selector_word: int, incoming_word: int) -> IndexProjection:
    """Return UV/laundry/pollen branch decisions in that order.

    ``validation_word`` is only the isolated native block's accumulator, not
    full-file acceptance. ``original_missing_string`` identifies a native
    copy branch; it neither supplies original text nor claims rendered pixels.
    Helper calls are call selection, not successful image/text presentation.
    """
    if len(codes) != 3 or len(tables) != 3:
        raise ValueError('Exactly three explicit codes and dictionaries are required')
    selector_word = _unsigned(selector_word, 32)
    word = _unsigned(incoming_word, 32)
    matches, helpers, modes = [], [], []
    for slot, (code, rows) in enumerate(zip(codes, tables)):
        _unsigned(code, 8)
        if not isinstance(rows, (tuple, list)) or any(not isinstance(row, IndexRow) for row in rows):
            raise ValueError('Dictionary rows must be IndexRow values')
        found = next((index for index, row in enumerate(rows) if row.code == code), None)
        if code != 255 and (slot == 0 or selector_word == 0) and found is None:
            word = 0xFFFFFFFF
        matches.append(found)
        helpers.append(found is not None and code != 255
                       and rows[found].text_pointer_present)
        modes.append('original_missing_string' if found is None or code == 255
                     else 'integer')
    uv_found = matches[0] is not None
    return IndexProjection(
        word, tuple(matches), any(index is not None for index in matches), uv_found,
        tuple(helpers), tuple(modes), uv_found,
        'skip' if not uv_found else modes[0],
    )


def native_direction_admitted(direction: int) -> bool:
    """The D310 validator block admits zero; this is not render-safety proof."""
    direction = _unsigned(direction, 8)
    return direction <= 16 or direction == 255
