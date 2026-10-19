"""Audit nationwide town candidates without truncating labels or filling saves."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.japan_post import areas
from jwc24.demae_towns import town_candidates
from tools.asset_publication import atomic_write


def main():
    root = Path(__file__).resolve().parents[1] / 'private/demae'
    database = root / 'postal/postal.sqlite'
    totals = {'municipalities': 0, 'town_candidates': 0, 'selectable_labels': 0,
              'municipality_defaults': 0, 'oversized_labels': 0, 'unrepresentable_labels': 0}
    registry = {}
    for prefecture in areas(database):
        for city in areas(database, prefecture['id']):
            totals['municipalities'] += 1
            for row in town_candidates(database, city['id']):
                code = row['experimental_code']
                if code in registry:
                    raise ValueError('Nationwide experimental identifier collision')
                registry[code] = row
                totals['town_candidates'] += 1
                totals['selectable_labels'] += row['label_eligible']
                totals['municipality_defaults'] += row['review_reason'] == 'municipality_default'
                totals['oversized_labels'] += row['review_reason'] == 'label_exceeds_capacity'
                totals['unrepresentable_labels'] += row['review_reason'] == 'shift_jis_unrepresentable'
    totals['scope'] = 'offline town candidates; native codes and selection flow unverified'
    atomic_write(root / 'postal/town-candidates.json',
                 json.dumps({'summary': totals, 'candidates': registry}, ensure_ascii=False).encode('utf-8'))
    print(json.dumps(totals))


if __name__ == '__main__':
    main()
