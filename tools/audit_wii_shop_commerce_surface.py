"""Metadata-only, offline comparison of the original v21 commerce surfaces.

Reads only explicitly supplied executable/container files and inventory-checked
client-library sources. No original code executes, no queries/credentials/source
bodies/disassembly are emitted, and no service or account state is accessed.
Static references are bounded candidates, not runtime call traces.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from tools.audit_wii_shop_sources import audit as source_audit
from tools.inspect_demae_references import sections

MAIN_SHA256 = 'aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898'
BROWSER_SHA256 = '7cebfa18a7b7525d25a9ebf407b648e13e4fa2470b6c628fd7f1e007adb2faa8'
COMPRESSED_SHA256 = '5742df998f3bcf4545e4a7ba1df591a11b76e660087fd3ceb2cdf8f90582fefe'
OVERLAY_SHA256 = '703a9810ee62c0a3c6675a4ebaa14ef498759dbc8c274e74be2f9ddf1512f514'
OVERLAY_SIZE = 9130272
MAX_BYTES = 16 * 1024 * 1024
MARKERS = ('ListTitles', 'listTitles', 'EC_ListTitles()', 'GetTitle', 'GetTitleDetails',
           'EC_GetTitle(titleId)', 'getTitleInfo', 'getTitleInfos', 'downloadTitle',
           'request', 'ECommerceInterface', 'GetECConfig', 'ECVersion',
           'ContentPrefixURL', 'UncachedContentPrefixURL', 'EcsURL', 'IasURL', 'CasURL',
           'ListResultOffset', 'ListResultLimit', 'ListResultTotalSize', 'Attributes',
           'AttributeFilters', 'Name', 'Value', 'TitleId', 'Titles', 'Version',
           'TitleType', 'TitleName', 'TitleDescription', 'TitleSize', 'FsSize',
           'Category', 'TitleKind', 'SERVICE', 'ADVENTURE', 'ACTION')
MARKERS += ('AttributeFiltersEx', 'FilterType', 'DataType', 'OrderByAttribute', 'OrderByType')
SELECTED = tuple('common/lib/ec/' + name for name in (
    'ec_getTitle.cpp', 'ec_getTitle.h', 'ec_js.cpp', 'ec_api.cpp', 'ec_soap.cpp',
    'ec_soap.h', 'ec_listTitles.cpp', 'ec_listTitles.h', 'ec_common.h',
    'include/ecbase.h', 'ec_test.cpp', 'ec_listServiceItems.cpp', 'ec_asyncOp.cpp',
    'ec_connect.cpp', 'include/ec_apip.h'))


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def marker_offsets(data):
    """Return only allowlisted complete NUL-terminated ASCII names, never context."""
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Binary outside commerce audit byte bound')
    result = {}
    for marker in MARKERS:
        found = [match.start() for match in re.finditer(re.escape(marker.encode()) + b'\0', data)
                 if match.start() == 0 or data[match.start() - 1] == 0]
        if len(found) > 256:
            raise ValueError('Too many commerce marker occurrences')
        result[marker] = found
    return result


def mapped_markers(data, layout):
    result = {}
    for marker, offsets in marker_offsets(data).items():
        rows = []
        for offset in offsets:
            for _, file_offset, address, size in layout:
                if file_offset <= offset < file_offset + size:
                    rows.append({'file_offset': offset, 'address': address + offset - file_offset})
        result[marker] = rows
    return result


def read_virtual(data, layout, address, size):
    if type(size) is not int or not 0 < size <= 8192:
        raise ValueError('Native audit slice outside byte bound')
    for _, offset, base, length in layout:
        if base <= address < address + size <= base + length:
            return data[offset + address - base:offset + address - base + size]
    raise ValueError('Native audit slice outside mapped sections')


def relative_string_loads(data, layout, start, end, base_address, base_register=31):
    """Find addi references to allowlisted strings from a manually verified base.

    This decodes one instruction form in a fingerprinted native slice. It is
    deliberately not a control-flow/dataflow proof or a general disassembler.
    """
    if start % 4 or end % 4 or not 0 <= base_register < 32:
        raise ValueError('Unaligned or invalid relative-string audit parameters')
    block = read_virtual(data, layout, start, end - start)
    # Compilers may share a suffix of another stored string. A native pointer
    # to that suffix is still an exact C string, regardless of the previous byte.
    targets = {}
    for marker in MARKERS:
        for match in re.finditer(re.escape(marker.encode()) + b'\0', data):
            for _, file_offset, address, size in layout:
                if file_offset <= match.start() < file_offset + size:
                    targets[address + match.start() - file_offset] = marker
    result = []
    for offset in range(0, len(block), 4):
        word = struct.unpack_from('>I', block, offset)[0]
        if word >> 26 != 14 or (word >> 16) & 31 != base_register:
            continue
        immediate = word & 0xffff
        immediate -= 65536 if immediate >= 32768 else 0
        target = (base_address + immediate) & 0xffffffff
        if target in targets:
            result.append({'instruction': f'0x{start + offset:08x}',
                           'marker': targets[target], 'target': f'0x{target:08x}',
                           'destination_register': (word >> 21) & 31})
    return result


def direct_callers(data, layout, target):
    """Enumerate relative branch-link instructions, without executing them."""
    rows = []
    for index, offset, base, size in layout:
        if index >= 7:
            continue
        for position in range(0, size - 3, 4):
            word = struct.unpack_from('>I', data, offset + position)[0]
            if word >> 26 != 18 or not word & 1 or word & 2:
                continue
            displacement = word & 0x03fffffc
            displacement -= 0x4000000 if displacement & 0x2000000 else 0
            if (base + position + displacement) & 0xffffffff == target:
                rows.append(f'0x{base + position:08x}')
    return rows


def source_vocabulary(root):
    """Extract schema/method identifiers from verified source, not proprietary bodies."""
    root = Path(root)
    report = source_audit(root, selected=SELECTED)
    test = (root / 'common/lib/ec/ec_test.cpp').read_text(encoding='latin-1')
    match = re.search(r'static\s+const\s+char\s*\*\s*requestedAttributes\[\]\s*=\s*\{([^}]+)\}', test)
    if not match:
        raise ValueError('Source-test attribute declaration differs')
    attributes = re.findall(r'"([A-Za-z][A-Za-z0-9_]{0,63})"', match[1])
    js = (root / 'common/lib/ec/ec_js.cpp').read_text(encoding='latin-1')
    getter = re.search(r'int\s+getter_ECInterface\s*\([^;{]+\)\s*\{(.*?)\n\}', js, re.S)
    if not getter:
        raise ValueError('Source interface getter differs')
    names = sorted(set(re.findall(r'strcmp\s*\(\s*name\s*,\s*"([A-Za-z][A-Za-z0-9_]{0,63})"', getter[1])))
    return report, {'test_requested_attribute_names': attributes,
                    'test_attribute_names_are_retail_schema': False,
                    'ec_interface_getter_names': names,
                    'dedicated_list_titles_getter_present': 'listTitles' in names}


def audit(main_path, browser_path, source_root):
    def read(path, expected):
        path = Path(path)
        if not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError('Commerce input outside byte bounds')
        data = path.read_bytes()
        if fingerprint(data) != expected:
            raise ValueError('Original v21 commerce fingerprint differs')
        return data

    main = read(main_path, MAIN_SHA256)
    container = read(browser_path, BROWSER_SHA256)
    from libWiiPy.archive import U8Archive, decompress_lz77
    archive = U8Archive()
    archive.load(container)
    name = 'wwwlib-rvl.lz7'
    if archive.file_name_list.count(name) != 1:
        raise ValueError('Browser overlay member differs')
    compressed = archive.file_data_list[archive.file_name_list.index(name)]
    if (fingerprint(compressed) != COMPRESSED_SHA256 or len(compressed) < 4
            or compressed[0] != 0x10 or int.from_bytes(compressed[1:4], 'little') != OVERLAY_SIZE):
        raise ValueError('Browser compressed overlay fingerprint/size differs')
    overlay = decompress_lz77(compressed)
    if len(overlay) != OVERLAY_SIZE or fingerprint(overlay) != OVERLAY_SHA256:
        raise ValueError('Browser overlay fingerprint/size differs')
    sources, vocabulary = source_vocabulary(source_root)
    layout = sections(main)
    markers = mapped_markers(main, layout)
    table = struct.unpack('>8I', read_virtual(main, layout, 0x8032cc08, 32))
    return {'schema_version': 1, 'checked_at': '2026-10-25',
            'original_main': {'bytes': len(main), 'sha256': MAIN_SHA256,
                              'allowlisted_marker_locations': markers,
                              'allowlisted_nul_terminated_suffix_counts': {
                                  marker: main.count(marker.encode() + b'\0') for marker in MARKERS}},
            'browser_container': {'bytes': len(container), 'sha256': BROWSER_SHA256},
            'browser_compressed_member': {'name': name, 'bytes': len(compressed), 'sha256': COMPRESSED_SHA256},
            'browser_overlay': {'bytes': len(overlay), 'sha256': OVERLAY_SHA256,
                                'allowlisted_marker_counts': {k: len(v) for k, v in marker_offsets(overlay).items()}},
            'source_audit': sources, 'source_vocabulary': vocabulary,
            'getecconfig_relative_string_loads': relative_string_loads(
                main, layout, 0x80088920, 0x80088f80, 0x80322020),
            'listtitles_relative_string_loads': relative_string_loads(
                main, layout, 0x800a3310, 0x800a3890, 0x8032c530),
            'listtitles_native_object_evidence': {
                'constructor': '0x800a39d0', 'constructor_direct_callers': direct_callers(main, layout, 0x800a39d0),
                'vtable': '0x8032cc08', 'vtable_words': [f'0x{word:08x}' for word in table],
                'run_dispatch': '0x800a3240', 'request_candidate': '0x800a3310',
                'extract_candidate': '0x800a3890',
                'initialization_is_not_operation_invocation': True},
            'retail_listtitles_source_differences': {
                'AttributeFiltersEx': {'outer_loop_stride_bytes': 20,
                                      'fields': ['FilterType', 'DataType', 'Name', 'Value'],
                                      'value_repeated': True},
                'OrderByAttribute': {'fields': ['OrderByType', 'DataType', 'Name']},
                'additional_caller_name_value_elements': {'loop_start': '0x800a378c',
                                                         'loop_stride_bytes': 8},
                'string_element_helper_candidate': '0x8007d7a0',
                'allowed_filter_order_data_type_values_verified': False,
                'complete_compatibility_with_old_source_codec': False},
            'native_slice_sha256': {name: fingerprint(read_virtual(main, layout, start, size))
                for name, start, size in (('getecconfig', 0x80088920, 0x660),
                                          ('listtitles_constructor', 0x800a39d0, 0x64),
                                          ('listtitles_request', 0x800a3310, 0x580),
                                          ('listtitles_extract', 0x800a3890, 0x140))},
            'raw_binary_context_or_disassembly_emitted': False, 'original_code_executed': False,
            'credentials_or_account_files_read': False, 'network_contacted': False,
            'runtime_or_nand_modified': False, 'retail_cas_call_path_verified': False,
            'retail_attribute_schema_verified': False, 'source_revision_exact_retail_match_verified': False,
            'account_or_entitlement_success_enabled': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', required=True, type=Path)
    parser.add_argument('--browser-container', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.main, args.browser_container, args.source_root), indent=2))


if __name__ == '__main__':
    main()
