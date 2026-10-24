"""Synthetic library-shaped fixtures; no captured client/account material."""
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from jwc24 import wii_shop_soap
from jwc24.wii_shop_soap import (
    CAS_NS, SOAP_NS, LIST_TITLES_ACTION, MAX_XML_BYTES, MAX_REPEATS,
    CatalogAttribute, CatalogTitle, SoapContractError,
    parse_list_titles_request, serialize_list_titles_response,
)


def request(extra="", *, prefix="c", offset="3", limit="2", common=""):
    # All values below are invented test inputs, not historical native data.
    fields = ("<c:Version>2.0</c:Version><c:MessageId>synthetic</c:MessageId>"
              "<c:Region>JPN</c:Region><c:Country>JP</c:Country>"
              "<c:Language>ja</c:Language>" + common +
              f"<c:ListResultOffset>{offset}</c:ListResultOffset>"
              f"<c:ListResultLimit>{limit}</c:ListResultLimit>" + extra)
    return (f'<s:Envelope xmlns:s="{SOAP_NS}" xmlns:c="{CAS_NS}" '
            'xmlns:x="http://www.w3.org/2001/XMLSchema-instance">'
            '<s:Body><c:ListTitles x:type="c:ListTitlesRequestType">' + fields +
            '</c:ListTitles></s:Body></s:Envelope>').replace("c:", prefix + ":").replace(
                "xmlns:c=", "xmlns:" + prefix + "=").encode("utf-8")


def parse(data, action=LIST_TITLES_ACTION):
    return parse_list_titles_request(data, soap_action=action)


def response(**changes):
    values = dict(total_size=1, total_source_ref="synthetic:test-total", titles=(
        CatalogTitle("0001000141424344", "synthetic:test-id"),), error_code="0")
    values.update(changes)
    return serialize_list_titles_response(**values)


