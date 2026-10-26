"""Compatibility entry point for the packaged independent HBNJ guide validator."""
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.hbnj_validation.guide import fail, main


if __name__ == '__main__':
    raise SystemExit(main())
