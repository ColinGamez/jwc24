"""Original HAGJ v7 task caller and reader-loop checks in synthetic RAM only.

SDK, storage, allocator and calendar boundaries are explicitly mocked. Original
caller branches and integer filename formatting execute. This never registers
a task, reads a profile, opens a network connection or changes source software.
"""
from __future__ import annotations

import hashlib
import struct

from tools.verify_news_native import SOURCE_SHA256

_SDK = {
    0x8007D578: 'get_task_mine', 0x8007C49C: 'get_id',
    0x8007E714: 'get_vf_name', 0x8007C25C: 'init_task',
    0x8007E8B8: 'create_vf', 0x8007CB74: 'set_url',
    0x8007C918: 'set_server_interval', 0x8007D3A0: 'set_subtask_parameters',
    0x8007C538: 'set_priority', 0x8007CD34: 'set_flags',
    0x8007C640: 'set_interval', 0x8007CA20: 'set_retry_margin',
    0x8007CEA0: 'set_filename', 0x8007D1A4: 'set_count',
    0x8007E0AC: 'add_task', 0x8007DB14: 'update_task',
    0x8007DF08: 'delete_task', 0x8007CD28: 'get_url',
    0x8007C88C: 'get_interval', 0x8007D000: 'get_subtask_filename',
    0x8007D508: 'post_commit_task_helper',
}


class _Machine:
    def __init__(self, source):
        if (not isinstance(source, bytes) or len(source) > 4 * 1024 * 1024
                or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
            raise ValueError('Japanese News v7 executable fingerprint mismatch')
        from tools.inspect_demae_references import sections
        from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
        from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
        self.reg0, self.lr, self.pc = UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
        self.cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
        self.cpu.mem_map(0x80000000, 0x1800000)
        self.source_ranges = []
        for _, offset, address, size in sections(source):
            self.cpu.mem_write(address, source[offset:offset + size])
            self.source_ranges.append((address, address + size))
        self.job, self.url, self.output = 0x81000000, 0x81001000, 0x81002000
        self.stack_lo, self.stack_hi, self.stack = 0x817D0000, 0x817E1000, 0x817E0000
        self.stop, self.guard = 0x817FF000, b'NEWS-TASK-GUARD!!' * 2
        self.cpu.mem_write(self.job, bytes(0x1B8))
        self.allocations = []
        self.protect(self.job, 0x1B8)
        self.protect(self.stack_lo, self.stack_hi - self.stack_lo)
        self.cpu.reg_write(self.reg0 + 1, self.stack)
        self.cpu.reg_write(self.reg0 + 2, 0x80360460)
        self.cpu.reg_write(self.reg0 + 13, 0x8035E740)
        self.instructions = 0

    def protect(self, pointer, length):
        self.cpu.mem_write(pointer - len(self.guard), self.guard)
        self.cpu.mem_write(pointer + length, self.guard)
        self.allocations.append((pointer, pointer + length))

    def reg(self, index):
        return self.cpu.reg_read(self.reg0 + index)

    def word(self, pointer, value):
        self.cpu.mem_write(pointer, struct.pack('>I', value & 0xFFFFFFFF))

    def stub_return(self, value=0):
        self.cpu.reg_write(self.reg0 + 3, value & 0xFFFFFFFF)
        self.cpu.reg_write(self.pc, self.cpu.reg_read(self.lr))

    def cstring(self, pointer, maximum=256):
        for lo, hi in self.allocations + self.source_ranges:
            if lo <= pointer < hi:
                value = bytes(self.cpu.mem_read(pointer, min(maximum, hi - pointer)))
                end = value.find(b'\0')
                if end >= 0:
                    return value[:end]
                break
        raise ValueError('Native News task string exceeded its fixture bounds')

    def run(self, entry, until, callback, allowed_code, allowed_global_writes=(), allowed_global_reads=()):
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

        def code(_cpu, address, _size, _context):
            self.instructions += 1
            if callback(address):
                return
            if not any(lo <= address < hi for lo, hi in allowed_code):
                raise ValueError('Unexpected native News task control flow')

        def read(_cpu, _access, address, size, _value, _context):
            if not any(lo <= address < address + size <= hi
                       for lo, hi in self.allocations + self.source_ranges + list(allowed_global_reads)):
                raise ValueError('Native News task read exceeds fixture bounds')

        def write(_cpu, _access, address, size, _value, _context):
            if not any(lo <= address < address + size <= hi
                       for lo, hi in self.allocations + list(allowed_global_writes)):
                raise ValueError('Native News task write exceeds fixture bounds')

        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, write)
        self.cpu.reg_write(self.lr, self.stop)
        self.cpu.emu_start(entry, until, count=200000)
        if self.cpu.reg_read(self.pc) != until:
            raise ValueError('Native News task instruction cap reached')
        for lo, hi in self.allocations:
            if (bytes(self.cpu.mem_read(lo - len(self.guard), len(self.guard))) != self.guard
                    or bytes(self.cpu.mem_read(hi, len(self.guard))) != self.guard):
                raise ValueError('Native News task fixture guard changed')


