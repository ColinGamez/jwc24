"""Read-only Windows MEM1 capture from an already running Dolphin process.

Matches two native executable anchors before saving RAM beneath private/.
Does not inject code, change registers, dismiss UI or write process memory.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.inspect_demae_references import sections


def capture(pid, source, output):
    private = Path(__file__).resolve().parents[1] / 'private'
    output = Path(output).resolve()
    if not output.is_relative_to(private.resolve()) or output.exists():
        raise ValueError('Capture must be a new private file')
    class MemoryInfo(c.Structure):
        _fields_ = [('base', c.c_void_p), ('allocation_base', c.c_void_p),
                    ('allocation_protect', w.DWORD), ('partition', w.WORD),
                    ('size', c.c_size_t), ('state', w.DWORD), ('protect', w.DWORD), ('kind', w.DWORD)]
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(MemoryInfo), c.c_size_t]
    kernel.VirtualQueryEx.restype = c.c_size_t
    kernel.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
    kernel.ReadProcessMemory.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise c.WinError(c.get_last_error())
    def read(address, length):
        buffer = c.create_string_buffer(length)
        count = c.c_size_t()
        if not kernel.ReadProcessMemory(handle, address, buffer, length, c.byref(count)) or count.value != length:
            raise OSError('Incomplete read-only process memory read')
        return buffer.raw
    def native(address, length):
        for _, offset, base, size in sections(source):
            if base <= address and address+length <= base+size:
                return source[offset+address-base:offset+address-base+length]
        raise ValueError('Anchor outside native executable')
    anchors = [(0x4000, native(0x80004000, 64)), (0x1A3D80, native(0x801A3D80, 64))]
    try:
        address = 0
        candidates = []
        while address < 0x7FFFFFFFFFFF:
            info = MemoryInfo()
            if not kernel.VirtualQueryEx(handle, address, c.byref(info), c.sizeof(info)):
                break
            base = info.base or 0
            if info.size == 0:
                break
            if (info.state == 0x1000 and 0x1800000 <= info.size <= 0x4000000
                    and not info.protect & (0x100 | 0x01)):
                try:
                    if all(read(base+offset, len(expected)) == expected for offset, expected in anchors):
                        candidates.append(base)
                except OSError:
                    pass
            address = base+info.size
        if not candidates:
            raise ValueError('No readable MEM1 mapping matches both executable anchors')
        data = read(candidates[0], 0x1800000)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        metadata = {'pid': pid, 'mem1_bytes': len(data), 'matching_mappings': len(candidates),
                    'sha256': hashlib.sha256(data).hexdigest(), 'read_only_capture': True}
        output.with_suffix('.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        return metadata
    finally:
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.pid, args.source.read_bytes(), args.output)))
