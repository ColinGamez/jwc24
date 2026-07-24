from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import dl_list, wc24_config
from .manifest import load_manifest
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

    provision = sub.add_parser("provision", help="provision manifest tasks (dry run by default)")
    provision.add_argument("manifest", type=Path)
    provision.add_argument("--dl-list", type=Path, required=True)
    provision.add_argument("--apply", action="store_true")

    server = sub.add_parser("serve", help="serve the payload routes in a manifest")
    server.add_argument("manifest", type=Path)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int)
    server.add_argument("--nand-root", type=Path)
    server.add_argument("--tls-cert", type=Path)
    server.add_argument("--tls-key", type=Path)

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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
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
        if args.command == "serve":
            parsed = urlparse(manifest.base_url)
            port = args.port or parsed.port or (443 if parsed.scheme == "https" else 80)
            serve(
                manifest,
                args.host,
                port,
                args.nand_root,
                args.tls_cert,
                args.tls_key,
            )
            return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
