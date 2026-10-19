import struct
from pathlib import Path
import unittest
from tools.build_demae_phone_title_resource import build, blocks, LABEL, PANE, LAYOUT, TEXTURE


def archives(*, enable_native_label=True):
    from libWiiPy.archive import U8Archive
    source=Path("private/demae/frontend-v512/0002-00000002.app")
    if not source.exists():raise unittest.SkipTest("Private original fixture unavailable")
    content=U8Archive();content.load(source.read_bytes())
    original=content.file_data_list[content.file_name_list.index("DtestTitle.arc")]
    before=U8Archive();before.load(original)
    after=U8Archive();after.load(build(original, enable_native_label=enable_native_label))
    return original,before,after


class PhoneTitleResourceTests(unittest.TestCase):
    def test_preserves_panes_targets_and_animation_bytes(self):
        _,before,after=archives()
        assert before.file_name_list==after.file_name_list
        for name,old,new in zip(before.file_name_list,before.file_data_list,after.file_data_list):
            if name not in (LAYOUT,TEXTURE):assert old==new
        old=blocks(before.file_data_list[before.file_name_list.index(LAYOUT)])
        new=blocks(after.file_data_list[after.file_name_list.index(LAYOUT)])
        picindex=next(i for i,b in enumerate(old) if b[:4]==b"pic1" and b[12:28].startswith(b"01_P_btn_d_font"))
        assert new[:picindex+1]==old[:picindex+1]
        tail_before=old[picindex+1:]
        tail_after=new[picindex+4:]
        assert len(tail_before)==len(tail_after)
        for original,updated in zip(tail_before,tail_after):
            if original[:4]==b"grp1" and original[8:24].startswith(b"txt_T"):
                assert updated[8:24]==original[8:24]
                assert updated[28:140]==original[28:140]
                assert struct.unpack_from(">H",updated,24)[0]==8
                assert updated[140:156]==PANE.encode().ljust(16,b"\0")
                assert struct.unpack_from(">I",updated,4)[0]==156
            else:
                assert updated==original
        assert new[picindex+1][:4]==b"pas1"
        txt=new[picindex+2]
        assert txt[:4]==b"txt1" and txt[12:28].startswith(PANE.encode())
        assert txt[116:128] == bytes.fromhex("30b930de30db30676ce86587")
        assert tuple(map(ord,LABEL)) == (0x30B9,0x30DE,0x30DB,0x3067,0x6CE8,0x6587)
        assert struct.unpack_from(">HH",txt,80)==(0,0)
        assert new[picindex+3][:4]==b"pae1"


    def test_dedicated_texture_keeps_header_and_pixel_indices(self):
        original,before,after=archives()
        i=before.file_name_list.index(TEXTURE)
        old,new=before.file_data_list[i],after.file_data_list[i]
        assert old[:32]==new[:32] and old[512:]==new[512:]
        assert new[32:512]==bytes(480)
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            build(original[:-1])

    def test_default_retains_stock_label_until_native_render_verified(self):
        _,before,after=archives(enable_native_label=False)
        i=before.file_name_list.index(TEXTURE)
        assert before.file_data_list[i] == after.file_data_list[i]
        layout=after.file_data_list[after.file_name_list.index(LAYOUT)]
        text=next(b for b in blocks(layout) if b[:4]==b"txt1" and b[12:28].startswith(PANE.encode()))
        assert text[8] & 1 == 0

    def test_native_font_group_has_exact_original_members_plus_phone_text(self):
        _,_,after=archives()
        layout=after.file_data_list[after.file_name_list.index(LAYOUT)]
        groups=[b for b in blocks(layout) if b[:4]==b"grp1" and b[8:24].startswith(b"txt_T")]
        assert len(groups)==1
        group=groups[0]
        members=tuple(bytes(group[i:i+16]).split(b"\0")[0].decode() for i in range(28,len(group),16))
        assert members == ("01_T_win_post00", "01_T_win_post01", "01_T_win_address",
                           "01_T_win_nama", "01_Tc_win_sama", "01_T_win_huriga",
                           "01_T_win_TEL", "JWC24_PHONE_TXT")
        assert struct.unpack_from(">H",group,24)[0]==len(members)==8
