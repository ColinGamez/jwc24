"""Compatibility entry point for the packaged independent HBNJ areas validator."""
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.hbnj_validation.areas import (
    LZ10_MAX_INPUT, VFF_CAPACITY, literal_lz10_size, main, parse_hdpk, read_text, u32,
)


if __name__ == '__main__':
    raise SystemExit(main())
