"""Child-process probe: only the installed package and explicit synthetic files."""
from __future__ import annotations

import contextlib
import hashlib
from http.server import ThreadingHTTPServer
import http.client
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import threading
import time
from unittest.mock import patch

from jwc24 import hbnj_publication, server
from jwc24.forecast import decode_lz10
from jwc24.hbnj_publication import HBNJPublicationError, load_hbnj_snapshot, publish_hbnj_snapshot
from jwc24.manifest import ChannelManifest, Task


def main():
    mode, inputs, working = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    assert importlib.util.find_spec('tools') is None, 'Checkout tools leaked into installed runtime'
    assert 'site-packages' in str(Path(hbnj_publication.__file__).resolve()), 'Source package shadowed wheel'
    assert not (working / 'tools').exists()
    guide, payloads, publication = inputs / 'guide.json', inputs / 'payloads', working / 'publication'
    now = int(time.time())
    publish_hbnj_snapshot(guide, payloads, publication, now=now,
                          rights_ref='synthetic-wheel-test-only', max_collection_age_seconds=3600)
    snapshot = load_hbnj_snapshot(publication, now=now)
    assert snapshot.metadata()['routes'] == 109
    for identifier in range(1001, 1055):
        for route, filename in (('epg.bin', 'epg.hdpk'), ('str.bin', 'string.hdpk')):
            assert snapshot.raw_payload(f'/{identifier}/{route}', now=now) == (
                payloads / 'areas' / str(identifier) / filename).read_bytes()
    assert snapshot.raw_payload('/header.bin', now=now) == (payloads / 'header.hdpk').read_bytes()
    if mode == 'validation':
        before = (publication / 'current.json').read_bytes()
        # Valid HDPK with a forged national description, not just bad magic:
        # retaining all independent content checks must reject it.
        wrong = working / 'wrong-national'
        shutil.copytree(payloads, wrong)
        data = bytearray((wrong / 'string.hdpk').read_bytes())
        at = data.index('Description A'.encode('utf-16-be'))
        data[at:at + 2] = 'X'.encode('utf-16-be')
        (wrong / 'string.hdpk').write_bytes(data)
        rejected = 0
        for bad_payloads in (wrong, working / 'wrong-area'):
            if bad_payloads.name == 'wrong-area':
                shutil.copytree(payloads, bad_payloads)
                epg = bad_payloads / 'areas/1054/epg.hdpk'
                data = bytearray(epg.read_bytes())
                station_table = struct.unpack_from('>I', data, 0x20 + 0x20)[0]
                struct.pack_into('>I', data, 0x20 + station_table, 0x90000)
                epg.write_bytes(data)
            try:
                publish_hbnj_snapshot(guide, bad_payloads, publication, now=now,
                                      rights_ref='synthetic-wheel-test-only', max_collection_age_seconds=3600)
            except HBNJPublicationError:
                rejected += 1
            else:
                raise AssertionError('Installed validator accepted inconsistent native content')
            assert (publication / 'current.json').read_bytes() == before
        assert rejected == 2
        # Even matching updated digests must not disable actual binary checks.
        generation = publication / json.loads(before)['generation']
        regional = generation / 'areas/1001/epg.hdpk'
        regional.write_bytes(b'invalid HDPK')
        manifest = json.loads((generation / 'manifest.json').read_text())
        for row in manifest['files']:
            if row['path'] == 'areas/1001/epg.hdpk':
                row['bytes'] = len(b'invalid HDPK')
                row['sha256'] = hashlib.sha256(b'invalid HDPK').hexdigest()
        (generation / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        # Payload cwd is never an import source. A complete shadow validator
        # would otherwise make all three `python -m` checks succeed.
        shadow = generation / 'jwc24/hbnj_validation'
        shadow.mkdir(parents=True)
        (shadow.parent / '__init__.py').write_text('', encoding='utf-8')
        for name in ('__init__', 'guide', 'payloads', 'areas'):
            (shadow / f'{name}.py').write_text('', encoding='utf-8')
        try:
            load_hbnj_snapshot(publication, now=now)
        except HBNJPublicationError:
            pass
        else:
            raise AssertionError('Installed loader trusted hashes without native validation')
    elif mode == 'serving':
        tasks = tuple(Task(10 + index, filename, route, working / 'missing-legacy' / filename,
                           60, 5, False, 'create', 'nintendo-lz10', 'wc24-aes-ofb')
                      for index, (filename, route) in enumerate((('epg.bin', '/1016/epg.bin'),
                                                                  ('str.bin', '/1016/str.bin'),
                                                                  ('header.bin', '/header.bin'))))
        manifest = ChannelManifest(working / 'manifest.json', 1, 'HBNJ', 'Synthetic wheel test',
                                   0x0001000148424E4A, 'JPN', 'http://127.0.0.1', False, tasks, ())
        key = working / 'title/00010001/48424e4a/data/wc24pubk.mod'
        key.parent.mkdir(parents=True)
        key.write_bytes(bytes(512) + bytes([7]) * 16 + bytes(16))
        ready, listeners, errors, clock = threading.Event(), [], [], [now]
        def factory(address, handler):
            listener = ThreadingHTTPServer(address, handler)
            listeners.append(listener)
            ready.set()
            return listener
        def run():
            try:
                server.serve(manifest, '127.0.0.1', 0, working, hbnj_snapshot=snapshot)
            except BaseException as error:
                errors.append(error)
                ready.set()
        worker, connection = None, None
        try:
            with patch.object(server, 'ThreadingHTTPServer', side_effect=factory), \
                    patch('jwc24.hbnj_publication.time.time', side_effect=lambda: clock[0]), \
                    contextlib.redirect_stdout(io.StringIO()):
                worker = threading.Thread(target=run, daemon=True)
                worker.start()
                assert ready.wait(10) and not errors, repr(errors)
                (publication / 'current.json').write_bytes(b'new pointer cannot mix prepared responses')
                connection = http.client.HTTPConnection('127.0.0.1', listeners[0].server_port, timeout=10)
                routes = ['/header.bin'] + [f'/{area}/{name}.bin' for area in range(1001, 1055)
                                             for name in ('epg', 'str')]
                for route in routes:
                    connection.request('GET', route)
                    response = connection.getresponse()
                    wire = response.read()
                    assert response.status == 200 and wire[:4] == b'Wc24'
                    assert int(response.getheader('Content-Length')) == len(wire)
                    compressed = server._aes_ofb(wire[320:], bytes([7]) * 16, wire[48:64], decrypt=True)
                    assert decode_lz10(compressed) == snapshot.raw_payload(route, now=now)
                for route in ('/1055/epg.bin', '/other/header.bin', '/epg.bin'):
                    connection.request('GET', route)
                    response = connection.getresponse()
                    response.read()
                    assert response.status == 404
                clock[0] = snapshot.expires_unix
                connection.request('GET', '/1016/epg.bin')
                response = connection.getresponse()
                response.read()
                assert response.status == 503
        finally:
            if connection:
                connection.close()
            for listener in listeners:
                listener.shutdown()
                listener.server_close()
            if worker:
                worker.join(10)
        assert not errors and not worker.is_alive()
    else:
        raise AssertionError('Unknown wheel probe mode')
    print(f'wheel-{mode}-verified')


if __name__ == '__main__':
    main()
