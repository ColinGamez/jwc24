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


def verify_request_reset(source, postal_code, *, cached_bucket=None, force_update=False):
    """Verify the stock request creator clears prior results before queueing.

    Formatting, manager lookup, cleanup/diagnostics and kernel synchronization
    are mocked. Native queue preparation, message send/receive and status execute.
    """
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    lookup_processed_postal(b'', postal_code)
    from jwc24.demae_postal_encode import postal_bucket
    bucket = postal_bucket(postal_code)
    if (type(force_update) is not bool or (cached_bucket is not None
            and (type(cached_bucket) is not int or not 0 <= cached_bucket <= 990 or cached_bucket % 10))):
        raise ValueError('Invalid synthetic request cache options')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    context, manager, end = 0x80910000, 0x80940000, 0x817ff000
    calls = {'queued': 0, 'cleanups': 0, 'formatted_bucket': None}
    synthetic_key, synthetic_iv = bytes(range(32)), bytes(range(16))
    def read_string(address, limit):
        return bytes(cpu.mem_read(address, limit)).split(b'\0', 1)[0]
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def hook(cpu, address, size, user):
        returned = 0
        if address == 0x8000443c:
            cpu.mem_write(reg(3), bytes([reg(4) & 255])*reg(5))
            returned = reg(3)
        elif address == 0x8002d7b4:
            returned = manager
        elif address == 0x801b5bc8:
            calls['formatted_bucket'] = reg(5)
            cpu.mem_write(reg(3), f'bucket-{reg(5)}'.encode('ascii')+b'\0')
        elif address == 0x801b5fc0:
            returned = int(read_string(reg(3), reg(5)) != read_string(reg(4), reg(5)))
        elif address == 0x801b5de8:
            value = b'synthetic-output' if reg(4) == 0x801e50a8 else read_string(reg(4), reg(5))
            cpu.mem_write(reg(3), (value+b'\0').ljust(reg(5), b'\0'))
            returned = reg(3)
        elif address == 0x80004338:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
            returned = reg(3)
        elif address == 0x8002cbb8:
            calls['cleanups'] += 1
        elif address == 0x8002c9f8:
            if reg(4) in (0x80960100, 0x80960104, 0x80960108):
                if reg(3) != manager or reg(5) != 0:
                    raise ValueError('Unexpected synthetic nonblocking send')
                return
            if (reg(3), reg(4), reg(5)) != (manager, manager+0x35c, 1):
                raise ValueError('Native queue thread dispatch shape differs')
            callback, passed_context = struct.unpack('>II', cpu.mem_read(manager+0x61c, 8))
            if callback != 0x8002e7c8 or passed_context != context:
                raise ValueError('Native request queued different processing context')
            if (int.from_bytes(cpu.mem_read(manager+0x628, 4), 'big') != 2
                    or int.from_bytes(cpu.mem_read(manager+0x360, 4), 'big') != manager+0x364
                    or bytes(cpu.mem_read(manager+0x464, 1)) != b'\x01'):
                raise ValueError('Native queue pending state differs at dispatch')
            # The ready flag and result must already be reset at submission.
            if bytes(cpu.mem_read(context+0x28, 1)) != b'\0':
                raise ValueError('Native request queued before clearing ready flag')
            if bytes(cpu.mem_read(context+0x2c, 0x108)) != struct.pack('>I', 2)+bytes(0x104):
                raise ValueError('Native request queued before clearing prior address fields')
            calls['queued'] += 1
            return  # Observe only: execute the original send wrapper below.
        elif address == 0x8013d740:
            returned = 1
        elif address == 0x8013d768:
            if reg(3) != 1:
                raise ValueError('Native queue interrupt restore token differs')
        cpu.reg_write(UC_PPC_REG_0+3, returned)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x8000443c, 0x80004338, 0x8002d7b4, 0x801b5bc8, 0x801b5fc0,
                    0x801b5de8, 0x8002cbb8, 0x8002dce0, 0x8002c9f8,
                    0x8013d740, 0x8013d768, 0x8014107c):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    cpu.mem_write(context, struct.pack('>II', 10, 0x40000))
    cpu.mem_write(context+0xc, b'\x01')
    cpu.mem_write(context+0x28, b'\x01')
    cpu.mem_write(context+0x2c, b'!'*0x108)
    cpu.mem_write(manager+0x628, struct.pack('>I', 1))
    cpu.mem_write(manager+0x630, b'synthetic-path\0')
    cpu.mem_write(manager+0x730, synthetic_key)
    cpu.mem_write(manager+0x750, synthetic_iv)
    if cached_bucket is not None:
        cpu.mem_write(manager+0x364, f'bucket-{cached_bucket}'.encode('ascii')+b'\0')
    queue_buffer, message_output = 0x80950020, 0x80960000
    queue_guard = b'!'*32
    cpu.mem_write(queue_buffer-32, queue_guard+bytes(8)+queue_guard)
    def call(address, *args):
        for register, value in {1: 0x817e0000, 2: 0x80374c40, 13: 0x80373820,
                               **dict(enumerate(args, 3))}.items():
            cpu.reg_write(UC_PPC_REG_0+register, value)
        cpu.reg_write(UC_PPC_REG_LR, end)
        cpu.emu_start(address, end, count=1_000_000)
        if cpu.reg_read(UC_PPC_REG_PC) != end:
            raise ValueError('Native message queue routine did not return')
        return reg(3)
    call(0x8013dedc, manager+0x318, queue_buffer, 2)
    for register, value in {1: 0x817e0000, 2: 0x80374c40, 13: 0x80373820,
                           3: context, 4: postal_code, 5: int(force_update)}.items():
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
    refresh = cached_bucket != bucket or force_update
    if calls['formatted_bucket'] != bucket or calls['cleanups'] != int(refresh):
        raise ValueError('Native request bucket or cache refresh differs')
    if bytes(cpu.mem_read(manager+0x624, 1)) != bytes([int(refresh)]):
        raise ValueError('Native queue refresh flag differs')
    if read_string(manager+0x364, 256) != f'bucket-{bucket}'.encode('ascii'):
        raise ValueError('Native queue request label differs')
    if int.from_bytes(cpu.mem_read(manager+0x618, 4), 'big') != 0x48000:
        raise ValueError('Native queue input work capacity differs')
    if (bytes(cpu.mem_read(manager+0x565, 32)) != synthetic_key
            or bytes(cpu.mem_read(manager+0x585, 16)) != synthetic_iv):
        raise ValueError('Native queue synthetic crypto parameters differ')
    if int.from_bytes(cpu.mem_read(manager+0x334, 4), 'big') != 1:
        raise ValueError('Native send did not enqueue one message')
    cpu.mem_write(message_output, b'!!!!')
    if (call(0x8002ca28, manager, message_output, 0) != 1
            or int.from_bytes(cpu.mem_read(message_output, 4), 'big') != manager+0x35c):
        raise ValueError('Native receive did not recover the queued request pointer')
    cpu.mem_write(message_output, b'!!!!')
    if call(0x8002ca28, manager, message_output, 0) != 0 or bytes(cpu.mem_read(message_output, 4)) != b'!!!!':
        raise ValueError('Native empty nonblocking receive changed output')
    # The first round trip advanced the head. Filling both slots now exercises
    # ring wraparound; flags zero deliberately avoids a real blocking wait.
    messages = (0x80960100, 0x80960104)
    for message in messages:
        if call(0x8002c9f8, manager, message, 0) != 1:
            raise ValueError('Native nonblocking send failed before queue capacity')
    if call(0x8002c9f8, manager, 0x80960108, 0) != 0:
        raise ValueError('Native full nonblocking queue accepted an extra message')
    for message in messages:
        if (call(0x8002ca28, manager, message_output, 0) != 1
                or int.from_bytes(cpu.mem_read(message_output, 4), 'big') != message):
            raise ValueError('Native queue wraparound changed FIFO order')
    if (int.from_bytes(cpu.mem_read(manager+0x334, 4), 'big') != 0
            or bytes(cpu.mem_read(queue_buffer-32, 32)) != queue_guard
            or bytes(cpu.mem_read(queue_buffer+8, 32)) != queue_guard):
        raise ValueError('Native queue occupancy or buffer guards differ')
    return {'native_request_creator_mocked': False, 'prior_result_reset_verified': True,
            'native_queue_preparation_mocked': False, 'native_status_reader_mocked': False,
            'native_message_send_receive_mocked': False, 'queue_round_trip_verified': True,
            'queue_wrap_and_full_verified': True,
            'bucket_verified': True, 'cache_refresh_required': refresh,
            'formatting_manager_kernel_sync_mocked': True, 'real_task_registration_verified': False}
