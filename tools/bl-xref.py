#!/usr/bin/env python3
# Find all BL call sites of a target vaddr inside a Mach-O __text section,
# then decode the few preceding instructions to recover the integer
# immediate loaded into argument registers (MOVZ/MOVK only - enough for
# confstr-style constant args). No capstone needed.
import struct, sys

path = sys.argv[1]
target = int(sys.argv[2], 16)
lo = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0
hi = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0xFFFFFFFF

f = open(path, 'rb')
data = f.read()

# parse mach-o 64 header
magic = struct.unpack_from('<I', data, 0)[0]
assert magic == 0xFEEDFACF, 'not macho64'
ncmds = struct.unpack_from('<I', data, 16)[0]
off = 32
text = None
for _ in range(ncmds):
    cmd, cmdsize = struct.unpack_from('<II', data, off)
    if cmd == 0x19:  # LC_SEGMENT_64
        segname = data[off+8:off+24].split(b'\0')[0].decode()
        nsects = struct.unpack_from('<I', data, off+64)[0]
        so = off + 72
        for _s in range(nsects):
            sectname = data[so:so+16].split(b'\0')[0].decode()
            addr, size = struct.unpack_from('<QQ', data, so+32)
            foff = struct.unpack_from('<I', data, so+48)[0]
            if segname == '__TEXT' and sectname == '__text':
                text = (addr, size, foff)
            so += 80
    off += cmdsize

assert text, '__text not found'
va, size, foff = text
code = data[foff:foff+size]
print(f'__text va={va:#x} size={size:#x} foff={foff:#x}')

def decode_imm(w, pc):
    # return list of (reg, value) for MOVZ/MOVK/MOVN building 32/64-bit imms
    top = w >> 26
    # MOVZ 32: 0x52800000, MOVZ 64: 0xD2800000 ; MOVK 32:0x72800000,64:0xF2800000 ; MOVN 32:0x12800000,64:0x92800000
    is64 = (w & 0x80000000) != 0
    opc = (w >> 29) & 0x3
    if (w & 0x1F000000) not in (0x10000000, 0x10000000 | 0x40000000):
        pass
    # generic: bits[28:24]=10010 movewide
    if (w >> 23) & 0x1FF != 0b10010100100 and (w >> 23) & 0x1FF != 0b10010101100 and (w >> 23) & 0x1FF != 0b10010100101 and (w >> 23) & 0x1FF != 0b10010101101 and (w >> 23) & 0x1FF != 0b10010101001 and (w >> 23) & 0x1FF != 0b10010101010 and (w >> 23) & 0x1FF != 0b10010100010 and (w >> 23) & 0x1FF != 0b10010100011:
        return None
    return None

# simpler: decode MOVZ/MOVK/MOVN by exact masks
REGS = {}
def movw_imm(w):
    # MOVZ/MOVK/MOVN wide immediate: op bits[30:29], fixed 100101 at [28:23]? Actually:
    # sf[31] opc[30:29] 100101[28:23] hw[22:21] imm16[20:5] Rd[4:0]
    sf = (w >> 31) & 1
    opc = (w >> 29) & 0x3
    fixed = (w >> 23) & 0x3F
    if fixed != 0b100101:
        return None
    hw = (w >> 21) & 0x3
    imm16 = (w >> 5) & 0xFFFF
    rd = w & 0x1F
    kind = {0: 'movn', 2: 'movz', 3: 'movk'}.get(opc)
    if kind is None:
        return None
    return (rd, sf, kind, hw, imm16)

def regval(regs, rd, sf, kind, hw, imm16):
    if kind == 'movz':
        regs[rd] = imm16 << (hw * 16)
        if sf == 0:
            regs[rd] &= 0xFFFFFFFF
    elif kind == 'movk':
        mask = 0xFFFF << (hw * 16)
        cur = regs.get(rd, 0) & ~mask
        regs[rd] = cur | (imm16 << (hw * 16))
        if sf == 0:
            regs[rd] &= 0xFFFFFFFF
    elif kind == 'movn':
        v = (~(imm16 << (hw * 16))) & ((1 << (64 if sf else 32)) - 1)
        regs[rd] = v

hits = []
for i in range(0, size, 4):
    w = struct.unpack_from('<I', code, i)[0]
    if (w >> 26) == 0b100101:  # BL
        imm26 = w & 0x3FFFFFF
        if imm26 & 0x2000000:
            imm26 -= 0x4000000
        pc = va + i
        t = pc + imm26 * 4
        if t == target:
            hits.append(i)

print(f'{len(hits)} call site(s) of {target:#x}')
for i in hits:
    pc = va + i
    print(f'\n--- call site pc={pc:#x} ---')
    regs = {}
    # scan back up to 40 instrs tracking movw (imperfect: ignores other writes)
    start = max(0, i - 40 * 4)
    for j in range(start, i, 4):
        w = struct.unpack_from('<I', code, j)[0]
        m = movw_imm(w)
        if m:
            rd, sf, kind, hw, imm16 = m
            regval(regs, rd, sf, kind, hw, imm16)
    for rd in sorted(regs):
        print(f'  x{rd}/w{rd} = {regs[rd]:#x}')
