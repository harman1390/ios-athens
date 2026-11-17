#!/usr/bin/env python3
"""Patch the iOS 16 dyld_shared_cache to neutralize the IOKit user-space
power-assertion API (IOPMAssertion*).

Why: on athens, profiled's main thread blocks forever inside
IOPMAssertionCreateWithDescription -> _io_pm_assertion_create -> mach_msg.
The MIG reply never arrives (the power-assertion backend - kernel
IOPMrootDomain user client or powerd - does not service it on this port).
profiled therefore never finishes init, never services
com.apple.managedconfiguration.profiled, and SpringBoard's launch sentinel
stalls in MCProfileConnection checkIn -> device stays on the Apple logo.

There is no real system sleep on this port (sweetfb_keep holds the panel),
so a fake "assertion held" result is harmless. We make the public create
entry points return success immediately and make release a no-op, so the
entire assertion lifecycle becomes a cheap fake that can never block.

Functions live in dyld_shared_cache_arm64.05 (dsc.05). File offsets were
resolved with `ipsw dyld a2o` against the iOS 16 rootfs cache.

Run inside WSL with the iOS rootfs mounted (mount -o loop -t hfsplus ...).
Patches are verified before and after. Idempotent.
"""
import sys, os

MNT = sys.argv[1] if len(sys.argv) > 1 else "/root/iosroot-work/mnt"
DSC_DIR = os.path.join(MNT, "System/Library/Caches/com.apple.dyld")
TARGET = os.path.join(DSC_DIR, "dyld_shared_cache_arm64.05")

# ARM64 encodings (little-endian byte strings), checked with llvm-mc.
MOV_W8_1    = bytes.fromhex("28008052")   # mov w8, #1       (dummy IOPMAssertionID)
CBZ_X1_8    = bytes.fromhex("410000b4")   # cbz x1, #8       (skip the store if id == NULL)
STR_W8_X1   = bytes.fromhex("280000b9")   # str w8, [x1]     (*AssertionID = 1, 32-bit)
CBZ_X6_8    = bytes.fromhex("460000b4")   # cbz x6, #8
STR_W8_X6   = bytes.fromhex("c80000b9")   # str w8, [x6]
MOV_W0_0    = bytes.fromhex("00008052")   # mov w0, #0       (kIOReturnSuccess)
RET         = bytes.fromhex("c0035fd6")   # ret

# (file offset, stub bytes, accepted prior heads, original tail the stub
#  overwrites, description). Prior heads: the pristine prologue, or the first
#  stub version (returned 0xffff / stored 8 bytes to [x3]: wrong register, it
#  crashed mediaserverd and locationd at IOPMAssertionCreateWithProperties+8).
PATCHES = [
    # IOPMAssertionCreateWithDescription(type, name, details, reason, bundle,
    # timeout(d0), timeoutAction, IOPMAssertionID *id): id is x6 (the body
    # does `mov x19, x6` and passes it as x1 to ...CreateWithProperties).
    (0x981a70, MOV_W8_1 + CBZ_X6_8 + STR_W8_X6 + MOV_W0_0 + RET,
     [bytes.fromhex("e0ff9f52c0035fd6"), bytes.fromhex("f44fbea9")],
     bytes.fromhex("fd430091e80300aa89578052"), "IOPMAssertionCreateWithDescription"),
    # IOPMAssertionCreateWithProperties(CFDictionaryRef, IOPMAssertionID *id):
    # id is x1 (the body does `mov x19, x1; cbz x1`).
    (0x977154, MOV_W8_1 + CBZ_X1_8 + STR_W8_X1 + MOV_W0_0 + RET,
     [bytes.fromhex("00008052280080d2680000f9c0035fd6"), bytes.fromhex("ffc301d1")],
     bytes.fromhex("f44f05a9"), "IOPMAssertionCreateWithProperties"),
    # IOPMAssertionRelease(...) -> IOReturn. No-op success so the fake
    # connection is never used in a real mach call.
    (0x976b3c, MOV_W0_0 + RET,
     [bytes.fromhex("ff0301d1")], b"", "IOPMAssertionRelease"),
]

def main():
    if not os.path.exists(TARGET):
        sys.exit(f"cache file not found: {TARGET} (is the rootfs mounted?)")
    st = os.stat(TARGET)
    print(f"target: {TARGET} ({st.st_size} bytes)")
    with open(TARGET, "r+b") as f:
        changed = False
        for off, stub, priors, tail, why in PATCHES:
            f.seek(off)
            cur = f.read(len(stub))
            if cur == stub:
                print(f"  0x{off:x}: already patched ({why})")
                continue
            if not any(cur.startswith(p) for p in priors) or                cur[len(stub) - len(tail):] != tail:
                sys.exit(f"  0x{off:x}: UNEXPECTED bytes {cur.hex()} ({why}) - aborting")
            f.seek(off)
            f.write(stub)
            changed = True
            print(f"  0x{off:x}: patched {why} ({len(stub)} bytes)")
        if changed:
            f.flush()
            os.fsync(f.fileno())
            print("patched + synced")
        else:
            print("nothing to do")

if __name__ == "__main__":
    main()
