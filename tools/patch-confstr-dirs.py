#!/usr/bin/env python3
"""Patch the iOS 16 dyld_shared_cache so confstr(_CS_DARWIN_USER_DIR) and
confstr(_CS_DARWIN_USER_CACHE_DIR) fall back to a real directory instead of
returning 0 on athens.

Why: on athens there is no separate APFS data volume and no per-user persona
session, so libsystem_c's per-user-directory resolver (the function pointer at
[0x1e1d36228], installed by libSystem init) returns 0 for the
_CS_DARWIN_USER_* names. In _confstr:

  * name 0x10001 (_CS_DARWIN_USER_TEMP_DIR) already has a fallback: on resolver
    failure it does getenv("TMPDIR") then access("/var/tmp/", W_OK).
  * names 0x10000 (_CS_DARWIN_USER_DIR) and 0x10002 (_CS_DARWIN_USER_CACHE_DIR)
    share ONE error path that just returns 0.

tccd (and other daemons) call confstr() for these names, get 0, and hit the
"confstr failed to get directory" trap -> crash-loop. profiled then blocks on
the TCCAccessSetOverride XPC to tccd and SpringBoard stalls on the launch
sentinel -> Apple logo.

Fix: redirect the shared 0x10000/0x10002 error path to the existing 0x10001
fallback block. Both names then resolve to TMPDIR or "/var/tmp/" (a real,
writable directory) exactly the way TEMP_DIR already does. The resolver is
still tried first; this only changes behaviour when it fails, so it is a safe
no-op on paths where the resolver works.

Location: dyld_shared_cache_arm64.05 (dsc.05), __TEXT mapping.
  vaddr 0x18dc5275c  (confstr shared error entry for names 0x10000/0x10002)
  -> file offset 0x6e75c  (verified with `ipsw dyld a2o`)
  original insn:  bl  __error          (35 66 b2 95)
  patched insn:   b   0x18dc527b8      (17 00 00 14)  -> type-1 fallback

Run inside WSL with the iOS rootfs mounted read-write
(`mount -t hfsplus -o loop,rw,force`). Patches are verified before/after.
Idempotent.
"""
import sys, os

MNT = sys.argv[1] if len(sys.argv) > 1 else "/root/iosroot-work/mnt"
DSC_DIR = os.path.join(MNT, "System/Library/Caches/com.apple.dyld")
TARGET = os.path.join(DSC_DIR, "dyld_shared_cache_arm64.05")

# file offset of confstr's shared 0x10000/0x10002 resolver-fail path
OFF = 0x6e75c
ORIG = bytes.fromhex("3566b295")   # bl __error
NEW  = bytes.fromhex("17000014")   # b 0x18dc527b8  (type-1 TMPDIR//var/tmp fallback)

def main():
    if not os.path.exists(TARGET):
        sys.exit(f"cache file not found: {TARGET} (is the rootfs mounted?)")
    st = os.stat(TARGET)
    print(f"target: {TARGET} ({st.st_size} bytes)")
    with open(TARGET, "r+b") as f:
        f.seek(OFF)
        cur = f.read(len(NEW))
        if cur == NEW:
            print(f"  0x{OFF:x}: already patched (confstr dir fallback)")
            return
        if cur != ORIG:
            sys.exit(f"  0x{OFF:x}: UNEXPECTED bytes {cur.hex()} != {ORIG.hex()} - aborting")
        f.seek(OFF)
        f.write(NEW)
        f.flush()
        os.fsync(f.fileno())
        # verify
        f.seek(OFF)
        chk = f.read(len(NEW))
        assert chk == NEW, f"verify failed: {chk.hex()}"
        print(f"  0x{OFF:x}: patched confstr 0x10000/0x10002 -> type-1 fallback ({chk.hex()})")
        print("patched + synced")

if __name__ == "__main__":
    main()
