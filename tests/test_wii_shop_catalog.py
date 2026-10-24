import unittest

from jwc24.wii_shop_catalog import parse_listing


def listing(name, href=None, size='123'):
    return ('<table id="files"><tr><td>-</td><td><a href="'+(href or name)+'">'+name+
            '</a></td><td>'+size+'</td><td></td><td>wad</td><td>2026-10-24</td></tr></table>')


class ShopCatalogTests(unittest.TestCase):
    def test_japan_browse_metadata_does_not_invent_title_id_or_install_support(self):
        r = parse_listing(listing('Test (Japan) (NES) (Virtual Console).wad'), 'T')[0]
        self.assertTrue(r['japan_browse_candidate'])
        self.assertEqual(r['name'], 'Test')
        self.assertIsNone(r['title_id'])
        self.assertFalse(r['install_supported'])
        self.assertEqual(r['listed_bytes'], 123)

    def test_regions_dlc_and_system_rows_do_not_become_japan_games(self):
        for name in ('Test (USA) (WiiWare).wad', 'Test (Japan) (WiiWare) (DLC).wad', 'IOS (Japan).wad'):
            self.assertFalse(parse_listing(listing(name), 'T')[0]['japan_browse_candidate'])

    def test_demo_is_retained_as_distinct_metadata(self):
        self.assertTrue(parse_listing(listing('Test (Japan) (Demo) (WiiWare).wad'), 'T')[0]['is_demo'])

    def test_real_listing_leading_filename_space_is_preserved(self):
        r = parse_listing(listing(' A Test (Japan) (WiiWare).wad',
                                 '%20A%20Test%20%28Japan%29%20%28WiiWare%29.wad'), 'A')[0]
        self.assertTrue(r['filename'].startswith(' '))
        self.assertEqual(r['name'], 'A Test')

    def test_external_parent_and_query_links_rejected(self):
        for href in ('https://other.example/test.wad', '../test.wad', 'test.wad?token=secret'):
            with self.assertRaises(ValueError):
                parse_listing(listing('test.wad', href), 'T')

    def test_changed_listing_bad_size_and_bucket_fail_closed(self):
        for html, bucket in (('<html>changed</html>', 'T'), (listing('test.wad', size='?'), 'T'),
                              (listing('test.wad'), '_Dangerous')):
            with self.assertRaises(ValueError):
                parse_listing(html, bucket)
