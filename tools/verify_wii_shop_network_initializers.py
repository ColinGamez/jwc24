"""Execute only original v21 socket/HTTP initializer callers on synthetic RAM.

Every allocator/SDK/socket/HTTP/thread/logging boundary is intercepted. No real
thread, network, browser, IOS, account, credential or NAND state is available.
The worker is invoked directly, not scheduled. Polling stops before unrelated
timer/callback processing. Native diagnostics corroborate API labels; complete
SDK symbol equivalence and EC/plugin startup are not claimed.
"""
from dataclasses import dataclass
import hashlib
import struct

from tools.verify_wii_shop_url import SOURCE_SHA

PREPARE = 0x8002F560
LAUNCH = 0x8002F680
WORKER = 0x8002F710
POLL = 0x8002F820
POLL_BOUNDARIES = (0x8002F884, 0x8002F968)
OBJECT = 0x81000000
WORKER_STATE = 0x803B2D18
STACK_BASE = 0x81120000
ERROR_MARKER = 50100


@dataclass(frozen=True)
class SyntheticNetworkResults:
    so_init_result: int = 0
    worker_stack_available: bool = True
    create_thread_result: int = 1
    so_startup_result: int = 0
    nhttp_startup_result: int = 0
    preparation_value: int = 0x1234
    socket_error_result: int = -0x77
    thread_terminated: int = 1
    poll_state: int | None = None


def _validate(results):
    if type(results) is not SyntheticNetworkResults:
        raise ValueError('Expected explicit synthetic initializer results')
    signed = ('so_init_result', 'so_startup_result', 'nhttp_startup_result', 'socket_error_result')
    for name in signed:
        value = getattr(results, name)
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError('Expected a synthetic signed32 result')
    for name in ('preparation_value',):
        value = getattr(results, name)
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError('Expected a synthetic uint32 value')
    for name in ('create_thread_result', 'thread_terminated'):
        value = getattr(results, name)
        if type(value) is not int or value not in (0, 1):
            raise ValueError('Expected a synthetic boolean SDK result')
    if type(results.worker_stack_available) is not bool:
        raise ValueError('Expected a synthetic stack-allocation switch')
    if results.poll_state is not None and (type(results.poll_state) is not int or results.poll_state not in range(5)):
        raise ValueError('Expected a bounded synthetic poll state')


