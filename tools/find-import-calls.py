#!/usr/bin/env python3
# Find call sites of an imported symbol in a Mach-O by resolving
# symtab -> indirect symtab -> __stubs -> bl targets.
import struct, sys

path = sys.argv[1]
symname = sys.argv[2]

d = open(path, 'rb').read()
magic = struct.unpack_from('<I', d, 0)[0]
assert magic == 0xFEEDFACF
ncmds = struct.unpack_from('<I', d, 16)[0]
off = 32
symoff = nsyms = stroff = strsize = None
indoff = nind = None
sects = {}   # name -> (addr,size,foff)
seginfo = []
for _ in range(ncmds):
    cmd, cs = struct.unpack_from('<II', d, off)
    if cmd == 0x2:
        symoff, nsyms, stroff, strsize = struct.unpack_from('<4I', d, off+8)
    elif cmd == 0xB:
        v = struct.unpack_from('<18I', d, off+8)
        indoff, nind = v[11], v[12]
    elif cmd == 0x19:
        seg = d[off+8:off+24].split(b'\0')[0].decode()
        nsects = struct.unpack_from('<I', d, off+64)[0]
        so = off + 72
        for s in range(nsects):
            sn = d[so:so+16].split(b'\0')[0].decode()
            addr, size = struct.unpack_from('<QQ', d, so+32)
            fo = struct.unpack_from('<I', d, so+48)[0]
            sects[sn] = (addr, size, fo)
            so += 80
    off += cs

def symname_at(i):
    n_strx = struct.unpack_from('<I', d, symoff + i*16)[0]
    e = d.index(b'\0', stroff + n_strx)
    return d[stroff+n_strx:e].decode('utf-8', 'replace')

# find symtab index of target
target_idx = None
for i in range(nsyms):
    if symname_at(i) == symname:
        target_idx = i
        break
print('symtab index', target_idx, symname)
if target_idx is None:
    sys.exit(1)

# indirect symtab: entries are uint32 symtab indices; first nindirect are for
# the section's indirect symbols. We need the __stubs section's reserved1
# (index into indirect symtab) and count.
stubs = sects.get('__stubs')
print('__stubs', stubs)
# find __stubs section header reserved1/reserved2 - need section struct; reparse
# simpler: __stubs addr/size known; each stub is 12 bytes? determine by count.
# Get reserved1 (indirect sym index start) from section - reparse sections with reserved fields
off = 32
stub_res1 = stub_nind = text_sect = None
for _ in range(ncmds):
    cmd, cs = struct.unpack_from('<II', d, off)
    if cmd == 0x19:
        nsects = struct.unpack_from('<I', d, off+64)[0]
        so = off + 72
        for s in range(nsects):
            sn = d[so:so+16].split(b'\0')[0].decode()
            addr, size = struct.unpack_from('<QQ', d, so+32)
            fo = struct.unpack_from('<I', d, so+48)[0]
            res1, res2 = struct.unpack_from('<II', d, so+68)
            if sn == '__stubs':
                stub_res1, stub_nind = res1, res2
                stub_addr, stub_size = addr, size
            if sn == '__text':
                text_sect = (addr, size, fo)
            so += 80
    off += cs
print('stub_res1', stub_res1, 'stub_nind', stub_nind, 'stub_addr', hex(stub_addr) if stub_addr else None, 'size', hex(stub_size) if stub_size else None)

# each stub = 12 bytes? check: stub_size / stub_nind
stub_sz = stub_size // stub_nind if stub_nind else 12
print('stub size each', stub_sz)

# find which indirect entry == target_idx
target_stub_idx = None
for k in range(stub_nind):
    si = struct.unpack_from('<I', d, indoff + (stub_res1 + k)*4)[0]
    if si == target_idx:
        target_stub_idx = k
        break
print('stub ordinal', target_stub_idx)
if target_stub_idx is None:
    # maybe symbol is in __got not __stubs
    sys.exit(2)

target_stub_va = stub_addr + target_stub_idx * stub_sz
print('target stub va', hex(target_stub_va))

# scan __text for BL to target_stub_va
ta, ts, tf = text_sect
code = d[tf:tf+ts]
hits = []
for i in range(0, ts, 4):
    w = struct.unpack_from('<I', code, i)[0]
    if (w >> 26) == 0b100101:
        imm = w & 0x3FFFFFF
        if imm & 0x2000000: imm -= 0x4000000
        pc = ta + i
        if pc + imm*4 == target_stub_va:
            hits.append(pc)
print('call sites:', [hex(h) for h in hits])
