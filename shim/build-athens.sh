#!/bin/bash
# Build the athens shim with clang + lld and wrap it into the stock boot.img.
#   shim/build-athens.sh STOCK_BOOT_IMG [PAYLOAD]   -> shim/out/athens-boot.img
# Without PAYLOAD the stock ramdisk stays and the shim stops at "no SWEETXNU payload".
set -euo pipefail
cd "$(dirname "$0")"
STOCK=${1:?usage: build-athens.sh STOCK_BOOT_IMG [PAYLOAD]}
CFLAGS="--target=aarch64-none-elf -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra -DATHENS"
mkdir -p out/athens
OBJS=()
for f in start.S athens.c console.c fdt.c loader.c ufsdump.c; do
	o=out/athens/${f%.*}.o
	clang $CFLAGS -c $f -o $o
	OBJS+=($o)
done
# LK puts the Image wherever it likes and nothing relocates it: no absolute
# pointers may appear in the C objects (start.o's image_size is the exception).
python ../tools/viva-check-abs.py out/athens/athens.o out/athens/console.o out/athens/fdt.o out/athens/loader.o
ld.lld -T shim.ld --build-id=none -N "${OBJS[@]}" -o out/athens/shim.elf
ld.lld -T shim.ld --build-id=none -N "${OBJS[@]}" --oformat=binary -o out/athens/Image
size=$(python ../tools/viva-check-abs.py --symbol _end out/athens/shim.elf)
python -c "f=open('out/athens/Image','r+b'); f.truncate($size)"
# MediaTek LK only boots a gzip kernel (viva proved it; verify on realme LK in
# Phase 1 — if a raw Image is needed, drop this step).
gzip -9 -n -c out/athens/Image > out/athens/Image.gz
python ../tools/viva-bootimg.py repack "$STOCK" out/athens/Image.gz out/athens-boot.img ${2:+--ramdisk "$2"}
ls -l out/athens/Image out/athens/Image.gz out/athens-boot.img
