"""Inspect private Global Voices source captures offline; emit counts, not stories."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.globalvoices_news import (MAX_BYTES, CaptureReceipt, GlobalVoicesError,
                                     parse_article, parse_feed)


def _pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise GlobalVoicesError("duplicate receipt field")
        output[key] = value
    return output


def load_capture(directory: Path, name: str) -> tuple[bytes, CaptureReceipt]:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name) is None:
        raise GlobalVoicesError("invalid local capture name")
    with (directory / (name + ".body")).open("rb") as source:
        body = source.read(MAX_BYTES + 1)
    with (directory / (name + ".json")).open("rb") as source:
        metadata = source.read(65537)
    if len(metadata) > 65536:
        raise GlobalVoicesError("oversized receipt")
    def invalid_constant(value):
        raise GlobalVoicesError("invalid JSON constant")
    raw = json.loads(metadata.decode("utf-8"), object_pairs_hook=_pairs,
                     parse_constant=invalid_constant)
    if not isinstance(raw, dict) or raw.get("complete") is not True or raw.get("failure") is not None:
        raise GlobalVoicesError("incomplete capture")
    receipt = CaptureReceipt(raw["url"], raw["body_sha256"], raw["body_bytes"],
                             datetime.fromisoformat(raw["retrieved_start_utc"]),
                             datetime.fromisoformat(raw["retrieved_end_utc"]), raw["status"])
    receipt.verify(body)
    return body, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--article-name", required=True)
    parser.add_argument("--guid", required=True)
    parser.add_argument("--checked-utc", required=True, help="Explicit timezone-qualified age-check instant")
    args = parser.parse_args(argv)
    try:
        feed_body, feed_receipt = load_capture(args.capture_dir, "feed")
        feed = parse_feed(feed_body, feed_receipt)
        body, receipt = load_capture(args.capture_dir, args.article_name)
        policies = tuple(load_capture(args.capture_dir, name) for name in
                         ("japanese-policy", "republishing-guidelines", "read-share"))
        candidate = parse_article(feed, guid=args.guid, body=body, receipt=receipt,
                                  policy_documents=policies)
        result = candidate.metadata(checked_utc=datetime.fromisoformat(args.checked_utc.replace("Z", "+00:00")))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        print(json.dumps({"source_candidate_inspected": False,
                          "error": "Local source captures failed bounded inspection"}))
        return 1
    print(json.dumps(dict(source_candidate_inspected=True, **result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
