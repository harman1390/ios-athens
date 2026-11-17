#!/usr/bin/env python3
# Scan a Mach-O __text for stores to a target vaddr via adrp+str/str patterns.
# Reports the storing instruction's vaddr so we can find the resolver registration.
import struct, sys, glob, os

target = int(sys.argv[1], 16)
tpage = target & ~0xFFF
toff = target & 0xFFF

def segs(data):
    ncmds = struct.unpack_from('<I', data, 16)[0]
    off = 32
    out = []
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from('<II', data, off)
        if cmd == 0x19:
            segname = data[off+8:off+24].split(b'\0')[0].decode()
            vmaddr, vmsize, fileoff = struct.unpack_from('<QQQ', data, off+24)[0:3]
            # actually vmaddr@24,vmsize@32,fileoff@40,filesize@48
            vmaddr, vmsize = struct.unpack_from('<QQ', data, off+24)
            fileoff, filesize = struct.unpack_from('<QQ', data, off+40)
            nsects = struct.unpack_from('<I', data, off+64)[0]
            so = off + 72
            for _s in range(nsects):
                sn = data[so:so+16].split(b'\0')[0].decode()
                addr, size = struct.unpack_from('<QQ', data, so+32)
                fo = struct.unpack_from('<I', data, so+48)[0]
                flags = struct.unpack_from('<I', data, so+64)[0]
                if sn == '__text':
                    out.append((addr, size, fo, segname))
                so += 80
        off += cmdsize
    return out

def scan(path):
    data = open(path,'rb').read()
    if struct.unpack_from('<I',data,0)[0] != 0xFEEDFACF: return
    for va,size,fo,seg in segs(data):
        code = data[fo:fo+size]
        # adrp xd, page  -> imm = (page - (pc&~fff))>>12 ; we just decode imm and compute target page
        adrp = {}  # reg -> page addr
        for i in range(0, size-4, 4):
            w = struct.unpack_from('<I', code, i)[0]
            pc = va + i
            op = w >> 24
            if (w & 0x9F000000) == 0x90000000:  # ADRP
                immlo = (w >> 29) & 3
                immhi = (w >> 5) & 0x7FFFF
                imm = (immhi << 2) | immlo
                if imm & (1<<20): imm -= (1<<21)
                rd = w & 0x1F
                page = (pc & ~0xFFF) + (imm << 12)
                adrp[rd] = page
            elif (w & 0x3B000000) == 0x39000000 or (w & 0x3B000000)==0xB9000000 or (w & 0x3B000000)==0xF9000000:
                # LDR/STR unsigned imm : size in bits31:30, opc...
                size_bits = (w >> 30) & 3
                rn = (w >> 5) & 0x1F
                imm12 = (w >> 10) & 0xFFF
                if rn in adrp:
                    eff = adrp[rn] + (imm12 << size_bits)
                    if eff == target:
                        kind = 'STR' if (w>>22)&1==0 else 'LDR?'
                        print(f'{os.path.basename(path)}: {"STR" if (w & 0x00400000)==0 else "LDR"} to {target:#x} at pc={pc:#x} (adrp page={adrp[rn]:#x} imm12={imm12} sz={size_bits})')
            elif (w & 0x3B200000) == 0x38200000:  # STR/LDR register offset (64-bit)
                rn = (w >> 5) & 0x1F
                rm = (w >> 16) & 0x1F
                if rn in adrp and adrp[rn] == target:
                    print(f'{os.path.basename(path)}: regoff access to {target:#x} at pc={pc:#x}')

for p in sys.argv[2:]:
    scan(p)
