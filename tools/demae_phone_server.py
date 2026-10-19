"""LAN phone handoff to Demae-can with explicit user-confirmed Wii notices."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_handoff import HandoffStore
from jwc24.mail import MailStore
from jwc24.demae_mail_queue import SharedMailQueue
from jwc24.demae_database import DemaeDatabase


def create_server(host, port, handoffs, mail):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Bearer tokens must never appear in request logs.

        def reply(self, status, body):
            data = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def token(self):
            url = urlsplit(self.path)
            parts = url.path.split('/')
            if url.query or len(parts) != 3 or parts[1] != 'h':
                raise ValueError('Unsupported handoff path')
            return parts[2]

        def do_GET(self):
            if self.path == '/health':
                return self.reply(200, 'JWC24 Demae phone handoff ready')
            url = urlsplit(self.path)
            if url.path.startswith('/p/') and not url.query:
                try:
                    token = handoffs.open_entry(url.path[3:])
                except ValueError:
                    return self.reply(404, 'This phone entry is unavailable.')
                self.send_response(303)
                self.send_header('Location', '/h/' + token)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            try:
                token = self.token()
                status = handoffs.status(token)
            except ValueError:
                return self.reply(404, 'This handoff is unavailable or expired.')
            if status['confirmed']:
                description = ('Your Wii notice is queued.' if status['notice_queued'] else
                               'Your confirmation is saved. Wii mail is pending; retry below.')
                button = 'Retry Wii notice' if not status['notice_queued'] else 'Confirmation saved'
            else:
                description = 'Complete checkout on Demae-can, then return here and confirm.'
                button = 'I placed my order / 注文しました'
            restaurant = status['restaurant']
            restaurant_text = (f'<p>Selected restaurant: <strong>{escape(restaurant["name"])}</strong></p>'
                               if restaurant else '')
            provider_url = escape(status['provider_url'], quote=True)
            plan = status.get('basket_plan')
            basket_text = ''
            if plan:
                lines = ''.join(f'<li>{escape(line["name"])} × {line["quantity"]} '
                                f'— ¥{line["listed_line_price_yen"]:,}</li>' for line in plan['lines'])
                basket_text = (f'<h2>Your item list</h2><ul>{lines}</ul>'
                    f'<p>Listed item subtotal: ¥{plan["listed_items_subtotal_yen"]:,}</p>'
                    '<p>Select these items again on Demae-can. Confirm options, delivery fees and final prices there.</p>')
            guidance = ('Check your delivery address and this branch on Demae-can, then choose your items there.'
                        if restaurant else 'Choose your delivery address, restaurant and items on Demae-can.')
            self.reply(200, f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Demae phone checkout</title>
<style>body{{font:18px system-ui;max-width:480px;margin:40px auto;padding:20px;background:#fff8ed;color:#332718}}a,button{{display:block;padding:16px;margin:20px 0;background:#ffb52c;color:#231a0e;border:0;border-radius:12px;font:inherit;text-align:center}}p{{line-height:1.5}}</style>
<h1>Finish your order on your phone</h1><p>{description}</p>
{restaurant_text}
{basket_text}
<a href="{provider_url}" target="_blank" rel="noopener noreferrer">Open Demae-can</a>
<p>{guidance} This handoff does not transfer a Wii basket or place an order.</p>
<form method="post" action="/h/{token}"><button>{button}</button></form>
<p>Confirm only after placing your order. The Wii notice records your confirmation; Demae-can supplies the official receipt and delivery status.</p></html>''')

        def do_POST(self):
            self.close_connection = True
            try:
                token = self.token()
                origin = self.headers.get('Origin')
                if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                    return self.reply(403, 'Confirmation must come from this handoff page.')
                if self.headers.get('Transfer-Encoding') or int(self.headers.get('Content-Length', '0')) != 0:
                    return self.reply(400, 'Unexpected confirmation payload.')
                handoffs.confirm(token)
            except ValueError:
                return self.reply(404, 'This handoff is unavailable or expired.')
            try:
                handoffs.dispatch_notices(mail)
            except (ValueError, OSError):
                return self.reply(503, 'Confirmation saved. Wii mail is pending. Return to this page and retry.')
            self.send_response(303)
            self.send_header('Location', '/h/' + token)
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', '0')
            self.end_headers()

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=18086)
    parser.add_argument('--mail-data-dir', type=Path, required=True)
    parser.add_argument('--restaurant-database', type=Path,
                        default=Path(__file__).resolve().parents[1]/'private/demae/demae.sqlite',
                        help='Archive containing reviewed closure notices for explicit followers')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'private/demae/handoff.sqlite'
    handoffs = HandoffStore(root)
    mail = SharedMailQueue(args.mail_data_dir)
    archive = DemaeDatabase(args.restaurant_database) if args.restaurant_database.is_file() else None
    stop = threading.Event()
    def retry_notices():
        while not stop.is_set():
            try:
                handoffs.dispatch_notices(mail)
            except (ValueError, OSError):
                pass  # Keep durable outbox entries; no account/token logging.
            if archive is not None:
                try:
                    archive.dispatch_closure_notices(mail)
                except (ValueError, OSError):
                    pass  # Reviewed closure notices remain queued for retry.
            stop.wait(5)
    worker = threading.Thread(target=retry_notices, daemon=True)
    with create_server(args.host, args.port, handoffs, mail) as server:
        worker.start()
        print('Demae phone handoff server ready; requests and bearer tokens are not logged', flush=True)
        try:
            server.serve_forever()
        finally:
            stop.set()
            worker.join(timeout=6)


if __name__ == '__main__':
    main()
