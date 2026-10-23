"""Verify selected private Shop client sources and emit metadata only.

Does not compile recovered code, contact services or read device/account files.
Literal SOAP calls are leads, not a complete protocol or runtime call trace.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


EC = 'common/lib/ec/'
SELECTED = tuple(EC+name for name in (
    'ec_connect.cpp', 'ec_checkReg.cpp', 'ec_register.cpp', 'ec_chkDevStat.cpp',
    'ec_soap.cpp', 'ec_soap.h', 'ec_js.cpp', 'ec_listTitles.cpp',
    'ec_listTitleContents.cpp', 'ec_purchaseTitle.cpp', 'ec_getTitle.cpp',
    'ec_downloadContents.cpp', 'ec_syncTickets.cpp', 'ec_getTicketEnvelope.cpp',
    'ec_getPoints.cpp', 'ec_buyPoints.cpp', 'ec_giftTitle.cpp',
    'ec_acceptGiftTitle.cpp', 'ec_listContentSets.cpp', 'ec_listServiceItems.cpp'
)) + ('devroot/tools/bw/wiishopping.mk',)


def audit(root, *, selected=SELECTED):
    root = Path(root).resolve()
    manifest_path = root/'inventory.json'
    if manifest_path.stat().st_size > 5*1024*1024:
        raise ValueError('Source inventory exceeds audit bound')
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode('utf-8'))
    if not isinstance(manifest, list) or not all(isinstance(row, dict) for row in manifest):
        raise ValueError('Invalid source inventory')
    files, actions, dynamic, globals_, dependencies = [], [], [], [], []
    for relative in selected:
        path = (root/relative).resolve()
        if not path.is_relative_to(root) or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Selected source must stay within the supplied root')
        records = [r for r in manifest if isinstance(r.get('member'), str)
                   and r['member'].endswith('/'+relative)]
        if len(records) != 1:
            raise ValueError(f'Selected source needs one inventory record: {relative}')
        if path.stat().st_size > 2*1024*1024:
            raise ValueError(f'Selected source exceeds audit bound: {relative}')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if records[0].get('bytes') != len(data) or records[0].get('sha256') != digest:
            raise ValueError(f'Source differs from recorded inventory: {relative}')
        files.append({'path': relative, 'bytes': len(data), 'sha256': digest})
        text = data.decode('latin-1')
        for match in re.finditer(r'\bSoap\s+\w+\s*\(\s*env\s*,\s*("[A-Za-z0-9]+"|\w+)\s*,\s*Soap::(ias|ecs|cas)', text):
            value, service = match.groups()
            record = {'file': relative, 'line': text.count('\n', 0, match.start())+1,
                      'service': service}
            if value.startswith('"'):
                actions.append(dict(record, action=value.strip('"')))
            else:
                dynamic.append(record)
        if relative == EC+'ec_js.cpp':
            match = re.search(r'const char\* globalNames\[\]\s*=\s*\{(.*?)\};', text, re.S)
            if match:
                globals_ = re.findall(r'"([A-Za-z][A-Za-z0-9]+)"', match[1])
        if relative.endswith('/wiishopping.mk'):
            dependencies = [{'variable': m[1], 'filename': m[2]} for m in re.finditer(
                r'^(WSHOP_FILE|LNDIR_FILE|OPERA_UPDATE)\s*=\s*([A-Za-z0-9_.-]+)', text, re.M)]
    return {'schema_version': 1, 'inventory_match_verified': True,
            'inventory_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'verified_files': files, 'literal_soap_calls': actions,
            'dynamic_soap_call_sites': dynamic, 'javascript_globals': globals_,
            'build_package_references': dependencies,
            'source_review_only': True, 'complete_protocol_verified': False,
            'retail_channel_match_verified': False, 'server_implementation_verified': False,
            'referenced_packages_presence_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.source_root), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
