"""Read-only preparation checks, separate from native channel acceptance."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re
import stat
import time
from urllib.parse import urlsplit

from . import dl_list, wc24_config
from .manifest import ChannelManifest
from .prepared_delivery import PreparedDeliveryError, snapshot_tasks
from .wc24_delivery import envelope_key_paths


def _bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError("input exceeds its supported size")
    return data


def inspect_readiness(
    manifests: Sequence[ChannelManifest], *,
    dl_path: Path | None = None, config_path: Path | None = None,
    nand_root: Path | None = None, max_payload_age_seconds: int | None = None,
    now: float | None = None,
    news_publication=None, hbnj_snapshot=None,
) -> dict:
    """Inspect explicit inputs; never open sockets, provision tasks or write files.

    Only metadata and fixed issue codes are returned. Paths, device identifiers,
    task URLs, passwords and check IDs are excluded, including on input errors.
    File modification age is a local policy, not payload freshness evidence.
    """
    if not manifests:
        raise ValueError("at least one manifest is required")
    if any(not isinstance(item.channel_id, str) or
           re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", item.channel_id) is None
           for item in manifests):
        raise ValueError("manifest channel identifier is not a bounded safe label")
    if max_payload_age_seconds is not None and (
        type(max_payload_age_seconds) is not int or max_payload_age_seconds <= 0
    ):
        raise ValueError("maximum payload age must be a positive integer")
    now = time.time() if now is None else now
    issues: list[dict] = []

    def issue(code: str, channel: str | None = None, slot: int | None = None):
        value = {"code": code}
        if channel is not None:
            value["channel"] = channel
        if slot is not None:
            value["slot"] = slot
        issues.append(value)

    prepared_checks = {'news': 'not_supplied', 'hbnj': 'not_supplied'}
    # Check each independently: a bad News input cannot hide an unrelated HBNJ
    # failure, and a valid snapshot never excuses another channel's missing file.
    supplied_tasks = {}
    for name, publication in (('news', news_publication), ('hbnj', hbnj_snapshot)):
        if publication is None:
            continue
        try:
            supplied = snapshot_tasks(
                manifests, news_publication=publication if name == 'news' else None,
                hbnj_snapshot=publication if name == 'hbnj' else None, now=int(now))
            if name == 'news' and not publication.is_current(int(now)):
                issue('news_publication_expired')
                prepared_checks[name] = 'outside_publication_window'
            else:
                supplied_tasks.update(supplied)
                prepared_checks[name] = 'validated_current_snapshot'
        except PreparedDeliveryError as error:
            issue(error.code)
            prepared_checks[name] = 'invalid_or_conflicting_snapshot'

    channels = []
    slots: set[int] = set()
    identities: set[int] = set()
    names: set[str] = set()
    routes: set[str] = set()
    endpoints = set()
    for manifest in manifests:
        parsed = urlsplit(manifest.base_url)
        endpoints.add((parsed.scheme, parsed.netloc))
        if manifest.title_id in identities:
            issue("duplicate_channel_title", manifest.channel_id)
        identities.add(manifest.title_id)
        channels.append({"channel": manifest.channel_id,
                         "tasks": len(manifest.tasks), "assets": len(manifest.assets)})
        for task in manifest.tasks:
            if task.slot in slots:
                issue("task_slot_collision", manifest.channel_id, task.slot)
            slots.add(task.slot)
            if task.route in routes:
                issue("task_route_collision", manifest.channel_id, task.slot)
            routes.add(task.route)
        for item in (*manifest.tasks, *manifest.assets):
            if item.filename in names:
                issue("payload_filename_collision", manifest.channel_id)
            names.add(item.filename)
            if any(item is owned for owned in supplied_tasks.values()):
                continue
            try:
                metadata = item.payload.stat()
                if not stat.S_ISREG(metadata.st_mode):
                    issue("payload_not_regular_file", manifest.channel_id)
                elif metadata.st_size == 0:
                    issue("payload_empty", manifest.channel_id)
                elif max_payload_age_seconds is not None:
                    age = now - metadata.st_mtime
                    if age < 0:
                        issue("payload_timestamp_in_future", manifest.channel_id)
                    elif age > max_payload_age_seconds:
                        issue("payload_exceeds_local_age_policy", manifest.channel_id)
            except FileNotFoundError:
                issue("payload_missing", manifest.channel_id)
            except OSError:
                issue("payload_unreadable", manifest.channel_id)
    # Check after collecting all routes so manifest order has no effect.
    for manifest in manifests:
        for asset in manifest.assets:
            aliases = {f"/{asset.filename}", *(f"/bin{i}/{asset.filename}" for i in range(1, 11))}
            if aliases & routes:
                issue("asset_task_route_collision", manifest.channel_id)
    if len(endpoints) != 1:
        issue("shared_listener_endpoint_mismatch")

    task_check = "not_supplied"
    if dl_path is not None:
        try:
            table = _bounded_read(dl_path, dl_list.FILE_SIZE)
            dl_list.validate(table)
            task_check = "checked"
            for manifest in manifests:
                for task in manifest.tasks:
                    current = dl_list.entry(table, task.slot)
                    if current is None:
                        issue("task_not_registered", manifest.channel_id, task.slot)
                        continue
                    if (current.title_id, current.filename) != (manifest.title_id, task.filename):
                        issue("task_slot_occupied_by_other_entry", manifest.channel_id, task.slot)
                        continue
                    if current.entry_type != dl_list.CHANNEL_CONTENT:
                        issue("task_type_mismatch", manifest.channel_id, task.slot)
                    if current.url != manifest.base_url + task.route:
                        issue("task_endpoint_mismatch", manifest.channel_id, task.slot)
                    if bool(current.flags & dl_list.UNSIGNED_FLAG) != task.unsigned:
                        issue("task_signature_flag_mismatch", manifest.channel_id, task.slot)
                    if (task.mode == "create" and
                        current.flags != dl_list._created_task_flags(task)):
                        issue("task_created_flags_mismatch", manifest.channel_id, task.slot)
                    if (task.envelope == "wc24-aes-ofb" and
                        current.flags & dl_list.ENCRYPTED_CHANNEL_FLAGS != dl_list.ENCRYPTED_CHANNEL_FLAGS):
                        issue("task_decryption_flag_missing", manifest.channel_id, task.slot)
        except (OSError, ValueError):
            task_check = "invalid_or_unreadable"
            issue("task_table_invalid_or_unreadable")

    account_check = "not_supplied"
    if config_path is not None:
        try:
            config = _bounded_read(config_path, wc24_config.FILE_SIZE)
            state = wc24_config.summarize(config)
            account_check = "checked"
            if not state.checksum_valid:
                issue("account_checksum_invalid")
            if not state.nwc24_id or state.creation_stage != wc24_config.STAGE_REGISTERED:
                issue("account_not_registered")
            if state.enable_booting != 1:
                issue("background_booting_not_enabled")
            if not all(wc24_config.mail_credentials_present(config)):
                issue("mail_credentials_missing")
        except (OSError, ValueError):
            account_check = "invalid_or_unreadable"
            issue("account_config_invalid_or_unreadable")

    key_check = "not_supplied"
    if nand_root is not None:
        try:
            envelope_key_paths(manifests, nand_root)
            key_check = "checked_presence_and_size_only"
        except (OSError, ValueError):
            key_check = "invalid_or_unreadable"
            issue("payload_owner_key_invalid_or_unreadable")

    return {
        "schema_version": 1, "scope": "read_only_offline_preparation",
        "channels": channels, "issues": issues,
        "preflight_passed": not issues,
        "checks": {"task_registration": task_check, "account": account_check,
                   "envelope_key_files": key_check,
                   "payload_age_policy_seconds": max_payload_age_seconds,
                   "prepared_publications": prepared_checks,
                   "news_native_subtask_registration":
                       "not_implemented" if news_publication is not None else "not_supplied"},
        "unverified": ["payload_schema_and_internal_freshness", "signature_trust_on_client",
                       "scheduler_readiness_and_individual_task_result", "network_delivery",
                       "native_storage_consumption", "original_ui_rendering", "mail_receipt_and_display"],
        "native_readiness_verified": False, "project_complete": False,
        "profile_modified": False, "network_used": False,
    }
