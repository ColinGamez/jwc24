"""Write all 47 catalog regions, optionally binding a provider area master."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_regions import prefectures, match_provider_areas
from tools.asset_publication import atomic_write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider-master', type=Path)
    parser.add_argument('--output', type=Path, default=Path('private/demae/catalog/regions.json'))
    args = parser.parse_args(argv)
    private = (Path(__file__).resolve().parents[1] / 'private').resolve()
    output = args.output.resolve()
    if not output.is_relative_to(private):
        parser.error('Output must be inside the project private directory')
    try:
        regions = prefectures()
        if args.provider_master:
            master = json.loads(args.provider_master.read_text(encoding='utf-8'))
            regions = match_provider_areas(master['results']['large_area'])
        payload = {'schema_version': 1, 'regions': regions,
                   'native_coverage_verified': False, 'ordering_supported': False}
        output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(output, (json.dumps(payload, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    except (OSError, ValueError, KeyError, TypeError):
        print('Region manifest failed; previous cache retained', file=sys.stderr)
        return 1
    print(f'Prepared {len(regions)} prefectures; restaurant imports tracked separately')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
