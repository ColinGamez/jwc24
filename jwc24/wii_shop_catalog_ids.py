"""Map catalog filenames to source-reported IDs, never to verified entitlements."""
from collections import defaultdict
import hashlib
from io import BytesIO
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

SOURCE = 'https://repo.mariocube.com/WADs/_WiiWare%2C%20VC%2C%20DLC%2C%20Channels%20%26%20IOS/WAD%20Info.xlsx'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_metadata(path):
    """Read only catalog columns A:D from the database sheet; emit no key columns."""
    path = Path(path)
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Workbook exceeds import bound')
    data = path.read_bytes()
    with ZipFile(BytesIO(data)) as archive:
        def xml(name):
            info = archive.getinfo(name)
            if info.file_size > 8*1024*1024:
                raise ValueError('Workbook XML exceeds import bound')
            payload = archive.read(name)
            if b'<!DOCTYPE' in payload.upper():
                raise ValueError('Workbook XML declarations unsupported')
            return ET.fromstring(payload)
        workbook = xml('xl/workbook.xml')
        sheet = next((s for s in workbook.findall('s:sheets/s:sheet', NS)
                      if s.get('name') == 'database'), None)
        if sheet is None:
            raise ValueError('Metadata database sheet missing')
        relation = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        targets = {r.get('Id'): r.get('Target') for r in xml('xl/_rels/workbook.xml.rels')}
        target = targets.get(relation, '')
        member = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        if not re.fullmatch(r'xl/worksheets/[A-Za-z0-9_.-]+\.xml', member):
            raise ValueError('Unexpected metadata worksheet target')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(si.itertext()) for si in xml('xl/sharedStrings.xml').findall('s:si', NS)]
        rows, header_seen = [], False
        for row in xml(member).findall('s:sheetData/s:row', NS):
            number = int(row.get('r', '0'))
            if not 1 <= number <= 50000:
                raise ValueError('Metadata row outside import bound')
            values = {}
            for cell in row.findall('s:c', NS):
                match = re.fullmatch(r'([A-D])[0-9]+', cell.get('r', ''))
                if not match:
                    continue
                if cell.find('s:f', NS) is not None:
                    raise ValueError('Catalog metadata formulas unsupported')
                value = cell.findtext('s:v', default='', namespaces=NS)
                if cell.get('t') == 's':
                    value = strings[int(value)]
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(cell.find('s:is', NS).itertext())
                values[match[1]] = value
            ordered = [values.get(col, '') for col in 'ABCD']
            if number == 1:
                if ordered != ['Filename', 'TitleID', 'Version', 'Region']:
                    raise ValueError('Unexpected catalog metadata columns')
                header_seen = True
            elif ordered[0]:
                rows.append({'row': number, 'filename': ordered[0], 'title_id': ordered[1],
                             'version': ordered[2], 'region': ordered[3]})
        if not header_seen:
            raise ValueError('Catalog metadata header missing')
    return rows, {'source_url': SOURCE, 'sha256': hashlib.sha256(data).hexdigest(),
                  'sheet': 'database', 'columns': 'A:D', 'rows': len(rows)}


def enrich(records, metadata, evidence):
    by_name = defaultdict(list)
    for row in metadata:
        by_name[row['filename']].append(row)
    result = []
    for original in records:
        record = dict(original)
        record.update(title_id=None, title_version=None, title_id_status='unresolved',
                      title_id_evidence=None, tmd_verified=False, install_supported=False)
        matches = by_name.get(record['filename'], [])
        reason = 'filename_not_found'
        if len(matches) > 1:
            reason = 'ambiguous_filename'
        elif matches:
            row = matches[0]
            identifier, version = str(row['title_id']), str(row['version'])
            if not re.fullmatch(r'[0-9A-Fa-f]{16}', identifier) or not re.fullmatch(r'[0-9]{1,5}', version) or int(version) > 65535:
                reason = 'invalid_metadata'
            elif row['region'] != record['region_label']:
                reason = 'region_mismatch'
            else:
                record.update(title_id=identifier.upper(), title_version=int(version),
                              title_id_status='source_metadata',
                              title_id_evidence=dict(evidence, row=row['row']))
                reason = None
        record['title_id_unresolved_reason'] = reason
        result.append(record)
    return result
