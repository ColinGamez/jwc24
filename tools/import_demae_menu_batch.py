"""Validate a reviewed branch/menu batch and retain it in the Demae archive."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_database import DemaeDatabase
from tools.asset_publication import atomic_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviews', type=Path, required=True)
    parser.add_argument('--observation', type=Path, action='append', required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1]/'private/demae'
    if any(not p.resolve().is_relative_to(private.resolve()) for p in [args.reviews, *args.observation]):
        parser.error('Reviewed source evidence must remain beneath private/demae')
    if not (private/'demae.sqlite').is_file():
        parser.error('Build the persistent restaurant archive first')
    reviews = json.loads(args.reviews.read_text(encoding='utf-8'))
    observations = [json.loads(p.read_text(encoding='utf-8')) for p in args.observation]
    archive = DemaeDatabase(private/'demae.sqlite')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive.backup(private/'backups'/('demae-before-menu-'+stamp+'.sqlite'))
    report = archive.ingest_reviewed_menus(reviews, observations)
    # Keep the legacy source-review index in sync with the authoritative
    # archive, so subsequent source refreshes do not present an older index.
    index = archive.menu_directory().reviews
    atomic_write(private/'restaurant-link-reviews.json',
                 json.dumps([index[key] for key in sorted(index)], ensure_ascii=False, indent=2).encode('utf-8'))
    archive.backup(private/'backups'/('demae-after-menu-'+stamp+'.sqlite'))
    print(json.dumps({'validated_branches': len(observations), **report,
                      'orders_submitted': 0, 'notices_sent': 0}))


if __name__ == '__main__':
    main()
