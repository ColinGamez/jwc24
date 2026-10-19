import struct
import unittest
from test_demae_qr_modal_resource import fixture
from tools.build_demae_qr_modal_resource import blocks
from tools.build_demae_directory_resource import patch_layout, GROUP, BODY


class DirectoryResourceTests(unittest.TestCase):
    def test_shared_message_and_original_sections_remain_unchanged(self):
        before = blocks(fixture())
        after = blocks(patch_layout(fixture()))
        for section in before:
            if section[:4] != b'grp1':
                self.assertIn(section, after)
        panes = {bytes(b[12:28]).split(b'\0')[0].decode(): b for b in after if b[:4] in (b'pan1', b'txt1')}
        self.assertEqual(panes[GROUP][8] & 1, 0)
        self.assertEqual(panes[BODY][9], 4)
        self.assertEqual(struct.unpack_from('>2f', panes[BODY], 60), (1, 1))
        self.assertEqual(struct.unpack_from('>2f', panes[BODY], 100), (18, 18))
        font = next(b for b in after if b[:4] == b'grp1')
        old_font = next(b for b in before if b[:4] == b'grp1')
        self.assertEqual(font[28:108], old_font[28:108])
        self.assertEqual(struct.unpack_from('>H', font, 24)[0], 6)
        self.assertEqual(bytes(font[-16:]).split(b'\0')[0], BODY.encode())

    def test_hidden_directory_group_belongs_to_animated_window(self):
        stack, last, parent = [], '', None
        for section in blocks(patch_layout(fixture())):
            if section[:4] in (b'pan1', b'txt1', b'pic1'):
                last = bytes(section[12:28]).split(b'\0')[0].decode()
                if last == GROUP:
                    parent = tuple(stack)
            elif section[:4] == b'pas1':
                stack.append(last)
            elif section[:4] == b'pae1':
                stack.pop()
        self.assertEqual(parent, ('RootPane', 'dib_N_window_00'))
        self.assertEqual(stack, [])

    def test_double_patch_rejected(self):
        with self.assertRaises(ValueError):
            patch_layout(patch_layout(fixture()))
