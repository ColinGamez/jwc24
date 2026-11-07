"""Inspect pinned private HAFJ condition resources; emit metadata only.

No raster, original text, definition records, drawing coordinates, colour bytes,
device data or patched application is emitted. Selected integer native fragments
run unchanged; complete floating-point composition and GX drawing do not run.
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

from jwc24.forecast import decode_lz10
from tools.verify_forecast_units import _Native, _image, _source_at
from tools.verify_forecast_precipitation import SOURCE_SHA256

TMD_BYTES = 916
TMD_SHA256 = '47ba6338a866739282b33151e4fe74b1c3d0c32f4d72212cbeca8000d1bb3bd2'
CONTENT_BYTES = 3271554
CONTENT_SHA256 = '039a0139a13723c1cc7348f7925b0c22860967565c8d9a480b2d1ecb6f7da0ee'
MEMBER_BYTES = 108506
MEMBER_SHA256 = '7917117afd532e69a61a3aec8be3867de5ac837839dec8458d976b2fa4bcea11'
TPL_BYTES = 396576
TPL_SHA256 = '6afcb4163c41be26531d1117e988c0c163ea2e879f5788c6df41be9f30f3bcb1'
MEMBER = b'TPLWeather.tpl.LZ'


def _pin(data, size, digest):
    if type(data) is not bytes or len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Forecast resource input identity differs')


def _archive_member(data):
    """Bounded U8 membership check; no member path is used for host file access."""
    if type(data) is not bytes or not 44 <= len(data) <= CONTENT_BYTES:
        raise ValueError('Invalid bounded resource archive')
    magic, root, _, files = struct.unpack_from('>4I', data)
    if magic != 0x55AA382D or not 32 <= root <= len(data) - 12:
        raise ValueError('Invalid resource archive root')
    kind, parent, count = struct.unpack_from('>III', data, root)
    if kind != 0x01000000 or parent != 0 or not 1 <= count <= 256:
        raise ValueError('Invalid resource archive root record')
    strings = root + count * 12
    if not strings < files <= len(data):
        raise ValueError('Invalid resource archive tables')
    found = []
    for index in range(1, count):
        word, offset, size = struct.unpack_from('>III', data, root + index * 12)
        start = strings + (word & 0xFFFFFF)
        if not strings <= start < files:
            raise ValueError('Resource member name outside string table')
        end = data.find(b'\0', start, files)
        if end < 0 or end - start > 255 or word >> 24 not in (0, 1):
            raise ValueError('Invalid resource member name or type')
        if word >> 24:
            if not index < size <= count or offset >= index:
                raise ValueError('Invalid resource archive directory')
            continue
        if not files <= offset <= offset + size <= len(data):
            raise ValueError('Resource member outside archive')
        if data[start:end] == MEMBER:
            found.append(data[offset:offset + size])
    if len(found) != 1:
        raise ValueError('Expected one exact weather resource member')
    return found[0], count


def _texture_metadata(data):
    """Check every TPL texture header and padded pixel range without drawing."""
    if type(data) is not bytes or not 12 <= len(data) <= TPL_BYTES:
        raise ValueError('Invalid bounded texture container')
    magic, count, table = struct.unpack_from('>III', data)
    if magic != 0x0020AF30 or not 1 <= count <= 64 or not 12 <= table <= len(data) - count * 8:
        raise ValueError('Invalid texture table')
    rows, regions = [], [(0, 12), (table, table + count * 8)]
    for index in range(count):
        header, palette = struct.unpack_from('>II', data, table + index * 8)
        if not table + count * 8 <= header <= len(data) - 36 or palette != 0:
            raise ValueError('Invalid direct-colour texture header')
        height, width, format_, pixels = struct.unpack_from('>HHII', data, header)
        if format_ not in (2, 3, 5) or not 1 <= width <= 512 or not 1 <= height <= 512:
            raise ValueError('Unsupported bounded texture dimensions or format')
        tile_width, bytes_per_pixel = (8, 1) if format_ == 2 else (4, 2)
        size = ((width + tile_width - 1) // tile_width * tile_width
                * ((height + 3) // 4 * 4) * bytes_per_pixel)
        if not header + 36 <= pixels <= pixels + size <= len(data):
            raise ValueError('Texture pixel range outside container')
        regions.extend(((header, header + 36), (pixels, pixels + size)))
        rows.append(dict(texture=index, width=width, height=height, format=format_,
                         header_offset=header, pixel_offset=pixels, pixel_bytes=size,
                         header_sha256=hashlib.sha256(data[header:header + 36]).hexdigest(),
                         pixel_sha256=hashlib.sha256(data[pixels:pixels + size]).hexdigest()))
    regions.sort()
    if any(left[1] > right[0] for left, right in zip(regions, regions[1:])):
        raise ValueError('Texture metadata or pixel regions overlap')
    return rows


def verify_membership(tmd, content):
    _pin(tmd, TMD_BYTES, TMD_SHA256)
    _pin(content, CONTENT_BYTES, CONTENT_SHA256)
    if tmd[0x18C:0x194] != bytes.fromhex('000100024841464a') or struct.unpack_from('>H', tmd, 0x1DC)[0] != 7:
        raise ValueError('Pinned title identity differs')
    count = struct.unpack_from('>H', tmd, 0x1DE)[0]
    if 0x1E4 + count * 36 != len(tmd):
        raise ValueError('Pinned content table differs')
    matches = []
    for index in range(count):
        record = 0x1E4 + index * 36
        cid, cindex, kind, size = struct.unpack_from('>IHHQ', tmd, record)
        if cindex == 9:
            matches.append((cid, kind, size, tmd[record + 16:record + 36]))
    if matches != [(16, 1, len(content), hashlib.sha1(content).digest())]:
        raise ValueError('Pinned content does not match retained TMD membership')
    compressed, archive_count = _archive_member(content)
    _pin(compressed, MEMBER_BYTES, MEMBER_SHA256)
    decoded = decode_lz10(compressed)
    _pin(decoded, TPL_BYTES, TPL_SHA256)
    textures = _texture_metadata(decoded)
    if len(textures) != 27:
        raise ValueError('Pinned texture count differs')
    return dict(tmd_sha256=TMD_SHA256, content_sha256=CONTENT_SHA256,
                content_index=9, content_id=16, retained_tmd_hash_size_match=True,
                archive_member_count=archive_count, exact_unique_member=MEMBER.decode('ascii'),
                compressed_sha256=MEMBER_SHA256, tpl_sha256=TPL_SHA256,
                textures=textures, all_texture_regions_bounded_and_disjoint=True,
                nintendo_signature_or_independent_provenance_verified=False)


def verify_selectors(source):
    """Run original selector and both isolated integer texture-substitution blocks."""
    _image(source)  # Refuse before optional execution backend import.
    native = _Native(source)
    rows, cases = [], 0
    try:
        for selector in range(127):
            native.run(0x800205B8, {31: selector}, {0x800208EC, 0x800208A4})
            if native.cpu.reg_read(native.pc) == 0x800208A4:
                continue
            address = native.reg(3)
            parts = []
            for part in range(16):
                raw = _source_at(source, native.layout, address + part * 24, 24)
                texture = struct.unpack_from('>I', raw)[0]
                if texture == 0xFFFFFFFF:
                    break
                if texture >= 27:
                    raise ValueError('Condition definition references absent texture')
                parts.append(texture)
            else:
                raise ValueError('Condition definition lacks bounded termination')
            if not parts:
                raise ValueError('Condition definition is empty')
            definition = _source_at(source, native.layout, address, (len(parts) + 1) * 24)
            rows.append(dict(selector=selector, definition_address=hex(address),
                             definition_sha256=hashlib.sha256(definition).hexdigest(),
                             unflagged_texture_indices=parts))
        for texture in range(27):
            for flag in (0, 1, 0x8000):
                for compare, branch, stop, registers in (
                    (0x80020BD0, 0x80020C18, 0x80020C58, {8: texture, 30: flag}),
                    (0x80020A04, 0x80020A2C, 0x80020A6C, {5: texture, 29: flag}),
                ):
                    # The entry's first BEQ depends on this real preceding cmpwi.
                    native.run(compare, registers, {compare + 4})
                    native.run(branch, registers, {stop})
                    expected = {4: 1, 15: 11}.get(texture, texture) if flag else texture
                    if native.reg(3) != expected or native.invalid_read is not None:
                        raise ValueError('Original texture substitution differs')
                    cases += 1
        native.check_unchanged()
        return dict(source_application_sha256=SOURCE_SHA256,
                    selector_cases=127, mapped_selectors=len(rows), definitions=rows,
                    original_substitution_cases=cases,
                    nonzero_flag_texture_substitutions={'4': 1, '15': 11},
                    original_integer_fragments_executed=True,
                    source_and_guards_unchanged=True, full_float_composition_executed=False,
                    gx_drawing_or_native_ui_executed=False,
                    high_bit_time_of_day_policy_verified=False,
                    provider_or_jma_semantic_mapping_verified=False)
    finally:
        native.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_app', type=Path)
    parser.add_argument('original_tmd', type=Path)
    parser.add_argument('original_content', type=Path)
    args = parser.parse_args(argv)
    try:
        from tools.verify_forecast_precipitation import SOURCE_BYTES
        values = []
        for path, limit in ((args.original_app, SOURCE_BYTES), (args.original_tmd, TMD_BYTES),
                            (args.original_content, CONTENT_BYTES)):
            with path.open('rb') as stream:
                values.append(stream.read(limit + 1))
        source, tmd, content = values
        _image(source)
        report = dict(resources=verify_membership(tmd, content), selectors=verify_selectors(source))
    except (OSError, ValueError, ImportError, struct.error):
        print('Forecast resource identity, membership or optional native dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
