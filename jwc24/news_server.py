"""Binary-only HTTP adapter for prepared News subtask files; no replacement UI."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import time

from .news_publication import NewsPublication, NewsPublicationError


class NewsApplication:
    """Keep one coherent verified generation in memory for a whole test session.

    Recreate the adapter from load_news_publication after publishing a refresh.
    Requests do not touch input files, device state, providers or trust keys.
    """
    def __init__(self, publication, *, clock=time.time):
        if (type(publication) is not NewsPublication or not publication.is_prepared()
                or not callable(clock)):
            raise NewsPublicationError('News HTTP serving needs an explicitly prepared publication')
        self.publication, self.clock = publication, clock

    def get(self, target):
        if not isinstance(target, str) or len(target) > 512:
            return 400, 'application/octet-stream', b''
        publication = self.publication
        if type(publication) is not NewsPublication or not publication.is_prepared():
            return 503, 'application/octet-stream', b''
        prefix = publication.route_prefix + '/news.bin.'
        if not target.startswith(prefix) or not re.fullmatch(r'(?:0[0-9]|1[0-9]|2[0-3])', target[len(prefix):]):
            return 404, 'application/octet-stream', b''
        try:
            current = publication.is_current(int(self.clock()))
        except (ValueError, TypeError, OverflowError):
            current = False
        if not current:
            return 503, 'application/octet-stream', b''
        return 200, 'application/octet-stream', publication.payloads[int(target[len(prefix):])]


def create_news_server(address, publication, *, clock=time.time):
    """Create an explicit listener; this function never edits a task/profile."""
    application = NewsApplication(publication, clock=clock)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            status, mime, body = application.get(self.path)
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *args):
            pass  # Do not log request selectors or private data.

    server = ThreadingHTTPServer(address, Handler)
    server.daemon_threads = True
    return server
