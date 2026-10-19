"""Create a private phone handoff QR, without placing orders or sending mail."""
import argparse
import io
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_handoff import HandoffStore
from tools.asset_publication import publish_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wii-id', required=True)
    parser.add_argument('--phone-base-url', required=True, help='Phone-reachable server origin, e.g. http://LAN-IP:18086')
    parser.add_argument('--stable-entry', action='store_true', help='Generate a reusable native-screen QR; scans create expiring sessions')
    args = parser.parse_args()
    origin = urlsplit(args.phone_base_url)
    if origin.scheme not in ('http', 'https') or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('', '/') or origin.hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
        parser.error('Supply a phone-reachable HTTP(S) origin without credentials or path')
    root = Path(__file__).resolve().parents[1] / 'private/demae'
    store = HandoffStore(root / 'handoff.sqlite')
    token = store.create_entry(args.wii_id) if args.stable_entry else store.create(args.wii_id)
    import qrcode
    output = root / 'phone-handoff.png'
    route = '/p/' if args.stable_entry else '/h/'
    url = args.phone_base_url.rstrip('/') + route + token
    png = io.BytesIO()
    qrcode.make(url).save(png, format='PNG')
    assets = [(output, png.getvalue())]
    if args.stable_entry:
        assets.append((root / 'phone-entry-url.txt', url.encode('utf-8')))
    publish_assets(assets)
    print('Created private/demae/phone-handoff.png; no order or mail sent')


if __name__ == '__main__':
    main()
