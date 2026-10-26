"""Build one private native News snapshot from explicit records; no feed acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.news import NewsFormatError, inspect_news
from jwc24.news_records import MAX_SPEC_BYTES, encode_news_records


def _document(data):
    if type(data) is not bytes or not 0 < len(data) <= MAX_SPEC_BYTES:
        raise NewsFormatError('News record specification exceeds local input bounds')

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise NewsFormatError('News record JSON repeats a field')
            result[key] = value
        return result

    def constant(_value):
        raise NewsFormatError('News record JSON contains a nonstandard number')

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise NewsFormatError('News record JSON is invalid or ambiguous') from None


def write_record_build(specification: bytes, output_directory: Path) -> dict:
    """Publish one new immutable directory containing raw bytes plus provenance.

    Does not replace an existing build. A failed encode/write leaves the final
    directory absent. The manifest records caller references, not an independent
    determination of provenance or reuse permission. No generation is activated.
    """
    document = _document(specification)
    raw = encode_news_records(document)
    inspection = inspect_news(raw)
    output = Path(output_directory).resolve()
    if output.exists():
        raise NewsFormatError('News record build output already exists')
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.news-records-', dir=parent)).resolve()
    if staging.parent != parent:
        raise NewsFormatError('News record staging directory escaped its explicit parent')
    manifest = {
        'schema_version': 1, 'payload_filename': 'news.raw', 'payload_bytes': len(raw),
        'payload_sha256': hashlib.sha256(raw).hexdigest(),
        'specification_sha256': hashlib.sha256(specification).hexdigest(),
        'evidence_ref': document['evidence_ref'], 'rights_ref': document['rights_ref'],
        'provider_provenance_or_rights_independently_verified': False,
        'native_delivery_or_rendering_verified': False,
    }
    try:
        for name, contents in (
            ('news.raw', raw),
            ('manifest.json', json.dumps(manifest, ensure_ascii=False).encode('utf-8')),
        ):
            with (staging / name).open('xb') as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
        # Same parent/volume; the complete directory appears as one operation.
        # Nonempty existing output directories cannot be silently replaced.
        if output.exists():
            raise NewsFormatError('News record build output appeared during staging')
        os.rename(staging, output)
    finally:
        if staging.exists():
            resolved = staging.resolve()
            if resolved.parent != parent or not resolved.name.startswith('.news-records-'):
                raise NewsFormatError('News record staging cleanup escaped its explicit parent')
            shutil.rmtree(resolved)
    return dict(inspection.metadata(), record_build_written=True,
                evidence_and_rights_references_recorded=True,
                provider_provenance_or_rights_independently_verified=False,
                signed_or_activated=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='new private build directory; existing builds are not replaced')
    args = parser.parse_args(argv)
    try:
        with args.input.open('rb') as stream:
            specification = stream.read(MAX_SPEC_BYTES + 1)
        report = write_record_build(specification, args.output_dir)
    except (OSError, NewsFormatError):
        print('News record build failed: unavailable input, invalid records or output conflict',
              file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
