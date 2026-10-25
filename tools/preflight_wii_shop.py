"""Validate all current Shop preview pages and display dependencies offline."""
import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys

from jwc24.wii_shop_preflight import PreviewPacks, load_preview_application, preflight_preview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in fields(PreviewPacks):
        parser.add_argument('--'+field.name.replace('_', '-'), type=Path, default=field.default)
    parser.add_argument('--progress', action='store_true', help='Print route counts to stderr while checking')
    args = parser.parse_args(argv)

    def progress(checked, total):
        print(json.dumps({'html_routes_checked': checked, 'html_routes_total': total}), file=sys.stderr, flush=True)

    try:
        packs = PreviewPacks(**{field.name: getattr(args, field.name) for field in fields(PreviewPacks)})
        result = preflight_preview(load_preview_application(packs), progress=progress if args.progress else None)
    except (ValueError, KeyError, TypeError, UnicodeError, OSError):
        # Private pack paths, selectors and source content are not public reports.
        print(json.dumps({'schema_version': 1, 'offline_preview_passed': False,
                          'error': 'Shop pack or offline route validation failed'}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result['offline_preview_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
