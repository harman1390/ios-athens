#!/bin/bash
# XNU kernel -> athens boot image (shim + SWEETXNU payload in the ramdisk).
#   tools/athens-mkboot.sh KERNEL STOCK_BOOT_IMG [STAGE]   -> shim/out/athens-boot.img
#
# STAGE (default ufs-ro):
#   nostorage  no UFS node: the kernel never touches storage, panics at root mount
#   ufs-ro     UFS node, writes refused (no ufsrw): finds "userdata" and tries to mount it
#   ufs-rw     iOS root in userdata, read-write; writes stay inside that partition
# Env: ATHENS_CMDLINE replaces the whole command line; ATHENS_EXTRA sets single
# boot-args on top (default "cpus=8": all eight cores, incl. the two A76s).
# sweetfb_noconsole=1 keeps kernel text off the screen once the GUI's first
# frame appears; panics still draw.
# Every stage turns off sweet's Qualcomm drivers (keys, touch, USB, persistent
# log): their fixed MMIO addresses are other blocks on MT6853.
set -euo pipefail
cd "$(dirname "$0")/.."
KERNEL=${1:?usage: athens-mkboot.sh KERNEL STOCK_BOOT_IMG [nostorage|ufs-ro|ufs-rw]}
STOCK=${2:?usage: athens-mkboot.sh KERNEL STOCK_BOOT_IMG [nostorage|ufs-ro|ufs-rw]}
STAGE=${3:-ufs-ro}

# athens userdata/GPT is on UFS LUN 2 (verified: sdc = SCSI 0:0:0:2).
# viva's were on LUN 2).
BASE='debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 wdt=-1 wdt_test=no_user_checkin sweetkeys=0 sweettouch=0 sweetusb=0 sweetusblog=0 sweetlog=0 sweetfb_noconsole=1'
case $STAGE in
nostorage) ADT_FLAGS=(--athens); CMDLINE=$BASE ;;
ufs-ro) ADT_FLAGS=(--athens --athens-ufs); CMDLINE=$BASE ;;
ufs-rw) ADT_FLAGS=(--athens --athens-ufs)
	CMDLINE="$BASE ufsrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1" ;;
*) echo "unknown stage $STAGE" >&2; exit 2 ;;
esac
# ATHENS_HIGHMEM=1 puts the XNU pool in the high DRAM bank (>4G): MTK
# firmware engines whose reserved-memory alloc-ranges are 32-bit cannot
# write there (run-6 hit at 0xe0000000 was inside dram_r1's range).
[ "${ATHENS_HIGHMEM-0}" = 1 ] && ADT_FLAGS+=(--highmem)
CMDLINE=${ATHENS_CMDLINE:-$CMDLINE}
# ATHENS_EXTRA="cpus=6": set/replace single boot-args (XNU uses the first match)
for arg in ${ATHENS_EXTRA-cpus=8}; do
	key=${arg%%=*}
	CMDLINE="$(printf ' %s ' "$CMDLINE" | sed -E "s/ -?$key(=[^ ]*)? / /g; s/^ +//; s/ +$//") $arg"
done
echo "stage $STAGE: $CMDLINE"

mkdir -p shim/out
python tools/mkadt.py shim/out/athens.adt "${ADT_FLAGS[@]}"
python tools/mkpayload.py "$KERNEL" shim/out/athens.adt shim/out/athens-payload.bin --cmdline "$CMDLINE"
# LK loads the ramdisk and DTB at fixed offsets; the payload must fit below the
# DTB load address. MEASURE both from the phone's LK log / live boot (viva's
# were ramdisk 0x47c80000, DTB 0x4bc80000 = 64 MiB of room).
size=$(python -c "import os;print(os.path.getsize('shim/out/athens-payload.bin'))")
[ "$size" -lt $((0x4bc80000 - 0x47c80000)) ] || { echo "error: payload ($size bytes) may overrun LK's DTB" >&2; exit 1; }
shim/build-athens.sh "$STOCK" "$PWD/shim/out/athens-payload.bin"
