"""Bounded pinned-original HAFJ index consumers; no provider or device IO."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.forecast_index_policy import (IndexRow, native_direction_admitted,
                                        project_indices)

SOURCE_SHA256 = 'ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5'
SOURCE_BYTES = 1925536
SDA, TOC = 0x80337540, 0x80339900
RAW, DAY, COOKED = 0x90000100, 0x90001000, 0x90002000
UI, RECORD, HANDLE, ALPHA = 0x90004000, 0x90005000, 0x90006000, 0x90006100
STACK, RETURN, OUTPUT = 0x90018000, 0x90020000, 0x801F7370
LOOKUPS = (0x8002044C, 0x80020488, 0x800204C4)


def original_image(path: Path) -> tuple[bytes, tuple[tuple[int, int, int, int], ...]]:
    data = path.read_bytes()
    if len(data) != SOURCE_BYTES or hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Original HAFJ v7 application identity does not match')
    sections = []
    for index in range(18):
        offset = struct.unpack_from('>I', data, index * 4)[0]
        address = struct.unpack_from('>I', data, 0x48 + index * 4)[0]
        size = struct.unpack_from('>I', data, 0x90 + index * 4)[0]
        if size:
            if offset < 256 or offset + size > len(data):
                raise ValueError('Original DOL section exceeds its input')
            sections.append((index, offset, address, size))
    return data, tuple(sections)


class _Native:
    """Unchanged original instructions, explicit synthetic RAM, graphics boundaries."""

    def __init__(self, path: Path):
        self.data, self.sections = original_image(path)
        from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                             UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                             UC_PROT_READ, UC_PROT_EXEC)
        from unicorn import ppc_const as reg
        self.reg = reg
        self.uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
        self.text = [(address, address + size) for i, _, address, size in self.sections if i < 7]
        self.source_ranges = [(address, address + size) for _, _, address, size in self.sections]
        # BSS locations are explicit fixtures, not original initialized data.
        self.fixture_ranges = [(0x90000000, 0x90010000), (0x90010000, 0x90020000),
                               (0x801F7300, 0x801F7400),
                               (SDA - 0x6B8C, SDA - 0x6B8C + 4),
                               (SDA - 0x6A04, SDA - 0x6A04 + 4),
                               (SDA - 0x6A0A, SDA - 0x6A0A + 1),
                               (SDA - 0x6B4C, SDA - 0x6B4C + 4)]
        pages = set()
        for lo, hi in self.source_ranges + self.fixture_ranges:
            pages.update(range(lo & ~0xFFF, (hi + 0xFFF) & ~0xFFF, 0x1000))
        for page in sorted(pages):
            self.uc.mem_map(page, 0x1000)
        for _, offset, address, size in self.sections:
            self.uc.mem_write(address, self.data[offset:offset + size])
        mutable_pages = {lo & ~0xFFF for lo, _ in self.fixture_ranges}
        mutable_pages.update(range(0x90000000, 0x90020000, 0x1000))
        for page in pages - mutable_pages:
            self.uc.mem_protect(page, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
        self.uc.hook_add(UC_HOOK_CODE, self._code)
        self.uc.hook_add(UC_HOOK_MEM_READ, self._read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self._write)
        self.events = []
        self.visited = set()
        self.reads = []
        self.graphics = {0x800D56E8, 0x800D3C7C, 0x8001C89C, 0x80031170,
                         0x800313F4, 0x8003E150, 0x8003F088}
        self.rendering = False
        self.writable = []

    @staticmethod
    def _inside(address, size, ranges):
        return any(lo <= address and address + size <= hi for lo, hi in ranges)

    def _read(self, uc, access, address, size, value, user):
        if not self._inside(address, size, self.source_ranges + self.fixture_ranges):
            raise AssertionError(f'Unbounded original read at {address:08X}, PC {self.pc():08X}')
        self.reads.append((address, size))

    def _write(self, uc, access, address, size, value, user):
        if not self._inside(address, size, self.writable):
            raise AssertionError(f'Unbounded original write at {address:08X}, PC {self.pc():08X}')

    def _code(self, uc, address, size, user):
        if not self._inside(address, size, self.text):
            raise AssertionError(f'Execution outside original text at {address:08X}')
        self.visited.add(address)
        if self.rendering and address in self.graphics:
            if address == 0x8001C89C:
                self.events.append(('helper', self.get(4), self.get(5)))
            elif address in (0x8003E150, 0x8003F088):
                self.events.append(('value', self.wide(self.get(3))))
            uc.reg_write(self.reg.UC_PPC_REG_PC, uc.reg_read(self.reg.UC_PPC_REG_LR))

    def pc(self):
        return self.uc.reg_read(self.reg.UC_PPC_REG_PC)

    def get(self, index):
        return self.uc.reg_read(getattr(self.reg, f'UC_PPC_REG_{index}')) & 0xFFFFFFFF

    def put(self, index, value):
        self.uc.reg_write(getattr(self.reg, f'UC_PPC_REG_{index}'), value)

    def word(self, address, value):
        self.uc.mem_write(address, struct.pack('>I', value))

    def wide(self, address):
        result = bytearray()
        for displacement in range(0, 128, 2):
            if not self._inside(address + displacement, 2,
                                self.source_ranges + self.fixture_ranges):
                raise AssertionError('Unbounded host wide-string observation')
            pair = bytes(self.uc.mem_read(address + displacement, 2))
            if pair == b'\0\0':
                return bytes(result)
            result.extend(pair)
        raise AssertionError('Observed wide string lacks a bounded terminator')

    def run(self, begin, end=RETURN, *, registers=None, render=False):
        for index in range(32):
            self.put(index, 0)
        self.put(1, STACK)
        self.put(2, TOC)
        self.put(13, SDA)
        self.uc.reg_write(self.reg.UC_PPC_REG_LR, RETURN)
        self.uc.reg_write(self.reg.UC_PPC_REG_CR, 0)
        self.uc.reg_write(self.reg.UC_PPC_REG_MSR, 0x2000)
        for index, value in (registers or {}).items():
            self.put(index, value)
        self.events, self.reads = [], []
        self.rendering = render
        self.writable = [(0x90010000, 0x90020000)]
        if render:
            self.writable += [(UI, UI + 0x200), (OUTPUT, OUTPUT + 128)]
        self.uc.emu_start(begin, end, count=20000)
        if self.pc() != end:
            raise AssertionError(f'Original execution stopped at {self.pc():08X}, expected {end:08X}')
        return self.get(3)

    def fixture(self, codes, tables, selector=0, day_index=0):
        # All original read-only tables, handles and record bytes are explicit
        # test fixtures; no constructor, network input or genuine catalog claim.
        self.uc.mem_write(0x90000000, bytes(0x10000))
        for slot, rows in enumerate(tables):
            raw_rows = RAW + 0x100 + slot * 0x100
            cooked_rows = COOKED + 0x100 + slot * 0x100
            self.word(RAW + 0x38 + slot * 8, len(rows))
            self.word(RAW + 0x3C + slot * 8, raw_rows - RAW)
            self.word(COOKED + 0x14 + slot * 4, cooked_rows)
            for index, row in enumerate(rows):
                self.uc.mem_write(raw_rows + index * 8, bytes([row.code]))
                self.word(cooked_rows + index * 8, raw_rows + index * 8)
                self.word(cooked_rows + index * 8 + 4,
                          0x90007000 + slot * 0x100 + index * 8
                          if row.text_pointer_present else 0)
        self.word(COOKED + 0x28, RAW)
        self.uc.mem_write(DAY + 0x19, bytes(codes))
        self.uc.mem_write(RECORD + day_index * 28 + 0x29, bytes(codes))
        self.word(UI + 0x190, day_index)
        self.word(HANDLE, RECORD)
        self.word(ALPHA, 0xC8)
        self.word(SDA - 0x6B8C, COOKED)
        self.word(SDA - 0x6A04, selector)
        return [COOKED + 0x100 + slot * 0x100 for slot in range(3)]

    def unchanged(self):
        for _, offset, address, size in self.sections:
            if bytes(self.uc.mem_read(address, size)) != self.data[offset:offset + size]:
                raise AssertionError('Original initialized section changed during proof')


def verify(path: Path) -> dict:
    native = _Native(path)
    counts = dict(direction=0, index_validation=0, lookup=0, availability=0,
                  combined_display=0, uv_only_display=0, direction_ff_suppression=0)
    admitted = 0
    empty = ((), (), ())
    example_rows = (IndexRow(0, True), IndexRow(7, False), IndexRow(7, True), IndexRow(255, True))
    for direction in range(256):
        native.fixture((255, 255, 255), empty)
        native.uc.mem_write(DAY + 0x16, bytes([direction]))
        native.run(0x8000D310, 0x8000D328, registers={0: 0x13579BDF, 6: DAY})
        expected = 0x13579BDF if native_direction_admitted(direction) else 0xFFFFFFFF
        if native.get(0) != expected:
            raise AssertionError('Original direction admission disagrees')
        admitted += native_direction_admitted(direction)
        counts['direction'] += 1

    for rows, selector, slot, value in itertools.product(((), example_rows), (0, 1), range(3), range(256)):
        codes = tuple(value if index == slot else 255 for index in range(3))
        tables = (rows, rows, rows)
        bases = native.fixture(codes, tables, selector)
        projected = project_indices(codes, tables, selector_word=selector, incoming_word=0x12345678)
        native.run(0x8000D328, 0x8000D448, registers={0: 0x12345678, 3: RAW, 6: DAY})
        if native.get(0) != projected.validation_word:
            raise AssertionError('Original index membership block disagrees')
        counts['index_validation'] += 1
        native.run(LOOKUPS[slot], registers={3: COOKED, 4: DAY + 0x19 + slot})
        match = projected.first_matches[slot]
        expected = 0 if match is None else bases[slot] + match * 8
        if native.get(3) != expected:
            raise AssertionError('Original lookup did not preserve first-match/null semantics')
        counts['lookup'] += 1

    # Matching bytes are dictionary keys, not a proved 0..N severity scale.
    # Include every byte as an explicit synthetic row, without assigning it
    # provider meaning. Preserve an already-failed validation accumulator.
    for value in range(256):
        tables = ((IndexRow(value, True),),) * 3
        bases = native.fixture((value,) * 3, tables, selector=0xFFFFFFFF)
        native.run(0x8000D328, 0x8000D448, registers={0: 0xFFFFFFFF, 3: RAW, 6: DAY})
        if native.get(0) != 0xFFFFFFFF:
            raise AssertionError('Index block cleared an incoming validation failure')
        native.word(SDA - 0x6A04, 0)
        native.run(0x8000D328, 0x8000D448, registers={0: 0x12345678, 3: RAW, 6: DAY})
        if native.get(0) != 0x12345678:
            raise AssertionError('Explicit matching index row was rejected')
        counts['index_validation'] += 2
        for slot in range(3):
            native.run(LOOKUPS[slot], registers={3: COOKED, 4: DAY + 0x19 + slot})
            if native.get(3) != bases[slot]:
                raise AssertionError('Explicit matching byte did not return its row')
            counts['lookup'] += 1

    # Exhaust lookup/text/missing states for each field, including ordinary
    # numeric values zero, seven and 254. They have no assigned provider units.
    states = ((9, ()), (7, (IndexRow(7, True),)), (7, (IndexRow(7, False),)),
              (255, ()), (255, (IndexRow(255, True),)),
              (0, (IndexRow(0, True),)), (254, (IndexRow(254, True),)))
    missing = native.wide(SDA - 0x781C)
    if not missing:
        raise AssertionError('Pinned original missing string unexpectedly empty')
    for state, day_index in itertools.product(itertools.product(states, repeat=3), (0, 1)):
        codes = tuple(item[0] for item in state)
        tables = tuple(item[1] for item in state)
        native.fixture(codes, tables, day_index=day_index)
        projection = project_indices(codes, tables, selector_word=0, incoming_word=0)
        for address, expected in ((0x80011D98, projection.any_available),
                                  (0x80011E64, projection.uv_available)):
            result = native.run(address, registers={3: UI, 4: HANDLE})
            if result != int(expected):
                raise AssertionError('Original availability callback disagrees')
            counts['availability'] += 1
        native.run(0x80011EB0, registers={3: UI, 4: HANDLE, 5: ALPHA}, render=True)
        helpers = [event[1] - UI for event in native.events if event[0] == 'helper']
        # Original display order is laundry, UV, pollen.
        expected_helpers = [offset for slot, offset in ((1, 0xAC), (0, 0xD0), (2, 0xF4))
                            if projection.combined_helper_calls[slot]]
        values = [event[1] for event in native.events if event[0] == 'value']
        expected_values = [missing if projection.combined_value_modes[slot] == 'original_missing_string'
                           else str(codes[slot]).encode('utf-16-be') for slot in (1, 0, 2)]
        if helpers != expected_helpers or values != expected_values:
            raise AssertionError('Original combined display branch or string output disagrees')
        counts['combined_display'] += 1
        # Existing caller slice, initialized at its language branch. The
        # surrounding layout selection and full parent function are not run.
        native.uc.mem_write(SDA - 0x6A0A, b'\x01')
        native.word(STACK + 0xC, 0xC8)
        native.run(0x80011A74, 0x80011BC0, registers={30: HANDLE, 31: UI}, render=True)
        helpers = [event for event in native.events if event[0] == 'helper']
        values = [event[1] for event in native.events if event[0] == 'value']
        expected_values = [] if projection.uv_only_value_mode == 'skip' else [
            missing if projection.uv_only_value_mode == 'original_missing_string'
            else str(codes[0]).encode('utf-16-be')]
        if bool(helpers) != projection.uv_only_helper_call or len(helpers) > 1 or values != expected_values:
            raise AssertionError('Original UV-only null/FF display branch disagrees')
        counts['uv_only_display'] += 1

    # FF direction takes the distant wind exit before either speed load.
    # This prefix does not assert safety of direction0+speedFF combinations.
    for selector in (0, 1):
        native.fixture((255, 255, 255), empty)
        native.uc.mem_write(DAY + 0x16, b'\xFF\x12\x34')
        native.word(SDA - 0x6B4C, selector)
        native.run(0x8001E1D0, 0x8001E8FC, registers={28: DAY})
        if any(address <= DAY + 0x18 and address + size > DAY + 0x17
               for address, size in native.reads):
            raise AssertionError('FF wind direction read a speed byte')
        counts['direction_ff_suppression'] += 1
    native.unchanged()
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise AssertionError('Original input changed on disk')
    required_entries = {*LOOKUPS, 0x80011D98, 0x80011E64, 0x80011EB0,
                        0x8016F588, 0x800362D8, 0x80036034}
    if not required_entries <= native.visited:
        raise AssertionError('An advertised original consumer/helper did not execute')
    return {
        'source_sha256': SOURCE_SHA256, 'source_bytes': SOURCE_BYTES,
        'comparisons': counts, 'total_comparisons': sum(counts.values()),
        'direction_admitted_cases': admitted,
        'synthetic_raw_and_cooked_tables': True, 'cooked_table_constructor_executed': False,
        'original_text_section_execution_bounds': True,
        'guarded_original_reads_and_writes': True, 'unchanged_original_sections_and_file': True,
        'original_string_copy_and_integer_helpers_executed': True,
        'graphics_calls_intercepted': [f'0x{address:08X}' for address in sorted(native.graphics)],
        'dictionary_ff_entries_remain_matchable': True,
        'combined_null_and_ff_use_original_missing_string': True,
        'uv_only_null_skips_value_path': True,
        'full_validator_executed': False, 'full_layout_selection_executed': False,
        'native_pixels_or_service_verified': False, 'provider_conversion_implemented': False,
        'speed_units_or_all_wind_combinations_verified': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_app', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.original_app), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
