"""Build/publish explicit private News inputs or serve their verified binary routes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.news import MAX_ENVELOPE_BYTES, MAX_RAW_BYTES
from jwc24.news_bundle import MAX_BUNDLE_BYTES
from jwc24.news_publication import (
    MAX_MANIFEST_BYTES, NewsPublicationError, _json, _read,
    build_news_publication, load_news_publication, prepare_news_publication, write_news_publication,
)
from jwc24.news_server import create_news_server


def _inputs(config, *, raw):
    config = Path(config).resolve()
    document = _json(_read(config, MAX_MANIFEST_BYTES))
    if (not isinstance(document, dict) or set(document) != {'schema_version', 'route_prefix', 'rights_ref', 'inputs'}
            or document['schema_version'] != 1 or not isinstance(document['inputs'], list)
            or len(document['inputs']) != 24):
        raise NewsPublicationError('News build configuration is invalid')
    buffers, refs, used = [], [], 0
    for slot, row in enumerate(document['inputs']):
        if (not isinstance(row, dict) or set(row) != {'slot', 'path', 'source_ref'}
                or type(row['slot']) is not int or row['slot'] != slot
                or not isinstance(row['path'], str) or not row['path'] or len(row['path']) > 1024):
            raise NewsPublicationError('News build input slot configuration is invalid')
        value = _read(config.parent / row['path'], min(MAX_RAW_BYTES if raw else MAX_ENVELOPE_BYTES,
                                                     MAX_BUNDLE_BYTES - used))
        used += len(value)
        buffers.append(value)
        refs.append(row['source_ref'])
    return buffers, dict(route_prefix=document['route_prefix'], source_refs=refs, rights_ref=document['rights_ref'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('publish', 'build'):
        command = commands.add_parser(name)
        command.add_argument('--config', type=Path, required=True)
        command.add_argument('--public-key', type=Path, required=True)
        command.add_argument('--output', type=Path, required=True)
        if name == 'build':
            command.add_argument('--private-key', type=Path, required=True)
    serve = commands.add_parser('serve')
    serve.add_argument('--root', type=Path, required=True)
    serve.add_argument('--public-key', type=Path, required=True)
    serve.add_argument('--bind', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8082)
    args = parser.parse_args(argv)
    try:
        if args.command in ('publish', 'build'):
            buffers, options = _inputs(args.config, raw=args.command == 'build')
            if args.command == 'build':
                publication = build_news_publication(buffers, private_key=args.private_key,
                                                     public_key=args.public_key, **options)
            else:
                publication = prepare_news_publication(buffers, public_key=args.public_key, **options)
            result = write_news_publication(args.output, publication)
            print(json.dumps(dict(publication_written=True, **result), sort_keys=True))
            return 0
        if not 0 <= args.port <= 65535:
            raise NewsPublicationError('News listener port is outside its valid range')
        publication = load_news_publication(args.root, public_key=args.public_key)
        server = create_news_server((args.bind, args.port), publication)
        print(json.dumps(dict(listener_prepared=True, **publication.metadata()), sort_keys=True), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except (NewsPublicationError, OSError, ValueError, TypeError):
        print(json.dumps({'operation_completed': False,
                          'error': 'Explicit News service inputs or publication failed validation'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
