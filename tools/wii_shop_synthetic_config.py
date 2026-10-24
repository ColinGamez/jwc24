"""Minimal indexed config records for the fingerprinted Shop v21 harness.

This builds emulated cache state, not a complete SYSCONF file. It never reads or
writes a console's configuration. Native config initialization remains untested.
"""
from dataclasses import dataclass
import struct


EULA_QUERY = 0x801fe1c0
CRITICAL_SECTION_CALLS = (0x801c8d30, 0x801c8d70)
NATIVE_QUERY_RANGES = (
    (0x801fe1c0, 0x801fe1fc),  # EULA getter
    (0x801fd180, 0x801fd280),  # Indexed bool lookup
    (0x801fc650, 0x801fc7d0),  # Record parser
    (0x800043c4, 0x80004750),  # Native copy/clear helpers
)


@dataclass(frozen=True)
class SyntheticEulaConfig:
    value: int = 1
    present: bool = True
    lookup_ready: bool = True
    record_type: int = 0xe0

    def __post_init__(self):
        if type(self.value) is not int or not 0 <= self.value <= 255:
            raise ValueError('Expected synthetic config byte')
        if type(self.present) is not bool or type(self.lookup_ready) is not bool:
            raise ValueError('Expected synthetic config flags')
        if type(self.record_type) is not int or self.record_type not in (0, 0x60, 0xe0):
            raise ValueError('Expected supported synthetic record type')

    def install(self, cpu):
        """Install an indexed IPL.EULA fixture in emulated RAM only."""
        def word(address):
            return int.from_bytes(cpu.mem_read(address, 4), 'big')

        name_pointer = word(0x8034bbd0)
        if (word(0x8034bbd4) != 7
                or bytes(cpu.mem_read(name_pointer, 9)) != b'IPL.EULA\0'):
            raise ValueError('Native config key 7 is not IPL.EULA')

        base = 0x8046f620
        cpu.mem_write(base, bytes(0x1200))
        # Lookup code uses an index counted backward from the cached table end.
        # Its entry locates a U16 offset that locates the serialized record.
        cpu.mem_write(0x80361074, struct.pack('>I', 8))
        cpu.mem_write(0x80361078, struct.pack('>I', 0x1000 if self.lookup_ready else 0))
        cpu.mem_write(base+0x1000-2*7, struct.pack('>H', 0x100 if self.present else 0))
        cpu.mem_write(base+0x100, struct.pack('>H', 0x200))
        name = b'IPL.EULA'
        record = bytes([self.record_type | (len(name)-1)])+name+bytes([self.value])
        cpu.mem_write(base+0x200, record)
