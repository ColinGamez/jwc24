from __future__ import annotations

import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from jwc24 import dl_list, wc24_config
from jwc24.__main__ import main
from jwc24.manifest import Asset, with_base_url
from jwc24.readiness import inspect_readiness
from tests.test_wc24_delivery import make_key, manifest


def empty_table() -> bytearray:
    value = bytearray(dl_list.FILE_SIZE)
    value[:4] = b"WcDl"
    struct.pack_into(">I", value, 4, 1)
    struct.pack_into(">H", value, 20, 120)
    return value


def account_config() -> bytearray:
    value = bytearray(wc24_config.FILE_SIZE)
    struct.pack_into(">IIQII", value, 0, wc24_config.MAGIC, wc24_config.VERSION,
                     1111222233334444, 0, wc24_config.STAGE_REGISTERED)
    value[wc24_config.MAIL_SECRET_OFFSET] = ord("s")
    value[wc24_config.MLCHKID_OFFSET] = ord("c")
    struct.pack_into(">I", value, wc24_config.ENABLE_BOOTING_OFFSET, 1)
    struct.pack_into(">I", value, wc24_config.CHECKSUM_OFFSET, wc24_config.checksum(value))
    return value


class ReadinessTests(unittest.TestCase):
    def test_explicit_shared_origin_override_is_in_memory_and_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = manifest(root, 1, "one.bin"), manifest(root, 2, "two.bin")
            second = replace(second, base_url="https://other.invalid")
            selected = with_base_url((first, second), "http://127.0.0.1:8080/")
            self.assertTrue(inspect_readiness(selected)["preflight_passed"])
            self.assertEqual(selected[0].base_url, "http://127.0.0.1:8080")
            self.assertEqual(first.base_url, "http://127.0.0.1")
            self.assertEqual(second.base_url, "https://other.invalid")
            for origin in ("file:///tmp", "http://x/prefix", "http://x?secret=1", "http://user:password@x",
                           "http://x/#fragment", "http://x?", "http://x/#", "http://x:99999",
                           "http://x:0", "http://x\n", "http://x;foo"):
                with self.subTest(origin=origin), self.assertRaises(ValueError):
                    with_base_url((first, second), origin)

    def test_manifest_identifiers_cannot_echo_arbitrary_uppercase_input(self):
        with tempfile.TemporaryDirectory() as directory:
            value = manifest(Path(directory), 1, "one.bin")
            for identifier in ("HTTPS://PRIVATE.INVALID/SECRET", "A" * 100, "PRIVATE ID", "PRIVATE\nSECRET"):
                with self.assertRaisesRegex(ValueError, "bounded safe label") as raised:
                    inspect_readiness((replace(value, channel_id=identifier),))
                self.assertNotIn(identifier, str(raised.exception))

    def test_prepared_bundle_does_not_claim_native_acceptance_or_modify_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = manifest(root, 1, "one.bin"), manifest(root, 2, "two.bin")
            make_key(root, first, 1)
            make_key(root, second, 2)
            table = empty_table()
            for channel in (first, second):
                dl_list._write_task(table, channel, channel.tasks[0])
            table_path, config_path = root / "dl.bin", root / "config.bin"
            table_path.write_bytes(table)
            config_path.write_bytes(account_config())
            snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = inspect_readiness((first, second), dl_path=table_path, config_path=config_path, nand_root=root)
            self.assertTrue(result["preflight_passed"])
            self.assertFalse(result["native_readiness_verified"])
            self.assertFalse(result["profile_modified"])
            self.assertFalse(result["project_complete"])
            self.assertEqual(result["checks"]["task_registration"], "checked")
            self.assertEqual({p: p.read_bytes() for p in root.rglob("*") if p.is_file()}, snapshot)
            output = json.dumps(result)
            self.assertNotIn(str(root), output)
            self.assertNotIn("1111222233334444", output)
            self.assertNotIn("127.0.0.1", output)

    def test_cross_channel_conflicts_are_caught_even_without_a_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = manifest(root, 1, "one.bin"), manifest(root, 2, "two.bin")
            second = replace(second, base_url="https://unreported.invalid", tasks=(replace(
                second.tasks[0], slot=1, filename="one.bin", route=first.tasks[0].route),))
            result = inspect_readiness((first, second))
            codes = {i["code"] for i in result["issues"]}
            self.assertTrue({"task_slot_collision", "task_route_collision", "payload_filename_collision",
                             "shared_listener_endpoint_mismatch"} <= codes)
            self.assertEqual(result["checks"]["account"], "not_supplied")

    def test_asset_route_collision_is_order_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = manifest(root, 1, "one.bin"), manifest(root, 2, "two.bin")
            first = replace(first, tasks=(), assets=(Asset("one.bin", root / "one.bin", "none", "raw"),))
            second = replace(second, tasks=(replace(second.tasks[0], route="/bin7/one.bin"),))
            for values in ((first, second), (second, first)):
                result = inspect_readiness(values)
                self.assertIn("asset_task_route_collision", {i["code"] for i in result["issues"]})

    def test_empty_missing_old_future_payloads_are_separate_local_policy_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = manifest(root, 1, "one.bin")
            payload = value.tasks[0].payload
            os.utime(payload, (100, 100))
            self.assertTrue(inspect_readiness((value,), now=1000)["preflight_passed"])
            result = inspect_readiness((value,), now=1000, max_payload_age_seconds=60)
            self.assertEqual(result["issues"][0]["code"], "payload_exceeds_local_age_policy")
            result = inspect_readiness((value,), now=99, max_payload_age_seconds=60)
            self.assertEqual(result["issues"][0]["code"], "payload_timestamp_in_future")
            payload.write_bytes(b"")
            self.assertEqual(inspect_readiness((value,))["issues"][0]["code"], "payload_empty")
            payload.unlink()
            self.assertEqual(inspect_readiness((value,))["issues"][0]["code"], "payload_missing")

    def test_native_task_registration_and_flags_are_checked_without_editing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = manifest(root, 1, "one.bin")
            path = root / "dl.bin"
            table = empty_table()
            path.write_bytes(table)
            self.assertIn("task_not_registered", {i["code"] for i in inspect_readiness((value,), dl_path=path)["issues"]})
            dl_list._write_task(table, value, value.tasks[0])
            offset = dl_list.ENTRY_BASE + dl_list.ENTRY_SIZE
            table[offset + 2] = 2
            struct.pack_into(">I", table, offset + 4, dl_list.UNSIGNED_FLAG)
            table[offset + 180:offset + 184] = b"junk"
            path.write_bytes(table)
            codes = {i["code"] for i in inspect_readiness((value,), dl_path=path)["issues"]}
            self.assertTrue({"task_type_mismatch", "task_endpoint_mismatch", "task_signature_flag_mismatch",
                             "task_decryption_flag_missing"} <= codes)
            self.assertEqual(path.read_bytes(), table)

    def test_create_flags_and_adopted_encryption_require_the_full_transport_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = manifest(root, 1, "one.bin")
            path = root / "dl.bin"
            table = empty_table()
            dl_list._write_task(table, value, value.tasks[0])
            offset = dl_list.ENTRY_BASE + dl_list.ENTRY_SIZE
            struct.pack_into(">I", table, offset + 4, 8)
            path.write_bytes(table)
            for mode in ("create", "adopt"):
                channel = replace(value, tasks=(replace(value.tasks[0], mode=mode),))
                codes = {i["code"] for i in inspect_readiness((channel,), dl_path=path)["issues"]}
                self.assertIn("task_decryption_flag_missing", codes)
                if mode == "create":
                    self.assertIn("task_created_flags_mismatch", codes)
            raw = replace(value, tasks=(replace(value.tasks[0], envelope="raw"),))
            self.assertIn("task_created_flags_mismatch", {
                i["code"] for i in inspect_readiness((raw,), dl_path=path)["issues"]})

    def test_corrupt_or_oversize_profile_reports_do_not_echo_paths_or_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = manifest(root, 1, "one.bin")
            path = root / "secret-marker"
            for payload in (b"private identifier and URL", bytes(dl_list.FILE_SIZE + 1)):
                path.write_bytes(payload)
                result = inspect_readiness((value,), dl_path=path, config_path=path, nand_root=path)
                self.assertFalse(result["preflight_passed"])
                self.assertNotIn("secret-marker", json.dumps(result))
                self.assertNotIn("private identifier", json.dumps(result))

    def test_account_failures_do_not_become_registration_or_mail_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = manifest(root, 1, "one.bin")
            config = account_config()
            config[8:16] = bytes(8)
            config[wc24_config.MAIL_SECRET_OFFSET] = 0
            struct.pack_into(">I", config, wc24_config.ENABLE_BOOTING_OFFSET, 0)
            path = root / "cfg"
            path.write_bytes(config)
            codes = {i["code"] for i in inspect_readiness((value,), config_path=path)["issues"]}
            self.assertTrue({"account_checksum_invalid", "account_not_registered", "background_booting_not_enabled",
                             "mail_credentials_missing"} <= codes)

    def test_cli_success_blocked_and_invalid_inputs_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "one.bin"
            payload.write_bytes(b"synthetic")
            path = root / "manifest.json"
            data = {"schema_version": 1, "channel_id": "SYNTHETIC", "name": "Synthetic",
                    "title_id": "0001000100000001", "system_menu_region": "JPN",
                    "base_url": "http://127.0.0.1", "tasks": [],
                    "assets": [{"filename": "one.bin", "payload": "one.bin"}]}
            path.write_text(json.dumps(data), encoding="utf-8")
            for expected in (0, 1, 2):
                output = io.StringIO()
                if expected == 1:
                    payload.unlink()
                if expected == 2:
                    path.write_text("secret-invalid-json", encoding="utf-8")
                with patch.object(sys, "argv", ["jwc24", "preflight", str(path)]), contextlib.redirect_stdout(output):
                    self.assertEqual(main(), expected)
                report = json.loads(output.getvalue())
                self.assertEqual(report["preflight_passed"], expected == 0)
                self.assertNotIn("secret-invalid-json", output.getvalue())
