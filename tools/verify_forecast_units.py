"""Bounded private HAFJ wind formatter and numerical condition dispatcher audit.

Original text/resources are never emitted. No native UI, profile, settings file,
provider conversion, or host/device service is used. All settings are synthetic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.verify_forecast_precipitation import SOURCE_BYTES, SOURCE_SHA256

SDA = 0x80337540
OUTPUT = 0x801F7370
DAY = 0x81000000
OBJECT = 0x81001000
DIRECTION_NAMES = ('calm', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N')
DIRECTION_HASHES = (
    '674c526f5822300eedfa3db139cc2129845dabdf3761afd4f30aa7f6a7be50a4',
    '6935b72c86367f67a6f8e3c81d0fb3171ca42b200a5309f16cdc326bf76d90bd',
    '5fc9ab733fb2ef95fe0f612bd5cd075b0c81687bb5735e17d76653f9d0f6e076',
    '901f5a4b4bcc18f4541b7c314030657944f16985e564a77b0c73b5d946f7737c',
    '7104cae00d98f78ce59f6286749e5c2ad9526f3be3fae530c7f61b50512b31a9',
    'e5cca6e8ef32f2303dde763c7113f7333d01b344a9a53a25b1e1d72441a25c19',
    '4435f091b50291e11a9060192e6d165c31f0a79540e21df156ebba6cbba03c6d',
    '3a886fa97827280d6a62d5a19f248a26e31ba9acb9f490b6e2af4b8944cf194e',
    '072f005fc3f2a49f2e29225d116c10a3904c326a1b810a6eb840d9a574526694',
    '9a11b141d651ad27385412034dfc4b5e774b7d528ee86a583f2671321cdc8340',
    'a6d516819800916da02b766e6329fa1a2b41c95990ac32754c986ac3011cd804',
    '48e3ade60eb8a1b8522246565dd6b989cfe98c44ebe76d33a94f64b58a687c43',
    'd4817591e52af25f7522fcac5efcb71d8702eace3ae5d670c51d25ed9d639b03',
    '893fef4b9f41ef823a445262fbbc7b10649f854e7485fac379814bd74ef7b5b0',
    '69ac266df812f039c9327741ceae6cf315d2e2be2dcf3581a1ea791c0214a9cf',
    '9595c6f7be4d3ad06289ed556ec7908e2ec4b0a4986d286a6f294226b46b060c',
    '1e4346300a6bf77cc946eed3a3e717366b026ebcabb8d0f54e93e142dd646572',
)
STACK_LO, STACK_HI, STACK, STOP = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000


def _image(data):
    if type(data) is not bytes or len(data) != SOURCE_BYTES or hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Original HAFJ v7 application identity does not match')
    layout = []
    for index in range(18):
        offset = struct.unpack_from('>I', data, index * 4)[0]
        address = struct.unpack_from('>I', data, 0x48 + index * 4)[0]
        size = struct.unpack_from('>I', data, 0x90 + index * 4)[0]
        if size:
            if offset < 0x100 or offset + size > len(data) or not 0x80000000 <= address < address + size <= 0x81800000:
                raise ValueError('Pinned application section bounds differ')
            layout.append((index, offset, address, size))
    return layout


def _source_at(data, layout, address, length):
    for _, offset, base, size in layout:
        if base <= address < address + length <= base + size:
            start = offset + address - base
            return data[start:start + length]
    raise ValueError('Pinned application lacks an expected region')


class _Native:
    def __init__(self, source):
        self.layout = _image(source)  # Refuse identity before importing an optional backend.
        from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID, UC_MEM_READ_UNMAPPED
        from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
        self.cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
        self.cpu.mem_map(0x80000000, 0x1800000)
        for _, offset, address, size in self.layout:
            self.cpu.mem_write(address, source[offset:offset + size])
        self.source = source
        self.reg0, self.lr, self.pc = UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
        self.read_unmapped = UC_MEM_READ_UNMAPPED
        self.guard = b'U' * 32
        for address, length in ((OUTPUT, 512), (DAY, 32), (STACK_LO, STACK_HI - STACK_LO)):
            self.cpu.mem_write(address - 32, self.guard)
            self.cpu.mem_write(address + length, self.guard)
        self.instructions = 0
        self.extra_inputs = {}
        self.formatter_args = self.format_args = None
        self.invalid_read = None
        self.ends = set()
        self.hooks = [self.cpu.hook_add(UC_HOOK_CODE, self._code),
                      self.cpu.hook_add(UC_HOOK_MEM_READ, self._read),
                      self.cpu.hook_add(UC_HOOK_MEM_WRITE, self._write),
                      self.cpu.hook_add(UC_HOOK_MEM_INVALID, self._invalid)]

    def reg(self, index):
        return self.cpu.reg_read(self.reg0 + index)

    def _code(self, cpu, address, size, _):
        if address in self.ends:
            cpu.emu_stop()
            return
        self.instructions += 1
        if not any(index < 7 and base <= address < address + size <= base + length
                   for index, _, base, length in self.layout):
            raise ValueError('Execution left pinned original text')
        if address == 0x8001F110:
            self.formatter_args = tuple(self.reg(n) for n in (3, 4, 5))
        if address == 0x8016F408:
            self.format_args = tuple(self.reg(n) for n in range(3, 9))

    def _read(self, _, _access, address, size, _value, _context):
        ranges = [(base, base + length) for _, _, base, length in self.layout]
        ranges += [(a, a + len(value)) for a, value in self.extra_inputs.items()]
        ranges += [(SDA - 0x6A04, SDA - 0x6A00), (SDA - 0x6B4C, SDA - 0x6B48),
                   (SDA - 0x6A0A, SDA - 0x6A09), (STACK_LO, STACK_HI),
                   (OUTPUT, OUTPUT + 512), (DAY, DAY + 32)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError('Original consumer read outside explicit fixture/static bounds')

    def _write(self, _, _access, address, size, _value, _context):
        if not (STACK_LO <= address < address + size <= STACK_HI or OUTPUT <= address < address + size <= OUTPUT + 512):
            raise ValueError('Original consumer write outside output/stack bounds')

    def _invalid(self, _, access, address, size, _value, _context):
        if access != self.read_unmapped:
            raise ValueError('Original consumer reached an unexpected memory boundary')
        self.invalid_read = (address, size, self.cpu.reg_read(self.pc))
        return False

    def run(self, entry, registers, ends):
        self.ends = set(ends)
        self.formatter_args = self.format_args = self.invalid_read = None
        for index, value in {1: STACK, 2: 0x80339900, 13: SDA, **registers}.items():
            self.cpu.reg_write(self.reg0 + index, value)
        self.cpu.reg_write(self.lr, STOP)
        from unicorn import UcError
        try:
            self.cpu.emu_start(entry, STOP, count=20000, timeout=500000)
        except UcError:
            if self.invalid_read is None:
                raise
        if self.invalid_read is None and self.cpu.reg_read(self.pc) not in self.ends | {STOP}:
            raise ValueError('Original consumer exceeded its instruction/runtime bound')

    def install_inputs(self, values):
        self.extra_inputs = dict(values)
        for address, value in self.extra_inputs.items():
            self.cpu.mem_write(address - 32, self.guard)
            self.cpu.mem_write(address, value)
            self.cpu.mem_write(address + len(value), self.guard)

    def check_unchanged(self, row=None):
        for address, value in self.extra_inputs.items():
            if (bytes(self.cpu.mem_read(address, len(value))) != value
                    or bytes(self.cpu.mem_read(address - 32, 32)) != self.guard
                    or bytes(self.cpu.mem_read(address + len(value), 32)) != self.guard):
                raise ValueError('Original consumer changed an explicit lookup input')
        if row is not None and bytes(self.cpu.mem_read(DAY, 32)) != row:
            raise ValueError('Original caller changed the input day')
        for address, length in ((OUTPUT, 512), (DAY, 32), (STACK_LO, STACK_HI - STACK_LO)):
            if (bytes(self.cpu.mem_read(address - 32, 32)) != self.guard
                    or bytes(self.cpu.mem_read(address + length, 32)) != self.guard):
                raise ValueError('Original consumer changed a fixture guard')
        for _, offset, address, size in self.layout:
            if bytes(self.cpu.mem_read(address, size)) != self.source[offset:offset + size]:
                raise ValueError('Original application code/static bytes changed')

    def close(self):
        for hook in self.hooks:
            self.cpu.hook_del(hook)


def verify_wind(source):
    """Execute original caller byte selection and complete Japanese formatter.

    country=1/language=0 and selector=0/1 are explicit synthetic settings.
    Every speed byte is tested with direction 0/1, all other directions use explicit
    boundary samples, and direction FF suppression is checked separately.
    One observed invalid-read combination remains a recorded boundary, never a
    successful rendering claim or a production-data inference.
    """
    native = _Native(source)
    cpu = native.cpu
    labels = []
    for code, (meaning, expected_hash) in enumerate(zip(DIRECTION_NAMES, DIRECTION_HASHES)):
        pointer = struct.unpack('>I', _source_at(source, native.layout, 0x801994D8 + code * 4, 4))[0]
        raw = _source_at(source, native.layout, pointer, 32)
        end = next((n for n in range(0, 32, 2) if raw[n:n + 2] == b'\0\0'), None)
        if end is None or hashlib.sha256(raw[:end]).hexdigest() != expected_hash:
            native.close()
            raise ValueError('Original direction-label binding differs')
        labels.append({'code': code, 'meaning': meaning, 'pointer': f'0x{pointer:08x}', 'label_sha256': expected_hash})
    completed = rejected = suppressed = 0
    format_pointers = set()
    boundary = None
    try:
        for selector in (0, 1):
            for direction in (*range(17), 255):
                for speed in (range(256) if direction in (0, 1) else (0, 1, 254, 255)):
                    row = bytearray(32)
                    metric, imperial = ((speed, 255 - speed) if selector else (255 - speed, speed))
                    row[0x16:0x19] = bytes((direction, metric, imperial))
                    cpu.mem_write(DAY, bytes(row)); cpu.mem_write(OUTPUT, bytes(512))
                    for offset, value in ((-0x6A04, 1), (-0x6B4C, selector)):
                        cpu.mem_write(SDA + offset, struct.pack('>I', value))
                    cpu.mem_write(SDA - 0x6A0A, b'\0')
                    native.run(0x8001E1D0, {27: OBJECT, 28: DAY, 29: 128}, {0x8001E8E4, 0x8001E8FC})
                    if direction == 255:
                        if native.formatter_args is not None or native.invalid_read is not None or cpu.reg_read(native.pc) != 0x8001E8FC:
                            raise ValueError('Original missing-direction suppression differs')
                        suppressed += 1
                    else:
                        if native.formatter_args != (OBJECT, direction, speed):
                            raise ValueError('Original caller-to-formatter argument mapping differs')
                        args = native.format_args
                        if args is None or args[:2] != (OUTPUT, 256):
                            raise ValueError('Original formatter arguments differ')
                        expected_format = (0x8019AF1C if speed == 255 else 0x8019AF0C) if direction == 0 else (0x8019AEF4 if speed == 255 else 0x8019AEDC)
                        if args[2] != expected_format:
                            raise ValueError('Original numeric/missing-format branch differs')
                        format_pointers.add(args[2])
                        if direction and args[3] != int(labels[direction]['pointer'], 16):
                            raise ValueError('Original direction-table selection differs')
                        unit_pointer = args[5] if direction and speed != 255 else args[4]
                        if unit_pointer != (0x80199928 if selector else 0x8032FCB0):
                            raise ValueError('Original Japanese unit-table binding differs')
                        if direction == 0 and speed == 255:
                            if native.invalid_read != (255, 2, 0x8016F574):
                                raise ValueError('Observed original missing-speed boundary differs')
                            rejected += 1
                            boundary = {'address': 255, 'size': 2, 'pc': '0x8016f574',
                                        'direction': 0, 'selected_speed': 255,
                                        'full_ui_or_all_state_reachability_verified': False}
                        else:
                            if native.invalid_read is not None or cpu.reg_read(native.pc) != 0x8001E8E4:
                                raise ValueError('Original complete formatter did not return to its caller')
                            raw = bytes(cpu.mem_read(OUTPUT, 512))
                            end = next((n for n in range(0, 512, 2) if raw[n:n + 2] == b'\0\0'), None)
                            if end is None:
                                raise ValueError('Original formatted output lacks bounded termination')
                            text = raw[:end].decode('utf-16-be')
                            if ('km/h' if selector else 'mph') not in text:
                                raise ValueError('Original output unit differs')
                            if speed != 255:
                                numeric_argument = args[4] if direction else args[3]
                                if numeric_argument != speed or str(speed) not in text:
                                    raise ValueError('Original formatter changed an integer speed')
                            completed += 1
                    native.check_unchanged(bytes(row))
                    for offset, value in ((-0x6A04, 1), (-0x6B4C, selector)):
                        if bytes(cpu.mem_read(SDA + offset, 4)) != struct.pack('>I', value):
                            raise ValueError('Original formatter changed explicit settings')
                    if bytes(cpu.mem_read(SDA - 0x6A0A, 1)) != b'\0':
                        raise ValueError('Original formatter changed explicit language')
        return {'source_sha256': SOURCE_SHA256, 'cases': completed + rejected + suppressed,
                'complete_original_formatter_cases': completed, 'observed_invalid_read_cases': rejected,
                'missing_direction_suppressed_cases': suppressed, 'instructions': native.instructions,
                'explicit_synthetic_country': 1, 'explicit_synthetic_language': 0,
                'settings_selector_zero': {'day_offset': 24, 'display_unit': 'mph', 'unit_pointer': '0x8032fcb0'},
                'settings_selector_one': {'day_offset': 23, 'display_unit': 'km/h', 'unit_pointer': '0x80199928'},
                'format_pointers': [f'0x{p:08x}' for p in sorted(format_pointers)],
                'native_direction_labels': labels,
                'calm_label_static_binding_verified': True,
                'nonzero_direction_label_arguments_executed': True,
                'isolated_invalid_read_boundary': boundary,
                'caller_byte_selection_and_japanese_dispatch_executed': True,
                'complete_original_formatter_and_helpers_executed_for_successful_cases': True,
                'helpers_or_service_boundaries_stubbed': False, 'input_settings_static_and_guards_unchanged': True,
                'fractional_provider_rounding_verified': False, 'provider_conversion_performed': False,
                'original_text_or_assets_published': False, 'native_ui_rendered': False,
                'real_settings_profile_or_device_io': False, 'all_locales_verified': False}
    finally:
        native.close()


def verify_condition_dispatch(source):
    """Execute only the numerical icon selector, before graphical calls.

    IDs are native graphical selectors, never treated as JMA weather meanings.
    No original drawing data or payload condition labels are emitted.
    """
    native = _Native(source)
    rows = []
    lookup_cases = 0
    try:
        manager, header, entries, records, query = (0x81002000, 0x81003000, 0x81004000, 0x81005000, 0x81006000)
        for key in (100, 300, 0x1001, 32767, 65534):
            for secondary in (1, 101, 0x8001, 65535):
                other, missing = (key + 1) % 65535, (key + 2) % 65535
                manager_bytes, header_bytes = bytearray(48), bytearray(56)
                struct.pack_into('>I', manager_bytes, 0x10, entries)
                struct.pack_into('>I', manager_bytes, 0x28, header)
                struct.pack_into('>I', header_bytes, 0x30, 2)
                for asked, expected in ((key, secondary), (other, 2), (missing, 65535)):
                    native.install_inputs({manager: bytes(manager_bytes), header: bytes(header_bytes),
                        entries: struct.pack('>4I', records, 0, records + 8, 0),
                        records: struct.pack('>HHIHHI', key, secondary, 0, other, 2, 0),
                        query: struct.pack('>I', asked)})
                    native.run(0x800203F0, {3: manager, 4: query}, {STOP})
                    if native.reg(3) != expected or native.invalid_read is not None:
                        raise ValueError('Original primary-key/secondary-selector lookup differs')
                    native.check_unchanged()
                    lookup_cases += 1
        codes = tuple(range(127)) + (127, 255, 300, 32767)
        for flag in (0, 0x8000):
            for code in codes:
                native.run(0x800205B8, {31: flag | code}, {0x800208EC, 0x800208A4})
                fallback = native.cpu.reg_read(native.pc) == 0x800208A4
                if native.reg(4) != code or native.reg(6) != flag:
                    raise ValueError('Original condition bit partition differs')
                target = struct.unpack('>I', _source_at(source, native.layout, 0x8019AF48 + code * 4, 4))[0] if code <= 126 else 0x800208A4
                if fallback != (target == 0x800208A4):
                    raise ValueError('Original condition table/default boundary differs')
                pointer = None if fallback else native.reg(3)
                if pointer is not None:
                    # Selected entries consist of original lis/addi/b instructions.
                    raw = _source_at(source, native.layout, target, 8)
                    upper, lower = struct.unpack('>II', raw)
                    if upper >> 16 != 0x3C60 or lower >> 16 != 0x3863:
                        raise ValueError('Original condition entry shape differs')
                    expected_pointer = ((upper & 0xFFFF) << 16) + struct.unpack('>h', raw[6:8])[0]
                    if pointer != expected_pointer:
                        raise ValueError('Original graphical definition pointer differs')
                rows.append((flag, code, fallback, pointer))
        native.check_unchanged()
        return {'source_sha256': SOURCE_SHA256, 'cases': len(rows),
                'native_low15_selector_range': [0, 126],
                'complete_original_lookup_cases': lookup_cases,
                'primary_u16_key_distinct_from_secondary_u16_graphical_selector': True,
                'absent_key_getter_returns_ffff': True,
                'original_lookup_stubbed': False,
                'full_payload_validator_or_all_callers_executed': False,
                'high_bit_preserved_as_separate_argument': True,
                'in_range_unmapped_selectors': [code for flag, code, fallback, _ in rows if not flag and code <= 126 and fallback],
                'mapped_selector_count': sum(not fallback for flag, _, fallback, _ in rows if not flag),
                'distinct_definition_pointers': len({p for _, _, fallback, p in rows if not fallback}),
                'instructions': native.instructions, 'original_selector_and_table_executed': True,
                'pre_graphics_prefix_or_drawing_suffix_executed': False,
                'selector_branch_or_table_stubbed': False, 'source_and_guards_unchanged': True,
                'jma_or_provider_semantic_mapping_verified': False, 'original_graphics_rendered': False,
                'original_assets_or_message_copy_published': False}
    finally:
        native.close()



def verify_temperature_format_prefix(source):
    """Execute the original signed-integer/missing formatter prefix before drawing.

    No float provider measurement is supplied. The selected prefix cannot
    establish a fractional rounding rule or Celsius/Fahrenheit conversion.
    """
    native = _Native(source)
    ordinary = missing = 0
    try:
        for value in range(-128, 128):
            native.cpu.mem_write(OUTPUT, bytes(512))
            native.run(0x8001D558, {3: OBJECT, 4: value & 0xFFFFFFFF, 5: 128}, {0x8001D5BC})
            if native.invalid_read is not None:
                raise ValueError('Original temperature formatter reached an unexpected boundary')
            raw = bytes(native.cpu.mem_read(OUTPUT, 512))
            end = next((n for n in range(0, 512, 2) if raw[n:n + 2] == b'\0\0'), None)
            if end is None:
                raise ValueError('Original temperature output lacks bounded termination')
            if value == -128:
                if hashlib.sha256(raw[:end]).hexdigest() != 'b6bd42da7ec0c2712293618f6289c5c5af8525e4822bff347ee9187d6e66de3a':
                    raise ValueError('Original unavailable-temperature branch differs')
                missing += 1
            else:
                if str(value) not in raw[:end].decode('utf-16-be'):
                    raise ValueError('Original temperature formatter changed a signed integer')
                ordinary += 1
            native.check_unchanged()
        return {'source_sha256': SOURCE_SHA256, 'cases': ordinary + missing,
                'preserved_signed_integer_cases': ordinary, 'missing_minus_128_cases': missing,
                'instructions': native.instructions, 'original_prefix_and_string_numeric_helpers_executed': True,
                'prefix_start': '0x8001d558', 'prefix_exit_before_drawing': '0x8001d5bc',
                'helpers_stubbed': False, 'source_and_guards_unchanged': True,
                'fractional_provider_rounding_or_unit_conversion_verified': False,
                'temperature_field_selection_or_full_draw_function_executed': False,
                'native_ui_rendered': False, 'original_message_copy_published': False}
    finally:
        native.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_app', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.original_app.open('rb') as stream:
            source = stream.read(SOURCE_BYTES + 1)
        report = {'wind': verify_wind(source), 'condition_dispatch': verify_condition_dispatch(source),
                  'temperature_format_prefix': verify_temperature_format_prefix(source)}
    except (OSError, ValueError, ImportError):
        print('Forecast consumer input or optional native dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
