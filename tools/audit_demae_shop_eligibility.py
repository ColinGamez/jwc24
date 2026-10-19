"""Audit cached directory capabilities without forging native shop fields."""
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_shop_validation import assess_directory_record
from tools.asset_publication import atomic_write


def main():
    root = Path(__file__).resolve().parents[1] / 'private/demae/hotpepper'
    reasons = Counter()
    checked = complete = 0
    for path in root.glob('JP-*-catalog.json'):
        for row in json.loads(path.read_text(encoding='utf-8'))['restaurants']:
            report = assess_directory_record(row)
            checked += 1
            complete += report['producer_fields_complete']
            reasons.update(report['reasons'])
    report = {'listings_checked': checked, 'producer_fields_complete': complete,
              'missing_or_invalid_counts': dict(reasons), 'native_verified': False,
              'ordering_verified': False}
    atomic_write(root / 'shop-eligibility-audit.json', json.dumps(report, indent=2).encode())
    print(json.dumps(report))


if __name__ == '__main__':
    main()
