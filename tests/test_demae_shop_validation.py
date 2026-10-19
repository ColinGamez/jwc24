import unittest
from jwc24.demae_shop_validation import assess_shop_list_record, assess_directory_record


class ShopValidationTests(unittest.TestCase):
    def test_closed_shop_still_requires_payment_and_reservation_fields(self):
        row = {'shopCode': 'test', 'homeCode': 'test-home', 'name': 'Test',
               'catchphrase': 'Test description', 'yoyaku': 'test-value',
               'activate': 'stop', 'paymentList': ['代金引換'],
               'shopStatus': {'status': {}}}
        self.assertTrue(assess_shop_list_record(row)['producer_fields_complete'])
        for field, reason in [('paymentList', 'cash_on_delivery_unestablished'),
                              ('yoyaku', 'missing_yoyaku'), ('homeCode', 'missing_homeCode')]:
            changed = dict(row)
            changed.pop(field)
            self.assertIn(reason, assess_shop_list_record(changed)['reasons'])
        changed = {**row, 'name': '😀', 'waitTime': True}
        self.assertIn('encoding_name', assess_shop_list_record(changed)['reasons'])
        self.assertIn('invalid_waitTime', assess_shop_list_record(changed)['reasons'])

    def test_directory_cannot_establish_order_capabilities(self):
        report = assess_directory_record({'id': 'source:1', 'name': 'Test', 'catchphrase': 'Real text'})
        self.assertFalse(report['producer_fields_complete'])
        self.assertIn('cash_on_delivery_unestablished', report['reasons'])
        self.assertFalse(report['ordering_verified'])
        self.assertFalse(report['native_verified'])
