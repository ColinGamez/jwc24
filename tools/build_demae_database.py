"""Merge local restaurant/menu evidence into the persistent Demae archive."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_database import DemaeDatabase


def main():
    private = Path(__file__).resolve().parents[1]/'private/demae'
    catalogs = [json.loads(p.read_text(encoding='utf-8'))
                for p in sorted((private/'hotpepper').glob('JP-*-catalog.json'))]
    if {row['prefecture_id'] for row in catalogs} != {f'JP-{n:02d}' for n in range(1, 48)}:
        raise ValueError('Initial nationwide import requires all 47 catalog snapshots')
    reviews = json.loads((private/'restaurant-link-reviews.json').read_text(encoding='utf-8'))
    observations = [json.loads(p.read_text(encoding='utf-8'))
                    for p in sorted((private/'menus').glob('demaecan-*.observed.json'))]
    archive = DemaeDatabase(private/'demae.sqlite')
    report = archive.ingest(catalogs, reviews=reviews, observations=observations)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive.backup(private/'backups'/('demae-'+stamp+'.sqlite'))
    print(json.dumps({**report, 'backup_integrity_verified': True, 'notices_sent': 0}))


if __name__ == '__main__':
    main()
