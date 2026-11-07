"""Execute bounded original condition-label handoff and text-length prefixes.

Original font metrics, floating-point fitting, glyph traversal and drawing are
not emulated by this check. It establishes pointer/UTF-16 length preservation
and the actual LF/tab control-branch boundary without inventing a character cap.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.jma_conditions import SUPPORTED
from tools.verify_forecast_precipitation import SOURCE_BYTES, SOURCE_SHA256
from tools.verify_forecast_units import STOP, _Native, _image


def verify_condition_text(source):
    _image(source)
    native = _Native(source)
    obj, row, wrapper, text_ptr = 0x81010000, 0x81011000, 0x81012000, 0x81013000
    manager, header, query = 0x81014000, 0x81015000, 0x81016000
    # Lengths are fixture bounds, not a claimed native maximum.
    texts = tuple(label for _, label in SUPPORTED.values()) + (
        '', 'A\nB', 'A\tB', '\U0001f600', 'A' * 31, 'A' * 32, 'A' * 255,
        'A' * 256, 'A' * 512, 'A' * 1024,
    )
    cases = handoffs = controls = 0
    try:
        reviewed = tuple((int(code), selector) for code, (selector, _) in SUPPORTED.items())
        for position, text in enumerate(texts):
            raw = text.encode('utf-16-be') + b'\0\0'
            primary, secondary = reviewed[position] if position < 4 else (100, 1)
            manager_bytes, header_bytes = bytearray(48), bytearray(56)
            struct.pack_into('>I', manager_bytes, 0x10, wrapper)
            struct.pack_into('>I', manager_bytes, 0x28, header)
            struct.pack_into('>I', header_bytes, 0x30, 1)
            native.install_inputs({obj: bytes(1024), row: struct.pack('>HHI', primary, secondary, 0),
                wrapper: struct.pack('>II', row, text_ptr), text_ptr: raw,
                manager: bytes(manager_bytes), header: bytes(header_bytes), query: struct.pack('>I', primary)})
            native.run(0x800203B4, {3: manager, 4: query}, {STOP})
            if native.reg(3) != wrapper:
                raise ValueError('Original primary lookup did not retain the condition/text wrapper')
            native.run(0x8001D7E4, {22: obj, 28: native.reg(3), 24: 255}, {0x8001C89C})
            if tuple(native.reg(k) for k in (3, 4, 5, 6)) != (obj, obj + 0xAC, text_ptr, 255):
                raise ValueError('Original condition-label pointer handoff differs')
            handoffs += 1
            for start, stop in ((0x800D5700, 0x800D5724), (0x800D59AC, 0x800D59D0)):
                native.run(start, {3: obj, 4: text_ptr}, {stop})
                if (native.reg(3) != len(raw) // 2 - 1 or native.reg(31) != text_ptr
                        or native.invalid_read is not None):
                    raise ValueError('Original width/height prefix changed UTF-16 source length')
                cases += 1
            native.check_unchanged()
        targets = {10: 0x800D040C, 9: 0x800D0440}
        for char in tuple(range(33)) + (0x6674, 0x66C7, 0x96E8, 0x96EA, 0xD83D):
            native.run(0x800D03E4, {4: char, 5: obj},
                       {0x800D040C, 0x800D0440, 0x800D04F4})
            if native.cpu.reg_read(native.pc) != targets.get(char, 0x800D04F4):
                raise ValueError('Original text control-branch boundary differs')
            controls += 1
        native.check_unchanged()
        return dict(source_application_sha256=SOURCE_SHA256,
                    condition_label_pointer_handoff_cases=handoffs,
                    complete_original_primary_key_lookup_cases=handoffs,
                    complete_utf16_length_helper_cases=cases,
                    width_height_prefix_cases=cases, control_branch_cases=controls,
                    largest_tested_utf16_units=1024,
                    condition_label_handoff='0x8001d7e4..0x8001d7f8',
                    original_fitting_function='0x8001c89c',
                    width_prefix='0x800d5700..0x800d5724',
                    height_prefix='0x800d59ac..0x800d59d0',
                    complete_utf16_length_helper='0x8016f56c',
                    control_prefix='0x800d03e4..0x800d040c/0x800d0440/0x800d04f4',
                    pointers_and_utf16_code_unit_lengths_preserved=True,
                    newline_tab_and_surrogate_units_preserved=True,
                    source_static_inputs_and_guards_unchanged=True,
                    original_instructions_or_helpers_stubbed=False,
                    full_fitting_font_metrics_line_bounds_or_glyph_rendering_executed=False,
                    fixed_character_cap_established=False,
                    native_ui_or_device_io_executed=False)
    finally:
        native.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_app', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.original_app.open('rb') as stream:
            source = stream.read(SOURCE_BYTES + 1)
        report = verify_condition_text(source)
    except (OSError, ValueError, ImportError):
        print('Forecast condition-text identity or optional native dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
