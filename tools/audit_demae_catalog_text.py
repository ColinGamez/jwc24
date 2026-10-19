"""Count cached text incompatibilities without altering text or printing names."""
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_text import inspect_native_text
from tools.asset_publication import atomic_write


def main():
    root = Path(__file__).resolve().parents[1] / 'private/demae/hotpepper'
    fields = {field: Counter() for field in ('name', 'catchphrase')}
    characters = Counter()
    for path in root.glob('JP-*-catalog.json'):
        for row in json.loads(path.read_text(encoding='utf-8'))['restaurants']:
            for field, counts in fields.items():
                value = row.get(field)
                if value is None:
                    counts['absent'] += 1
                    continue
                report = inspect_native_text(value)
                counts['checked'] += 1
                if not report['strict_shift_jis']:
                    counts['strict_incompatible'] += 1
                    counts['cp932_compatible'] += report['cp932']
                    counts['nfkc_candidate_compatible'] += report['nfkc_strict_shift_jis']
                    characters.update(report['unsupported_codepoints'])
                counts['xml_control_records'] += report['xml_controls']
    result = {'fields': {field: dict(counts) for field, counts in fields.items()},
              'unsupported_codepoint_record_counts': dict(characters),
              'source_text_modified': False, 'native_repertoire_verified': False}
    atomic_write(root / 'text-audit.json', json.dumps(result, indent=2).encode())
    print(json.dumps(result['fields']))


if __name__ == '__main__':
    main()
