"""Guarded unchanged CMOC decompressor/wrapper execution on synthetic inputs."""
import hashlib
from jwc24.cmoc_compression import inspect_compression, _validate_inputs
from tools.verify_cmoc_framing import SOURCE_SHA256

def _execute(source, *, chunks, enabled, limit, application, capacity):
    if type(source) is not bytes or len(source) != 3410304 or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    _validate_inputs(chunks, enabled, limit, capacity, application)
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_3, UC_PPC_REG_LR, UC_PPC_REG_PC
    from tools.inspect_demae_references import sections
    u = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    u.mem_map(0x80000000, 0x1800000)
    for _, o, a, n in sections(source):
        u.mem_write(a, source[o:o + n])
    context, out = (0x81000000, 0x81100000)
    slo, shi, sp, stop = (0x817d0000, 0x817e1000, 0x817e0000, 0x817ff000)
    guard = b'CMOC-COMPRESSION-GUARD' * 2
    objs = []

    def put(p, b, mut=False):
        u.mem_write(p - len(guard), guard)
        u.mem_write(p, b)
        u.mem_write(p + len(b), guard)
        objs.append((p, b, mut))
    put(context, bytes(0x24), True)
    put(out, b'\xa5' * capacity, True)
    for i, b in enumerate(chunks):
        put(0x81200000 + i * 0x2000, b)
    u.mem_write(slo - len(guard), guard)
    u.mem_write(slo, b'\xa5' * (shi - slo))
    u.mem_write(shi, guard)
    counts = {'instructions': 0, 'sdk_calls': 0, 'size_header_reads': 0}
    returns = []
    touched = set()

    def code(c, a, n, _):
        counts['instructions'] += 1
        if a == 0x80177c58:
            counts['sdk_calls'] += 1
        if a == 0x801783d0:
            counts['size_header_reads'] += 1
        if a == 0x80178010:
            v = c.reg_read(UC_PPC_REG_3)
            returns.append(v if v < 0x80000000 else v - 4294967296)
        allowed = ((0x80004000, 0x80004134), (0x80069428, 0x800695d0),
                   (0x80177be4, 0x80178014), (0x801783d0, 0x80178410))
        if not any(lo <= a < hi for lo, hi in allowed):
            raise ValueError(f'Unexpected PC {a:#x}')

    def read(c, access, a, n, v, _):
        if not any((lo <= a < a + n <= hi for lo, hi in [(p, p + len(b)) for p, b, m in objs] + [(slo, shi)])):
            raise ValueError(f'Unexpected read {a:#x}')

    def write(c, access, a, n, v, _):
        if not any((lo <= a < a + n <= hi for lo, hi in [(p, p + len(b)) for p, b, m in objs if m] + [(slo, shi)])):
            raise ValueError(f'Unexpected write {a:#x}')
        if out <= a < a + n <= out + capacity:
            touched.update(range(a, a + n))
    u.hook_add(UC_HOOK_CODE, code)
    u.hook_add(UC_HOOK_MEM_READ, read)
    u.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(a, args):
        for r, v in {1: sp, 2: 0x80435be0, 13: 0x80432ba0, **args}.items():
            u.reg_write(UC_PPC_REG_0 + r, v)
        u.reg_write(UC_PPC_REG_LR, stop)
        u.emu_start(a, stop, count=1000000)
        if u.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('CMOC decompressor instruction cap reached')
        return u.reg_read(UC_PPC_REG_3)
    if application:
        call(0x80069428, {3: context, 4: out, 5: limit, 6: int(enabled)})
    else:
        call(0x80177be4, {3: context, 4: out})
        u.mem_write(context + 8, limit.to_bytes(4, 'big'))
    rows = []
    for i, b in enumerate(chunks):
        touched.clear()
        sdk_start = len(returns)
        r = call(0x800694ec if application else 0x80177c58,
                 {3: context, 4: 0x81200000 + i * 0x2000, 5: len(b)})
        c = bytes(u.mem_read(context, 0x24))
        cursor = int.from_bytes(c[0:4] if enabled else c[0x18:0x1c], 'big') - out
        if not 0 <= cursor <= capacity:
            raise ValueError('CMOC decompressor cursor exceeds explicit backing')
        rows.append(dict(
            return_value=r if application or r < 0x80000000 else r - 4294967296,
            sdk_return=None if len(returns) == sdk_start else returns[-1],
            remaining=int.from_bytes(c[4:8], 'big', signed=True),
            limit=int.from_bytes(c[8:12], 'big', signed=True), header_remaining=c[0x13],
            variant=c[0x14], cached_remaining=int.from_bytes(c[0x1c:0x20], 'big'),
            reference_state=c[0x10], reference_word=int.from_bytes(c[0xc:0x10], 'big'),
            flag_byte=c[0x11], flag_bits_remaining=c[0x12], output_size=cursor,
            written_offsets=tuple(sorted(address - out for address in touched)),
            output=bytes(u.mem_read(out, cursor)),
            tail_unchanged=bytes(u.mem_read(out + cursor, capacity - cursor)) == b'\xa5' * (capacity - cursor)))
    for p, b, m in objs:
        if bytes(u.mem_read(p - len(guard), len(guard))) != guard or bytes(u.mem_read(p + len(b), len(guard))) != guard:
            raise ValueError('CMOC decompressor object guard changed')
        if not m and bytes(u.mem_read(p, len(b))) != b:
            raise ValueError('CMOC decompressor input changed')
    if bytes(u.mem_read(slo - len(guard), len(guard))) != guard or bytes(u.mem_read(shi, len(guard))) != guard:
        raise ValueError('CMOC decompressor stack guard changed')
    return dict(rows=rows, counts=counts)

def verify_compression(source, *, chunks, enabled, output_limit, output_capacity, application=True):
    expected = inspect_compression(chunks=chunks, enabled=enabled, output_limit=output_limit,
                                   output_capacity=output_capacity, application=application)
    actual = _execute(source, chunks=chunks, enabled=enabled, limit=output_limit,
                      capacity=output_capacity, application=application)
    previous = 0
    for step, row in zip(expected.steps, actual['rows']):
        fields = ('return_value', 'sdk_return', 'remaining', 'cached_remaining',
                  'header_remaining', 'variant', 'reference_state', 'reference_word',
                  'flag_byte', 'flag_bits_remaining', 'output_size')
        if (any(getattr(step, name) != row[name] for name in fields)
                or row['written_offsets'] != tuple(range(previous, step.output_size))
                or not row['tail_unchanged']
                or row['output'] != expected.output[:step.output_size]):
            raise ValueError('Original CMOC streaming decompressor differs from independent projection')
        previous = step.output_size
    return dict(**expected.metadata(), counts=actual['counts'], original_decoder_executed=True,
                application_wrappers_executed=application, input_and_stack_guards_verified=True,
                exact_write_spans_and_untouched_tail_verified=True, decoder_stubs_used=False)
