#!/usr/bin/env python3
"""Sparse-aware Android sparse image -> raw image converter.

  simg2raw-sparse.py IN.simg OUT.raw.img

Unlike simg2img (which expands every block and so allocates the full ~51 GiB),
this leaves zero-fill and uncovered regions as filesystem holes, so OUT only
consumes real disk for actual data (~11 GiB for the iOS rootfs). The output is
still a complete, mountable raw image: holes read back as zeros.

Chunk types (standard Android sparse):
  0xCAC1 RAW       -> write csz*blk_sz literal bytes at the logical offset
  0xCAC2 FILL      -> expand the 4-byte value over csz blocks; value 0 is left
                      as a hole (reads as 0), non-zero values are written
  0xCAC3 DONT_CARE -> left as hole (reads as 0)
  0xCAC4 CRC       -> skipped

Gaps between chunks stay holes (implicit zeros). OUT.raw.img is (re)created
sparse via truncate, so re-running is safe.
"""
import os
import struct
import sys

HDR = struct.Struct('<IHHHHIIII')
CH = struct.Struct('<HHII')
MAGIC = 0xED26FF3A
RAW, FILL, DONT_CARE, CRC = 0xCAC1, 0xCAC2, 0xCAC3, 0xCAC4
COPY = 4 << 20  # 4 MiB io buffer


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]

    with open(src, 'rb') as f:
        magic, _maj, _min, fhs, chs, blk, total_blks, total_chunks, _cs = HDR.unpack(f.read(28))
        if magic != MAGIC:
            sys.exit(f'{src}: not a sparse image (magic {magic:#x})')
        logical = total_blks * blk

        if os.path.exists(dst):
            os.remove(dst)
        out = open(dst, 'w+b')
        out.truncate(logical)  # sparse: size set, blocks unallocated

        pos, blkpos, written_chunks = fhs, 0, 0
        for _ in range(total_chunks):
            f.seek(pos)
            ctype, _r1, csz, tsz = CH.unpack(f.read(chs))
            off = blkpos * blk
            if ctype == RAW:
                out.seek(off)
                remaining = csz * blk
                while remaining:
                    d = f.read(min(COPY, remaining))
                    if not d:
                        raise EOFError(f'{src}: truncated in chunk at blk {blkpos}')
                    out.write(d)
                    remaining -= len(d)
            elif ctype == FILL:
                v = f.read(4)
                if v != b'\0\0\0\0':
                    out.seek(off)
                    nbytes = csz * blk
                    reps = min(nbytes // 4, COPY // 4)
                    buf = v * reps
                    done = 0
                    while done < nbytes:
                        w = min(len(buf), nbytes - done)
                        out.write(buf[:w])
                        done += w
            # DONT_CARE / CRC: leave hole / skip

            if ctype == RAW:
                pos += chs + csz * blk
            elif ctype in (FILL, CRC):
                pos += chs + 4
            else:
                pos += chs
            blkpos += csz
            written_chunks += 1

        out.flush()
        out.close()

    st = os.stat(dst)
    print(f'{dst}: logical {logical} bytes ({logical / 2**30:.1f} GiB), '
          f'allocated ~{st.st_blocks * 512 / 2**30:.1f} GiB, {written_chunks} chunks')


if __name__ == '__main__':
    main()
