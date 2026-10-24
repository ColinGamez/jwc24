"""Execute selected v21 browser commands up to an intercepted title launch.

Original property lookup, callback adapters, request setters, dispatcher and
AREA decoding execute on synthetic state. Browser object creation, settings
access, cleanup and the final launch are stubs. No console/profile is changed.
"""
import hashlib
import re
import struct

from tools.verify_wii_shop_url import SOURCE_SHA


METHODS = {
    'jumpToEULAViewer': (0x8002aee0, 7, 0x00010008, b'HAK'),
    'jumpToManualChannel': (0x8002af10, 9, 0x00010002, b'HCU'),
}
AREA_CODES = dict(zip(('JPN', 'USA', 'EUR', 'AUS', 'BRA', 'TWN', 'ROC',
                       'KOR', 'HKG', 'ASI', 'LTN', 'SAF', 'CHN'),
                      (0, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9, 10, 11)))
CLEANUP = (0x80021cc0, 0x801d4b70, 0x80287ea0, 0x800890d0)


def verify_transition(source, property_name, *, area='JPN', pending_request=0, factory_result=0):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    if (not isinstance(property_name, str)
            or not re.fullmatch(r'[\x20-\x7e]{1,64}', property_name)):
        raise ValueError('Expected bounded synthetic property name')
    if area is not None and (not isinstance(area, str) or not re.fullmatch(r'[A-Z]{3}', area)):
        raise ValueError('Expected synthetic three-letter AREA or None')
    if type(pending_request) is not int or not 0 <= pending_request <= 0xffffffff:
        raise ValueError('Expected synthetic U32 pending request')
    if type(factory_result) is not int or not -0x80000000 <= factory_result <= 0x7fffffff:
        raise ValueError('Expected synthetic I32 factory result')

    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])

    def word(address):
        return int.from_bytes(cpu.mem_read(address, 4), 'big')

    def write_word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))

    def register(index):
        return cpu.reg_read(UC_PPC_REG_0+index)

    def cstring(address):
        data = bytes(cpu.mem_read(address, 128))
        if b'\0' not in data:
            raise ValueError('Unterminated native string')
        return data.split(b'\0', 1)[0]

    end, factory_stub = 0x817ff000, 0x81600000
    interface, context, name_pointer = 0x81000000, 0x81001000, 0x81002000
    result_pointer, browser_function, transition_object = 0x81003000, 0x81004000, 0x81005000
    write_word(0x803607f0, interface)
    write_word(interface, factory_stub)
    write_word(0x8036c424, transition_object)
    cpu.mem_write(name_pointer, property_name.encode('ascii')+b'\0')
    result_before = b'!'*16+b'?'*16+b'!'*16
    cpu.mem_write(result_pointer-16, result_before)
    cpu.mem_write(transition_object-16, b'!'*16+b'?'*0x20c+b'!'*16)
    write_word(transition_object+4, pending_request)
    object_before = bytes(cpu.mem_read(transition_object-16, 0x22c))
    for index, value in {1: 0x817e0000, 2: 0x80369460, 13: 0x803674e0}.items():
        cpu.reg_write(UC_PPC_REG_0+index, value)

    selected = METHODS.get(property_name)
    factories, cleanups, settings, area_results, selectors, launches = [], [], [], [], [], []
    phase = None

    def stub_return(value=0):
        cpu.reg_write(UC_PPC_REG_0+3, value & 0xffffffff)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def hook(_cpu, address, _size, _data):
        if phase == 'property' and address == factory_stub:
            callback = register(6)
            if (selected is None or callback != selected[0] or register(7) != callback
                    or register(3) != context or any(register(i) != 0 for i in (4, 5, 9))):
                raise ValueError('Unexpected native browser function factory arguments')
            factories.append(callback)
            if factory_result >= 0:
                write_word(register(10), browser_function)
            stub_return(factory_result)
            return
        if phase == 'dispatch':
            if address in CLEANUP:
                cleanups.append(address)
                stub_return()
                return
            if address == 0x801fe360:
                if cstring(register(3)) != b'AREA' or register(5) != 4:
                    raise ValueError('Native settings lookup did not request AREA')
                settings.append(address)
                if area is not None:
                    cpu.mem_write(register(4), area.encode('ascii')+b'\0')
                stub_return(int(area is not None))
                return
            if address == 0x80014360:
                area_results.append(register(3))
            elif address == 0x800143a8:
                selectors.append(register(3))
            elif address == 0x801d0740:
                launches.append(tuple(register(i) for i in range(3, 7)))
                stub_return()
                return

        shared = ((0x802becf8, 0x802bee14), (0x802b5970, 0x802b59dc))
        allowed = {
            'property': ((0x8002b360, 0x8002b8f0), (0x8002aa40, 0x8002aab8))+shared,
            'callback': ((0x8002aee0, 0x8002af38), (0x80018370, 0x80018380),
                         (0x8001a440, 0x8001a458), (0x8001a4d0, 0x8001a4e8)),
            'dispatch': ((0x8001a530, 0x8001a8f8), (0x80014350, 0x800143b8),
                         (0x801fe4e0, 0x801fe564))+shared,
        }
        if not any(start <= address < stop for start, stop in allowed[phase]):
            raise ValueError(f'Unexpected native control flow in {phase}: {address:08x}')

    cpu.hook_add(UC_HOOK_CODE, hook)

    def run(start, arguments):
        for index, value in arguments.items():
            cpu.reg_write(UC_PPC_REG_0+index, value)
        cpu.reg_write(UC_PPC_REG_LR, end)
        cpu.emu_start(start, end, count=100000)
        if cpu.reg_read(UC_PPC_REG_PC) != end:
            raise ValueError(f'Native {phase} did not return')
        return register(3)

    phase = 'property'
    getter_result = run(0x8002b360, {3: context, 4: name_pointer, 5: result_pointer})
    expected_getter = 8 if selected is None else (10 if factory_result < 0 else 7)
    if getter_result != expected_getter or factories != ([selected[0]] if selected else []):
        raise ValueError('Native property lookup result differs')
    expected_result = bytearray(result_before)
    callable_created = getter_result == 7
    if callable_created:
        struct.pack_into('>I', expected_result, 16, 0)
        struct.pack_into('>I', expected_result, 24, browser_function)
    if bytes(cpu.mem_read(result_pointer-16, len(result_before))) != expected_result:
        raise ValueError('Native property result or guards differ')

    callback_result = None
    expected_pending = pending_request
    if callable_created:
        phase = 'callback'
        callback_result = run(factories[0], {})
        expected_pending = pending_request or selected[1]
        if callback_result != 0x11:
            raise ValueError('Native callback status differs')
    expected_object = bytearray(object_before)
    struct.pack_into('>I', expected_object, 20, expected_pending)
    if bytes(cpu.mem_read(transition_object-16, len(object_before))) != expected_object:
        raise ValueError('Native transition setter changed unexpected object bytes')

    # Existing pending work is preserved but deliberately not dispatched here.
    dispatched = callable_created and pending_request == 0
    if dispatched:
        phase = 'dispatch'
        run(0x8001a530, {3: transition_object})
        suffix = 'J' if area in ('JPN', 'TWN', 'ROC') else 'P' if area in ('EUR', 'AUS') else 'K' if area == 'KOR' else 'E'
        low = int.from_bytes(selected[3]+suffix.encode('ascii'), 'big')
        selector = {'J': 0, 'E': 1, 'P': 2, 'K': 3}[suffix]
        if (cleanups != list(CLEANUP) or len(settings) != 1
                or area_results != [AREA_CODES.get(area, 0xffffffff)]
                or selectors != [selector] or launches != [(selected[2], low, 0, 0)]):
            raise ValueError('Native title selection or launch arguments differ')
        if bytes(cpu.mem_read(transition_object-16, len(object_before))) != expected_object:
            raise ValueError('Native dispatcher changed transition object or guards')
    if bytes(cpu.mem_read(result_pointer-16, len(result_before))) != expected_result:
        raise ValueError('Native transition changed property result or guards')

    return {
        'property_name': property_name, 'getter_result': getter_result,
        'function_factory_result': factory_result if factories else None,
        'function_factory_calls_stubbed': len(factories), 'callback_result': callback_result,
        'pending_before': pending_request, 'pending_after': word(transition_object+4),
        'existing_pending_request_preserved': bool(pending_request),
        'native_property_lookup_mocked': False, 'native_callback_mocked': False,
        'native_callback_executed': callable_created,
        'native_request_setter_mocked': False, 'native_dispatcher_executed': dispatched,
        'native_area_decoder_executed': bool(settings), 'area_lookup_calls_stubbed': len(settings),
        'area_code': area_results[0] if area_results else None,
        'title_id_requested': f'{launches[0][0]:08X}{launches[0][1]:08X}' if launches else None,
        'cleanup_calls_stubbed': len(cleanups), 'title_launch_calls_intercepted': len(launches),
        'result_and_object_guards_verified': True, 'title_launch_executed': False,
        'browser_or_network_invoked': False, 'nand_config_accessed': False,
        'origin_access_verified': False, 'eula_acceptance_verified': False,
        'complete_channel_transition_verified': False,
    }
