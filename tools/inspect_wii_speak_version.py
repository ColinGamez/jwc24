"""Inspect an explicit private HCFJ VF record or opaque capture; metadata only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.wii_speak_version import (CAPTURE_BYTES, VERSION_DATA_BYTES,
                                    WiiSpeakVersionError,
                                    inspect_version_capture, inspect_version_data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--decoded-vf', type=Path)
    group.add_argument('--capture', type=Path)
    args = parser.parse_args(argv)
    path, maximum = ((args.decoded_vf, VERSION_DATA_BYTES) if args.decoded_vf
                     else (args.capture, CAPTURE_BYTES))
    try:
        with path.open('rb') as stream:
            data = stream.read(maximum + 1)
        result = (inspect_version_data(data).metadata() if args.decoded_vf
                  else inspect_version_capture(data))
    except (OSError, WiiSpeakVersionError):
        print('Explicit Wii Speak input could not be inspected', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