def verify_task_registration(source, *, interval=30, count=240, existing=False,
                             fail_service=None):
    """Execute original task caller with explicit synthetic SDK responses.

    The descriptor enables only News task type 2. The supplied SDK lookup says
    either no task (-13) or synthetic task ID 5 with a matching URL/interval.
    Captured setter arguments prove caller intent, not SDK/NAND acceptance.
    """
    if (type(interval) is not int or not 1 <= interval <= 65535
            or type(count) is not int or not 0 <= count <= 65535
            or type(existing) is not bool
            or fail_service is not None and fail_service not in set(_SDK.values())):
        raise ValueError('Expected bounded synthetic News task settings')
    machine = _Machine(source)
    cpu, job = machine.cpu, machine.job
    url = b'http://synthetic.invalid/news.bin'
    cpu.mem_write(machine.url, url + b'\0')
    machine.protect(machine.url, len(url) + 1)
    machine.protect(machine.output, 4)
    cpu.mem_write(job + 4, struct.pack('>HH', 2, 0))
    machine.word(job + 0x148, machine.url)
    machine.word(job + 0x150, 0x3A0000)
    events, parameters, filenames = [], {}, []
    sdk_failure_seen = False

    def callback(address):
        nonlocal sdk_failure_seen
        if address in _SDK:
            name = _SDK[address]
            events.append(name)
            if name == fail_service and not sdk_failure_seen:
                sdk_failure_seen = True
                machine.stub_return(-3)
                return True
            if name == 'get_task_mine':
                machine.stub_return(0 if existing else -13)
                return True
            if name == 'get_id':
                cpu.mem_write(machine.reg(4), struct.pack('>H', 5))
            elif name == 'get_vf_name':
                cpu.mem_write(machine.reg(4), b'synthetic.vff\0')
            elif name == 'get_url':
                cpu.mem_write(machine.reg(4), url + b'\0')
            elif name == 'get_interval':
                cpu.mem_write(machine.reg(4), struct.pack('>H', interval))
            elif name == 'get_subtask_filename':
                cpu.mem_write(machine.reg(4), b'synthetic\0')
            elif name == 'set_url':
                parameters[name] = {'matches_explicit_fixture_url': machine.cstring(machine.reg(4)) == url}
            elif name == 'set_filename':
                filenames.append(machine.cstring(machine.reg(4)).decode('ascii'))
            elif name == 'set_subtask_parameters':
                parameters[name] = [machine.reg(index) for index in (4, 5, 6)]
            elif name in ('set_server_interval', 'set_priority', 'set_flags', 'set_interval',
                          'set_retry_margin', 'set_count', 'init_task', 'create_vf'):
                parameters[name] = machine.reg(4)
            machine.stub_return()
            return True
        # Explicit storage boundary substitutes, including an empty existing VF.
        if address in (0x8012B7C8, 0x8006C7F0, 0x8006CC94, 0x8006CF28):
            events.append('storage_boundary_stub')
            machine.stub_return()
            return True
        if address == 0x8006D328:
            machine.stub_return(1)
            return True
        if address == 0x8006CE4C:
            machine.stub_return(0)
            return True
        if address == 0x800794A8:
            machine.stub_return(-7)
            return True
        return False

    for register, value in {3: job, 4: 1, 5: 0, 6: 0,
                            7: interval, 8: count, 9: machine.output}.items():
        cpu.reg_write(machine.reg0 + register, value)
    allowed = ((0x80043178, 0x80043C44), (0x80043FA0, 0x80044090),
               (0x80179F00, 0x80188D00), (0x80004338, 0x80004500))
    machine.run(0x80043178, machine.stop, callback, allowed,
                allowed_global_writes=((0x803576E9, 0x803576EA),))
    status = machine.reg(3)
    return {'native_return': status - 0x100000000 if status & 0x80000000 else status,
            'sdk_calls_stubbed': events, 'setter_arguments': parameters,
            'native_formatted_filenames': filenames,
            'sdk_failure_injected': sdk_failure_seen,
            'instructions': machine.instructions, 'guard_checks_passed': True,
            'sdk_storage_and_task_commit_executed': False,
            'original_caller_executed': True,
            'original_integer_filename_formatter_executed': bool(filenames),
            'full_first_run_or_download_verified': False}


