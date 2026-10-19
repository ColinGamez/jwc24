"""Inspect a local processed Demae postal file without printing addresses."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae import MAX_INSPECTION_BYTES, PostalFormatError, inspect_postal_records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('processed_file', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.processed_file.open('rb') as source:
            data = source.read(MAX_INSPECTION_BYTES + 1)
        records = inspect_postal_records(data)
    except (OSError, PostalFormatError) as error:
        print(f'Cannot inspect postal data: {error}', file=sys.stderr)
        return 1
    print(json.dumps({'byte_length': len(data), 'record_count': len(records),
                      'scope': 'processed record framing only; wire format and authenticity not checked'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
