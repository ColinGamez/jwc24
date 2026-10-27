"""Guard original HFNJ descriptor/task preparation with explicit synthetic IO.

SDK initializer and local setters execute; context, storage, task database, clock
and key-import boundaries are mocked. No profile or original material is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.body_check_tasks import DatasetTaskConfiguration, prepare_dataset_task
from tools.verify_body_check_completion import _cpu
from tools.verify_body_check_header_crc import SOURCE_BYTES, SOURCE_SHA256

SDK = {0x801BC038: 'lookup', 0x801BB860: 'initializer', 0x801BCC58: 'vff_name',
       0x80138794: 'find_vff', 0x801BCCD4: 'create_vff', 0x801BBCF4: 'url',
       0x801BBA70: 'byte_flags', 0x801BBB10: 'interval', 0x801BBC58: 'server_interval',
       0x801BBF4C: 'priority', 0x801BBDF0: 'word_flags', 0x801BBFE8: 'opaque_word_1f8',
       0x801BBEA4: 'filename', 0x801BCDF4: 'keys', 0x801BC834: 'add', 0x801BC550: 'update'}


def fixture_configuration(**changes):
    """Explicit test fixture only; never an enabled production configuration."""
    values = dict(url='http://synthetic.invalid/WiiFitDataAll.enc', filename='WiiFitData.dat',
                  app_id=0x48464E4A, title_id=0x0001000148464E4A, title_version=256,
                  flags_byte=0xC0, flags_word=0xA, interval_minutes=1440,
                  server_interval_minutes=1440, priority=100, opaque_word_1f8=0,
                  signing_key_present=True, encryption_key_present=True,
                  evidence_ref='synthetic native-task comparison only')
    values.update(changes)
    return DatasetTaskConfiguration(**values)


class _TaskMachine:
    def __init__(self, source):
        self.cpu = _cpu(source)
        from tools.inspect_demae_references import sections
        from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_MSR
        self.r0, self.lr, self.pc = UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
        self.cpu.reg_write(UC_PPC_REG_MSR, self.cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
        self.static = [(base, base + size) for index, _, base, size in sections(source) if index >= 7]
        self.sda, self.desc, self.manager = 0x805A0840, 0x81000000, 0x81001000
        self.url, self.filename = 0x81002000, 0x81003000
        self.signing, self.encryption, self.work = 0x81004000, 0x81005000, 0x81300000
        self.stack_lo, self.stack_hi, self.stack, self.stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
        self.guard, self.inputs, self.globals = b'T' * 32, {}, {}
        self.instructions = 0
        self.events = []
        self.put(self.desc, bytes(0x22C))
        self.put(self.manager, bytes(0x40))
        self.put(self.work, bytes(0x5000))
        self.cpu.mem_write(self.stack_lo - 32, self.guard)
        self.cpu.mem_write(self.stack_hi, self.guard)
        for pointer, value in ((self.sda - 0x5D38, self.manager), (self.sda - 0x6180, self.work),
                               (self.sda - 0x617C, 1), (self.sda - 0x6128, 0)):
            self.global_word(pointer, value)
        self.cpu.mem_write(self.work + 0x3612, struct.pack('>HH', 120, 120))
        self.inputs[self.work] = bytes(self.cpu.mem_read(self.work, 0x5000))

    def reg(self, index):
        return self.cpu.reg_read(self.r0 + index)

    def word(self, pointer, value):
        self.cpu.mem_write(pointer, struct.pack('>I', value & 0xFFFFFFFF))

    def global_word(self, pointer, value):
        self.word(pointer, value)
        self.globals[pointer] = struct.pack('>I', value & 0xFFFFFFFF)

    def put(self, pointer, data):
        self.inputs[pointer] = bytes(data)
        self.cpu.mem_write(pointer - 32, self.guard)
        self.cpu.mem_write(pointer, data)
        self.cpu.mem_write(pointer + len(data), self.guard)

    def ret(self, value=0):
        self.cpu.reg_write(self.r0 + 3, value & 0xFFFFFFFF)
        self.cpu.reg_write(self.pc, self.cpu.reg_read(self.lr))

    def run(self, entry, callback, arguments=()):
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
        code_ranges = ((0x8031A310, 0x8031AC38), (0x8031BA7C, 0x8031BA98),
                       (0x8031BEA0, 0x8031BF7C), (0x801BB738, 0x801BC038),
                       (0x801BCC58, 0x801BCCD4),
                       (0x801AF000, 0x801AF618), (0x800C0000, 0x800D0000),
                       (0x80004000, 0x800066A0), (0x801AC608, 0x801AC668))

        def code(_cpu, address, _size, _context):
            self.instructions += 1
            if address in SDK:
                self.events.append(SDK[address])
            if callback(address):
                return
            if not any(lo <= address < hi for lo, hi in code_ranges):
                raise ValueError(f'Unexpected original Body Check task control flow at {address:08x}')

        def read(_cpu, _access, address, size, _value, _context):
            ranges = [(pointer, pointer + len(data)) for pointer, data in self.inputs.items()]
            ranges += self.static + [(self.stack_lo, self.stack_hi)]
            ranges += [(pointer, pointer + len(data)) for pointer, data in self.globals.items()]
            if not any(lo <= address < address + size <= hi for lo, hi in ranges):
                raise ValueError('Original Body Check task read exceeds fixture/static bounds')

        def write(_cpu, _access, address, size, _value, _context):
            ranges = [(self.desc, self.desc + 0x22C), (self.manager + 0x24, self.manager + 0x38),
                      (self.stack_lo, self.stack_hi)]
            if not any(lo <= address < address + size <= hi for lo, hi in ranges):
                raise ValueError('Unexpected original Body Check task write')

        hooks = [self.cpu.hook_add(UC_HOOK_CODE, code), self.cpu.hook_add(UC_HOOK_MEM_READ, read),
                 self.cpu.hook_add(UC_HOOK_MEM_WRITE, write)]
        for register, value in {1: self.stack, 2: 0x805A2B20, 13: self.sda}.items():
            self.cpu.reg_write(self.r0 + register, value)
        for register, value in enumerate(arguments, 3):
            self.cpu.reg_write(self.r0 + register, value)
        self.cpu.reg_write(self.lr, self.stop)
        try:
            self.cpu.emu_start(entry, self.stop, count=200000, timeout=2000000)
        finally:
            for hook in hooks:
                self.cpu.hook_del(hook)
        if self.cpu.reg_read(self.pc) != self.stop:
            raise ValueError('Original Body Check task execution budget exceeded')
        for pointer, data in self.inputs.items():
            if (bytes(self.cpu.mem_read(pointer - 32, 32)) != self.guard
                    or bytes(self.cpu.mem_read(pointer + len(data), 32)) != self.guard):
                raise ValueError('Original Body Check task object guard changed')
            if pointer not in (self.desc, self.manager) and bytes(self.cpu.mem_read(pointer, len(data))) != data:
                raise ValueError('Original Body Check task immutable input changed')
        if (bytes(self.cpu.mem_read(self.stack_lo - 32, 32)) != self.guard
                or bytes(self.cpu.mem_read(self.stack_hi, 32)) != self.guard
                or any(bytes(self.cpu.mem_read(pointer, len(data))) != data for pointer, data in self.globals.items())):
            raise ValueError('Original Body Check task stack/global guard changed')
        return self.reg(3)


def verify_task_preparation(source, configuration, *, existing_task, outcomes=None):
    """Compare a complete original caller/local-SDK path with a local image.

    Outcomes are explicit synthetic external results; defaults select the normal
    fixture path. Actual IOS/task database acceptance and storage never execute.
    """
    expected = prepare_dataset_task(configuration, existing_task=existing_task)
    values = {'lookup': 0 if existing_task is not None else -13, 'find_vff': -12,
              'create_vff': 0, 'keys': 0, 'add': 0, 'update': 0}
    if outcomes is not None:
        if (type(outcomes) is not dict or not set(outcomes) <= set(values)
                or any(type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                       for value in outcomes.values())):
            raise ValueError('Expected bounded explicit external task results')
        values.update(outcomes)
    if existing_task is not None and values['lookup'] == -13:
        raise ValueError('A missing-task fixture cannot also supply an existing task image')
    c, m = configuration, _TaskMachine(source)
    m.put(m.url, c.url.encode('ascii') + b'\0')
    m.put(m.filename, c.filename.encode('ascii') + b'\0')
    m.put(m.signing, b'S' * 256)
    m.put(m.encryption, b'E' * 16)
    key_addresses = (m.signing if c.signing_key_present else 0,
                     m.encryption if c.encryption_key_present else 0)
    # Execute the original descriptor constructor using explicit caller inputs.
    for offset, value in ((8, c.flags_word), (12, m.filename), (16, key_addresses[0]), (20, key_addresses[1])):
        m.word(m.stack + offset, value)
    m.run(0x8031A9A4, lambda _address: False,
          (m.desc, m.url, c.flags_byte, c.interval_minutes, 1,
           c.server_interval_minutes, c.priority, c.opaque_word_1f8))
    create_sizes, key_calls, initializer_kinds, diagnostic_inputs = [], 0, [], []

    def callback(address):
        nonlocal key_calls
        if address == 0x801BB860:
            initializer_kinds.append(m.reg(4))
        if address == 0x8031BA7C and m.reg(4):
            diagnostic_inputs.append(m.reg(4))
        if address == 0x801BC038:
            if values['lookup'] == 0:
                if existing_task is None:
                    raise ValueError('A reported existing task needs an explicit task image')
                m.cpu.mem_write(m.reg(3), existing_task)
            m.ret(values['lookup'])
        elif address == 0x80138430:
            path = f'/title/{c.title_id >> 32:08x}/{c.title_id & 0xFFFFFFFF:08x}/data'.encode() + b'\0'
            if not m.stack_lo <= m.reg(3) < m.reg(3) + len(path) <= m.stack_hi:
                raise ValueError('SDK context path destination exceeds synthetic stack')
            m.cpu.mem_write(m.reg(3), path)
            m.ret()
        elif address == 0x801AEE44:
            m.ret(c.app_id)
        elif address == 0x801AEE90:
            m.ret(c.title_version)
        elif address == 0x80138794:
            m.ret(values['find_vff'])
        elif address == 0x801BCCD4:
            create_sizes.append(m.reg(4))
            m.ret(values['create_vff'])
        elif address == 0x801BCDF4:
            if (m.reg(3), m.reg(4)) != key_addresses:
                raise ValueError('Original key-import arguments differ from explicit predicates')
            key_calls += 1
            m.ret(values['keys'])
        elif address == 0x801BC834:
            m.ret(values['add'])
        elif address == 0x801BC550:
            m.ret(values['update'])
        elif address == 0x801BB134:
            m.ret(-1)  # External clock unavailable; no task-table time is written.
        else:
            return False
        return True

    returned = m.run(0x8031A5A0, callback, (m.desc,))
    actual = bytes(m.cpu.mem_read(m.desc + 0x24, 0x200))
    manager = bytearray(0x40)
    if diagnostic_inputs:
        struct.pack_into('>I', manager, 0x24, diagnostic_inputs[-1])
    if bytes(m.cpu.mem_read(m.manager, 0x40)) != manager:
        raise ValueError('Original task preparation changed unrelated manager state')
    if returned == 0 and actual != expected.data:
        raise ValueError('Original local SDK task image differs from independent preparation')
    if (returned == 0 and (initializer_kinds != ([] if existing_task is not None else [3])
                          or create_sizes != ([32768] if values['find_vff'] == -12 else [])
                          or key_calls != int(expected.key_import_requested))):
        raise ValueError('Original task preparation boundary calls differ from expected contract')
    return {'native_return': returned, 'events': m.events, 'instructions': m.instructions,
            'initializer_kinds': initializer_kinds, 'vff_create_sizes': create_sizes,
            'key_import_calls': key_calls, 'local_task_image_matches': actual == expected.data,
            'original_initializer_executed': bool(initializer_kinds),
            'original_local_setter_entries': [event for event in m.events if event in
                ('url', 'byte_flags', 'interval', 'server_interval', 'priority', 'word_flags',
                 'opaque_word_1f8', 'filename')],
            'descriptor_constructor_and_complete_preparation_caller_executed': True,
            'context_storage_task_database_clock_and_key_import_mocked': True,
            'immutable_inputs_and_object_stack_global_guards_verified': True,
            'task_registration_or_persistence_verified': False,
            'signature_trust_scheduler_or_native_ui_verified': False}


def verify_original_descriptor(source, *, allocation_succeeds=True):
    """Execute the original resource/allocation/descriptor caller separately."""
    if type(allocation_succeeds) is not bool:
        raise ValueError('Expected an explicit allocation-result predicate')
    m = _TaskMachine(source)
    owner, resources, heap = 0x81400000, 0x81401000, 0x81402000
    m.put(owner, bytes(0x48)); m.put(resources, bytes(8)); m.put(heap, bytes(8))
    m.global_word(m.sda - 0x6040, owner)
    m.global_word(m.sda - 0x6078, heap)
    m.word(owner + 0x44, resources)
    m.word(heap + 4, 0x12340000)
    # Update immutable expected context after deliberate fixture initialization.
    m.inputs[owner] = bytes(m.cpu.mem_read(owner, 0x48))
    m.inputs[heap] = bytes(m.cpu.mem_read(heap, 8))
    key_calls, allocation_calls, constructor_calls = [], [], []

    def callback(address):
        if address == 0x8031A9A4:
            constructor_calls.append(address)
        if address == 0x8022F380:
            name = bytes(m.cpu.mem_read(m.reg(4), 12)).split(b'\0', 1)[0]
            if m.reg(3) != resources or m.reg(5) != 0 or name not in (b'signkey.key', b'enckey.key'):
                raise ValueError('Unexpected original key-resource request')
            key_calls.append(name)
            m.ret(m.signing if name == b'signkey.key' else m.encryption)
        elif address == 0x800B5EA0:
            allocation_calls.append((m.reg(3), m.reg(4), m.reg(5)))
            m.ret(m.desc if allocation_succeeds else 0)
        else:
            return False
        return True

    returned = m.run(0x8031BEA0, callback, (m.manager,))
    data = bytes(m.cpu.mem_read(m.desc, 0x22C))
    if (key_calls != [b'signkey.key', b'enckey.key']
            or allocation_calls != [(0x22C, 0x12340000, 4)]):
        raise ValueError('Original descriptor resource/allocation intent differs')
    manager = bytearray(0x40)
    struct.pack_into('>III', manager, 0x2C, m.desc if allocation_succeeds else 0, m.signing, m.encryption)
    if (returned != (m.desc if allocation_succeeds else 0)
            or bytes(m.cpu.mem_read(m.manager, 0x40)) != manager
            or len(constructor_calls) != int(allocation_succeeds)):
        raise ValueError('Original descriptor manager state differs')
    if allocation_succeeds:
        if (data[0x12] != 0xC0 or struct.unpack_from('>HHH', data, 12) != (1440, 1440, 100)
                or struct.unpack_from('>I', data, 20)[0] != 10
                or struct.unpack_from('>I', data, 24)[0] != 0):
            raise ValueError('Original descriptor constants differ')
    return {'allocation_succeeds': allocation_succeeds, 'resource_lookup_calls': len(key_calls),
            'descriptor_allocation_bytes': 0x22C, 'descriptor_allocation_alignment': 4,
            'native_flags_byte': 0xC0 if allocation_succeeds else None,
            'native_flags_word': 0xA if allocation_succeeds else None,
            'native_interval_minutes': 1440 if allocation_succeeds else None,
            'native_server_interval_minutes': 1440 if allocation_succeeds else None,
            'native_priority': 100 if allocation_succeeds else None,
            'opaque_descriptor_word_18': 0 if allocation_succeeds else None,
            'original_descriptor_constructor_executed': bool(constructor_calls),
            'original_resource_allocation_descriptor_caller_executed': True,
            'resource_lookup_and_allocation_mocked': True,
            'original_key_bodies_read': False, 'task_registered': False,
            'instructions': m.instructions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='explicit private original decoded HFNJ v256 application')
    args = parser.parse_args(argv)
    try:
        with args.source.open('rb') as stream:
            source = stream.read(SOURCE_BYTES + 1)
        configuration = fixture_configuration()
        existing = bytearray(prepare_dataset_task(configuration, existing_task=None).data)
        struct.pack_into('>H', existing, 0, 5)
        report = {'source_sha256': SOURCE_SHA256,
                  'descriptor_cases': [verify_original_descriptor(source, allocation_succeeds=value)
                                       for value in (True, False)],
                  'preparation_cases': [verify_task_preparation(source, configuration, existing_task=value)
                                        for value in (None, bytes(existing))],
                  'synthetic_inputs_only': True, 'native_io_or_registration_verified': False}
    except (OSError, ValueError, ImportError):
        print('Body Check task comparison input or optional dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
