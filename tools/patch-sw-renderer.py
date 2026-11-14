#!/usr/bin/env python3
"""Patch the iOS 16 dyld_shared_cache to disable the CoreAnimation
software-renderer crash-guard in CA::WindowServer::Server::sw_renderer().

sw_renderer() lazily builds a real CA::OGL::SWContext + OGL::Renderer, then
deliberately calls an abort_with_reason-style helper twice ("Software renderer!
Simulating crash!" and "Failed to initialize Metal or OpenGLES contexts!").
On a device with no GPU accelerator these are the ONLY thing stopping the CPU
renderer, so NOP-ing the two `bl` crash calls lets backboardd composite via
software -> visible GUI without a GPU.

Run inside WSL with the iOS rootfs mounted (mount -o loop -t hfsplus ...).
Patches are verified before and after. Idempotent.
"""
import sys, os

MNT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/iosroot"
DSC_DIR = os.path.join(MNT, "System/Library/Caches/com.apple.dyld")
TARGET = os.path.join(DSC_DIR, "dyld_shared_cache_arm64.03")

# (file offset, expected insn bytes, reason)
PATCHES = [
    (0x1768d34, bytes.fromhex("545f5b95"), "bl crash #1 (Simulating crash)"),
    (0x1768d8c, bytes.fromhex("3e5f5b95"), "bl crash #2 (Failed to init Metal/GLES)"),
]
NOP = bytes.fromhex("1fd003d5")  # ARM64 NOP = 0xd503201f

def main():
    if not os.path.exists(TARGET):
        sys.exit(f"cache file not found: {TARGET} (is the rootfs mounted?)")
    st = os.stat(TARGET)
    print(f"target: {TARGET} ({st.st_size} bytes)")
    with open(TARGET, "r+b") as f:
        changed = False
        for off, expect, why in PATCHES:
            f.seek(off)
            cur = f.read(4)
            if cur == NOP:
                print(f"  0x{off:x}: already NOP ({why})")
                continue
            if cur != expect:
                sys.exit(f"  0x{off:x}: UNEXPECTED bytes {cur.hex()} != {expect.hex()} ({why}) - aborting, cache differs")
            f.seek(off)
            f.write(NOP)
            changed = True
            print(f"  0x{off:x}: {expect.hex()} -> NOP ({why})")
        if changed:
            f.flush()
            os.fsync(f.fileno())
            print("patched + synced")
        else:
            print("nothing to do")

if __name__ == "__main__":
    main()
