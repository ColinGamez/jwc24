import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit_wii_shop_sources import audit


class ShopSourceAuditTests(unittest.TestCase):
    def fixture(self, root):
        relative = 'common/lib/ec/ec_connect.cpp'
        data = (b'Soap msg (env, "GetECConfig", Soap::ecs);\n'
                b'Soap next (env, requestName, Soap::ias);\n// private test account value\n')
        path = root/relative
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
        row = {'member': 'archive/build/'+relative, 'bytes': len(data),
               'sha256': hashlib.sha256(data).hexdigest()}
        (root/'inventory.json').write_text(json.dumps([row]))
        return relative, row

    def test_metadata_and_literal_call_without_source_body(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            relative, _ = self.fixture(root)
            report = audit(root, selected=(relative,))
            self.assertEqual(report['literal_soap_calls'][0]['action'], 'GetECConfig')
            self.assertEqual(report['literal_soap_calls'][0]['service'], 'ecs')
            self.assertEqual(len(report['literal_soap_calls']), 1)
            self.assertEqual(report['dynamic_soap_call_sites'][0]['service'], 'ias')
            self.assertNotIn('action', report['dynamic_soap_call_sites'][0])
            self.assertNotIn('private test account value', json.dumps(report))
            self.assertFalse(report['complete_protocol_verified'])

    def test_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            relative, _ = self.fixture(root)
            (root/relative).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'differs'):
                audit(root, selected=(relative,))

    def test_missing_or_duplicate_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            relative, row = self.fixture(root)
            for rows in ([], [row, row]):
                (root/'inventory.json').write_text(json.dumps(rows))
                with self.assertRaisesRegex(ValueError, 'one inventory record'):
                    audit(root, selected=(relative,))

    def test_selected_path_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'within'):
                audit(root, selected=('../outside.cpp',))
