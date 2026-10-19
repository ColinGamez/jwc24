"""Execute the compiled PPC modal payload against mocked native SDK calls.

This checks payload control flow and ABI behavior, not Dolphin or SDK rendering.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_demae_directory_modal import NATIVE

GLOBAL, MODAL, HOME, PANE = 0x8038A210, 0x80400000, 0x80410000, 0x80420000
SCENE, SHOP, ID, BODY, STACK = 0x80440000, 0x80430000, 0x80431000, 0x80432000, 0x81008000
ROOT, GROUP, ORIGINAL_MESSAGE = 0x80450000, 0x80460000, 0x80470000


class Machine:
    def __init__(self, payload, metadata, *, body='Directory source text', identifier='hotpepper:J000000001'):
        from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
        from unicorn import ppc_const as registers
        self.regs = registers
        self.uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
        for address in (0x80000000, 0x80300000, 0x80400000, 0x81000000):
            self.uc.mem_map(address, 0x100000)
        self.uc.mem_write(metadata['base_address'], payload)
        self.symbols = metadata['symbols']
        self.context = self.symbols['directory_context']
        self.calls = []
        self.close_now = False
        self.found = True
        self.uc.reg_write(registers.UC_PPC_REG_MSR, 0x2000)
        for n in range(32):
            self.setreg(n, 0x10100000+n)
        self.setreg(1, STACK)
        self.setreg(24, SCENE)
        self.setreg(25, SCENE)
        self.uc.reg_write(registers.UC_PPC_REG_LR, 0xDEADF00D)
        self.put(GLOBAL+0x248, HOME)
        self.put(GLOBAL+0x24C, MODAL)
        self.put(GLOBAL+0x2BC, 4)
        self.put(GLOBAL+0x2C0, 4)
        self.put(MODAL+4, 4)
        self.put(MODAL+0x280, ORIGINAL_MESSAGE)
        self.put(ORIGINAL_MESSAGE, 0x12345678)
        self.put(MODAL+0x1E0, ROOT)
        for pane in (ROOT, GROUP):
            self.put(pane, pane+0x1000)
            self.put(pane+0x1000+0x3C, 0x80001008)
        for n, offset in enumerate((0x218, 0x21c, 0x17c, 0x1a0, 0x1c4)):
            self.put(MODAL+offset, 0x80480000+n*0x1000)
        self.put(PANE, PANE+0x1000)
        self.put(PANE+0x1000+0x74, 0x80001000)
        self.put(PANE+0x1000+0x7C, 0x80001004)
        self.put(SHOP+0x18, BODY)
        self.uc.mem_write(ID, identifier.encode()+b'\0')
        self.uc.mem_write(BODY, body.encode('utf-16-be')+b'\0\0')
        self.put(self.context, SCENE)
        self.put(SCENE+0x1A8, 2)
        self.uc.hook_add(UC_HOOK_CODE, self.hook)

    def reg(self, n):
        return self.uc.reg_read(self.regs.UC_PPC_REG_0+n)

    def setreg(self, n, value):
        self.uc.reg_write(self.regs.UC_PPC_REG_0+n, value)

    def put(self, address, value):
        self.uc.mem_write(address, value.to_bytes(4, 'big'))

    def get(self, address):
        return int.from_bytes(self.uc.mem_read(address, 4), 'big')

    def hook(self, uc, address, size, _):
        if address in (NATIVE['native_job_exit'], NATIVE['native_row_resume'], NATIVE['native_cleanup_resume']):
            uc.emu_stop()
            return
        names = {value: key for key, value in NATIVE.items()}
        names.update({0x80001000: 'text_capacity', 0x80001004: 'text_set', 0x80001008: 'find_pane'})
        name = names.get(address)
        if name is None:
            return
        args = tuple(self.reg(n) for n in range(3, 7))
        self.calls.append((name, args))
        if name == 'native_selected_shop':
            self.setreg(3, SHOP)
        elif name == 'native_shop_id':
            self.setreg(3, ID)
        elif name == 'find_pane':
            self.setreg(3, (GROUP if args[0] == ROOT else PANE) if self.found else 0)
        elif name == 'native_open_dynamic':
            self.put(MODAL, 0)
            self.put(MODAL+4, 1)
        elif name == 'native_modal_update':
            self.put(MODAL, 0 if self.close_now or args[1] == 0 else 2)
            self.put(MODAL+4, 4)
        uc.reg_write(self.regs.UC_PPC_REG_PC, uc.reg_read(self.regs.UC_PPC_REG_LR))

    def run(self, symbol='directory_job'):
        before = {n: self.reg(n) for n in range(24, 32)}
        lr = self.uc.reg_read(self.regs.UC_PPC_REG_LR)
        self.uc.emu_start(self.symbols[symbol], NATIVE['native_job_exit']+4, count=10000)
        pc = self.uc.reg_read(self.regs.UC_PPC_REG_PC)
        expected = (NATIVE['native_row_resume'] if symbol == 'directory_enter' else
                    NATIVE['native_cleanup_resume'] if symbol == 'directory_cleanup' else NATIVE['native_job_exit'])
        assert pc == expected, 'Payload did not reach its reviewed continuation'
        if symbol != 'directory_enter':
            assert self.reg(1) == (STACK-128 if symbol == 'directory_cleanup' else STACK)
            assert self.uc.reg_read(self.regs.UC_PPC_REG_LR) == lr
            assert all(self.reg(n) == value for n, value in before.items()), 'Native callback locals changed'
            assert self.get(ORIGINAL_MESSAGE) == 0x12345678, 'Shared message pane was changed'


def verify(payload, metadata):
    if hashlib.sha256(payload).hexdigest() != metadata['payload_sha256']:
        raise ValueError('Payload fingerprint mismatch')
    count = 0
    m = Machine(payload, metadata)
    m.run('directory_enter')
    assert m.reg(3) == 0x53B and m.get(m.context) == SCENE and m.get(m.context+4) == 0
    count += 1
    for pending in (0, 3, 4):
        m = Machine(payload, metadata)
        m.put(MODAL+4, pending)
        m.run()
        assert m.get(m.context+4) == 1
        assert any(name == 'native_open_dynamic' and args[:3] == (MODAL, 0x101, 0) for name, args in m.calls)
        assert any(name == 'text_set' and args[1] == BODY for name, args in m.calls)
        assert any(name == 'native_draw_list' and args[2:] == (0, 30) for name, args in m.calls)
        assert m.uc.mem_read(GROUP+0xbb, 1)[0] & 1
        count += 1
    m = Machine(payload, metadata)
    m.run()
    m.calls.clear()
    m.run()
    assert m.get(MODAL) == 2 and m.get(m.context+4) == 1
    m.close_now = True
    m.calls.clear()
    m.run()
    assert m.get(SCENE+0x10) == 0xFA and m.get(m.context) == 0
    assert [name for name, _ in m.calls] == ['native_modal_update', 'native_reset_row']
    assert not m.uc.mem_read(GROUP+0xbb, 1)[0] & 1
    count += 1
    for current, pending in ((2, 4), (0, 1), (0, 2)):
        m = Machine(payload, metadata)
        m.put(MODAL, current)
        m.put(MODAL+4, pending)
        m.run()
        assert m.get(MODAL) == current and m.get(MODAL+4) == pending
        assert [name for name, _ in m.calls] == ['native_reset_row']
        count += 1
    for body, identifier in (('', 'hotpepper:J000000001'), ('x'*513, 'hotpepper:J000000001'),
                             ('text', 'other:1'), ('text', 'hotp')):
        m = Machine(payload, metadata, body=body, identifier=identifier)
        m.run()
        assert not any(name == 'native_open_dynamic' for name, _ in m.calls)
        assert m.get(SCENE+0x10) == 0xFA
        count += 1
    for phase in (0, 1):
        m = Machine(payload, metadata)
        m.put(m.context+4, phase)
        m.put(HOME+0xAC, 1)
        m.run()
        assert not m.calls and m.get(m.context+4) == phase
        count += 1
    m = Machine(payload, metadata)
    m.put(m.context+4, 1)
    m.put(GLOBAL+0x2C0, 3)
    m.run()
    assert [name for name, _ in m.calls] == ['native_modal_update']
    assert m.calls[0][1][1:3] == (0, 0) and m.get(m.context) == 0
    count += 1
    m = Machine(payload, metadata)
    m.put(m.context, SCENE+0x100)
    m.run()
    assert not m.calls
    count += 1
    m = Machine(payload, metadata)
    m.found = False
    m.run()
    assert not any(name == 'native_open_dynamic' for name, _ in m.calls)
    assert m.get(SCENE+0x10) == 0xFA
    count += 1
    for active, owner in ((0, SCENE), (1, SCENE), (1, SCENE+0x100)):
        m = Machine(payload, metadata)
        m.setreg(3, SCENE)
        m.put(m.context, owner)
        m.put(m.context+4, active)
        m.put(m.context+8, GROUP)
        m.uc.mem_write(GROUP+0xbb, b'\x01')
        before = [m.reg(n) for n in range(3, 32)]
        m.uc.reg_write(m.regs.UC_PPC_REG_CR, 0x12345678)
        m.uc.reg_write(m.regs.UC_PPC_REG_CTR, 0xFEED0000)
        m.run('directory_cleanup')
        assert before == [m.reg(n) for n in range(3, 32)]
        assert m.uc.reg_read(m.regs.UC_PPC_REG_CR) == 0x12345678
        assert m.uc.reg_read(m.regs.UC_PPC_REG_CTR) == 0xFEED0000
        if owner == SCENE:
            assert m.get(m.context) == 0 and not m.uc.mem_read(GROUP+0xbb, 1)[0] & 1
            assert len(m.calls) == active
        else:
            assert not m.calls and m.get(m.context) == owner
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    args = parser.parse_args()
    count = verify(args.payload.read_bytes(), json.loads(args.metadata.read_bytes()))
    print(f'{count} compiled PPC scenarios passed with mocked SDK calls; no Dolphin/render verification')


if __name__ == '__main__':
    main()
