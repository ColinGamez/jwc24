"""Prepare private content2 with a hidden QR modal; does not enable its hook."""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.asset_publication import atomic_write

SOURCE_SHA = 'e2d26e503f8308f51028005291457b4a7b8d605553ac113204ebe54d1fde55eb'


def build_content(source, modal, title=None):
    from libWiiPy.archive import U8Archive
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Stock resource content fingerprint mismatch')
    replacement = U8Archive()
    replacement.load(modal)
    if 'jwc24_phone_qr.tpl' not in replacement.file_name_list:
        raise ValueError('Dedicated QR texture is missing')
    layout = replacement.file_data_list[replacement.file_name_list.index('dialogue_layout.brlyt')]
    if b'JWC24_QR\0' not in layout:
        raise ValueError('Dedicated QR group is missing')
    archive = U8Archive()
    archive.load(source)
    original = list(archive.file_data_list)
    replacements = {archive.file_name_list.index('DtestDialog.arc'): modal}
    if title is not None:
        title_archive = U8Archive()
        title_archive.load(title)
        from tools.build_demae_phone_title_resource import LABEL, LAYOUT
        title_layout = title_archive.file_data_list[title_archive.file_name_list.index(LAYOUT)]
        if LABEL.encode('utf-16-be') + b'\0\0' not in title_layout:
            raise ValueError('Phone ordering entry label is missing')
        replacements[archive.file_name_list.index('DtestTitle.arc')] = title
    for position, replacement_data in replacements.items():
        archive.file_data_list[position] = replacement_data
        archive.u8_node_list[position].size = len(replacement_data)
    result = archive.dump()
    verified = U8Archive()
    verified.load(result)
    if verified.file_name_list != archive.file_name_list:
        raise ValueError('Resource file inventory changed')
    for index, value in enumerate(original):
        expected = replacements.get(index, value)
        if verified.file_data_list[index] != expected:
            raise ValueError('Unexpected resource replacement')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--modal', type=Path, required=True)
    parser.add_argument('--title', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error('Output must remain private')
    atomic_write(args.output, build_content(args.source.read_bytes(), args.modal.read_bytes(),
                                          args.title.read_bytes() if args.title else None))
    print('Prepared private QR resource content; native hook remains disabled; no installation')


if __name__ == '__main__':
    main()
