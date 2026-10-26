"""Compatibility entry point for the packaged independent HBNJ payloads validator."""
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.hbnj_validation.payloads import EXPECTED_GENRE_NAMES, u16, u32, parse_hdpk, read_text, main


if __name__ == '__main__':
    raise SystemExit(main())
