# athens device procedures (RMX2117 / Narzo 30 Pro 5G)

Everything here runs against the real phone over USB. Do the whole checklist
in order on the first session; later sessions only need the relevant parts.

Tools on the PC: `mtkclient` (bkerler; works on Windows), platform-tools
(`adb`, `fastboot`), `avbtool`, and `python3`.

## Phase 0 — discovery + backup (before any flash)

Enter BROM: power off → hold **Vol+ and Vol-** → plug USB. `mtkclient` should
print the MT6853 handshake (HW code 0996). If the handshake fails, retry while
holding Power ~10 s.

```sh
# 0.1 Partition table: UFS LUNs, "userdata" LUN/offset/size
python mtk.py printgpt

# 0.2 Backup — everything with per-device data or needed to restore stock
python mtk.py r boot,recovery,vbmeta,vbmeta_system,vbmeta_vendor,lk,nvram,persist,proinfo,seccfg,frp,para,expdb backup/
python mtk.py r preloader backup/preloader.bin    # sanity copy; never write it casually

# 0.3 Live device tree + boot image dtb (authoritative hardware description)
#     either boot stock Android with adb root:
adb shell su -c 'cat /sys/firmware/fdt' > dtb/athens-live.dtb
#     or unpack it from the stock boot.img you just backed up:
python3 tools/unpack_bootv2.py backup/boot.img dtb/boot_unpacked
```

From the live DTB, record into `ATHENS.md`:
- `memory` + every `reserved-memory` region → the XNU-usable RAM window
- `/chosen` / lk atag `videolfb` → fb phys address, pitch, pixel format
- which touch node is populated: `gt9886` on i2c0 **or** `gt9896s` on spi4
- `kp@10010000` key map (kpd-hw-init-map) for the volume-down bit
- `main_pmic` interrupt number (expect EINT 118)
- the ufs node + LUN carrying `userdata` (expect LUN 2; verify)

## Unlock + verified boot (one time)

```sh
python mtk.py da seccfg unlock        # seccfg unlock via DA (works on MT6853)
```

Then boot once to Android, enable OEM unlocking + USB debugging in developer
options, and patch vbmeta:

```sh
avbtool make_vbmeta_image --output vbmeta-disabled.img --flags 3
python mtk.py w vbmeta vbmeta-disabled.img
```

For normal fastboot access afterwards, use lkpatcher on `backup/lk` (web
lkpatcher patches lk to keep fastboot usable), then `mtk w lk patched-lk`.
`fastboot boot` is expected to be ignored by lk (as on viva): every test boot
flashes the `boot` partition.

## Recovery for logs

Flash the unofficial athens TWRP 3.7.0 to `recovery` once:

```sh
python mtk.py w recovery twrp-athens.img    # or: fastboot flash recovery ...
```

It gives adb-root access to the whole UFS; kernel log pulls read the log ring
at the tail of `userdata` (`tools/athens-log-pull.sh`) — or use the USB link
live console once ported.

## Flashing the port

```sh
# boot image (shim + XNU payload) — only the "boot" partition, nothing else
python mtk.py w boot shim/out/athens-boot.img
# or: fastboot flash boot athens-boot.img

# iOS root — the whole image goes into "userdata" (Android user data is lost;
# stock system/vendor/product in "super" are NOT touched)
python mtk.py w userdata ios16-root.img
# faster path if lk fastboot accepts it:
# fastboot -S 512M flash userdata ios16-root.simg
```

Force back to lk/BROM any time: hold Power ~10 s, or Power+Vol- for fastboot.

## Restore stock Android

```sh
python mtk.py w boot backup/boot.img
python mtk.py w vbmeta backup/vbmeta.img
# then format userdata from recovery (it was an HFS+ volume)
```

## Safety rules (carried over from viva — the LUN that holds `userdata` also
holds `nvram`/`proinfo`/`seccfg`)

- Never write outside `userdata` when flashing the iOS root.
- Never write `preloader` unless restoring a known-good backup deliberately.
- Keep `backup/` off git (already gitignored).
