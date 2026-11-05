#!/usr/bin/env python3
"""athens-bands.py KERNEL OUT [VA ...]

Like athens-ckpt but each checkpoint paints a colored stripe at a different
framebuffer row (fb phys = VA while MMU off / V=P bootstrap map). Bands stay
visible while the phone is frozen: the screen shows the deepest point reached.
Rows: 800, 1000, ... Colors: red, orange, yellow, green, cyan, blue, magenta, white.
"""
import struct, sys

TEXT_EXEC_VA, TEXT_EXEC_FO = 0xfffffe0007300000, 0x2fc000
ENTRY = 0xfffffe00074ab488
STUB_BASE = ENTRY + 0x400
FB = 0x77e20000
COLORS = [0xffff0000, 0xffff8000, 0xffffff00, 0xff00ff00,
          0xff00ffff, 0xff0000ff, 0xffff00ff, 0xffffffff]

def fo(va):
    return TEXT_EXEC_FO + (va - TEXT_EXEC_VA)

def band(marker, orig_word, site):
    addr = FB + (700 + marker * 200) * 4352   # rows 900,1100,...2300
    col = COLORS[(marker - 1) & 7]
    back = site + 4
    instrs = [
        0xd280000a | ((addr & 0xffff) << 5),          # movz x10, #lo
        0xf2a00000 | (((addr >> 16) & 0xffff) << 5) | 0xa,  # movk x10, #hi, lsl16
        0xaa0a03e5,                                   # mov x5, x10
        0x52800001 | ((col & 0xffff) << 5),           # movz w1, #col_lo
        0x72a00000 | (((col >> 16) & 0xffff) << 5) | 1,     # movk w1, #col_hi, lsl16
        0xd2810002,                                   # movz x2, #0x80 (128 words)
        0xb8004421,                                   # loop: str w1,[x5],#4
        0xf1000442,                                   # subs x2,x2,#1
        0x54ffffc1,                                   # b.ne -8
        0xaa0a03e5,                                   # mov x5, x10
        0xd2801002,                                   # movz x2, #8 (8 lines*64B)
        0xd50b7a25,                                   # cl: dc cvac, x5
        0x910100a5,                                   # add x5,x5,#64
        0xf1000442,                                   # subs
        0x54ffffa1,                                   # b.ne -12
        0xd5033f9f,                                   # dsb sy
        struct.unpack('<I', orig_word)[0],
        0x14000000 | (((back - (STUB_BASE + (marker - 1) * 80 + 68)) >> 2) & 0x3ffffff),
    ]
    return struct.pack('<18I', *instrs)

def main():
    kernel, out = sys.argv[1], sys.argv[2]
    sites = [int(a, 0) for a in sys.argv[3:]]
    d = bytearray(open(kernel, 'rb').read())
    d[fo(0xfffffe00074ad0ec):fo(0xfffffe00074ad0ec) + 4] = b'\x1f\x20\x03\xd5'
    for i, va in enumerate(sites, 1):
        o = fo(va)
        orig = bytes(d[o:o + 4])
        stub_va = STUB_BASE + (i - 1) * 80
        d[o:o + 4] = struct.pack('<I', 0x14000000 | (((stub_va - va) >> 2) & 0x3ffffff))
        d[fo(stub_va):fo(stub_va) + 72] = band(i, orig, va)
        print(f'band{i} @{va:#x} -> {stub_va:#x} color {COLORS[(i-1)&7]:#x}')
    open(out, 'wb').write(d)
    print('wrote', out)

if __name__ == '__main__':
    main()
