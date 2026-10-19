"""Fetch the official nationwide UTF-8 postal directory and publish a private DB."""
from datetime import datetime, timezone
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.japan_post import DOWNLOAD_URL, SOURCE_URL, MAX_CSV_BYTES, build_database
from tools.asset_publication import atomic_write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Already downloaded official ZIP; no network request')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1] / 'private/demae/postal'
    root.mkdir(parents=True, exist_ok=True)
    try:
        if args.archive:
            with args.archive.open('rb') as source:
                archive = source.read(8 * 1024 * 1024 + 1)
        else:
            with urlopen(Request(DOWNLOAD_URL, headers={'User-Agent': 'JWC24-postal-import/1.0'}), timeout=45) as response:
                archive = response.read(8 * 1024 * 1024 + 1)
        if len(archive) > 8 * 1024 * 1024:
            raise ValueError('Postal archive exceeds limit')
        with ZipFile(io.BytesIO(archive)) as source:
            members = source.infolist()
            if len(members) != 1 or members[0].filename.lower() != 'utf_ken_all.csv' or members[0].file_size > MAX_CSV_BYTES:
                raise ValueError('Unexpected postal archive contents')
            data = source.read(members[0])
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            database = Path(temporary) / 'postal.sqlite'
            summary = build_database(data, database)
            if summary['prefectures'] != 47 or summary['records'] < 100000:
                raise ValueError('Nationwide directory coverage is incomplete')
            atomic_write(root / 'postal.sqlite', database.read_bytes())
        atomic_write(root / 'source.zip', archive)
        metadata = {**summary, 'source_url': SOURCE_URL, 'download_url': DOWNLOAD_URL,
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                    'source_sha256': hashlib.sha256(archive).hexdigest(),
                    'scope': 'public address directory; no personal addresses or delivery eligibility'}
        atomic_write(root / 'metadata.json', (json.dumps(metadata, indent=2)+'\n').encode())
    except Exception:
        print('Postal import failed; existing database retained if publication was not reached', file=sys.stderr)
        return 1
    print(f'Imported {summary["records"]} postal records covering {summary["prefectures"]} prefectures')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
