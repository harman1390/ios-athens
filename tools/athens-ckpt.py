#!/usr/bin/env python3
"""athens-ckpt.py KERNEL OUT [VA ...]

Binary-patch checkpoint stubs into the kernel's early init path. Each site
gets `b stub_i`; the stub writes marker i+1 to CKPT_MAGIC (0x4ff00000),
dc cvac + dsb, runs the replaced instruction, and branches back. After a
reset the shim prints the last marker on screen (DRAM survives warm resets).
"""
import struct, sys

TEXT_EXEC_VA, TEXT_EXEC_FO = 0xfffffe0007300000, 0x2fc000
ENTRY = 0xfffffe00074ab488
STUB_BASE = ENTRY + 0x400          # inside the post-entry NOP sled
CKPT = 0xc256bf00

def fo(va):
    return TEXT_EXEC_FO + (va - TEXT_EXEC_VA)

def stub(marker, orig_word, site):
    b_back = 0x14000000 | (((site + 4 - (STUB_BASE + (marker - 1) * 32 + 28)) >> 2) & 0x3ffffff)
    return [
        0x52800000 | (marker << 5) | 9,     # movz w9, #marker
        0xd297e00a,                          # movz x10, #0xbf00
        0xf2b84aca,                          # movk x10, #0xc256, lsl#16 -> x10 = 0xc256bf00
        0xb9000149,                          # str w9, [x10]
        0xd50b7a2a,                          # dc cvac, x10
        0xd5033f9f,                          # dsb sy
        struct.unpack('<I', orig_word)[0],   # replaced instruction
        b_back,                              # b site+4
    ]

def main():
    kernel, out = sys.argv[1], sys.argv[2]
    sites = [int(a, 0) for a in sys.argv[3:]]
    d = bytearray(open(kernel, 'rb').read())
    # nop the debug-lock write (traps on SBC-fused units)
    d[fo(0xfffffe00074ad0ec):fo(0xfffffe00074ad0ec) + 4] = b'\x1f\x20\x03\xd5'
    for i, va in enumerate(sites, 1):
        o = fo(va)
        orig = bytes(d[o:o + 4])
        stub_va = STUB_BASE + (i - 1) * 32
        # detour at site -> stub
        d[o:o + 4] = struct.pack('<I', 0x14000000 | (((stub_va - va) >> 2) & 0x3ffffff))
        # stub body
        d[fo(stub_va):fo(stub_va) + 32] = struct.pack('<8I', *stub(i, orig, va))
        print(f'ckpt{i} @{va:#x} -> stub {stub_va:#x} (was {orig.hex()})')
    open(out, 'wb').write(d)
    print('wrote', out)

if __name__ == '__main__':
    main()
