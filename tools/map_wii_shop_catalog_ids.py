"""Enrich a private catalog from workbook A:D without exporting key columns."""
import argparse
import json
from pathlib import Path

from jwc24.wii_shop_catalog_ids import enrich, read_metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path)
    parser.add_argument('metadata_workbook', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    private = (Path(__file__).resolve().parents[1]/'private').resolve()
    output = args.output.resolve()
    if not output.is_relative_to(private):
        parser.error('Enriched catalog must remain under private/')
    if args.catalog.stat().st_size > 32*1024*1024:
        parser.error('Catalog exceeds import bound')
    report = json.loads(args.catalog.read_text(encoding='utf-8'))
    rows, evidence = read_metadata(args.metadata_workbook)
    report['records'] = enrich(report['records'], rows, evidence)
    report['title_metadata_source'] = evidence
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({'metadata_rows': len(rows), 'mapped_records': sum(r['title_id'] is not None for r in report['records']),
                      'mapped_japan_candidates': sum(r['title_id'] is not None and r['japan_browse_candidate'] for r in report['records']),
                      'tmd_verified': 0, 'install_supported': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