def verify_network_initializers(source, results=None):
    if not isinstance(source, bytes) or len(source) > 16*1024*1024 or hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    results = SyntheticNetworkResults() if results is None else results
    _validate(results)
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    stack, stop = 0x817E0000, 0x817FF000
    heap_object, vtable, heap_handle = 0x81001000, 0x81002000, 0x81003000
    heap_slot, heap_base_slot, heap_handle_slot = 0x80360788, 0x80360830, 0x80360834
    phase, calls, visited, phase_returns = None, [], set(), {}
    poll_boundary = None

    def reg(index):
        return cpu.reg_read(UC_PPC_REG_0+index)

    def word(address):
        return int.from_bytes(cpu.mem_read(address, 4), 'big')

    def put(address, value):
        cpu.mem_write(address, struct.pack('>I', value & 0xFFFFFFFF))

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0+3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def record(name, **values):
        calls.append({'phase': phase, 'boundary': name, **values})

    def hook(_cpu, address, _size, _data):
        nonlocal poll_boundary
        visited.add(address)
        if phase == 'poll' and address in POLL_BOUNDARIES:
            poll_boundary = address
            cpu.emu_stop()
            return
        if phase == 'prepare':
            if address == 0x81600000:
                if (reg(3), reg(4)) != (heap_object, 4):
                    raise ValueError('Unexpected synthetic heap-selection arguments')
                record('heap_selection', selector=reg(4))
                ret()
                return
            if address == 0x81600004:
                if (reg(3), reg(4), reg(5)) != (heap_object, 0x18000, 0x20):
                    raise ValueError('Unexpected synthetic heap-allocation arguments')
                record('heap_allocation', bytes=reg(4), alignment=reg(5))
                ret(0x81100000)
                return
            if address == 0x801F4EA0:
                if (reg(3), reg(4), reg(5)) != (0x81100000, 0x18000, 4):
                    raise ValueError('Unexpected synthetic heap-construction arguments')
                record('heap_construction', bytes=reg(4), option=reg(5))
                ret(heap_handle)
                return
            if address == 0x80004714:
                if not stack-0x100 <= reg(3) < reg(3)+reg(5) <= stack or (reg(4), reg(5)) != (0, 8):
                    raise ValueError('Unexpected initializer local-clear arguments')
                cpu.mem_write(reg(3), bytes(reg(5)))
                ret(reg(3))
                return
            if address == 0x800BF214:
                pointer = reg(3)
                if not stack-0x100 <= pointer <= stack-8:
                    raise ValueError('SOInit callback pair outside synthetic frame')
                pair = (word(pointer), word(pointer+4))
                if pair != (0x8002FAA0, 0x8002FAC0):
                    raise ValueError('Original SOInit allocator callbacks differ')
                record('SOInit_diagnostic_associated', allocator_callbacks=[f'0x{x:08x}' for x in pair])
                ret(results.so_init_result)
                return
            if address == 0x8002FAA0:
                if (reg(3), reg(4)) != (0x4000, 0x20):
                    raise ValueError('Unexpected worker-stack allocation arguments')
                record('worker_stack_allocation', bytes=reg(3), alignment=reg(4))
                ret(STACK_BASE if results.worker_stack_available else 0)
                return
        if phase == 'launch':
            if address == 0x801CC6D0:
                expected = (OBJECT+0x18, WORKER, 0, STACK_BASE+0x4000, 0x4000, 14, 1)
                if tuple(reg(i) for i in range(3, 10)) != expected:
                    raise ValueError('Original thread-creation boundary arguments differ')
                record('thread_creation', entry=f'0x{reg(4):08x}', argument=reg(5), stack_bytes=reg(7),
                       priority=reg(8), attributes=reg(9))
                ret(results.create_thread_result)
                return
            if address == 0x801CCE00:
                if reg(3) != OBJECT+0x18:
                    raise ValueError('Unexpected synthetic thread-resume object')
                record('thread_resume')
                ret()
                return
        if phase == 'worker':
            if address == 0x800A9C0C:
                record('worker_preparation_value')
                ret(results.preparation_value)
                return
            if address == 0x800BF3E0:
                record('SOStartup_diagnostic_associated')
                ret(results.so_startup_result)
                return
            if address == 0x800A9EDC:
                if reg(3) != (results.so_startup_result & 0xFFFFFFFF):
                    raise ValueError('Unexpected socket-error conversion input')
                record('socket_error_conversion')
                ret(results.socket_error_result)
                return
            if address == 0x800B0B30:
                if (reg(3), reg(4), reg(5)) != (0x8002FAE0, 0x8002FB00, 15):
                    raise ValueError('Original NHTTPStartup boundary arguments differ')
                record('NHTTPStartup_diagnostic_associated', allocator_callbacks=['0x8002fae0', '0x8002fb00'], priority=reg(5))
                ret(results.nhttp_startup_result)
                return
        if phase == 'poll' and address == 0x801CC0E0:
            if reg(3) != OBJECT+0x18:
                raise ValueError('Unexpected synthetic thread-completion query object')
            record('thread_completion_query')
            ret(results.thread_terminated)
            return
        if address == 0x800138E0 and phase in ('prepare', 'worker'):
            record('logging_stub')
            ret()
            return
        ranges = {
            'prepare': ((PREPARE, 0x8002F678), (0x802B5974, 0x802B59DC)),
            'launch': ((LAUNCH, 0x8002F70C),),
            'worker': ((WORKER, 0x8002F81C), (0x802B5974, 0x802B59DC)),
            'poll': ((POLL, 0x8002F884),),
        }
        if not any(begin <= address < end for begin, end in ranges[phase]):
            raise ValueError('Unexpected native initializer control flow')

    allowed_writes = ((OBJECT, OBJECT+0x360), (stack-0x1000, stack+0x1000),
                      (heap_base_slot, heap_handle_slot+4), (WORKER_STATE, WORKER_STATE+12))

    def memory_write(_cpu, _access, address, size, _value, _data):
        if not any(begin <= address < address+size <= end for begin, end in allowed_writes):
            raise ValueError('Native initializer write outside synthetic state')

    put(heap_slot, heap_object)
    put(heap_object, vtable)
    put(vtable+0x2C, 0x81600000)
    put(vtable+0x18, 0x81600004)
    guards = ((OBJECT-16, 16), (OBJECT+0x360, 16), (WORKER_STATE-16, 16),
              (WORKER_STATE+12, 16), (stack-0x1010, 16), (stack+0x1000, 16))
    for address, size in guards:
        cpu.mem_write(address, b'!'*size)
    put(WORKER_STATE, 0)
    put(WORKER_STATE+4, 0)
    put(WORKER_STATE+8, 0)
    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)

    def run(name, start, argument=OBJECT):
        nonlocal phase
        phase = name
        for index, value in {1: stack, 2: 0x80369460, 13: 0x803674E0, 3: argument}.items():
            cpu.reg_write(UC_PPC_REG_0+index, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(start, stop, count=10000)
        if name != 'poll' and cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Native initializer did not return within instruction bound')
        if name == 'poll' and poll_boundary not in POLL_BOUNDARIES:
            raise ValueError('Native polling prefix did not reach selected boundary')
        phase_returns[name] = reg(3)

    run('prepare', PREPARE)
    prepared = phase_returns['prepare'] == 1
    state_after_prepare = word(OBJECT+4)
    launched = worker_executed = False
    if prepared:
        run('launch', LAUNCH)
        launched = phase_returns['launch'] == 1
        if launched:
            run('worker', WORKER, 0)
            worker_executed = True
    state_before_poll = word(OBJECT+4)
    if results.poll_state is not None:
        put(OBJECT+4, results.poll_state)
    run('poll', POLL)
    for address, size in guards:
        if bytes(cpu.mem_read(address, size)) != b'!'*size:
            raise ValueError('Native initializer synthetic guard changed')
    return {'source_sha256': SOURCE_SHA, 'prepare_return': phase_returns['prepare'],
            'state_after_prepare': state_after_prepare, 'launch_return': phase_returns.get('launch'),
            'worker_invoked_directly': worker_executed, 'worker_return': phase_returns.get('worker'),
            'worker_state': word(WORKER_STATE), 'worker_error': word(WORKER_STATE+4),
            'worker_preparation_value': word(WORKER_STATE+8), 'state_before_poll': state_before_poll,
            'state_after_poll': word(OBJECT+4), 'error_after_poll': word(OBJECT+0x10),
            'preparation_value_after_poll': word(OBJECT+0x0C),
            'poll_stop_address': f'0x{poll_boundary:08x}', 'boundary_calls': calls,
            'native_instruction_addresses_visited': len(visited),
            'guards_verified': True, 'write_ranges_checked': True,
            'all_allocator_socket_http_thread_calls_stubbed': True,
            'native_thread_scheduler_invoked': False, 'browser_or_network_invoked': False,
            'account_device_or_NAND_state_accessed': False, 'full_startup_executed': False,
            'EC_init_connect_or_plugin_registration_verified': False,
            'poll_timer_callbacks_executed': False}
