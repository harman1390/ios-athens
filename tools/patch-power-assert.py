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

# ARM64 encodings (little-endian byte strings).
MOV_W0_FFFF = bytes.fromhex("e0ff9f52")   # mov w0, #0xffff  (fake io_connect_t)
MOV_W0_0    = bytes.fromhex("00008052")   # mov w0, #0       (kIOReturnSuccess)
MOV_X8_1    = bytes.fromhex("280080d2")   # mov x8, #1       (dummy IOPMAssertionID)
STR_X8_X3   = bytes.fromhex("680000f9")   # str x8, [x3]     (*AssertionID = 1)
RET         = bytes.fromhex("c0035fd6")   # ret

# (file offset, stub bytes, expected first-4 original bytes, description)
PATCHES = [
    # IOPMAssertionCreateWithDescription(...) -> io_connect_t
    # return a non-zero fake connection; callers only check != IO_OBJECT_NULL.
    (0x981a70, MOV_W0_FFFF + RET,
     bytes.fromhex("f44fbea9"), "IOPMAssertionCreateWithDescription"),
    # IOPMAssertionCreateWithProperties(type,name,details,IOPMAssertionID *id)
    # -> IOReturn. Return success and write a dummy non-zero assertion ID.
    (0x977154, MOV_W0_0 + MOV_X8_1 + STR_X8_X3 + RET,
     bytes.fromhex("ffc301d1"), "IOPMAssertionCreateWithProperties"),
    # IOPMAssertionRelease(...) -> IOReturn. No-op success so the fake
    # connection is never used in a real mach call.
    (0x976b3c, MOV_W0_0 + RET,
     bytes.fromhex("ff0301d1"), "IOPMAssertionRelease"),
]

def main():
    if not os.path.exists(TARGET):
        sys.exit(f"cache file not found: {TARGET} (is the rootfs mounted?)")
    st = os.stat(TARGET)
    print(f"target: {TARGET} ({st.st_size} bytes)")
    with open(TARGET, "r+b") as f:
        changed = False
        for off, stub, expect, why in PATCHES:
            f.seek(off)
            cur = f.read(len(stub))
            if cur == stub:
                print(f"  0x{off:x}: already patched ({why})")
                continue
            # accept either pristine prologue or (for re-runs) already-stubbed
            f.seek(off)
            head = f.read(4)
            if head != expect and cur != stub:
                sys.exit(f"  0x{off:x}: UNEXPECTED bytes {head.hex()} != {expect.hex()} ({why}) - aborting")
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