class ShopSoapTests(unittest.TestCase):
    def test_native_shape_repeats_order_unicode_and_escaping(self):
        data = request('<c:Attributes>synthetic-name</c:Attributes>'
                       '<c:Attributes>synthetic-name</c:Attributes>'
                       '<c:AttributeFilters><c:Name>合成&amp;条件</c:Name>'
                       '<c:Value>&lt;値&gt;</c:Value></c:AttributeFilters>'
                       '<c:AttributeFilters><c:Name>合成&amp;条件</c:Name>'
                       '<c:Value>別</c:Value></c:AttributeFilters>'
                       '<c:TitleId>00010001414243AB</c:TitleId>'
                       '<c:TitleId>00010001414243AB</c:TitleId>')
        result = parse(data)
        self.assertEqual((result.offset, result.limit), (3, 2))
        self.assertEqual(result.attributes, ("synthetic-name", "synthetic-name"))
        self.assertEqual([(f.name, f.value) for f in result.attribute_filters],
                         [("合成&条件", "<値>"), ("合成&条件", "別")])
        self.assertEqual(result.title_ids, ("00010001414243ab",) * 2)

    def test_namespace_prefixes_and_quoted_action(self):
        self.assertEqual(parse(request(prefix="arbitrary"), '"' + LIST_TITLES_ACTION + '"'),
                         parse(request()))

    def test_common_data_is_opaque_and_excluded_from_repr(self):
        result = parse(request(common='<c:DeviceToken>synthetic-secret</c:DeviceToken>'
                               '<c:DeviceId>synthetic-device</c:DeviceId>'
                               '<c:AccountId>synthetic-account</c:AccountId>'))
        self.assertIn(("DeviceToken", "synthetic-secret"), result.common_fields)
        self.assertNotIn("synthetic-secret", repr(result))
        self.assertNotIn("synthetic-device", repr(result))
        # Structural parsing also works without account fields, conferring no auth.
        self.assertNotIn("AccountId", dict(parse(request()).common_fields))

    def test_u32_range_is_not_offline_catalog_page_size(self):
        self.assertEqual(parse(request(offset="4294967295", limit="0")).limit, 0)
        self.assertEqual(parse(request(limit="4294967295")).limit, 4294967295)
        for value in ("-1", "4294967296", "1.0", "", "true", " 2"):
            with self.subTest(value=value), self.assertRaises(SoapContractError):
                parse(request(limit=value))

    def test_unknown_duplicate_missing_and_cross_namespace_fields_reject(self):
        cases = [request('<c:Unknown/>'), request('<c:Version>2.0</c:Version>'),
                 request().replace(b'<c:Version>2.0</c:Version>', b''),
                 request().replace(b'2.0', b'1.0'),
                 request('<c:TitleId xmlns:c="urn:other">0001000141424344</c:TitleId>'),
                 request('<c:TitleId>bad</c:TitleId>'),
                 request('<c:Attributes><c:Name>nested</c:Name></c:Attributes>')]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(SoapContractError):
                parse(data)

    def test_bad_filter_shapes_reject(self):
        for contents in ('<c:Name>x</c:Name>', '<c:Value>x</c:Value><c:Name>y</c:Name>',
                         '<c:Name>x</c:Name><c:Value>y</c:Value><c:Name>z</c:Name>'):
            with self.subTest(contents=contents), self.assertRaises(SoapContractError):
                parse(request('<c:AttributeFilters>' + contents + '</c:AttributeFilters>'))

    def test_operations_actions_bodies_and_types_are_scoped(self):
        for data in (request().replace(b'ListTitlesRequestType', b'PurchaseTitleRequestType'),
                     request().replace(b'c:ListTitles', b'c:PurchaseTitle'),
                     request().replace(b'</s:Body>', b'<c:ListTitles/></s:Body>'),
                     request().replace(b'<s:Body>', b'<s:Header/><s:Body>'),
                     request().replace(b'x:type="c:ListTitlesRequestType"',
                                       b'xmlns:q="urn:other" x:type="q:ListTitlesRequestType"')):
            with self.subTest(data=data), self.assertRaises(SoapContractError):
                parse(data)
        with self.assertRaises(SoapContractError):
            parse(request(), "urn:ecs.wsapi.broadon.com/PurchaseTitle")

    def test_entity_malformed_non_utf8_and_bounds_reject(self):
        cases = [b'<!DOCTYPE x [<!ENTITY x "value">]>' + request(),
                 request()[:-10], b'\xff' + request(), b' ' * (MAX_XML_BYTES + 1),
                 request('<c:Attributes>x</c:Attributes>' * (MAX_REPEATS + 1)),
                 request('<c:Attributes>' + 'x' * 4097 + '</c:Attributes>'),
                 request('<c:A><c:B><c:C/></c:B></c:A>')]
        for data in cases:
            with self.subTest(size=len(data)), self.assertRaises(SoapContractError):
                parse(data)

    def test_parser_errors_do_not_echo_common_values(self):
        data = request(common='<c:AccountId>synthetic-secret</c:AccountId>'
                       '<c:AccountId>synthetic-secret</c:AccountId>')
        try:
            parse(data)
        except SoapContractError as error:
            self.assertNotIn("synthetic-secret", str(error))
        else:
            self.fail("Duplicate account field accepted")

    def test_response_lexical_envelope_matches_client_reader_contract(self):
        data = response(timestamp="123")
        self.assertTrue(data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(b'<soapenv:Envelope ', data)
        self.assertIn(b'<soapenv:Body>', data)
        self.assertIn(b'<ListTitlesResponse xmlns="urn:cas.wsapi.broadon.com">', data)
        self.assertLess(data.index(b'<TimeStamp>'), data.index(b'<ErrorCode>'))
        self.assertLess(data.index(b'<ErrorCode>'), data.index(b'<ListResultTotalSize>'))
        root = ET.fromstring(data)
        result = root[0][0]
        self.assertEqual(result.tag, '{' + CAS_NS + '}ListTitlesResponse')
        self.assertEqual(result.find('{' + CAS_NS + '}Titles')[0].text, '0001000141424344')
        for unsupported in (b'AccountId', b'DeviceToken', b'Prices', b'LicenseKind', b'Owned',
                            b'Contents', b'synthetic:test'):
            self.assertNotIn(unsupported, data)

    def test_only_explicit_attributes_are_serialized_and_escaped(self):
        title = CatalogTitle('00010001414243AB', 'synthetic:id', (
            CatalogAttribute('合成&属性', '<合成値>', 'synthetic:attribute-contract'),))
        data = response(titles=(title,))
        self.assertIn('合成&amp;属性'.encode(), data)
        self.assertIn('&lt;合成値&gt;'.encode(), data)
        self.assertIn(b'00010001414243ab', data)
        self.assertNotIn(b'TimeStamp', data)

    def test_explicit_empty_page_and_historical_total(self):
        self.assertIn(b'<ListResultTotalSize>0</ListResultTotalSize>',
                      response(total_size=0, titles=()))
        self.assertNotIn(b'<Titles>', response(total_size=100, titles=()))

    def test_unverified_missing_or_invalid_response_inputs_reject(self):
        for changes in ({'total_source_ref': ''}, {'total_size': True},
                        {'total_size': -1}, {'total_size': 0}, {'error_code': '123'},
                        {'timestamp': 'invented'}, {'titles': []},
                        {'titles': (CatalogTitle('bad', 'synthetic:id'),)},
                        {'titles': (CatalogTitle('0001000141424344', ''),)},
                        {'titles': (CatalogTitle('0001000141424344', 'synthetic:id', (
                            CatalogAttribute('x', 'y', ''),)),)},
                        {'titles': (CatalogTitle('0001000141424344', 'synthetic:id', (
                            CatalogAttribute('x', '\x00', 'synthetic:attr'),)),)}):
            with self.subTest(changes=changes), self.assertRaises(SoapContractError):
                response(**changes)

    def test_response_bound(self):
        attribute = CatalogAttribute('x', 'y' * 4096, 'synthetic:attr')
        title = CatalogTitle('0001000141424344', 'synthetic:id', (attribute,) * 40)
        with self.assertRaises(SoapContractError):
            response(titles=(title,))

    def test_oversized_multi_title_response_stops_processing_early(self):
        # This shape could expand to about 1 GiB if accumulated before checking.
        # Repetition shares fixture objects and keeps the test input itself small.
        attribute = CatalogAttribute('x', '界&' * 2048, 'synthetic:large-attribute')
        title = CatalogTitle('0001000141424344', 'synthetic:first-title',
                             (attribute,) * MAX_REPEATS)
        later = CatalogTitle('0001000141424345', 'synthetic:unreached-title',
                             (attribute,) * MAX_REPEATS)
        with patch.object(wii_shop_soap, '_source', wraps=wii_shop_soap._source) as checked:
            with self.assertRaisesRegex(SoapContractError, 'Response exceeds local byte bound'):
                response(total_size=MAX_REPEATS,
                         titles=(title,) + (later,) * (MAX_REPEATS - 1))
        # Failure must occur within the first title, without visiting its complete
        # attribute list or any later title's evidence/attributes.
        self.assertLess(checked.call_count, MAX_REPEATS)
        self.assertNotIn(('synthetic:unreached-title',),
                         [call.args for call in checked.call_args_list])


if __name__ == '__main__':
    unittest.main()
