"""Execute HCCJ's postal processing orchestration with a synthetic task file.

Native crypto, header, unpack and lookup execute in one emulated process.
The filesystem, heap, locks and initialization are mocked; no WC24 task runs.
"""
import hashlib
import struct

from jwc24.demae import decode_postal_download, lookup_processed_postal
from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, key, iv, ciphertext, postal_code, *, cancelled=False,
           fault=None, prior_result=False):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    faults = {None: (3, 2, 2, 5, 1),
              'decrypt_read': (1, 0, 0, 2, 0), 'decrypt_write': (1, 0, 1, 2, 1),
              'unpack_read': (2, 1, 1, 3, 1), 'unpack_write': (2, 1, 2, 4, 1),
              'final_read': (3, 2, 2, 5, 1)}
    if (type(cancelled) is not bool or type(prior_result) is not bool
            or fault not in faults or (cancelled and fault is not None)):
        raise ValueError('Invalid synthetic pipeline options')
    if not isinstance(key, bytes) or len(key) != 32 or not isinstance(iv, bytes) or len(iv) != 16:
        raise ValueError('Expected synthetic AES-256 key and IV')
    raw = decode_postal_download(ciphertext, key, iv)
    expected = lookup_processed_postal(raw, postal_code)
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    state = {'file': ciphertext, 'handles': {}, 'next_handle': 1, 'allocations': [],
             'freed': [], 'locks': 0, 'unlocks': 0, 'writes': [], 'deletes': 0,
             'mounts': 0, 'unmounts': 0, 'fault_hit': False}
    guard = b'!'*32
    heap, request, result, cancel = 0x80930000, 0x80900000, 0x80910000, 0x80920000
    def word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def fail(operation):
        stage = {1: 'decrypt', 2: 'unpack', 3: 'final'}.get(state['mounts'])
        if fault == f'{stage}_{operation}' and not state['fault_hit']:
            state['fault_hit'] = True
            return True
        return False
    def hook(cpu, address, size, user):
        returned = 0
        if address == 0x80004338:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
            returned = reg(3)
        elif address == 0x8000443c:
            cpu.mem_write(reg(3), bytes([reg(4) & 255])*reg(5))
            returned = reg(3)
        elif address == 0x800a02fc:
            returned = 1
        elif address == 0x800a0600:
            state['mounts'] += 1
        elif address == 0x800a0ad0:
            mode = reg(4)
            if mode not in (0x80373820-0x7e1c, 0x80373820-0x7e18, 0x80373820-0x7e0c):
                raise ValueError('Unexpected native synthetic file mode')
            writing = mode == 0x80373820-0x7e18
            if state['file'] is None and not writing:
                raise ValueError('Native read opened an absent synthetic file')
            returned = state['next_handle']
            state['next_handle'] += 1
            state['handles'][returned] = {'writing': writing, 'data': state['file']}
            if writing:
                state['file'] = b''
        elif address == 0x800a0f6c:
            returned = len(state['handles'][reg(3)]['data'])
        elif address == 0x8016014c:
            size = reg(4)
            if not 0 < size <= 0x40000 or len(state['allocations']) >= 5:
                raise ValueError('Unexpected native pipeline allocation')
            returned = 0x81000020+len(state['allocations'])*0x60000
            cpu.mem_write(returned-32, guard+bytes(size)+guard)
            state['allocations'].append((returned, size))
        elif address == 0x800a0ca4:
            data = state['handles'][reg(3)]['data']
            if reg(5) != len(data):
                raise ValueError('Native pipeline read size differs')
            if fail('read'):
                returned = 5
            else:
                cpu.mem_write(reg(4), data)
                word(reg(6), len(data))
        elif address == 0x800a0bac:
            del state['handles'][reg(3)]
        elif address == 0x800a0d40:
            if not state['handles'][reg(3)]['writing'] or reg(5) > 0x40000:
                raise ValueError('Unexpected native pipeline write')
            if fail('write'):
                returned = 5
            else:
                data = bytes(cpu.mem_read(reg(4), reg(5)))
                state['file'] = data
                state['writes'].append(data)
        elif address == 0x800a0fb0:
            returned = 5
        elif address == 0x800a0dcc:
            state['file'] = None
            state['deletes'] += 1
        elif address == 0x80086f9c:
            state['locks'] += 1
            returned = 1
        elif address == 0x8008702c:
            state['unlocks'] += 1
        elif address == 0x800a0918:
            state['unmounts'] += 1
        elif address == 0x8015fa1c:
            returned = heap
        elif address == 0x801601fc:
            state['freed'].append(reg(4))
        cpu.reg_write(UC_PPC_REG_0+3, returned)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x80004338, 0x8000443c, 0x8013b5d4, 0x800a02fc,
                    0x800a0600, 0x800a0ad0, 0x800a0f6c, 0x8016014c,
                    0x800a0ca4, 0x800a0bac, 0x800a0d40, 0x800a0dcc, 0x800a0fb0,
                    0x80086f9c, 0x8008702c, 0x800a0918, 0x8015fa1c, 0x801601fc):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    cpu.mem_write(request+0x201, key)
    cpu.mem_write(request+0x221, iv)
    cpu.mem_write(request+0x2c0, b'\x01')
    word(request+0x2b4, 0x40000)
    word(request+0x2bc, result)
    word(result+8, 1)
    word(result+0x18, heap)
    prior_fields = b'!'*0x108 if prior_result else bytes(0x108)
    cpu.mem_write(result+0x28, bytes([int(prior_result)]))
    cpu.mem_write(result+0x2c, prior_fields)
    word(result+0x134, postal_code)
    cpu.mem_write(cancel+4, bytes([int(cancelled)]))
    end = 0x817ff000
    for register, value in {1: 0x817e0000, 2: 0x80374c40, 13: 0x80373820,
                           3: request, 4: cancel, 5: result}.items():
        cpu.reg_write(UC_PPC_REG_0+register, value)
    cpu.reg_write(UC_PPC_REG_LR, end)
    cpu.emu_start(0x8002e7c8, end, count=30_000_000)
    expected_status = 0x15 if fault else int(cancelled)
    if cpu.reg_read(UC_PPC_REG_PC) != end or reg(3) != expected_status:
        raise ValueError('Native processing orchestration status differs')
    completed = not cancelled and fault is None
    ready = bytes(cpu.mem_read(result+0x28, 1)) == b'\x01'
    if ready != (completed or prior_result):
        raise ValueError('Native result readiness differs')
    if completed:
        wanted = bytearray(0x108)
        struct.pack_into('>I', wanted, 0, {'exact': 0, 'alternative': 1, 'not_found': 2}[expected.kind])
        if expected.record is not None:
            struct.pack_into('>I', wanted, 4, expected.record.postal_code)
            for offset, units, text in zip((8, 0x48, 0x88), (32, 32, 64), expected.record.strings):
                wanted[offset:offset+units*2] = (text.encode('utf-16-be')+b'\0\0').ljust(units*2, b'\0')
        if bytes(cpu.mem_read(result+0x2c, 0x108)) != wanted or state['file'] != raw:
            raise ValueError('Native pipeline processed file or address selection differs')
    elif bytes(cpu.mem_read(result+0x2c, 0x108)) != prior_fields:
        raise ValueError('Incomplete native processing changed prior address fields')
    if int.from_bytes(cpu.mem_read(result+0x24, 4), 'big') != (5 if fault else 0):
        raise ValueError('Native pipeline file-service diagnostic differs')
    if fault is not None and not state['fault_hit']:
        raise ValueError('Requested stage fault was not exercised')
    from Crypto.Cipher import AES
    plain = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
    if state['writes'] and state['writes'][0] != plain[plain[4]:]:
        raise ValueError('Native pipeline intermediate compressed file differs')
    if (state['handles'] or state['mounts'] != state['unmounts']
            or state['locks'] != state['unlocks']
            or sorted(state['freed']) != sorted(a for a, _ in state['allocations'])):
        raise ValueError('Native pipeline resource cleanup differs')
    for address, size in state['allocations']:
        if bytes(cpu.mem_read(address-32, 32)) != guard or bytes(cpu.mem_read(address+size, 32)) != guard:
            raise ValueError('Native pipeline allocation guard changed')
    mounts, writes, deletes, allocations, locks = (1, 1, 1, 2, 1) if cancelled else faults[fault]
    if len(state['writes']) != writes or state['deletes'] != deletes:
        raise ValueError('Native pipeline intermediate file sequence differs')
    if (state['mounts'] != mounts or state['locks'] != locks
            or len(state['allocations']) != allocations):
        raise ValueError('Native pipeline stage service counts differ')
    return {'native_status': expected_status, 'result_kind': expected.kind if completed else None,
            'fault_exercised': fault, 'prior_result_retained': prior_result and not completed,
            'native_ready_flag': ready, 'new_result_published': completed,
            'native_orchestration_mocked': False, 'native_processing_mocked': False,
            'filesystem_heap_locks_initialization_mocked': True, 'cleanup_verified': True,
            'wc24_download_verified': False, 'native_ui_verified': False}


