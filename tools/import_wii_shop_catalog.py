"""Import MarioCube directory metadata only; never follows WAD download links."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from jwc24.wii_shop_catalog import BASE, BUCKETS, parse_listing


class ListingRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if unquote(newurl) != unquote(req.full_url):
            raise ValueError('Directory redirect changed the requested resource')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(bucket):
    if bucket not in BUCKETS:
        raise ValueError('Only catalog listing buckets may be fetched')
    url = BASE+bucket+'/'
    opener = build_opener(ListingRedirect())
    with opener.open(Request(url, headers={'User-Agent': 'JWC24-catalog-research/1.0'}), timeout=25) as response:
        if unquote(response.geturl()) != unquote(url) or response.headers.get_content_type() != 'text/html':
            raise ValueError('Unexpected directory response')
        data = response.read(2*1024*1024+1)
    if len(data) > 2*1024*1024:
        raise ValueError('Directory exceeds import limit')
    return {'bucket': bucket, 'url': url, 'sha256': hashlib.sha256(data).hexdigest(),
            'records': parse_listing(data.decode('utf-8'), bucket)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--buckets', nargs='+', choices=BUCKETS, default=BUCKETS)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    private = (Path(__file__).resolve().parents[1]/'private').resolve()
    if not output.is_relative_to(private):
        parser.error('Catalog output must remain under private/')
    buckets = tuple(dict.fromkeys(args.buckets))
    with ThreadPoolExecutor(max_workers=3) as pool:
        pages = list(pool.map(fetch, buckets))
    records = {record['catalog_id']: record for page in pages for record in page['records']}
    report = {'schema_version': 1, 'source': 'MarioCube',
              'fetched_at': datetime.now(timezone.utc).isoformat(),
              'listing_pages': [{k: v for k, v in page.items() if k != 'records'} for page in pages],
              'records': list(records.values()), 'metadata_only': True,
              'binary_downloads': 0, 'native_catalog_integrated': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({'pages': len(pages), 'records': len(records),
                      'japan_browse_candidates': sum(r['japan_browse_candidate'] for r in records.values()),
                      'binary_downloads': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
