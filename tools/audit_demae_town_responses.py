"""Validate every decimal town response offline; never alter native saves."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.japan_post import areas
from jwc24.demae_area_registry import AreaRegistry
from tools.build_demae_town_fixture import build_towns, NoDisplayableTowns
from tools.asset_publication import atomic_write


def main():
    root = Path(__file__).resolve().parents[1] / 'private/demae/postal'
    database = root / 'postal.sqlite'
    registry = AreaRegistry(json.loads((root / 'replacement-area-registry.json').read_text(encoding='utf-8')))
    summary = {'municipalities_checked': 0, 'responses_validated': 0, 'terminal_rows': 0,
               'excluded_candidates': 0, 'largest_response_bytes': 0,
               'no_displayable_towns': [], 'failures': [], 'native_verified': False}
    for prefecture in areas(database):
        for city in areas(database, prefecture['id']):
            summary['municipalities_checked'] += 1
            try:
                data, report = build_towns(database, city['id'], registry=registry)
                codes = [row.text for row in ET.fromstring(data).iter('areaCode')]
                if len(codes) != len(set(codes)):
                    raise ValueError('Duplicate terminal IDs')
                for code in codes:
                    resolved = registry.resolve(code)
                    if resolved is None or resolved['municipality'] != city['id']:
                        raise ValueError('Terminal ID resolves to wrong municipality')
                summary['responses_validated'] += 1
                summary['terminal_rows'] += report['row_count']
                summary['excluded_candidates'] += len(report['excluded'])
                summary['largest_response_bytes'] = max(summary['largest_response_bytes'], len(data))
            except NoDisplayableTowns:
                summary['no_displayable_towns'].append(city['id'])
            except ValueError:
                # Record public municipality IDs only, never request/save values.
                summary['failures'].append(city['id'])
    atomic_write(root / 'town-response-audit.json', (json.dumps(summary, indent=2)+'\n').encode())
    print(json.dumps(summary))
    return bool(summary['failures'])


if __name__ == '__main__':
    raise SystemExit(main())
