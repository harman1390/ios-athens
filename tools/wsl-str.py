#!/usr/bin/env python3
# Read a C string from a Mach-O by preferred vmaddr (file off = va - 0x100000000
# holds for __TEXT in these binaries; adjust base if needed).
import sys

path = sys.argv[1]
base = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x100000000
addrs = [int(a, 16) for a in sys.argv[3:]]

with open(path, 'rb') as f:
    data = f.read()

for va in addrs:
    off = va - base
    end = data.index(b'\x00', off)
    print(hex(va), repr(data[off:end].decode('utf-8', 'replace')))
