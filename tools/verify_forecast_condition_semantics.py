"""Metadata-only original manual membership and bounded condition-consumer proof.

The original manual image was inspected privately. No image, caption, resource
record, drawing coordinate, colour or proprietary software byte is emitted.
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

from tools.verify_forecast_resources import TMD_BYTES, TMD_SHA256, _pin
from tools.verify_forecast_precipitation import SOURCE_BYTES, SOURCE_SHA256
from tools.verify_forecast_units import _Native, _image, _source_at

MANUAL_BYTES = 276617
MANUAL_SHA256 = '6ba845fc812a4106632b2843ae2439e2a14057d8a02cb8782a6514a0ba453b79'
SCREENSHOT_SHA256 = '1e1fb971235d7b001762cb64ae7ae9514041aae298ba8532c290a740e49c4db6'
CALLS = (0x80010FA0, 0x80014524, 0x800149E0, 0x8001931C, 0x800193E0,
         0x8001D79C, 0x8001E174, 0x80024580, 0x800247BC, 0x80024AA8,
         0x80024D28, 0x80024FA8, 0x8002524C, 0x800254E0, 0x8002575C)


def _member(data, wanted):
    if type(data) is not bytes or not 44 <= len(data) <= 512 * 1024:
        raise ValueError('Manual archive outside bounds')
    magic, root, _, files = struct.unpack_from('>4I', data)
    if magic != 0x55AA382D or not 32 <= root <= len(data) - 12:
        raise ValueError('Manual archive root differs')
    kind, parent, count = struct.unpack_from('>III', data, root)
    strings = root + count * 12
    if kind != 0x01000000 or parent or not 1 <= count <= 256 or not strings < files <= len(data):
        raise ValueError('Manual archive tables differ')
    matches = []
    for index in range(1, count):
        tag, offset, size = struct.unpack_from('>III', data, root + index * 12)
        start = strings + (tag & 0xFFFFFF)
        if not strings <= start < files:
            raise ValueError('Manual member name outside table')
        stop = data.find(b'\0', start, files)
        if stop < 0 or stop - start > 255 or tag >> 24 not in (0, 1):
            raise ValueError('Manual member name or kind differs')
        if tag >> 24:
            if not index < size <= count or offset >= index:
                raise ValueError('Manual directory bounds differ')
            continue
        if not files <= offset <= offset + size <= len(data):
            raise ValueError('Manual member outside archive')
        if data[start:stop] == wanted:
            matches.append(data[offset:offset + size])
    if len(matches) != 1:
        raise ValueError('Manual member is absent or ambiguous')
    return matches[0]


def verify_manual_membership(tmd, manual):
    _pin(tmd, TMD_BYTES, TMD_SHA256)
    _pin(manual, MANUAL_BYTES, MANUAL_SHA256)
    records = []
    for index in range(struct.unpack_from('>H', tmd, 0x1DE)[0]):
        offset = 0x1E4 + index * 36
        cid, cindex, kind, size = struct.unpack_from('>IHHQ', tmd, offset)
        if cindex == 10:
            records.append((cid, kind, size, tmd[offset + 16:offset + 36]))
    if records != [(10, 1, len(manual), hashlib.sha1(manual).digest())]:
        raise ValueError('Manual does not match retained TMD membership')
    nested = _member(manual, b'html-jp.arc')
    screenshot = _member(nested, b'page03gazo.png')
    _pin(screenshot, 15220, SCREENSHOT_SHA256)
    return dict(content_index=10, content_id=10, manual_bytes=MANUAL_BYTES,
                manual_sha256=MANUAL_SHA256, retained_tmd_hash_size_match=True,
                nested_archive_sha256=hashlib.sha256(nested).hexdigest(),
                screenshot_member='page03gazo.png', screenshot_sha256=SCREENSHOT_SHA256,
                screenshot_bytes=15220, original_assets_or_captions_emitted=False,
                nintendo_signature_or_independent_provenance_verified=False)


def _direct_calls(source, layout):
    found = []
    for index, offset, address, size in layout:
        if index >= 7:
            continue
        for step in range(0, size, 4):
            instruction = struct.unpack_from('>I', source, offset + step)[0]
            if instruction >> 26 == 18 and instruction & 3 == 1:
                displacement = instruction & 0x3FFFFFC
                if displacement & 0x2000000:
                    displacement -= 0x4000000
                if address + step + displacement == 0x80020574:
                    found.append(address + step)
    if tuple(found) != CALLS:
        raise ValueError('Pinned immediate icon-call inventory differs')
    return found


def verify_native_semantics(source):
    layout = _image(source)
    calls = _direct_calls(source, layout)
    native = _Native(source)
    from unicorn.ppc_const import UC_PPC_REG_FPR0, UC_PPC_REG_MSR
    obj, row, wrapper, alpha = 0x81010000, 0x81011000, 0x81012000, 0x81013000
    component_cases = handoffs = 0
    definitions = {}
    try:
        # Enable the architectural FP facility in the synthetic CPU; no code is patched.
        native.cpu.reg_write(UC_PPC_REG_MSR, native.cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
        for selector in (2, 6, 11):
            native.run(0x800205B8, {31: selector}, {0x800208EC})
            address = native.reg(3)
            parts = []
            for position in range(4):
                raw = _source_at(source, layout, address + position * 24, 24)
                texture = struct.unpack_from('>I', raw)[0]
                if texture == 0xFFFFFFFF:
                    break
                parts.append((texture, *struct.unpack_from('>fff', raw, 4)))
            else:
                raise ValueError('Selected original definition lacks bounded terminator')
            definitions[selector] = [part[0] for part in parts]
            for scale in (0.5, 1.0, 2.0):
                for anchor in ((0.0, 0.0), (10.0, -5.0)):
                    for flag in (0, 0x8000):
                        native.install_inputs({obj: struct.pack('>ff', *anchor)})
                        observed = []
                        for position, (texture, x, y, part_scale) in enumerate(parts):
                            for register, value in ((29, 4503599627370496.0), (30, scale), (31, 1.0)):
                                bits = struct.unpack('>Q', struct.pack('>d', value))[0]
                                native.cpu.reg_write(UC_PPC_REG_FPR0 + register, bits)
                            native.run(0x80020B68, {31: address + position * 24, 29: obj,
                                       30: flag, 28: 0x43300000}, {0x80020CCC})
                            expected_texture = 1 if texture == 4 and flag else texture
                            expected = (anchor[0] + x * scale, anchor[1] + y * scale)
                            actual = struct.unpack('>ff', native.cpu.mem_read(native.reg(4), 8))
                            draw_scale = struct.unpack('>d', struct.pack('>Q', native.cpu.reg_read(UC_PPC_REG_FPR0 + 1)))[0]
                            if native.reg(3) != expected_texture or actual != expected or draw_scale != part_scale * scale:
                                raise ValueError('Original component placement or texture selection differs')
                            observed.append(actual)
                            component_cases += 1
                        if selector == 2 and not (observed[0][0] < observed[1][0] and observed[0][1] < observed[1][1]):
                            raise ValueError('Original sun/cloud relative placement differs')
                        native.check_unchanged()
        for secondary in (1, 2, 6, 11, 101, 0x8001, 0x8002, 0x8006, 0x8065, 0xFFFF):
            object_bytes = bytearray(1024)
            object_bytes[0x27D] = 255
            native.install_inputs({obj: bytes(object_bytes), row: struct.pack('>HHI', 101, secondary, 0),
                                   wrapper: struct.pack('>II', row, 0), alpha: struct.pack('>I', 255)})
            fixtures = (
                (0x80010F9C, {3: row}), (0x80014510, {3: wrapper, 29: obj, 31: alpha}),
                (0x800149CC, {3: wrapper, 27: obj, 21: alpha}),
                (0x8001930C, {3: secondary, 29: obj}), (0x800193D0, {3: secondary, 30: obj}),
                (0x8001D774, {5: wrapper, 24: 255}), (0x8001E164, {5: wrapper, 29: 255}),
                (0x80024554, {3: wrapper, 26: obj, 31: 255}),
                (0x800247A8, {3: wrapper, 24: 255, 27: obj}),
                (0x80024A94, {3: wrapper, 31: 255, 26: obj}),
                (0x80024D14, {3: wrapper, 31: 255, 26: obj}),
                (0x80024F94, {3: wrapper, 26: 255, 24: obj}),
                (0x80025238, {3: wrapper, 27: 255, 28: obj}),
                (0x800254CC, {3: wrapper, 27: 255, 28: obj}),
                (0x80025748, {3: wrapper, 31: 255, 25: obj}),
            )
            for entry, registers in fixtures:
                native.run(entry, registers, {0x80020574})
                if native.reg(3) != secondary:
                    raise ValueError('Selected original caller suffix altered secondary/high bit')
                handoffs += 1
            native.check_unchanged()
        return dict(source_application_sha256=SOURCE_SHA256,
                    original_float_component_cases=component_cases,
                    selectors_and_texture_indices=definitions,
                    sun_first_x_and_y_less_than_cloud_for_selector2=True,
                    actual_component_draw_scale_verified=True,
                    original_immediate_icon_call_sites=[hex(address) for address in calls],
                    immediate_call_sites=len(calls), selected_handoff_cases=handoffs,
                    selected_suffixes_preserve_secondary_including_high_bit=True,
                    source_static_inputs_and_guards_unchanged=True,
                    native_code_or_helpers_patched=False,
                    paired_single_prolog_full_composition_loop_or_gx_executed=False,
                    indirect_call_inventory_or_whole_ui_clock_policy_verified=False,
                    native_arrow_temporal_meaning_verified=False,
                    original_definition_coordinates_colours_or_assets_emitted=False)
    finally:
        native.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_app', type=Path)
    parser.add_argument('original_tmd', type=Path)
    parser.add_argument('original_manual_content', type=Path)
    args = parser.parse_args(argv)
    try:
        values = []
        for path, limit in ((args.original_app, SOURCE_BYTES), (args.original_tmd, TMD_BYTES),
                            (args.original_manual_content, MANUAL_BYTES)):
            with path.open('rb') as stream:
                values.append(stream.read(limit + 1))
        source, tmd, manual = values
        _image(source)
        result = dict(manual=verify_manual_membership(tmd, manual), native=verify_native_semantics(source))
    except (OSError, ValueError, ImportError, struct.error):
        print('Forecast semantics identity, membership or optional native dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
