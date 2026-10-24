"""Cache archived Shop page layouts and their artwork beneath private/.

No archived JavaScript is executed. Page bodies and original images are not
redistributed in Git. Source URLs and hashes accompany the local asset pack.
"""
import concurrent.futures
import argparse
from functools import partial
import hashlib
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ORIGIN = 'https://wiishopchannel.net'
PRIVATE = Path(__file__).resolve().parents[1]/'private'
ROOT = PRIVATE/'wii_shop/artwork-v2'


def fetch(path, root):
    url = ORIGIN+path
    with urlopen(Request(url, headers={'User-Agent': 'JWC24-asset-research/1'}), timeout=25) as response:
        if urlsplit(response.url).hostname != 'wiishopchannel.net':
            raise ValueError('Asset redirect left source archive')
        data = response.read(2*1024*1024+1)
    if len(data) > 2*1024*1024:
        raise ValueError('Archived resource exceeds bound')
    target = root/path.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return path, {'url': url, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT)
    root = parser.parse_args(argv).output.resolve()
    if root.exists() or not root.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Artwork pack already exists; refusing overwrite')
    pages = ['/oss/serv/'+name for name in ('W_03.html', 'B_01.html', 'B_27.html', 'B_04.html', 'B_05.html')]
    get = partial(fetch, root=root)
    manifest = dict(get(path) for path in pages)
    resources = {'/oss/oss/common/css/oss.css', '/oss/oss/common/css/error.css', '/oss/oss/common/css/B_05.css'}
    for path in pages:
        text = (root/path.lstrip('/')).read_text(encoding='utf-8', errors='replace')
        for value in re.findall(r'/oss/oss/[A-Za-z0-9_./-]+\.(?:png|gif|css)', text):
            resources.add(posixpath.normpath(value))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for path, row in pool.map(get, sorted(resources)):
            manifest[path] = row
    # CSS backgrounds are often expressed relative to their stylesheet.
    extras = set()
    for path in resources:
        if not path.endswith('.css'):
            continue
        text = (root/path.lstrip('/')).read_text(encoding='utf-8', errors='replace')
        for value in re.findall(r'url\([\"\x27]?([^\"\x27)]+)', text):
            resolved = urlsplit(urljoin(ORIGIN+path, value)).path
            if resolved.endswith(('.png', '.gif')) and resolved not in manifest:
                extras.add(resolved)
    for path in sorted(extras):
        key, row = get(path)
        manifest[key] = row
    (root/'manifest.json').write_text(json.dumps({'source': ORIGIN, 'files': manifest}, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'archived_resources_cached': len(manifest), 'page_layouts': len(pages),
                      'original_resources_private': True}))


if __name__ == '__main__':
    main()
