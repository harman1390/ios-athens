#!/usr/bin/env python3
# Minimal Mach-O symtab dump: list symbols (name, value) matching keywords,
# and find the symbol whose range contains a given address.
import struct, sys

path = sys.argv[1]
keywords = [k.lower() for k in sys.argv[2].split(',')] if len(sys.argv) > 2 else []
want_addr = int(sys.argv[3], 16) if len(sys.argv) > 3 else None

with open(path, 'rb') as f:
    data = f.read()

magic, cputype, cpusub, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from('<8I', data, 0)
symoff = nsyms = stroff = strsize = None
indirectsymoff = nindirect = None
off = 32
for _ in range(ncmds):
    cmd, cmdsize = struct.unpack_from('<II', data, off)
    if cmd == 0x2:  # LC_SYMTAB
        symoff, nsyms, stroff, strsize = struct.unpack_from('<4I', data, off + 8)
    elif cmd == 0xB:  # LC_DYSYMTAB
        vals = struct.unpack_from('<18I', data, off + 8)
        indirectsymoff, nindirect = vals[11], vals[12]
    off += cmdsize

assert symoff is not None, 'no symtab'
syms = []
for i in range(nsyms):
    n_strx, n_type, n_sect, n_desc, n_value = struct.unpack_from('<IBBHQ', data, symoff + i * 16)
    if n_strx == 0:
        continue
    end = data.index(b'\x00', stroff + n_strx)
    name = data[stroff + n_strx:end].decode('utf-8', 'replace')
    syms.append((name, n_value, n_type))

syms.sort(key=lambda s: s[1])
if want_addr is not None:
    prev = None
    for name, val, _t in syms:
        if val > want_addr:
            break
        prev = (name, val)
    print(f'addr {hex(want_addr)} -> nearest symbol <= : {prev[0]} @ {hex(prev[1])} (+{hex(want_addr - prev[1])})')

for name, val, _t in syms:
    if keywords and any(k in name.lower() for k in keywords):
        print(f'{hex(val)} {name}')
