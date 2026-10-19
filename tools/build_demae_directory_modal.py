"""Assemble a private directory-modal payload for offline verification only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.asset_publication import publish_assets
from tools.demae_native_hook_support import OWNED_PADDING_START, OWNED_PADDING_END

NATIVE = {'native_row_resume': 0x8003C3C0, 'native_selected_shop': 0x80037B10,
          'native_shop_id': 0x800C0314, 'native_open_dynamic': 0x8001AD94,
          'native_size_dialog': 0x8001B4A0, 'native_modal_update': 0x80018724,
          'native_draw_list': 0x8003A62C, 'native_modal_draw': 0x80018B7C,
          'native_reset_row': 0x8003C6F4, 'native_job_exit': 0x800B75C4,
          'native_cleanup_resume': 0x800AA2E0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, default=Path('C:/devkitPro/devkitPPC/bin'))
    parser.add_argument('--output-prefix', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / 'tools/demae_directory_modal.review.s'
    outputs = [Path(str(args.output_prefix)+suffix) for suffix in ('.bin', '.elf', '.metadata.json')]
    if any(not p.resolve().is_relative_to((root/'private').resolve()) or p.exists() for p in outputs):
        parser.error('Outputs must be new private files')
    snapshot = source.read_bytes()
    with tempfile.TemporaryDirectory(prefix='directory-modal-') as temp:
        work = Path(temp)
        asm, obj, elf, binary = [work/name for name in ('source.s', 'source.o', 'source.elf', 'source.bin')]
        asm.write_bytes(snapshot)
        def run(name, *arguments):
            return subprocess.run([str(args.toolchain/('powerpc-eabi-'+name+'.exe')), *map(str, arguments)],
                                  check=True, capture_output=True, text=True).stdout
        run('as', '-mgekko', '-o', obj, asm)
        run('ld', f'-Ttext={hex(OWNED_PADDING_START)}',
            *[f'--defsym={name}={hex(address)}' for name, address in NATIVE.items()],
            '-e', 'directory_enter', '-o', elf, obj)
        run('objcopy', '-O', 'binary', '--only-section=.text', elf, binary)
        payload = binary.read_bytes()
        if not payload or len(payload) % 4 or len(payload) > OWNED_PADDING_END-OWNED_PADDING_START:
            raise ValueError('Payload exceeds reviewed owned padding')
        symbols = {}
        for line in run('nm', '-n', elf).splitlines():
            fields = line.split()
            if len(fields) == 3:
                symbols[fields[2]] = int(fields[0], 16)
        metadata = {'base_address': OWNED_PADDING_START, 'symbols': symbols,
                    'payload_sha256': hashlib.sha256(payload).hexdigest(),
                    'source_sha256': hashlib.sha256(snapshot).hexdigest(),
                    'native_sdk_mock_verification_required': True, 'installed': False}
        publish_assets([(outputs[0], payload), (outputs[1], elf.read_bytes()),
                        (outputs[2], json.dumps(metadata, indent=2).encode())], source_check=(source, snapshot))
    print(f'Assembled {len(payload)} private review bytes; no installation or launch')


if __name__ == '__main__':
    main()
