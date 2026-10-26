#!/usr/bin/env python3
"""Inspect local Body Check plaintext header; omit health records and key data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.body_check import BodyCheckFormatError, MAX_DATASET_BYTES, inspect_dataset


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path, help='already decrypted plaintext dataset')
    args = parser.parse_args(argv)
    try:
        with args.dataset.open('rb') as stream:
            data = stream.read(MAX_DATASET_BYTES + 1)
        result = inspect_dataset(data)
    except (OSError, BodyCheckFormatError):
        print('Cannot inspect dataset: input unavailable or unsupported plaintext header', file=sys.stderr)
        return 1
    print(json.dumps(result.metadata(), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
