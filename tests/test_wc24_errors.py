import contextlib
import io
import json
import unittest

from jwc24.wc24_errors import explain_error
from tools.explain_wc24_error import main


class Wc24ErrorTests(unittest.TestCase):
    def test_reference_categories_do_not_claim_root_causes(self):
        examples = {'107305': 'download_task', '102305': 'service_connection',
                    '109026': 'busy_retry_timeout', '109106': 'outbox_capacity',
                    '109014': 'file_or_storage', '109049': 'system_update_required',
                    '109107': 'wc24_setting_disabled', '109001': 'wc24_initialization',
                    '102312': 'network_configuration', '109999': 'other_wc24_error'}
        for code, category in examples.items():
            with self.subTest(code=code):
                result = explain_error(code)
                self.assertEqual(result['category'], category)
                self.assertFalse(result['root_cause_verified'])
                self.assertTrue(result['diagnostic_only'])

    def test_reference_families_and_leading_zero_integer(self):
        self.assertEqual(explain_error(51234)['code'], '051234')
        self.assertEqual(explain_error('051234')['category'], 'network_configuration')
        self.assertEqual(explain_error('110001')['category'], 'service_connection')
        self.assertEqual(explain_error('109214')['category'], 'file_or_storage')

    def test_unknown_channel_codes_and_zero_stay_unknown(self):
        for code in ('336195', '334011', '000000', 0):
            result = explain_error(code)
            self.assertEqual(result['category'], 'unknown')
            self.assertIsNone(result['reference'])

    def test_invalid_codes_rejected(self):
        for code in (True, -1, 1000000, 107305.0, None, '', '10730', '1073050',
                     ' 107305', '\uff11\uff10\uff17\uff13\uff10\uff15', '10730x'):
            with self.subTest(code=code), self.assertRaises(ValueError):
                explain_error(code)

    def test_cli_is_metadata_only(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['107305']), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['category'], 'download_task')
        self.assertFalse(result['root_cause_verified'])
