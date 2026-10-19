"""Build an uninstalled modal clone with a default-hidden phone QR group."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_demae_qr_resource import qr_pixels, TEXT_PANES, TEXTURE

SOURCE_SHA = '9a58dadc0932aaf4c1fc38e3dfbb45fe5a0f6d4f16e612837d03bc76b987f344'
GROUP = 'JWC24_QR'
TEXT_NAMES = tuple(f'JWC24_QR_txt{i}' for i in range(3))


def encode_rgb565(pixels, width=224, height=224):
    """Encode an opaque, lossless black/white QR using GX 4x4 tiles."""
    if width % 4 or height % 4 or len(pixels) != width * height:
        raise ValueError('Invalid RGB565 dimensions')
    if any(p not in (0, 255) for p in pixels):
        raise ValueError('Expected binary QR pixels')
    header = struct.pack('>III', 0x20af30, 1, 12) + struct.pack('>II', 20, 0)
    header += struct.pack('>HHIIIIIIfBBBB', height, width, 4, 64, 0, 0, 0, 0, 0.0, 0, 0, 0, 0)
    tiled = bytearray()
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            for dy in range(4):
                for dx in range(4):
                    tiled.extend(b'\xff\xff' if pixels[(y+dy)*width+x+dx] else b'\0\0')
    return header.ljust(64, b'\0') + tiled


def blocks(data):
    if data[:4] != b'RLYT' or len(data) < 16:
        raise ValueError('Expected RLYT')
    p = int.from_bytes(data[12:14], 'big')
    out = []
    for _ in range(int.from_bytes(data[14:16], 'big')):
        n = int.from_bytes(data[p+4:p+8], 'big')
        if n < 8 or p+n > len(data):
            raise ValueError('Invalid section size')
        out.append(bytearray(data[p:p+n])); p += n
    if p != len(data):
        raise ValueError('Unexpected trailing layout bytes')
    return out


def named(block, name):
    block[12:28] = name.encode().ljust(16, b'\0')
    return block


def patch_layout(data):
    parts = blocks(data)
    byname = {bytes(b[12:28]).split(b'\0')[0].decode(): b for b in parts if b[:4] in (b'pan1', b'pic1', b'txt1')}
    if GROUP in byname:
        raise ValueError('QR group already exists')
    tx = next(b for b in parts if b[:4] == b'txl1')
    if int.from_bytes(tx[8:10], 'big') != 20:
        raise ValueError('Unexpected texture count')
    names = []
    for i in range(20):
        o = int.from_bytes(tx[12+i*8:16+i*8], 'big')+12
        names.append(bytes(tx[o:tx.index(0,o)]))
    names.append(TEXTURE.encode())
    nt = bytearray(b'txl1'+bytes(4)+struct.pack('>HH',21,0)+bytes(21*8))
    for i,n in enumerate(names):
        struct.pack_into('>I',nt,12+i*8,len(nt)-12);nt.extend(n+b'\0')
    nt.extend(bytes(-len(nt)%4));struct.pack_into('>I',nt,4,len(nt));parts[parts.index(tx)]=nt
    mt = next(b for b in parts if b[:4] == b'mat1')
    if int.from_bytes(mt[8:10], 'big') != 44:
        raise ValueError('Unexpected material count')
    offsets = [int.from_bytes(mt[12+i*4:16+i*4], 'big') for i in range(44)]
    src = bytearray(mt[offsets[29]:offsets[30]])
    if int.from_bytes(src[60:64],'big') & 15 != 1:
        raise ValueError('Unexpected icon material texture map')
    src[:20] = b'JWC24_QR_mat'.ljust(20,b'\0');struct.pack_into('>H',src,64,20)
    nm = bytearray(mt[:12]+bytes(45*4)+mt[188:])
    struct.pack_into('>H',nm,8,45)
    for i,o in enumerate(offsets):struct.pack_into('>I',nm,12+i*4,o+4)
    struct.pack_into('>I',nm,12+44*4,len(nm));nm.extend(src);struct.pack_into('>I',nm,4,len(nm));parts[parts.index(mt)]=nm
    group = named(bytearray(byname['RootPane']),GROUP)
    group[8] &= 254
    struct.pack_into('>3f',group,36,0,0,0)
    pic = named(bytearray(byname['dic_P_iconH00_00']),'JWC24_QR_pic')
    pic[8] |= 1;pic[9]=4;struct.pack_into('>2f',pic,36,-130,0);struct.pack_into('>3f',pic,48,0,0,0);struct.pack_into('>2f',pic,60,1,1);struct.pack_into('>2f',pic,68,224,224);struct.pack_into('>H',pic,92,44)
    added = [group,bytearray(b'pas1'+struct.pack('>I',8)),pic]
    for i,(_, (text,x,y,w,h,font)) in enumerate(TEXT_PANES.items()):
        textblock=named(bytearray(byname['dic_T_msg00']),f'JWC24_QR_txt{i}')
        if int.from_bytes(textblock[88:92],'big') !=116:raise ValueError('Unexpected text format')
        encoded=text.encode('utf-16-be')+b'\0\0'
        textblock=textblock[:116]+encoded;textblock.extend(bytes(-len(textblock)%4))
        textblock[8]|=1;textblock[9]=4
        struct.pack_into('>I',textblock,4,len(textblock));struct.pack_into('>HH',textblock,76,len(encoded),len(encoded))
        struct.pack_into('>2f',textblock,36,x,y);struct.pack_into('>2f',textblock,68,w,h);struct.pack_into('>4f',textblock,100,font,font,0,0)
        added.append(textblock)
    added.append(bytearray(b'pae1'+struct.pack('>I',8)))
    stack=[];last='';insert=None
    for i,b in enumerate(parts):
        if b[:4] in (b'pan1',b'pic1',b'txt1',b'wnd1'):
            last=bytes(b[12:28]).split(b'\0')[0].decode()
        elif b[:4]==b'pas1':stack.append(last)
        elif b[:4]==b'pae1':
            if not stack:raise ValueError('Unbalanced hierarchy')
            if stack[-1]=='dib_N_window_00':insert=i;break
            stack.pop()
    if insert is None:raise ValueError('Animated window hierarchy not found')
    parts[insert:insert]=added
    font_groups = [b for b in parts if b[:4] == b'grp1' and bytes(b[8:24]).split(b'\0')[0] == b'txt_T']
    if len(font_groups) != 1:
        raise ValueError('Expected one modal text font group')
    font_group = font_groups[0]
    if struct.unpack_from('>H', font_group, 24)[0] != 5 or len(font_group) != 108:
        raise ValueError('Unexpected modal text font group shape')
    # Startup binds the Japanese system font to every member of this group.
    font_group.extend(b''.join(name.encode('ascii').ljust(16, b'\0') for name in TEXT_NAMES))
    struct.pack_into('>H', font_group, 24, 8)
    struct.pack_into('>I', font_group, 4, len(font_group))
    result=bytearray(data[:16]+b''.join(parts));struct.pack_into('>I',result,8,len(result));struct.pack_into('>H',result,14,len(parts))
    blocks(result)
    return bytes(result)


def build(source,url):
    from libWiiPy.archive import U8Archive
    if hashlib.sha256(source).hexdigest()!=SOURCE_SHA:raise ValueError('Stock modal archive fingerprint mismatch')
    a=U8Archive();a.load(source)
    idx=a.file_name_list.index('dialogue_layout.brlyt');originals=dict(zip(a.file_name_list,a.file_data_list))
    a.file_data_list[idx]=patch_layout(a.file_data_list[idx]);a.u8_node_list[idx].size=len(a.file_data_list[idx])
    pixels,modules,scale=qr_pixels(url);texture=encode_rgb565(pixels)
    # Target timg directory by its existing texture children, not an unrelated same-name directory.
    directory=a.file_name_list.index('timg');insertion=a.u8_node_list[directory].size
    node=copy.copy(a.u8_node_list[-1]);node.type=0;node.name_offset=node.data_offset=0;node.size=len(texture)
    for entry in a.u8_node_list:
        if entry.type:
            if entry.size>=insertion:entry.size+=1
            if entry.data_offset>=insertion:entry.data_offset+=1
    a.u8_node_list.insert(insertion,node);a.file_name_list.insert(insertion,TEXTURE);a.file_data_list.insert(insertion,texture)
    result=a.dump();b=U8Archive();b.load(result)
    for name,value in originals.items():
        if name!='dialogue_layout.brlyt' and b.file_data_list[b.file_name_list.index(name)]!=value:raise ValueError('Original resource changed')
    if b.file_data_list[b.file_name_list.index(TEXTURE)]!=texture:raise ValueError('Texture verification failed')
    return result,pixels,{'modules_with_border':modules,'integer_scale':scale,'width':224,'height':224,'original_resources_preserved':len(originals)-1,'group_default_hidden':True,'parent_pane':'dib_N_window_00','texture_index':20,'material_index':44,'text_panes':list(TEXT_NAMES),'system_font_group':'txt_T'}


def main():
    from libWiiPy.archive import U8Archive
    from PIL import Image
    import zxingcpp
    from tools.asset_publication import publish_assets
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--content',type=Path,required=True);p.add_argument('--url-file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    private=Path(__file__).resolve().parents[1]/'private'
    if not args.output.resolve().is_relative_to(private.resolve()):p.error('Output must remain private')
    a=U8Archive();a.load(args.content.read_bytes());src=a.file_data_list[a.file_name_list.index('DtestDialog.arc')]
    snapshot=args.url_file.read_bytes();url=snapshot.decode('utf8').strip();result,pixels,report=build(src,url)
    preview=Image.frombytes('L',(224,224),pixels);decoded=zxingcpp.read_barcode(preview)
    if not decoded or decoded.text!=url:raise ValueError('QR decode verification failed')
    png=io.BytesIO();preview.save(png,format='PNG');report.update(stock_sha256=SOURCE_SHA,output_sha256=hashlib.sha256(result).hexdigest(),qr_decode_verified=True,scope='private uninstalled modal clone; native type hook unverified')
    publish_assets([(args.output,result),(args.output.with_suffix('.preview.png'),png.getvalue()),(args.output.with_suffix('.metadata.json'),json.dumps(report,indent=2).encode())],source_check=(args.url_file,snapshot))
    print('Built private default-hidden modal QR resource; no installation or launch')

if __name__=='__main__':main()
