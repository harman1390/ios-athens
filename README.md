# ios-athens

**Apple's iOS 16 on a realme Narzo 30 Pro 5G / realme 7 5G (RMX2117 "athens", MediaTek Dimensity 800U / MT6853).**

This project ports Apple's open-source XNU kernel (xnu-8796, the iOS 16 generation) to athens. On top of it runs the **unmodified iOS 16.7.16 (20H392) userland of the iPhone X**: launchd, the system daemons, backboardd, SpringBoard and the stock apps.

It is the third phone in a lineage of ports:

- **[ios-sweet](https://github.com/dipa-studio/ios-sweet)** — Redmi Note 10 Pro (`sweet`, Qualcomm SM7150). Reached the **iOS home screen**: touch, buttons, Settings, Control Center and the notification center all work.
- **[ios-viva](https://github.com/Nik300/ios-viva)** — Redmi Note 11 Pro 4G (`viva`, MediaTek Helio G96 / MT6781). Lock screen, interrupt-driven keys, a live USB console link, Mali-G57 GPU, Wi-Fi (en0, WPA2), CPU DVFS and thermal throttling. See [`VIVA.md`](VIVA.md).
- **ios-athens** (this repo, branch `athens`) — same kernel and patch series, ported sideways to a second MediaTek SoC. Athens support is added next to sweet/viva: `--athens` in `tools/mkadt.py`, `shim/athens.c`, `shim/build-athens.sh`, `tools/athens-mkboot.sh`, `xnu/patches/0160+-athens-*.patch`.

> **Bring-up is in early stages.** As of 2026-11-06 the device has been measured and backed up, the shim/ADT/build scaffold is in place, and the first athens kernel patch (0160, early framebuffer console) exists — and XNU now **boots into early userspace** (UFS root on LUN 2, all 8 CPUs, framebuffer + touch + HFS, launchd spawning daemons) before hitting memory-corruption panics. The kernel drivers still bind to MT6781 compatible strings; the athens patch series extends matching to `mt6853-*` and parametrizes the MT6359-vs-MT6366 differences. Milestones are tracked in [`ATHENS.md`](ATHENS.md).

> Experimental bring-up, not a usable phone OS. Apple's security model is mostly switched off, and the install puts the iOS root into the `userdata` partition — **Android user data is erased** (the `super` partition with system/vendor is left intact).

## Device facts (measured on the phone, 2026-11-05/06)

| What | Value |
| --- | --- |
| Boot | realme LK; `fastboot boot` expected ignored → flash `boot` (non-A/B) |
| Security | SBC + DAA on; **Kamakiri BROM bypass works** (mtkclient full access) |
| Kernel format | **gzip Image** (stock boot.img kernel starts `1f 8b`); boot.img v2, page 2048, DTB inside |
| Entry | EL1, MMU off, `x0` = DTB (same as viva; verify) |
| UFS | ufshci `0x11270000`, left running by LK. **LU0** carries GPT + `userdata` (~49.8 GiB at `0x272800000`) — `ufslun=0`; LU1/LU2 are 4 MiB preloader LUNs |
| RAM | 6 GiB, `0x40000000`–`0x1c0000000`; XNU window provisional `0xc0000000`–`0x1be000000` |
| Framebuffer | `0x77e20000` from `/chosen/atag,videolfb` (vramSize `0x01be0000`); pitch 1088 px provisional |
| Panel | NT36672C JDI 1080×2400 120 Hz DSI video mode **or** NT35595 Truly cmd-mode — two variants, runtime decides |
| CPUs | 6× Cortex-A55 (MPIDR 0x000–0x500) + 2× Cortex-A76 (0x600/0x700), PSCI CPU_ON |
| GICv3 | GICD `0x0c000000`, GICR `0x0c040000`; virtual timer PPI 11 = INTID 27, 13 MHz |
| Watchdog | toprgu `0x10007000`, stop with `WDT_MODE = (mode & ~1 & 0xffffff) \| 0x22000000` |
| Keys | PWRKEY/HOMEKEY in MT6359 PMIC via pwrap `0x10026000` (EINT 118); volume down = keypad `kp@10010000` |
| Touch | **Goodix GT9896s on `spi4@11018000`** (measured live FDT) — not the i2c variant on this unit |
| GPU | Mali-G57 MC3 `0x13000000` (stretch goal, same family as viva's driver) |
| Wi-Fi | MT663x connac combo (same family as viva's driver) |

Full table with sources and open measurements: [`ATHENS.md`](ATHENS.md).

## How it boots

```
realme LK (unlocked, vbmeta flags 3)
  -> "boot" partition flashed with athens-boot.img   (fastboot boot is ignored; non-A/B)
     -> gzip Image = bare-metal shim: stop toprgu, take over LK's framebuffer
        (from /chosen/atag,videolfb), load the SWEETXNU payload from the ramdisk
        -> XNU Mach-O + generated Apple Device Tree (ADT) + boot-args
           -> XNU -> MediaTek UFS driver -> HFS+ root in the "userdata" partition (LU0)
              -> dyld + shared cache -> launchd -> daemons -> backboardd + SpringBoard
```

Flashing goes through the **BROM**: power off, hold **Vol+ and Vol-**, plug USB, then `mtkclient` (the Kamakiri exploit bypasses DAA). Only `boot` and `userdata` are ever written; `preloader`, `lk`, `seccfg`, `nvram`, `persist` are restored from backup only.

The kernel draws its early console into LK's framebuffer (patch 0160, at `0x77e20000`); panics draw too. A recovery log-pull through TWRP is planned (`docs/athens-flash.md`); viva's USB live-link console is the longer-term answer.

## Build and boot

You need the phone with an unlocked bootloader (`docs/athens-flash.md` has the unlock + vbmeta procedure), a PC with `mtkclient`, platform-tools and `python3`, and a GitHub fork for the kernel build.

```sh
# kernel (GitHub Actions, macos-14 — also builds on every push to this branch)
gh workflow run xnu.yml -R YOU/ios-athens --ref athens
gh run download RUN_ID -R YOU/ios-athens -n xnu-kernel -D xnu/out

# boot image — shim + XNU payload repacked into the backed-up stock boot.img
tools/athens-mkboot.sh xnu/out/kernel.development.sweet backup/boot.img nostorage

# flash through the BROM (power off, Vol±, plug)
python mtk.py w boot shim/out/athens-boot.img
```

`tools/athens-mkboot.sh` stages the bring-up one step at a time:

| Stage | ADT | Kernel writes | Expected result |
| --- | --- | --- | --- |
| `nostorage` | no UFS node | none | panic `ufsroot0 unavailable` = milestone "XNU boots" |
| `ufs-ro` (default) | UFS node | refused (no `ufsrw`) | finds `userdata` on LU0, tries to mount |
| `ufs-rw` | UFS node | only inside `userdata` | iOS boots from the flashed HFS+ root |

Boot-args: `ATHENS_EXTRA` replaces single args (default `cpus=8`; `ATHENS_EXTRA="cpus=1"` is the safe fallback), `ATHENS_CMDLINE` replaces the whole command line. Every staged command line already disables the sweet Qualcomm drivers (`sweetkeys=0 sweettouch=0 sweetusb=0 sweetlog=0`): their fixed MMIO addresses are different blocks on MT6853.

### iOS root image

Same recipe as the other phones — iPhone10,3 iOS 16.7.16 (20H392) IPSW, one HFS+ volume with the OS + cryptexes, then the bring-up tweaks. A GitHub workflow (`rootfs.yml`) builds it on `ubuntu-latest` from an IPSW URL, or use `tools/mkiosroot.sh` + `tools/sweet-root-tweaks.py` locally on Linux, `tools/viva-mkiosroot-macos.sh` on macOS. Then:

```sh
python mtk.py w userdata ios16-root.img      # Android user data is lost; super is NOT touched
# or, if lk fastboot accepts it: fastboot -S 512M flash userdata ios16-root.simg
```

The ADT's `/product` comes from the real D22AP device tree (MobileGestalt needs it) plus a synthetic serial/MLB/UDID (`ATHENS_IDENTITY` in `tools/mkadt.py` — stand-ins, never commit real ones). Extract the tree once without downloading the whole IPSW:

```sh
python3 tools/remotezip.py IPSW_URL DeviceTree.d22ap.im4p research/ipsw-x/dt
ipsw img4 im4p extract research/ipsw-x/dt/Firmware/all_flash/DeviceTree.d22ap.im4p -o research/ipsw-x/d22ap.adt
```

## Safety

The UFS LUN that holds `userdata` also holds `nvram`, `proinfo` and `seccfg`. The `--athens` ADT therefore has **no UFS node** without `--athens-ufs`, and every stage turns off the sweet/viva drivers whose fixed MMIO lands on a different MT6853 block. Keep partition backups out of git — `.gitignore` covers `backup/`, `dtb/`, `recovery/`. Restore stock Android by flashing back `backup/boot.img` + `backup/vbmeta.img` and formatting `userdata` from recovery.

## Repository layout

| Path | What |
| --- | --- |
| `ATHENS.md` | Device facts, safety rules, milestones, per-session handoffs for athens |
| `VIVA.md` | Same for the parent MT6781 port |
| `NOTES.md` | Engineering log inherited from the sweet port (boots, crashes, decisions) |
| `docs/athens-flash.md` | Device runbook: Phase-0 discovery, unlock/vbmeta, BROM flashing, restore |
| `docs/PIANO-GPU.md`, `docs/QEMU_TESTING.md` | GPU plan (Mali/Metal) and QEMU test guide |
| `shim/` | Bare-metal boot shim (C + asm): `athens.c` / `viva.c` / `shim.c` per device, packed as a gzip Image |
| `tools/mkadt.py` | Generates the Apple Device Tree (`--athens`, `--viva`, `--qemu`) incl. identity/`/product` |
| `tools/mkpayload.py` | Packs kernel + ADT + boot-args into the shim payload |
| `tools/athens-mkboot.sh` | One-command staged boot image (`nostorage`/`ufs-ro`/`ufs-rw`) |
| `tools/viva-bootimg.py` | Repacks the shim into a stock boot.img (keeps cmdline, DTB, header) |
| `tools/mkiosroot.sh`, `viva-mkiosroot-macos.sh`, `sweet-root-tweaks.py` | Build and tweak the iOS HFS+ root |
| `tools/viva-link.py`, `vivad/` | USB live console link + on-phone helper (viva; athens port pending) |
| `tools/remotezip.py`, `unpack_bootv2.py`, `viva-extract-dt.py` | IPSW/boot.img helpers |
| `tools/xnu-cc.py` | Local single-file compile check replayed from a CI log |
| `xnu/patches/` | The XNU patch series, applied in order by CI |
| `.github/workflows/xnu.yml`, `rootfs.yml` | Kernel and rootfs CI builds |
| `site/` | Project website |

Not in git: partition backups, live device trees, recovery images, Apple firmware and root images, downloaded or generated build trees. They contain device serials/calibration or Apple's copyrighted files.

## Kernel patches

| Range | What |
| --- | --- |
| `0001`–`0080` | The sweet core: toolchain fixes, SWEET machine config, non-PAC arm64, early fb console, device-tree platform expert, libpthread/HFS+/BearSSL staging, UFS root read/write, IOSurface + IOMobileFramebuffer (AppleCLCD), HID event services, iPhone X identity, SPMI keys, GENI touch, SMP, USB device + CDC-ECM link, diagnostics (persistent log, IOKit trace, crash sampler) |
| `0090`–`0154` | The viva series (MT6781): MTK framebuffer/UFS LUN discovery/USB link, GIC + EINT + pwrap + MT6366 keys, GT9896 touch on MTK i2c, Mali-G57 GPU (Metal) work, display scanout/vsync, CPU DVFS + LVTS thermal, Wi-Fi connac (scan, WPA2, en0), PMIC RTC |
| `0160`– | The athens series (MT6853): `0160` early fb console at `0x77e20000`; next up — extend driver matching to `mt6853-*`, MT6359-vs-MT6366 registers, spi4 touch, ssusb link |

## Credits

Built on Apple's open-source releases (xnu, IOHIDFamily, libpthread, hfs), [BearSSL](https://bearssl.org), [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build), [ipsw](https://github.com/blacktop/ipsw), [mtkclient](https://github.com/bkerler/mtkclient), Qualcomm/Xiaomi/realme's published Linux kernel sources for the hardware details, TWRP/[OrangeFox](https://orangefox.download), and the upstream [`dipa-studio/ios-sweet`](https://github.com/dipa-studio/ios-sweet) → [`Nik300/ios-viva`](https://github.com/Nik300/ios-viva) ports. iOS itself is Apple's and is not distributed here.