def verify_request_reset(source, postal_code):
    """Verify the stock request creator clears prior results before queueing.

    Formatting, manager lookup/status and queue submission are mocked. This
    exercises an accepted request, not real registration or thread scheduling.
    """
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    lookup_processed_postal(b'', postal_code)
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    context, manager, end = 0x80910000, 0x80940000, 0x817ff000
    calls = {'queued': 0}
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def hook(cpu, address, size, user):
        returned = 0
        if address == 0x8000443c:
            cpu.mem_write(reg(3), bytes([reg(4) & 255])*reg(5))
            returned = reg(3)
        elif address == 0x8002d7b4:
            returned = manager
        elif address == 0x8002dc08:
            returned = 1 if calls['queued'] else 0
        elif address == 0x801b5bc8:
            cpu.mem_write(reg(3), b'synthetic\0')
        elif address == 0x8002da48:
            if reg(7) != 0x8002e7c8 or reg(8) != context:
                raise ValueError('Native request queued different processing context')
            # The ready flag and result must already be reset at submission.
            if bytes(cpu.mem_read(context+0x28, 1)) != b'\0':
                raise ValueError('Native request queued before clearing ready flag')
            if bytes(cpu.mem_read(context+0x2c, 0x108)) != struct.pack('>I', 2)+bytes(0x104):
                raise ValueError('Native request queued before clearing prior address fields')
            calls['queued'] += 1
        cpu.reg_write(UC_PPC_REG_0+3, returned)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x8000443c, 0x8002d7b4, 0x8002dc08, 0x801b5bc8, 0x8002da48):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    cpu.mem_write(context, struct.pack('>II', 10, 0x40000))
    cpu.mem_write(context+0xc, b'\x01')
    cpu.mem_write(context+0x28, b'\x01')
    cpu.mem_write(context+0x2c, b'!'*0x108)
    for register, value in {1: 0x817e0000, 2: 0x80374c40, 13: 0x80373820,
                           3: context, 4: postal_code, 5: 0}.items():
        cpu.reg_write(UC_PPC_REG_0+register, value)
    cpu.reg_write(UC_PPC_REG_LR, end)
    cpu.emu_start(0x8002e34c, end, count=1_000_000)
    if cpu.reg_read(UC_PPC_REG_PC) != end or reg(3) != 1 or calls['queued'] != 1:
        raise ValueError('Native accepted request did not queue successfully')
    expected = struct.pack('>I', 2)+bytes(0x104)
    if bytes(cpu.mem_read(context+0x2c, 0x108)) != expected:
        raise ValueError('Native request did not clear prior address fields')
    if int.from_bytes(cpu.mem_read(context+0x134, 4), 'big') != postal_code:
        raise ValueError('Native request did not retain the requested postcode')
    return {'native_request_creator_mocked': False, 'prior_result_reset_verified': True,
            'formatting_manager_queue_mocked': True, 'real_task_registration_verified': False}
