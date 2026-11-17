#!/usr/bin/env python3
"""Parse an Android sparse image and report the logical-block offset where the
final chunk begins — i.e. how much of the partition `fastboot flash` covers
before it dies on the last (huge FILL) chunk.

  sparse-tail.py IMAGE.simg

Prints: total_chunks, and for the LAST chunk its type, starting logical block,
and block count. The recovery-dd fallback then writes the raw image tail with
`dd of=/dev/block/sdc59 bs=4096 seek=<start_blk> conv=notrunc`.
"""
import struct, sys

MAGIC = 0xED26FF3A
CHUNK_RAW, CHUNK_FILL, CHUNK_DONT_CARE, CHUNK_CRC = 0xCAC1, 0xCAC2, 0xCAC3, 0xCAC4
TYPES = {CHUNK_RAW: 'RAW', CHUNK_FILL: 'FILL', CHUNK_DONT_CARE: 'DONT_CARE', CHUNK_CRC: 'CRC'}


def main():
    path = sys.argv[1]
    with open(path, 'rb') as f:
        hdr = f.read(28)
        magic, maj, minor, fhdr, chdr, blk, total_blks, total_chunks, csum = struct.unpack('<IHHHHIIII', hdr)
        if magic != MAGIC:
            sys.exit(f'{path}: not a sparse image (magic {magic:#x})')
        print(f'sparse: blk={blk} total_blks={total_blks} ({total_blks*blk/2**30:.1f} GiB) chunks={total_chunks}')
        pos = fhdr
        blkpos = 0
        last = None
        counts = {}
        for i in range(total_chunks):
            f.seek(pos)
            ch = f.read(chdr)
            ctype, _, csz, tsz = struct.unpack('<HHII', ch)
            name = TYPES.get(ctype, hex(ctype))
            counts[name] = counts.get(name, 0) + 1
            last = (i, name, blkpos, csz, tsz)
            blkpos += csz
            # advance: header + payload (RAW=data, FILL=4B, others=0)
            if ctype == CHUNK_RAW:
                pos += chdr + csz * blk
            elif ctype == CHUNK_FILL:
                pos += chdr + 4
            elif ctype == CHUNK_CRC:
                pos += chdr + 4
            else:
                pos += chdr
        print('chunk types:', counts)
        i, name, start, csz, tsz = last
        print(f'LAST chunk #{i}: {name} start_blk={start} blocks={csz} '
              f'({csz*blk/2**30:.2f} GiB) ends_blk={start+csz}')
        print(f'>> fastboot covers blocks [0,{start}); tail dd seek={start}')


if __name__ == '__main__':
    main()
