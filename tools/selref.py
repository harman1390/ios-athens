#!/usr/bin/env python3
# Resolve an __objc_selrefs entry: read the pointer at `selref_va`, treat it as
# a vaddr into __TEXT.__objc_methname, and print the selector string.
import struct, sys

path = sys.argv[1]
selref_va = int(sys.argv[2], 16)
TEXT_BASE = 0x100000000  # file off == va - base for this binary's segments

with open(path, 'rb') as f:
    data = f.read()

def read_va(va, n):
    return data[va - TEXT_BASE: va - TEXT_BASE + n]

ptr = struct.unpack('<Q', read_va(selref_va, 8))[0]
print(f'selref {hex(selref_va)} -> {hex(ptr)}')
# ptr should be a vaddr in __objc_methname (0x10006c026-0x100074dca)
if 0x100000000 <= ptr < 0x100080000:
    end = data.index(b'\x00', ptr - TEXT_BASE)
    print('selector:', data[ptr - TEXT_BASE:end].decode('utf-8', 'replace'))
else:
    print('(pointer not a plain vaddr - chained fixup?)')
