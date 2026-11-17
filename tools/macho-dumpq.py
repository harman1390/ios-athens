#!/usr/bin/env python3
# Dump qwords from a Mach-O file at given vaddrs. Maps vaddr->file offset using
# the LC_SEGMENT_64 table (handles __DATA_DIRTY etc).
import struct, sys

path = sys.argv[1]
addrs = [int(a, 16) for a in sys.argv[2:]]

with open(path, 'rb') as f:
    data = f.read()

magic, cputype, cpusub, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from('<8I', data, 0)
segs = []
off = 32
for _ in range(ncmds):
    cmd, cmdsize = struct.unpack_from('<II', data, off)
    if cmd == 0x19:  # LC_SEGMENT_64
        segname = data[off + 8:off + 24].split(b'\x00')[0].decode()
        vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<4Q', data, off + 24)
        segs.append((segname, vmaddr, vmsize, fileoff, filesize))
    off += cmdsize

def va2off(va):
    for name, vmaddr, vmsize, fileoff, filesize in segs:
        if vmaddr <= va < vmaddr + vmsize and va - vmaddr < filesize:
            return fileoff + (va - vmaddr)
    return None

for va in addrs:
    o = va2off(va)
    if o is None:
        print(hex(va), 'unmapped')
        continue
    val = struct.unpack_from('<Q', data, o)[0]
    print(f'{hex(va)} -> {hex(val)}')
