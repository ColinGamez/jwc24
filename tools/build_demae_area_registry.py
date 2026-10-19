"""Assign persistent replacement-service IDs without changing native saves."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_area_registry import area_identity, assign_area_codes
from tools.asset_publication import atomic_write


def main():
    root = Path(__file__).resolve().parents[1] / 'private/demae/postal'
    source = json.loads((root / 'town-candidates.json').read_text(encoding='utf-8'))
    path = root / 'replacement-area-registry.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    identities = [area_identity(row['municipality'], row['postal'], row['name'])
                  for row in source['candidates'].values()]
    registry = assign_area_codes(previous, identities)
    atomic_write(path, json.dumps(registry, ensure_ascii=False).encode('utf-8'))
    print(f'Replacement area IDs: {len(registry)}; native geographic acceptance unverified; no saves changed')


if __name__ == '__main__':
    main()