def verify_reader_slot_order(source, *, hour=0, stop_after_current=False):
    """Execute the actual reader's hour-to-slot loop, with file/data stubs.

    The loop starts at the synthetic calendar hour and moves backward modulo24.
    File names themselves are mocked here; no URL suffix is inferred from them.
    A load result of one exercises the original remaining-slot clearing path.
    """
    if type(hour) is not int or not 0 <= hour < 24 or type(stop_after_current) is not bool:
        raise ValueError('Expected bounded synthetic News reader options')
    machine = _Machine(source)
    cpu, job = machine.cpu, machine.job
    cells, sizes = 0x81003000, 0x81004000
    machine.protect(cells, 96)
    machine.protect(sizes, 96)
    for slot in range(24):
        machine.word(job + 0x14 + slot * 4, cells + slot * 4)
        machine.word(job + 0xD4 + slot * 4, sizes + slot * 4)
        machine.word(cells + slot * 4, 0xA5A5A5A5)
        machine.word(sizes + slot * 4, 0xA5A5A5A5)
    slots = []

    def callback(address):
        if address == 0x80076138:
            cpu.mem_write(machine.reg(3), struct.pack('>10I', 0, 0, hour, 1, 0, 2000, 6, 0, 0, 0))
        elif address == 0x8007D000:
            slots.append(machine.reg(6))
            cpu.mem_write(machine.reg(4), b'synthetic\0')
        elif address == 0x8006CE4C:
            machine.stub_return(1)
            return True
        elif address == 0x80044090:
            machine.word(machine.reg(6), 0x12345678)
            machine.word(machine.reg(7), 104)
            machine.stub_return(int(stop_after_current))
            return True
        elif address == 0x8006CF28:
            pass
        else:
            return False
        machine.stub_return()
        return True

    cpu.reg_write(machine.reg0 + 27, job)
    cpu.reg_write(machine.reg0 + 30, 0)
    machine.run(0x80042E30, 0x8004309C, callback, ((0x80042E30, 0x8004309C),))
    cleared = [slot for slot in range(24)
               if bytes(cpu.mem_read(cells + slot * 4, 4)) == bytes(4)]
    return {'requested_slots': slots, 'cleared_buffer_slots': cleared,
            'instructions': machine.instructions, 'guard_checks_passed': True,
            'calendar_filename_file_and_load_services_stubbed': True,
            'download_or_real_storage_verified': False}


