"""Convert an owner's Wii U OTP to a private preview profile's BootMii key file.

Layout references: Dolphin IOS/IOSC.cpp and ShowMiiVWiiKeys OTP.h/OTP.cpp.
No key bytes or console identifiers are printed. No NAND image is imported and
no source backup or existing credential file is overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path

PRIVATE = Path(__file__).resolve().parents[1]/'private'
DEFAULT_DOLPHIN_ID = bytes.fromhex('0403ac68')


def convert_otp(data):
    if not isinstance(data, bytes) or len(data) != 0x400:
        raise ValueError('Expected a 1024-byte Wii U OTP dump')
    for start, size in ((0x24, 4), (0x28, 0x1c), (0x58, 0x10), (0x30c, 0x3c)):
        part = data[start:start+size]
        if part in (bytes(size), b'\xff'*size):
            raise ValueError('OTP lacks populated vWii credential fields')
    if data[0x24:0x28] == DEFAULT_DOLPHIN_ID:
        raise ValueError('OTP contains the emulator default device ID')
    output = bytearray(0x400)
    label = b'JWC24 owner-supplied vWii OTP conversion\n'
    output[:len(label)] = label
    output[0x100:0x180] = data[:0x80]
    output[0x200:0x248] = data[0x300:0x348]
    output[0x274:0x284] = data[0x348:0x358]
    return bytes(output)


def prepare(otp, profile):
    otp, profile = otp.resolve(), profile.resolve()
    if not profile.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Credentials may only be prepared in a private preview profile')
    marker = json.loads((profile/'preview-profile.json').read_text())
    if marker.get('base_url') != 'https://127.0.0.1:18443' or marker.get('title_id') != '0001000248414241':
        raise ValueError('Profile is not the owned loopback Shop preview')
    target = (profile/'Wii/keys.bin').resolve()
    if not target.is_relative_to(profile) or target.exists():
        raise ValueError('Refusing to overwrite an existing credential file')
    if otp.stat().st_size != 0x400:
        raise ValueError('Expected a 1024-byte Wii U OTP dump')
    data = otp.read_bytes()
    converted = convert_otp(data)
    with target.open('xb') as handle:
        handle.write(converted)
    if target.read_bytes() != converted or hashlib.sha256(otp.read_bytes()).digest() != hashlib.sha256(data).digest():
        raise ValueError('Credential write or source verification failed')
    return {'credential_file_bytes': len(converted), 'source_unchanged': True,
            'nondefault_vwii_credentials_prepared': True, 'nand_image_imported': False,
            'credential_values_exported': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--otp', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=PRIVATE/'wii_shop/preview-profile')
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.otp, args.profile)))


if __name__ == '__main__':
    main()
