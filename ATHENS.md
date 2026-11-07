# ios-sweet on athens (realme Narzo 30 Pro 5G / realme 7 5G, RMX2117, MediaTek Dimensity 800U / MT6853)

Branch `athens` of this fork, based on `viva` (the MT6781 port). Everything
sweet- and viva-specific stays as is; athens support is added next to it
(`--athens` in `tools/mkadt.py`, `shim/athens.c`, `shim/build-athens.sh`,
`tools/athens-*`, `xnu/patches/0160+-athens-*.patch`).

Full plan: see the megaplan in the project notes (phases, acceptance criteria,
identity/storage decisions). Device runbook: `docs/athens-flash.md`.

## Device facts

| What | Value | Source / status |
| --- | --- | --- |
| Boot | LK (realme); non-A/B single slot - `boot` = sdc52, `boot_para` = sdc33; flash via recovery adb `dd` - fastboot sparse fails on the last `userdata` chunk | verified 2026-11-07 |
| Kernel format | **gzip Image** (stock boot.img kernel starts `1f 8b`) | measured 2026-11-06 |
| Security | SBC + DAA on; **Kamakiri BROM bypass works** (mtkclient full access) | measured 2026-11-06 |
| UFS LUNs | **LUN 2 = sdc (SCSI 0:0:0:2), carries GPT + userdata**; LUN 0/1 = no GPT | verified recovery sysfs + kernel log 2026-11-07 |
| `userdata` | LUN 2 part 58, first block 0x272800 (LBA 2566144), 13049848 blk ~ 49.8 GiB -> `ufslun=2` or omit (scan all) | verified GPT dump + kernel |
| `super` | offset 0x71800000, length 0x1e5000000 (~7.5 GiB) — left intact | measured `printgpt` |
| `boot` | offset 0x6cf00000, 32 MiB; partition data = first bytes of each 128 MiB backup dump | measured |
| boot.img | header v2, page 2048, DTB inside, cmdline `bootopt=64S3,32N2,64N2` (keep it) | BoardConfig.mk |
| boot addrs | dtb_addr 0x4bc80000; kernel@2048, ramdisk@5791744, dtbo/dtb@6694912 | boot.img header |
| Entry | EL1, MMU off, `x0` = DTB | same as viva; verify |
| Watchdog | toprgu 0x10007000, `WDT_MODE = (mode & ~1 & 0xffffff) \| 0x22000000` | mt6853.dts + viva |
| Panel | NT36672C JDI 1080×2400 120 Hz **DSI video mode** (videolfb blob name) OR NT35595 Truly cmd-mode (lcmname prop) — two panel variants, runtime tells which | measured live FDT |
| Framebuffer | presented surface at **0x78816000** (AppleCLCD 1080x2400 stride 4320); OVL1 L0 also at 0x77e20000 | verified kernel log |
| RAM | **6 GiB, 0x40000000–0x1c0000000** (memory/reg) + reserved@1401x000 carve-outs | measured live FDT |
| XNU RAM | provisional 0xc0000000–0x1be000000 (viva-style high window) | verify against live reserved-memory |
| GICv3 | GICD 0x0c000000 (0x40000), GICR 0x0c040000 (0x200000), INTPOL 0x0c53d668 | mt6853.dts |
| Timer | 13 MHz, virtual timer PPI 11 = INTID 27 | mt6853.dts |
| CPUs | 6× A55 MPIDR 0x000–0x500, 2× A76 0x600/0x700, PSCI CPU_ON | mt6853.dts |
| UFS | ufshci@0x11270000 (sz 0x2300, SPI 105), mphy@0x11fa0000; LK leaves it running | mt6853.dts |
| UFS LUN | `userdata` **LUN 2** (sdc = SCSI 0:0:0:2); `ufslun=2` or omit | verified 2026-11-07 |
| eint/pinctrl | apirq@1000b000; pio interrupt GIC SPI 212 | mt6853.dts |
| Keypad | kp@10010000, SPI 74 edge; volume-down bit from kpd-hw-init-map | mt6853.dts |
| PMIC | MT6359 via pwrap@10026000; interrupt = pio EINT 118 level | mt6853.dts |
| Keys | PWRKEY/HOMEKEY in MT6359 (+ _r variants); volume down = keypad | mt6359p.dtsi; regs TBD |
| Touch | **Novatek NT36672C on spi4** (kernel detects + downloads 139392-byte fw; 1080x2400, irq=gpio14) | verified kernel log |
| i2c0 | 0x11e00000 (+ apdma 0x10217080), SPI 112 level, 400 kHz, div 5, scl 97 / sda 98 | mt6853.dts |
| Battery | MT6359 internal gauge (FGADC/auxadc via pwrap), 5000 mAh, 30 W Dart (MT6360 charger companion) | mt6853.dts; regs TBD |
| GPU | Mali-G57 MC3 @0x13000000, SPI 364–368 (GPU/MMU/JOB/EVENT/PWR), SCP_SYS_MFG0-5 domains | mt6853.dts |
| USB | ssusb xhci0@0x11200000, usb0phy@0x11e40000 — NOT the musb viva's link used | mt6853.dts; link port TBD |
| Wi-Fi | MT663x connac combo (same family as viva's in-progress driver) | later |
| Recovery | unofficial TWRP 3.7.0 for athens (adb root, decryption) | XDA 4584321 |

## Safety

Same rule as viva: the UFS LUN holding `userdata` also holds `nvram`,
`proinfo`, `seccfg`. The `--athens` ADT has **no UFS node** without
`--athens-ufs`; the staged boot turns off every sweet/viva driver whose fixed
MMIO lands on a different MT6853 block. Only `boot` + `userdata` are ever
written; `preloader`, `lk`, `seccfg`, `nvram`, `persist` are restored from
backup only.

## Build and boot

```sh
# kernel (GitHub Actions, macos-14)
gh workflow run xnu.yml -R YOU/ios-athens --ref athens
gh run download RUN_ID -R YOU/ios-athens -n xnu-kernel -D xnu/out
# boot image (stock boot.img backed up from the phone)
tools/athens-mkboot.sh xnu/out/kernel.development.sweet backup/boot.img nostorage
python mtk.py w boot shim/out/athens-boot.img   # BROM: power off, Vol±, plug
```

Stages: `nostorage` (panic at `ufsroot0 unavailable`) → `ufs-ro` (find
`userdata`, no writes) → `ufs-rw` (iOS root from `userdata`).

`ATHENS_EXTRA="cpus=8"` is the default; `ATHENS_EXTRA=cpus=1` is the safe
fallback. `ATHENS_CMDLINE` replaces the whole command line.

## Milestones

1. ⬜ Own code runs (shim), framebuffer drawable, text console, live RAM map
2. ⬜ XNU boots to root mounting (`nostorage` panic = success)
3. ⬜ Storage: MediaTek UFS from LK's state, `userdata` LUN found (`ufs-ro`)
4. ⬜ iOS 16.7.16 lock screen (`ufs-rw`, ~5–20 min first boot)
5. ⬜ Keys (MT6359 PWRKEY/HOMEKEY + keypad) as HID consumer events
6. Touch - Novatek NT36672C on spi4 working (fw download, live events)
7. ⬜ `cpus=8`: all cores incl. A76s online
8. ⬜ GUI usable: unlock, home screen, Settings/CC/notification center
9. ⬜ Identity: serial/model/region/MLB/UDID in Settings → About (mkadt ATHENS_IDENTITY)
10. ⬜ Storage fills userdata (~50+ GiB visible in Settings)
11. ⬜ (stretch) Metal on Mali-G57 MC3 via viva-gpu; Wi-Fi via connac work

## Handoff (2026-11-06, Phase 0 partial — device session 1)

Done on the phone: BROM entry confirmed (power off, Vol±, plug); Kamakiri
bypass + xflash DA works; `printgpt` captured (see facts table);
21-partition backup in `backup/` (gitignored): recovery, misc, para, expdb,
frp, vbmeta{,_system,_vendor}, nvcfg, persist, seccfg, proinfo, nvram, lk,
lk2, boot, logo, dtbo, tee1, tee2, spmfw — each file is the 128 MiB DA read;
real data starts at offset 0 (sizes in the mtkclient log: boot 32 MiB, lk
5 MiB, vbmeta small). Stock `boot.img` unpacked to `dtb/boot_unpacked/`
(dtb, kernel, ramdisk): kernel is gzip, dtb_addr 0x4bc80000.

The boot dtb matches the published mt6853.dts: mt6359 PMIC + mt6360
companion, ufshci@11270000, mali@13000000, i2c0@11e00000, spi4@11018000,
generic `/touch` node only — **no populated gt98xx chip node and no
atag,videolfb in the static dtb** (lk injects those at runtime).

Still needed from device: **live FDT** (`adb shell su -c 'cat /sys/firmware/fdt'`
under stock Android or TWRP) for the RAM map/reserved regions, atag videolfb
address+pitch, and the populated touch node; lk behavior on `fastboot boot`.

## Handoff (2026-11-05, initial scaffold)

Done: fork seeded from `Nik300/ios-viva@viva` (patch series to 0154); `athens`
branch; `mkadt.py --athens` + `athens_devices()` (MT6853 keypad/EINT/pwrap/
MT6359/GPIO/i2c0/GT9886/G57-MC3/wlan nodes, identity props injected into
/product); `shim/athens.c` (toprgu stop, atag fb takeover, warn-not-halt on fb
mismatch); `shim/build-athens.sh`; `tools/athens-mkboot.sh` (stages);
`docs/athens-flash.md` (Phase-0 discovery, unlock, flash, restore runbook);
`ATHENS.md` facts table.

Not done: kernel patches for athens (the drivers match `mediatek,mt6781-*` /
viva-compatible strings today — patches 0160+ must extend matching to
`mt6853-*` and parametrize the MT6359-vs-MT6366 register differences);
athens fb console patch (equivalent of viva 0090 at the measured address);
USB link (ssusb on MT6853 — viva's 0093 was musb-style); iOS rootfs build +
flash; GPU driver.

Waiting on device (Phase 0, see docs/athens-flash.md): live FDT, GPT/LUN for
userdata, atag videolfb, which touch variant is populated, lk kernel-format
and `fastboot boot` behavior.
