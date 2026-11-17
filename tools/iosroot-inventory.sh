#!/bin/bash
# Inventory the mounted iOS rootfs: which bring-up dirs/files exist.
M="${1:-/root/ioswork/mnt}"
echo "=== mount check ==="
findmnt "$M" || cat /proc/mounts | grep hfs
echo
echo "=== /private/var/installd tree ==="
find "$M/private/var/installd" -maxdepth 5 -type d 2>/dev/null | sed "s|$M||"
echo
echo "=== required dirs present? ==="
for p in \
  "/Library/Application Support/com.apple.TCC" \
  "/private/var/mobile/Library/Application Support" \
  "/private/var/mobile/Library/Application Support/com.apple.TCC" \
  "/private/var/installd/Library/Caches/com.apple.containermanagerd" \
  "/private/var/folders" \
  "/private/var/Keychains" \
  "/private/var/MobileActivation" \
  "/private/var/tmp" \
  "/private/var/containers" \
  "/private/var/mobile/Library" \
  ; do
  if [ -d "$M$p" ]; then echo "EXISTS : $p"; else echo "MISSING: $p"; fi
done
echo
echo "=== dyld cache dsc.05 patch offsets ==="
DSC="$M/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64.05"
if [ -f "$DSC" ]; then
  ls -la "$DSC"
  python3 - "$DSC" <<'PY'
import sys
d=open(sys.argv[1],'rb')
def rd(off,n): d.seek(off); return d.read(n).hex()
print('powerassert 0x981a70 :', rd(0x981a70,8), '(want e0ff9f52c0035fd6)')
print('powerassert 0x977154 :', rd(0x977154,12),'(want 00008052280080d2680000f9c0035fd6)')
print('powerassert 0x976b3c :', rd(0x976b3c,8), '(want 00008052c0035fd6)')
print('confstr     0x6e75c  :', rd(0x6e75c,4),  '(orig 3566b295 / patched 17000014)')
PY
else
  echo "DSC.05 NOT FOUND at $DSC"
fi
