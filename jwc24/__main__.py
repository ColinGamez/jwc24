from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import dl_list, launcher, wc24_config
from .manifest import load_manifest, with_base_url
from .mail import MailStore
from .mail_server import serve_mail
from .server import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jwc24")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="inspect a Dolphin WC24 task table")
    audit.add_argument("--dl-list", type=Path, required=True)

    validate = sub.add_parser("validate-manifest", help="validate and summarize a channel manifest")
    validate.add_argument("manifest", type=Path)

    preflight = sub.add_parser("preflight", help="read-only multi-channel preparation checks; no native acceptance claim")
    preflight.add_argument("manifest", type=Path, nargs="+")
    preflight.add_argument("--dl-list", type=Path)
    preflight.add_argument("--config", type=Path)
    preflight.add_argument("--nand-root", type=Path)
    preflight.add_argument("--max-payload-age-seconds", type=int)
    preflight.add_argument("--base-url", help="select a shared origin in memory; does not rewrite manifests")
    preflight.add_argument("--news-root", type=Path, help="explicit validated private News publication")
    preflight.add_argument("--news-public-key", type=Path, help="explicit News signature verification key")
    preflight.add_argument("--hbnj-root", type=Path, help="explicit coherent private HBNJ publication root")

    provision = sub.add_parser("provision", help="provision manifest tasks (dry run by default)")
    provision.add_argument("manifest", type=Path)
    provision.add_argument("--dl-list", type=Path, required=True)
    provision.add_argument("--apply", action="store_true")

    server = sub.add_parser("serve", help="serve the payload routes in a manifest")
    server.add_argument("manifest", type=Path, nargs="+")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int)
    server.add_argument("--nand-root", type=Path)
    server.add_argument("--tls-cert", type=Path)
    server.add_argument("--tls-key", type=Path)
    server.add_argument("--base-url", help="select a shared origin in memory; does not rewrite manifests")
    server.add_argument("--news-root", type=Path, help="explicit validated private News publication")
    server.add_argument("--news-public-key", type=Path, help="explicit News signature verification key")
    server.add_argument("--hbnj-root", type=Path, help="explicit coherent private HBNJ publication root")

    account = sub.add_parser("account", help="audit or locally bootstrap the WC24 account")
    account.add_argument("--config", type=Path, required=True)
    account.add_argument("--bootstrap-local", action="store_true")
    account.add_argument("--apply", action="store_true")

    mail_server = sub.add_parser("mail-serve", help="run the shared WC24 mail service")
    mail_server.add_argument("--host", default="127.0.0.1")
    mail_server.add_argument("--port", type=int, default=8081)
    mail_server.add_argument("--data-dir", type=Path, required=True)

    mail_config = sub.add_parser(
        "mail-config", help="provision Dolphin's WC24 mail URLs and credentials"
    )
    mail_config.add_argument("--config", type=Path, required=True)
    mail_config.add_argument("--base-url", required=True)
    mail_config.add_argument("--data-dir", type=Path, required=True)
    mail_config.add_argument("--apply", action="store_true")

    launch = sub.add_parser("launch", help="run JWC24 mail and patched Dolphin together")
    launch.add_argument("--dolphin", type=Path, required=True)
    launch.add_argument("--data-dir", type=Path, required=True)
    launch.add_argument("--host", default="127.0.0.1")
    launch.add_argument("--port", type=int, default=8081)
    launch.add_argument("--title", default="0000000100000002")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "preflight":
            import json
            from .readiness import inspect_readiness
            # Avoid printing source paths, URLs or input-derived exception text.
            try:
                manifests = tuple(load_manifest(path) for path in args.manifest)
                if args.base_url:
                    manifests = with_base_url(manifests, args.base_url)
                if (args.news_root is None) != (args.news_public_key is None):
                    raise ValueError('News preparation requires both publication and verification key')
                prepared = {}
                if args.news_root is not None:
                    from .news_publication import load_news_publication
                    prepared['news_publication'] = load_news_publication(
                        args.news_root, public_key=args.news_public_key)
                if args.hbnj_root is not None:
                    from .hbnj_publication import load_hbnj_snapshot
                    prepared['hbnj_snapshot'] = load_hbnj_snapshot(args.hbnj_root)
                report = inspect_readiness(
                    manifests, dl_path=args.dl_list, config_path=args.config,
                    nand_root=args.nand_root,
                    max_payload_age_seconds=args.max_payload_age_seconds,
                    **prepared,
                )
            except (OSError, ValueError, KeyError, TypeError):
                print(json.dumps({"preflight_passed": False,
                                  "error": "invalid_or_unreadable_preflight_input",
                                  "profile_modified": False, "network_used": False}))
                return 2
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if report["preflight_passed"] else 1
        if args.command == "launch":
            return launcher.launch(
                args.dolphin, args.data_dir, args.host, args.port, args.title
            )
        if args.command == "mail-serve":
            serve_mail(args.host, args.port, args.data_dir)
            return 0
        if args.command == "mail-config":
            config = wc24_config.read(args.config)
            state = wc24_config.summarize(config)
            account = MailStore(args.data_dir).register(f"{state.nwc24_id:016d}")
            before, after, backup = wc24_config.configure_mail(
                args.config,
                args.base_url,
                account.password,
                account.mlchkid,
                args.apply,
            )
            for old, new in zip(before, after):
                print(f"{old} -> {new}")
            print(f"applied; backup: {backup}" if backup else "dry run only; pass --apply")
            return 0
        if args.command == "account":
            if args.apply and not args.bootstrap_local:
                raise ValueError("--apply requires --bootstrap-local")
            if args.bootstrap_local:
                before, after, backup = wc24_config.bootstrap_local(args.config, args.apply)
                print(
                    f"stage {before.creation_stage} -> {after.creation_stage}; "
                    f"booting {before.enable_booting} -> {after.enable_booting}; "
                    f"WiiConnect24 ID {after.nwc24_id}"
                )
                print(f"checksum: {after.calculated_checksum:08x} (valid={after.checksum_valid})")
                print(f"applied; backup: {backup}" if backup else "dry run/no change")
            else:
                config = wc24_config.read(args.config)
                state = wc24_config.summarize(config)
                print(f"WiiConnect24 ID: {state.nwc24_id}")
                print(f"ID generation: {state.id_generation}")
                print(f"creation stage: {state.creation_stage}")
                print(f"background booting: {state.enable_booting}")
                print(
                    f"checksum: stored={state.stored_checksum:08x} "
                    f"calculated={state.calculated_checksum:08x} valid={state.checksum_valid}"
                )
                password_set, check_id_set = wc24_config.mail_credentials_present(config)
                print(
                    f"mail credentials: password={password_set} "
                    f"check_id={check_id_set}"
                )
                for index, url in enumerate(wc24_config.mail_urls(config)):
                    print(f"mail URL {index}: {url}")
            return 0
        if args.command == "audit":
            data = dl_list.read(args.dl_list)
            found = dl_list.entries(data)
            print(f"valid WcDl v1 table: {len(found)}/120 occupied slots")
            for item in found:
                print(
                    f"{item.slot:3}  {item.title_id:016x}  "
                    f"{item.filename or '<mail>':20}  {item.url}"
                )
            return 0

        if args.command == "serve":
            if (args.news_root is None) != (args.news_public_key is None):
                raise ValueError("News serving requires both --news-root and --news-public-key")
            news = None
            if args.news_root is not None:
                from .news_publication import load_news_publication
                news = load_news_publication(args.news_root, public_key=args.news_public_key)
            manifests = tuple(load_manifest(path) for path in args.manifest)
            if args.base_url:
                manifests = with_base_url(manifests, args.base_url)
            netlocs = {urlparse(item.base_url).netloc for item in manifests}
            if len(netlocs) != 1:
                raise ValueError("served manifests must share one base host and port")
            parsed = urlparse(manifests[0].base_url)
            port = args.port or parsed.port or (443 if parsed.scheme == "https" else 80)
            prepared = {}
            if news is not None:
                prepared["news_publication"] = news
            if args.hbnj_root is not None:
                from .hbnj_publication import load_hbnj_snapshot
                prepared["hbnj_snapshot"] = load_hbnj_snapshot(args.hbnj_root)
            serve(
                manifests,
                args.host,
                port,
                args.nand_root,
                args.tls_cert,
                args.tls_key,
                **prepared,
            )
            return 0

        manifest = load_manifest(args.manifest)
        if args.command == "validate-manifest":
            print(f"{manifest.channel_id}: {manifest.name}")
            print(f"title: {manifest.title_id:016x}; region: {manifest.system_menu_region}")
            for task in manifest.tasks:
                state = "present" if task.payload.is_file() else "MISSING"
                print(f"slot {task.slot}: {task.filename} {task.route} [{state}: {task.payload}]")
            return 0
        if args.command == "provision":
            changes, backup = dl_list.provision(args.dl_list, manifest, args.apply)
            for change in changes:
                print(change)
            if backup:
                print(f"applied; backup: {backup}")
            else:
                print("dry run only; pass --apply to write")
            return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
