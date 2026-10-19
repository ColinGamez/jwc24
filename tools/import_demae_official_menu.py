"""Import a privately captured official menu index; does not serve or order it."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_menu_source import parse_official_menu
from tools.asset_publication import publish_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error('Source-derived menu data must remain private')
    snapshot = args.source.read_bytes()
    result = parse_official_menu(snapshot)
    publish_assets([(args.output, json.dumps(result, ensure_ascii=False, indent=2).encode('utf8'))],
                   source_check=(args.source, snapshot))
    print(f"Imported {len(result['products'])} official product records; no checkout quotes or native routes enabled")


if __name__ == '__main__':
    main()
