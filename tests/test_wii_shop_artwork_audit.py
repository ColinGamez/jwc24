import unittest

from tools.audit_wii_shop_artwork import compare_files


class ArtworkProvenanceTests(unittest.TestCase):
    def test_matching_names_are_not_matching_content(self):
        rows = compare_files({'/button.gif': b'changed'}, [('button.gif', b'original')])
        self.assertEqual(rows[0]['installed_byte_matches'], [])

    def test_identical_bytes_match_even_when_names_differ(self):
        rows = compare_files({'/web/button.gif': b'original'},
                             [('native-button.gif', b'original'), ('alias.gif', b'original')])
        self.assertEqual(rows[0]['installed_byte_matches'], ['alias.gif', 'native-button.gif'])

    def test_empty_directory_entries_are_not_provenance(self):
        rows = compare_files({'/empty': b''}, [('directory', b'')])
        self.assertEqual(rows[0]['installed_byte_matches'], [])