def verify_subtask_filename(source, *, slot=0, capacity=16, subtasks_enabled=True):
    """Execute the original SDK filename getter and formatter on one fake task.

    Context availability, task ID and the base filename are synthetic RAM. The
    original getter itself performs suffix formatting and capacity validation.
    This establishes a local VF name, not the remote scheduler's URL spelling.
    """
    if (type(slot) is not int or not 0 <= slot < 24
            or type(capacity) is not int or not 1 <= capacity <= 64
            or type(subtasks_enabled) is not bool):
        raise ValueError('Expected bounded synthetic News filename options')
    machine = _Machine(source)
    cpu, task = machine.cpu, machine.job
    context, context_slot = 0x81008000, 0x80357868
    machine.protect(context, 0x3620)
    machine.word(context_slot, context)
    cpu.mem_write(context + 0x3614, struct.pack('>H', 120))
    cpu.mem_write(task, b'\xFF\xFF')  # Synthetic unassigned SDK task identity.
    cpu.mem_write(task + 0x26, struct.pack('>H', int(subtasks_enabled)))
    cpu.mem_write(task + 0x1A0, b'2.bin\0')
    machine.protect(machine.output, 64)
    for register, value in {3: task, 4: machine.output, 5: capacity, 6: slot}.items():
        cpu.reg_write(machine.reg0 + register, value)
    machine.run(0x8007D000, machine.stop, lambda address: False,
                ((0x8007D000, 0x8007D1A4), (0x80179F00, 0x80188D00),
                 (0x80004338, 0x80004500)), allowed_global_reads=((context_slot, context_slot + 4),))
    if bytes(cpu.mem_read(context_slot, 4)) != struct.pack('>I', context):
        raise ValueError('Synthetic News SDK context pointer changed')
    status = machine.reg(3)
    status = status - 0x100000000 if status & 0x80000000 else status
    filename = machine.cstring(machine.output, 64).decode('ascii') if status == 0 else None
    return {'native_return': status, 'synthetic_local_filename': filename,
            'instructions': machine.instructions, 'guard_checks_passed': True,
            'original_sdk_getter_and_formatters_executed': True,
            'synthetic_sdk_context': True, 'remote_url_or_download_verified': False}


def verify_queued_task_settings(source, *, interval=0, count=0, queue_accept=True, queued_count=0):
    """Execute the original job creator up to mocked OS message submission.

    Zero inputs select its original 30/240 defaults. The queued descriptor is
    synthetic state; acceptance proves neither actual scheduling nor WC24 work.
    """
    if (type(interval) is not int or not 0 <= interval <= 65535
            or type(count) is not int or not 0 <= count <= 65535
            or type(queue_accept) is not bool or type(queued_count) is not int
            or not 0 <= queued_count <= 8):
        raise ValueError('Expected bounded synthetic News queue settings')
    machine = _Machine(source)
    cpu = machine.cpu
    pool = 0x8020CEB8
    machine.protect(pool, 8 * 0x1B8)
    machine.word(0x803576F4, 0)
    machine.word(0x803576F8, queued_count)
    url = b'http://synthetic.invalid/news.bin\0'
    machine.cpu.mem_write(machine.url, url)
    machine.protect(machine.url, len(url))
    submitted = []

    def callback(address):
        if address != 0x80103820:
            return False
        if machine.reg(4) != pool or machine.reg(5) != 0:
            raise ValueError('Unexpected native News queue submission arguments')
        submitted.append(machine.reg(4))
        machine.stub_return(int(queue_accept))
        return True

    for register, value in {3: machine.url, 4: 0x3A0000, 5: 0, 6: interval, 7: count}.items():
        cpu.reg_write(machine.reg0 + register, value)
    counters = ((0x803576F4, 0x803576FC),)
    machine.run(0x80041514, machine.stop, callback,
                ((0x80041514, 0x80041964),), allowed_global_writes=counters,
                allowed_global_reads=counters)
    status = machine.reg(3)
    status = status - 0x100000000 if status & 0x80000000 else status
    settings = None
    if submitted:
        settings = {'job_kind': struct.unpack('>I', cpu.mem_read(pool, 4))[0],
                    'task_type': struct.unpack('>H', cpu.mem_read(pool + 4, 2))[0],
                    'interval': struct.unpack('>H', cpu.mem_read(pool + 0x15C, 2))[0],
                    'count': struct.unpack('>H', cpu.mem_read(pool + 0x15E, 2))[0],
                    'max_vf_bytes': struct.unpack('>I', cpu.mem_read(pool + 0x150, 4))[0]}
    return {'native_return': status, 'submitted_descriptors': len(submitted),
            'settings': settings, 'instructions': machine.instructions,
            'guard_checks_passed': True, 'os_message_submission_stubbed': True,
            'real_worker_scheduler_or_task_registration_verified': False}
