#!/usr/bin/env python3
# Parse LC_DYLD_INFO(_ONLY) bind opcodes -> map GOT/vaddr -> symbol name.
# Then find the stub that references a given symbol's GOT slot and BL callers.
import struct, sys

path = sys.argv[1]
target_sym = sys.argv[2] if len(sys.argv) > 2 else None

d = open(path, 'rb').read()
ncmds = struct.unpack_from('<I', d, 16)[0]
off = 32
bind_off = bind_size = lazy_off = lazy_size = None
sects = {}
seg_vm = {}   # seg index -> (vmaddr, fileoff) not needed; we track vaddr directly
for _ in range(ncmds):
    cmd, cs = struct.unpack_from('<II', d, off)
    if cmd in (0x22, 0x80000022):  # LC_DYLD_INFO / LC_DYLD_INFO_ONLY
        vals = struct.unpack_from('<10I', d, off+8)
        # rebase_off,size,bind_off,size,weak_bind_off,size,lazy_bind_off,size,export_off,size
        bind_off, bind_size = vals[2], vals[3]
        lazy_off, lazy_size = vals[6], vals[7]
    elif cmd == 0x19:
        nsects = struct.unpack_from('<I', d, off+64)[0]
        so = off + 72
        for s in range(nsects):
            sn = d[so:so+16].split(b'\0')[0].decode()
            addr, size = struct.unpack_from('<QQ', d, so+32)
            fo = struct.unpack_from('<I', d, so+48)[0]
            sects[sn] = (addr, size, fo)
            so += 80
    off += cs

def uleb(p):
    r = 0; s = 0
    while True:
        b = d[p]; p += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80): break
        s += 7
    return r, p

def sleb(p):
    r = 0; s = 0
    while True:
        b = d[p]; p += 1
        r |= (b & 0x7F) << s
        s += 7
        if not (b & 0x80):
            if b & 0x40: r |= -(1 << s)
            break
    return r, p

def parse_binds(start, size, tag):
    p = start; end = start + size
    seg_idx = 0; seg_off = 0; sym = ''; typ = 1; addend = 0
    dylib = 0; flags = 0
    # need segment vmaddrs in order - get from LC_SEGMENT_64 order
    results = []
    while p < end:
        b = d[p]; p += 1
        op = b & 0xF0; imm = b & 0x0F
        if op == 0x00:  # DONE
            pass
        elif op == 0x10: dylib = imm
        elif op == 0x20:
            dylib, p = uleb(p)
        elif op == 0x30: dylib = 0xF0 - imm  # special
        elif op == 0x40:
            e = d.index(b'\0', p); sym = d[p:e].decode('utf8','replace'); p = e+1
            flags = imm
        elif op == 0x50: typ = imm
        elif op == 0x60:
            addend, p = sleb(p)
        elif op == 0x70:
            seg_idx = imm; seg_off, p = uleb(p)
        elif op == 0x80:
            seg_off += uleb(p)[0]; p = uleb(p)[1] if False else p
            # redo: need value
            # (handled below properly)
            pass
        elif op == 0x90:  # DO_BIND
            results.append((seg_idx, seg_off, sym, typ))
            seg_off += 8 if typ == 1 else (4 if typ == 0 else 8)
        elif op == 0xA0:  # DO_BIND_ADD_ADDR_ULEB
            v, p = uleb(p)
            results.append((seg_idx, seg_off, sym, typ))
            seg_off += (8 if typ == 1 else 4) + v
        elif op == 0xB0:  # DO_BIND_ADD_ADDR_IMM_SCALED
            results.append((seg_idx, seg_off, sym, typ))
            seg_off += (8 if typ == 1 else 4) + imm*8 if typ==1 else (4+imm*4)
        elif op == 0xC0:  # DO_BIND_ULEB_TIMES_SKIPPING_ULEB
            cnt, p = uleb(p); skip, p = uleb(p)
            for _ in range(cnt):
                results.append((seg_idx, seg_off, sym, typ))
                seg_off += (8 if typ == 1 else 4) + skip
        else:
            pass
    return results

# The seg_off is an OFFSET within the segment, not a vaddr. Need segment vmaddrs.
# Re-parse to get ordered segment vmaddrs.
segs = []
off = 32
for _ in range(ncmds):
    cmd, cs = struct.unpack_from('<II', d, off)
    if cmd == 0x19:
        vmaddr = struct.unpack_from('<Q', d, off+24)[0]
        segs.append(vmaddr)
    off += cs

print('segments', [hex(s) for s in segs])

# My opcode parsing above is buggy for ADD_ADDR; rewrite cleanly below.
def parse(start, size):
    p = start; end = start + size
    seg_i = 0; seg_off = 0; sym=''; typ=1; dylib=0
    out=[]
    while p < end:
        b=d[p]; p+=1
        op=b&0xF0; imm=b&0x0F
        if op==0x00: continue
        if op==0x10: dylib=imm; continue
        if op==0x20: dylib,p=uleb(p); continue
        if op==0x30: dylib=0xF0-imm; continue
        if op==0x40:
            e=d.index(b'\0',p); sym=d[p:e].decode('utf8','replace'); p=e+1; continue
        if op==0x50: typ=imm; continue
        if op==0x60: _,p=sleb(p); continue
        if op==0x70: seg_i=imm; seg_off,p=uleb(p); continue
        if op==0x80:
            v,p=uleb(p); seg_off+=v; continue
        step = 8 if typ==1 else 4
        if op==0x90:
            out.append((seg_i,seg_off,sym)); seg_off+=step; continue
        if op==0xA0:
            v,p=uleb(p); out.append((seg_i,seg_off,sym)); seg_off+=step+v; continue
        if op==0xB0:
            out.append((seg_i,seg_off,sym)); seg_off+=step+imm*step; continue
        if op==0xC0:
            cnt,p=uleb(p); skip,p=uleb(p)
            for _ in range(cnt):
                out.append((seg_i,seg_off,sym)); seg_off+=step+skip
            continue
    return out

if bind_off:
    for seg_i, so, sym in parse(bind_off, bind_size):
        va = segs[seg_i] + so if seg_i < len(segs) else so
        if target_sym is None or sym == target_sym:
            print(f'{tag if False else "bind"} GOT/vaddr={va:#x} sym={sym}')
