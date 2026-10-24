"""Execute isolated v21 URL initialization, selection and browser dispatch.

The browser symbol resolver, unrelated constructors, launch-mode query,
configuration prerequisite and two initialization routines are stubs. No browser
or network runs. This checks small native contracts, not the complete boot
sequence or an HTTP request.
"""
import hashlib
import struct

from tools.verify_wii_shop_url import SOURCE_SHA


def verify_navigation(source, prerequisite_result, *, callback_result=0, launch_argument_count=0):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    if any(type(value) is not int or not 0 <= value <= 0xffffffff
           for value in (prerequisite_result, callback_result)):
        raise ValueError('Expected synthetic U32 results')
    if type(launch_argument_count) is not int or launch_argument_count not in (0, 1):
        raise ValueError('This harness checks only zero/one-argument launch branches')

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
        raw = bytes(cpu.mem_read(address, 1025))
        if b'\0' not in raw:
            raise ValueError('Unterminated native string')
        return raw.split(b'\0', 1)[0]

    end = 0x817ff000
    for index, value in {1: 0x817e0000, 2: 0x80369460, 13: 0x803674e0}.items():
        cpu.reg_write(UC_PPC_REG_0+index, value)

    base_pointer, eula_pointer, object_pointer = 0x81000000, 0x81001000, 0x81002000
    base, eula = b'https://shop.example', b'file:/synthetic/eula.html'
    for slot, pointer, value in ((0x8035f4f8, base_pointer, base),
                                 (0x8035f4e8, eula_pointer, eula)):
        write_word(slot, pointer)
        cpu.mem_write(pointer, value+b'\0')
    # Accessor 0x80013940 reads the object pointer from this singleton slot.
    write_word(0x8036c428, object_pointer)
    write_word(0x803607d8, 0xdeadbeef)

    constructors = []
    for index in range(48):
        target = word(0x802ce920+4*index)
        if not target:
            break
        constructors.append(target)
    if len(constructors) != 46 or constructors.count(0x80028ce0) != 1:
        raise ValueError('Unexpected native constructor table')

    imports = []
    for index in range(117):
        name_pointer = word(0x8030beb8+8*index)
        slot = word(0x8030bebc+8*index)
        if slot != 0x80360540+4*index:
            raise ValueError('Unexpected browser import slot')
        imports.append((cstring(name_pointer), slot, 0x81600000+4*index))
    if imports[29][:2] != (b'WWWOpenUrl', 0x803605b4):
        raise ValueError('WWWOpenUrl import binding differs')

    phase = None
    constructor_calls, resolved, initializer_calls, opened = [], [], [], []
    prerequisite_calls = []
    launch_mode_calls = []
    browser_object, browser_handle, module_handle = 0x81003000, 0x81004000, 0x81005000
    write_word(browser_object+0x240, browser_handle)

    def stub_return(value=0):
        cpu.reg_write(UC_PPC_REG_0+3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def hook(_cpu, address, _size, _data):
        if phase == 'constructors' and address in constructors:
            constructor_calls.append(address)
            if address != 0x80028ce0:
                stub_return()
                return
        elif phase == 'imports' and address == 0x80258a80:
            index = len(resolved)
            if index >= len(imports) or register(3) != module_handle:
                raise ValueError('Unexpected browser resolver invocation')
            name = cstring(register(4))
            if name != imports[index][0]:
                raise ValueError('Native browser symbol order differs')
            resolved.append(name)
            stub_return(imports[index][2])
            return
        elif phase == 'launch' and address == 0x801cf020:
            launch_mode_calls.append(address)
            stub_return(0)
            return
        elif phase == 'selection' and address == 0x801fe1c0:
            prerequisite_calls.append(address)
            stub_return(prerequisite_result)
            return
        elif phase == 'selection' and address in (0x8002f560, 0x8002f680):
            if register(3) != object_pointer:
                raise ValueError('Native initializer object differs')
            initializer_calls.append(address)
            stub_return(1)
            return
        elif phase == 'dispatch' and address == imports[29][2]:
            if register(3) != browser_handle or register(4) != word(0x803607d8):
                raise ValueError('Native WWWOpenUrl arguments differ')
            opened.append(cstring(register(4)))
            stub_return(callback_result)
            return

        allowed = {
            'constructors': ((0x801d0910, 0x801d0958), (0x80028ce0, 0x80028cec)),
            'imports': ((0x80028944, 0x80028978),),
            'launch': ((0x80023df0, 0x8002407c), (0x8002bca0, 0x8002bcc0)),
            'selection': ((0x800136a8, 0x800136f0), (0x80013930, 0x80013950)),
            'dispatch': ((0x800293a0, 0x800293b4),),
        }
        if not any(start <= address < stop for start, stop in allowed[phase]):
            raise ValueError(f'Unexpected native control flow in {phase}: {address:08x}')

    cpu.hook_add(UC_HOOK_CODE, hook)

    def run(start, stop=end):
        cpu.reg_write(UC_PPC_REG_LR, end)
        cpu.emu_start(start, stop, count=10000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError(f'Native {phase} did not reach its boundary')

    phase = 'constructors'
    run(0x801d0910)
    if constructor_calls != constructors or word(0x803607d8) != base_pointer:
        raise ValueError('Native constructor did not publish normal base')

    phase = 'launch'
    cpu.reg_write(UC_PPC_REG_0+3, launch_argument_count)
    # Neither tested branch should dereference argv or invoke the URL builder.
    cpu.reg_write(UC_PPC_REG_0+4, 0xdeadbeef)
    run(0x80023df0, 0x8002407c)
    if (launch_mode_calls != [0x801cf020] or word(0x80360728) != 0
            or word(0x803607d8) != base_pointer):
        raise ValueError('Native mode-zero entry URL branch differs')
    # The entry slice stops before general initialization and its epilogue.
    cpu.reg_write(UC_PPC_REG_0+1, 0x817e0000)

    phase = 'imports'
    cpu.reg_write(UC_PPC_REG_0+29, 0x8030b348)
    cpu.reg_write(UC_PPC_REG_0+26, module_handle)
    run(0x80028944, 0x80028978)
    if len(resolved) != 117 or any(word(slot) != target for _, slot, target in imports):
        raise ValueError('Native browser import publication differs')

    phase = 'selection'
    run(0x800136a8, 0x800136f0)
    accepted = prerequisite_result == 1
    expected_pointer, expected_url = (base_pointer, base) if accepted else (eula_pointer, eula)
    if (prerequisite_calls != [0x801fe1c0]
            or bytes(cpu.mem_read(object_pointer+8, 1)) != bytes([int(accepted)])
            or initializer_calls != ([0x8002f560, 0x8002f680] if accepted else [])
            or word(0x803607d8) != expected_pointer):
        raise ValueError('Native startup URL selection differs')

    phase = 'dispatch'
    cpu.reg_write(UC_PPC_REG_0+3, browser_object)
    run(0x800293a0)
    if opened != [expected_url] or register(3) != callback_result:
        raise ValueError('Native WWWOpenUrl dispatch/return differs')

    return {
        'constructor_entries_dispatched': len(constructor_calls),
        'unrelated_constructors_stubbed': len(constructor_calls)-1,
        'browser_symbols_resolved_with_stub': len(resolved),
        'launch_mode': 0, 'launch_argument_count': launch_argument_count,
        'launch_mode_query_mocked': True, 'native_entry_url_branch_mocked': False,
        'open_url_symbol': 'WWWOpenUrl', 'open_url_calls': len(opened),
        'prerequisite_result': prerequisite_result, 'eula_selected': not accepted,
        'initializers_stubbed': len(initializer_calls),
        'published_url': expected_url.decode('ascii'),
        'callback_result': callback_result, 'callback_return_forwarded': True,
        'native_url_initializer_mocked': False, 'native_import_loop_mocked': False,
        'native_selection_branch_mocked': False, 'native_dispatch_thunk_mocked': False,
        'prerequisite_query_mocked': True, 'symbol_resolver_mocked': True,
        'browser_or_network_invoked': False, 'startup_request_verified': False,
        'complete_boot_sequence_verified': False,
    }
