"""Execute HCDJ's URL controller on synthetic settings without HTTP or ordering.

Original provider URL strings remain in the private executable. The native
selector and formatter execute; no original bytes or disassembly are embedded.
Only production selector 0 and unhandled selector probes are exposed here.
"""
import hashlib
import struct


SOURCE_SHA256 = '419c295d0745a5991df5468a4dd1dfc502fdf6c81f47898629f65fbd42e40f7e'


def verify_provider_urls(source, *, selector=0):
    if (not isinstance(source, bytes) or not 0 < len(source) <= 8*1024*1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Expected fingerprinted HCDJ v1024 application')
    if type(selector) is not int or selector not in (0, 7, 255):
        raise ValueError('Expected a production or unhandled synthetic selector')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    output, setting, stack, stop = 0x81000020, 0x81001020, 0x817e0000, 0x817ff000
    cpu.mem_write(output, b'\xa5'*0x400)
    cpu.mem_write(setting, bytes(0x80))
    cpu.mem_write(setting+0x25, bytes([selector]))
    # Only the synthetic CPU image is changed; no NAND configuration is read.
    cpu.mem_write(0x804a35d0, struct.pack('>I', setting))
    guards = ((output, 0x400), (setting, 0x80), (stack-0x2000, 0x2100))
    for address, size in guards:
        cpu.mem_write(address-16, b'!'*16)
        cpu.mem_write(address+size, b'!'*16)
    count = 0
    visits = set()

    def instruction(_cpu, address, _size, _data):
        nonlocal count
        count += 1
        visits.add(address)
        allowed = ((0x80004300, 0x80004600), (0x80045ed4, 0x8004618c),
                   (0x800ad000, 0x800c0000))
        if not any(start <= address < end for start, end in allowed):
            raise ValueError(f'Unexpected HCDJ URL-controller control flow: {address:08x}')

    def write(_cpu, _access, address, size, _value, _data):
        if not ((output <= address < address+size <= output+0x400)
                or (stack-0x2000 <= address < address+size <= stack+0x100)):
            raise ValueError('HCDJ URL controller wrote outside synthetic buffers')

    for index, value in {1: stack, 2: 0x804ac140, 13: 0x804aa600, 3: output}.items():
        cpu.reg_write(UC_PPC_REG_0+index, value)
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.emu_start(0x80045ed4, stop, count=500000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('HCDJ URL controller did not return within instruction bound')
    for address, size in guards:
        if (bytes(cpu.mem_read(address-16, 16)) != b'!'*16
                or bytes(cpu.mem_read(address+size, 16)) != b'!'*16):
            raise ValueError('HCDJ synthetic buffer guard changed')
    if bytes(cpu.mem_read(setting, 0x80)) != bytes(0x25)+bytes([selector])+bytes(0x80-0x26):
        raise ValueError('HCDJ synthetic setting changed')
    body = bytes(cpu.mem_read(output, 0x400))
    if selector == 0:
        parts = (body[:0x200], body[0x200:])
        if any(b'\0' not in part for part in parts):
            raise ValueError('HCDJ provider URL lacks bounded terminator')
        urls = [part.split(b'\0', 1)[0].decode('ascii') for part in parts]
    else:
        if body != b'\xa5'*0x400:
            raise ValueError('Unhandled HCDJ selector modified output')
        urls = []
    return {'selector': selector, 'provider_urls': urls,
            'native_url_controller_executed': True, 'native_tls_selector_executed': True,
            'native_formatter_executed': 0x800b3ef4 in visits,
            'native_formatter_or_selector_stubbed': False,
            'native_instructions': count, 'synthetic_buffer_guards_verified': True,
            'native_write_ranges_checked': True, 'network_or_print_order_invoked': False,
            'settings_or_credentials_read_from_nand': False}
