"""Capture one explicitly selected JMA office/station; no native publication."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.jma_capture import capture_bundle
from jwc24.jma_weather import JMAError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--office", required=True, help="explicit six-digit JMA forecast office ID")
    parser.add_argument("--station", required=True, help="explicit five-digit JMA observation station ID")
    parser.add_argument("--output", required=True, type=Path, help="new evidence directory (must not already exist)")
    args = parser.parse_args()
    try:
        result = capture_bundle(args.output, office_code=args.office, station_code=args.station)
    except (JMAError, OSError):
        print(json.dumps({"complete": False, "failure": "invalid_input_or_output_path"}))
        return 2
    # Aggregate status only. Exact data, source URLs and headers stay in the bundle.
    print(json.dumps({"complete": result["complete"], "resources": len(result["resources"]),
                      "failure": result["failure"], "native_payload_written": False,
                      "provider_activated": False}))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
