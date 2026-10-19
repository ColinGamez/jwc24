"""Build a private Title archive with a native phone-ordering entry label."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_demae_qr_modal_resource import blocks
from tools.asset_publication import atomic_write

SOURCE_SHA = "22c8c7fdd19fe2a70bebf5a509ae578e647aa04b4a9a6e823e2e44fc204bd11e"
LABEL = "\u30b9\u30de\u30db\u3067\u6ce8\u6587"
PANE = "JWC24_PHONE_TXT"
LAYOUT = "01_m_layout.brlyt"
TEXTURE = "01_btn_demae_font.tpl"


def blank_label_texture(data):
    # This dedicated stock label uses one RGB5A3 palette. Zero alpha palette
    # entries suppress its old wording while retaining geometry and all indices.
    if data[:12] != bytes.fromhex("0020af30000000010000000c"):
        raise ValueError("Unexpected label TPL header")
    palette = struct.unpack_from(">I", data, 16)[0]
    count, unpacked, pad, fmt, offset = struct.unpack_from(">HBBII", data, palette)
    if (count, unpacked, pad, fmt, offset) != (240, 0, 0, 2, 32):
        raise ValueError("Unexpected stock label palette")
    result = bytearray(data)
    result[offset:offset + count*2] = bytes(count*2)
    return bytes(result)


def patch_layout(data, *, enable_native_label=False):
    sections = blocks(data)
    byname = {bytes(b[12:28]).split(b"\0")[0].decode(): b for b in sections
              if b[:4] in (b"pan1", b"pic1", b"txt1", b"wnd1", b"bnd1")}
    if PANE in byname or "01_B_btn_demae" not in byname:
        raise ValueError("Unexpected Title layout")
    picture = byname["01_P_btn_d_font"]
    if struct.unpack_from(">2f", picture, 68) != (200.0, 48.0):
        raise ValueError("Unexpected order label dimensions")
    text = bytearray(byname["01_T_win_post00"][:116])
    text[12:28] = PANE.encode().ljust(16, b"\0")
    text[8:12] = bytes((int(enable_native_label),4,255,0))
    struct.pack_into(">3f", text, 36, 0,0,0)
    struct.pack_into(">3f", text, 48, 0,0,0)
    struct.pack_into(">2f", text, 60, 1,1)
    struct.pack_into(">2f", text, 68, 200,48)
    encoded = LABEL.encode("utf-16-be") + b"\0\0"
    struct.pack_into(">HHHH", text, 76, len(encoded),len(encoded),0,0)
    text[84:88] = bytes((4,1,0,0))
    struct.pack_into(">I", text, 88,116)
    text[92:100] = bytes.fromhex("d86600ffd86600ff")
    struct.pack_into(">4f", text, 100,28,28,0,0)
    text.extend(encoded);text.extend(bytes(-len(text)%4))
    struct.pack_into(">I", text,4,len(text))
    index = sections.index(picture)+1
    if sections[index][:4] == b"pas1":
        raise ValueError("Stock label unexpectedly has children")
    sections[index:index] = [bytearray(b"pas1"+struct.pack(">I",8)),text,
                             bytearray(b"pae1"+struct.pack(">I",8))]
    # Title loader 0x800F4894 resolves txt_T and calls SetFont at 0x800F49A4
    # for every member (setter 0x80285EF0 writes TextBox+0xE4). Preserve stock
    # members and append this pane so it receives the same runtime font.
    groups = [b for b in sections if b[:4] == b"grp1" and
              bytes(b[8:24]).split(b"\0")[0] == b"txt_T"]
    if len(groups) != 1:
        raise ValueError("Expected unique native text font group")
    group = groups[0]
    expected_names = ("01_T_win_post00", "01_T_win_post01", "01_T_win_address",
                      "01_T_win_nama", "01_Tc_win_sama", "01_T_win_huriga", "01_T_win_TEL")
    expected_members = b"".join(name.encode().ljust(16, b"\0") for name in expected_names)
    if len(group) != 140 or struct.unpack_from(">H",group,24)[0] != 7 or bytes(group[28:]) != expected_members:
        raise ValueError("Unexpected native text font group membership")
    extended = bytearray(group + PANE.encode().ljust(16,b"\0"))
    struct.pack_into(">I",extended,4,len(extended))
    struct.pack_into(">H",extended,24,8)
    sections[sections.index(group)] = extended
    result = bytearray(data[:16]+b"".join(sections))
    struct.pack_into(">I",result,8,len(result));struct.pack_into(">H",result,14,len(sections))
    blocks(result)
    return bytes(result)


def build(source, *, enable_native_label=False):
    from libWiiPy.archive import U8Archive
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError("Stock Title archive fingerprint mismatch")
    archive=U8Archive();archive.load(source)
    original=list(archive.file_data_list)
    patches = [(LAYOUT, lambda data: patch_layout(data, enable_native_label=enable_native_label))]
    if enable_native_label:
        patches.append((TEXTURE,blank_label_texture))
    for name, patch in patches:
        i=archive.file_name_list.index(name)
        archive.file_data_list[i]=patch(original[i]);archive.u8_node_list[i].size=len(archive.file_data_list[i])
    output=archive.dump();verified=U8Archive();verified.load(output)
    if verified.file_name_list != archive.file_name_list:
        raise ValueError("Title inventory changed")
    for name,before,after in zip(archive.file_name_list,original,verified.file_data_list):
        if name not in (LAYOUT,TEXTURE) and before != after:
            raise ValueError("Unrelated Title resource changed")
    return output


def main():
    from libWiiPy.archive import U8Archive
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--enable-native-label",action="store_true", help="Experimental: replace stock label only after native font/render verification")
    args=parser.parse_args()
    private=Path(__file__).resolve().parents[1]/"private"
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error("Output must remain private")
    archive=U8Archive();archive.load(args.content.read_bytes())
    result=build(archive.file_data_list[archive.file_name_list.index("DtestTitle.arc")], enable_native_label=args.enable_native_label)
    atomic_write(args.output,result)
    print("Built private phone-ordering Title label; not installed or rendered")

if __name__ == "__main__":main()
