#!/usr/bin/env python3
"""Streaming raw image -> Android sparse image for `fastboot flash`.

  stream-img2simg.py IN.img OUT.simg

Constant-memory img2simg: emits each sparse chunk as soon as it is produced
instead of buffering the whole image, so it cannot OOM on a ~50 GiB rootfs.

Zero runs shorter than ZMIN blocks are folded into the surrounding RAW chunk
as literal zeros (keeps chunk count low — tiny per-block RAW chunks are what
tripped the ABL sparse writer before). Zero runs >= ZMIN become a single FILL
chunk. Reads in READ-byte pieces; the file-header chunk count is patched in
after streaming. Holes in a sparse input read as zeros -> FILL (harmless).
"""
import os
import struct
import sys

BLK = 4096
CHUNK_RAW, CHUNK_FILL = 0xCAC1, 0xCAC2
MAX_RAW = 16 << 20          # bytes per RAW chunk
READ = 8 << 20              # read buffer
ZMIN = 64                   # zero-run >= this many blocks -> FILL, else fold
ZERO_BLK = bytes(BLK)
ZERO_FULL = ZERO_BLK * (READ // BLK)
HDR = struct.Struct('<IHHHHIIII')
CH = struct.Struct('<HHII')


def convert(src, dst):
    size = os.path.getsize(src)
    if size % BLK:
        sys.exit(f'{src}: size not a multiple of {BLK}')
    total = size // BLK
    nchunks = 0
    raw_data = 0

    with open(src, 'rb') as f, open(dst, 'wb') as o:
        o.write(b'\0' * HDR.size)          # header patched at end
        raw = bytearray()                  # pending RAW payload (contiguous)
        zrun = 0                           # consecutive zero blocks pending

        def emit_raw():
            nonlocal nchunks, raw_data
            if raw:
                n = len(raw) // BLK
                o.write(CH.pack(CHUNK_RAW, 0, n, 12 + len(raw)))
                o.write(bytes(raw))
                nchunks += 1
                raw_data += n
                raw.clear()

        def emit_fill(n):
            nonlocal nchunks
            # MAX_FILL (env, blocks) caps a single FILL chunk; the ABL sparse
            # writer has been seen to fail expanding one giant trailing fill.
            cap = int(os.environ.get('MAX_FILL', '0') or 0)
            while n:
                k = n if not cap else min(n, cap)
                o.write(CH.pack(CHUNK_FILL, 0, k, 16))
                o.write(struct.pack('<I', 0))
                nchunks += 1
                n -= k

        def resolve_zeros():
            """Decide pending zero-run: FILL if large, fold into raw if small."""
            nonlocal zrun
            if zrun > ZMIN:
                emit_raw()
                emit_fill(zrun)
            elif zrun:
                raw.extend(ZERO_BLK * zrun)
            zrun = 0

        pos = 0
        while pos < size:
            buf = f.read(min(READ, size - pos))
            if not buf:
                break
            nblk = len(buf) // BLK
            # Fast path: every block in this buffer is zero.
            if (len(buf) == READ and buf == ZERO_FULL) or \
               buf == ZERO_BLK * nblk:
                zrun += nblk
                pos += len(buf)
                continue
            base = 0
            for i in range(nblk):
                b = buf[base:base + BLK]
                base += BLK
                if b == ZERO_BLK:
                    zrun += 1
                else:
                    resolve_zeros()
                    raw += b
                    if len(raw) >= MAX_RAW:
                        emit_raw()
            pos += len(buf)

        resolve_zeros()
        emit_raw()

        o.seek(0)
        o.write(HDR.pack(0xED26FF3A, 1, 0, HDR.size, CH.size, BLK,
                         total, nchunks, 0))

    print(f'{dst}: {total} blocks, {nchunks} chunks, '
          f'{raw_data * BLK >> 20} MiB RAW')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2])
