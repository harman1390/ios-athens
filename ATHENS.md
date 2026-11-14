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
| XNU RAM | **0xc0000000–0xffe60000** — must NOT include mblock-17-DPM-reserved 0xffe60000–0xffffffff (only fixed carve-out inside the old viva-style window; stray-writer source). High bank 0x100000000–0x1bfff000 is free for a future second range | verified live FDT 2026-11-08 |
| GICv3 | GICD 0x0c000000 (0x40000), GICR 0x0c040000 (0x200000), INTPOL 0x0c53d668 | mt6853.dts |
| Timer | 13 MHz, virtual timer PPI 11 = INTID 27 | mt6853.dts |
| CPUs | 6× A55 MPIDR 0x000–0x500, 2× A76 0x600/0x700, PSCI CPU_ON | mt6853.dts |
| UFS | ufshci@0x11270000 (sz 0x2300, SPI 105), mphy@0x11fa0000; LK leaves it running | mt6853.dts |
| UFS LUN | `userdata` **LUN 2** (sdc = SCSI 0:0:0:2); `ufslun=2` or omit | verified 2026-11-07 |
| eint/pinctrl | apirq@1000b000; pio interrupt GIC SPI 212 | mt6853.dts |
| Keypad | kp@10010000, SPI 74 edge; volume-down bit from kpd-hw-init-map | mt6853.dts |
| PMIC | MT6359 via pwrap@10026000; interrupt = pio EINT 118 level | mt6853.dts |
| Keys | PWRKEY/HOMEKEY in MT6359 (+ _r variants); volume down = keypad | mt6359p.dtsi; regs TBD |
| Touch | **Novatek NT36672C on spi4** — driver binds + embedded 139 KB fw downloads (15 parts, nt36672a map), but post-download `reset state timeout (last 0x00)` → fw download reports failed; not yet sensing touches. irq=EINT14, reset=GPIO33 | verified kernel log 2026-11-14 |
| i2c0 | 0x11e00000 (+ apdma 0x10217080), SPI 112 level, 400 kHz, div 5, scl 97 / sda 98 | mt6853.dts |
| Battery | MT6359 internal gauge (FGADC/auxadc via pwrap), 5000 mAh, 30 W Dart (MT6360 charger companion) | mt6853.dts; regs TBD |
| GPU | Mali-G57 MC3 @0x13000000, SPI 364–368 (GPU/MMU/JOB/EVENT/PWR), MT6359 vproc1+vsram_md rails, 5 MTCMOS domains mfg0/1/2/3/5, MFGPLL 0x268/0x26c/0x274. **Kernel driver port in progress** (patches 0182/0183, `mediatek,mali` match) — powers on but nub/match not yet confirmed | mt6853.dts + live DT; port spec `docs/ATHENS-GPU.md` |
| USB | ssusb xhci0@0x11200000, usb0phy@0x11e40000 — NOT the musb viva's link used | mt6853.dts; link port TBD |
| Wi-Fi | On-die CONNSYS_6853 (connac2x2): `wifi@0x18000000` `mediatek,wifi` (SPI 377) + `consys@0x18002000` `mediatek,mt6853-consys` (SPI 378/79/379); MT6359 VCN33_1/2 rails, 4+6 MB reserve pools; BT `btif@0x1100c000` | stock mt6853.dtb + k6853v1_64_defconfig; later |
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
6. ⬜ Touch - NT36672C binds + fw downloads, but `reset state timeout (0x00)` blocks contact reports (SPI status-read bug)
7. ⬜ `cpus=8`: all cores incl. A76s online
8. ⬜ GUI usable: unlock, home screen, Settings/CC/notification center
9. ⬜ Identity: serial/model/region/MLB/UDID in Settings → About (mkadt ATHENS_IDENTITY)
10. ⬜ Storage fills userdata (~50+ GiB visible in Settings)

## Live-dt decisive evidence (adb harvest 2026-11-12)

- `reserved-memory/reserve-memory-dram_r1_dummy_read` alloc-ranges =
  `0xc0000000 + 0x3fe60000` → the dummy-read engine can allocate/write
  ANYWHERE in `[0xc0000000, 0xffe60000)` = the entire former XNU pool.
  run6's stray hit at `0xe0000000` sits inside it. r0's range is
  `[0x56000000, 0x5ff00000)`. The highmem window `[0x100000000,
  0x1bffff000)` is outside BOTH engines' reach — the move is
  evidence-backed, not a guess. (Writer identity still inferred: range
  proves the engine *can* write there, not that it *does*.)
- `reserve-memory-dram_rX_dummy_read` sizes are 0x1000 with alignment
  0x1000 — the engine DMAs 4 KiB dummy reads for DRAM calibration.
- `/chosen/linux,initrd-start` = 0x47c80000 → LK ramdisk base is the
  same 0x47c80000 as viva (mkboot payload guard verified).
- DRAM is ONE bank reg=<0x40000000 0x180000000> (6 GiB, ends
  0x1bfffffff); lowmem and highmem windows are slices of it.
- Touch (spi4@0x11018000 child `touchscreen@0`): compat `oppo,tp_noflash`,
  chip-name `OPPO_TP_NOFLASH` → SPI driver `novatek,nf_nt36672c`;
  irq-gpio 14 (EINT14), reset-gpio 33, spi-max 9.6 MHz, 1080x2400,
  16TXx36RX, 10-pt, incell. Fingerprint goodix_fp on spi5@0x11019000.
- **Live FDT pulled from PitchBlack recovery 2026-11-12 (verified):**
  - spi4@11018000: compatible `mediatek,mt6765-spi`, reg size 0x100,
    GIC SPI 163 (+32 = INTID 195, /proc/interrupts shows GICv3 195
    `11018000.spi4` level), clocks parent/sel/spi-clk,
    `mediatek,pad-select`=0.
  - touchscreen@0: `oppo,tp_noflash`/`OPPO_TP_NOFLASH`, irq-gpio
    <2,14,0x2002> = EINT14 edge, reset-gpio <2,33,0>, spi-max-frequency
    0x927c00 = 9.6 MHz, tx-rx 16x36, max-num 10, coords 1080x2400,
    pinctrl default/suspend states.
  - SPI4 pins (pinctrl/spimode_default/pins_cmd_dat): pinmux
    <0xc02 0xd02 0x6102 0x6202> = GPIO12 MI, GPIO13 MO, GPIO97 CLK,
    GPIO98 CSB, drive-strength 4.
  - `/proc/interrupts` live: `mt-eint 14 Edge touchpanel` (firing),
    `GICv3 195 11018000.spi4`, `mt-eint 80 Edge mtk-kpd-vol-down`,
    `GICv3 106 Edge mtk-kpd` (= SPI 74 + 32, confirms SPI+32 convention),
    `mt-eint 118 Level mt6358-irq` with children `mt6358-irq 48 pwrkey`,
    `49 homekey`, `50 pwrkey_r`, `51 homekey_r` (PMIC key IRQs live).
  - input devices: event1 `mtk-kpd` (10010000.kp), event2 `touchpanel`,
    event3 `touchpanel_kpd`, event4 `qwerty`.
  - **Buttons architecture (verified, changes earlier guess):**
    volume-down = EINT 80 GPIO key (NOT the KP matrix); power = MT6359
    PWRKEY; volume-up = MT6359 HOMEKEY (standard MTK mapping); the KP
    matrix hw-init-map is ALL ZEROS (114 entries) -> matrix scan unused.
    kp node compatible is `mediatek,kp` (not mt6781-keypad), key-debounce
    0x400, pinctrl states named `volume_up_as_int`/`volume_down_as_int`.
  - PMIC: `pwrap@10026000` has child `mt6359-pmic`; also
    `pwraphal@10026000`, `pwrap_mpu@10026000` siblings; i2c5 has
    `subpmic@34` + `subpmic_ldo@64` + `subpmic_pmic@1a` (MT6360 companion).
- dsi@0x14013000 has 4 panel children; this unit boots
  `jdi,nt36672c,dphy,vdo,120` (cmdline `lcm=`). toprgu@0x10007000
  matches the shim's TOPRGU address (verified).
11. ⬜ **Metal on Mali-G57 MC3 via viva-gpu — ACTIVE (not stretch).** Kernel driver ported (0182/0183); userspace `VivaMTLDriver.bundle` staged at `ios/viva-gpu-artifacts/` (upstream CI artifact, arm64 iOS16). Blocker: GPU nub/match not yet confirmed in SWEETLOG. Wi-Fi via connac work remains stretch.

## Distance to daily driver (honest assessment, 2026-11-14)

"Daily driver" = boots to a usable SpringBoard you can unlock, touch,
browse, and leave running. Scored against the verified SWEETLOG state.
**Cellular is realistically out of reach** — iOS has no MediaTek baseband
stack; even the most advanced iOS-on-Android ports do not do cellular.
The realistic ceiling is a **Wi-Fi-only iOS device** (iPad-class).

| Subsystem | State | Evidence | Gap to daily-driver |
| --- | --- | --- | --- |
| Kernel→userspace boot | ✅ deep bring-up | SpringBoard/backboardd/wifid exec; userspace crash-loops are normal bring-up noise | done |
| Display scan-out | ✅ pipeline proven | Apple logo renders; `sweetfb_keep` holds last frame | done (CPU path) |
| Real GUI compositing | ❌ **THE blocker** | backboardd `IOAcceleratorES` match → 0 found; frozen logo | GPU kernel match+power, then Metal userspace |
| Touch | ⚠️ partial | binds + 139 KB fw downloads, but `reset state timeout (0x00)` → no contact reports | fix SPI status-read/reset bug |
| Buttons | ⚠️ partial | `SweetHIDButtons` opened by backboardd (GPIO keys) | verify PMIC PWRKEY/HOMEKEY + volume |
| Storage (UFS r/w) | ✅ works | iOS root runs off `userdata` LUN2 | done |
| Battery | ❌ fake | `SWEET BATTERY: static fallback, 100%` | MT6359 gauge/FGADC driver |
| Wi-Fi | ❌ none | `wifid`/`wifianalyticsd` exec but no connac driver | connac2x2 driver port (big) |
| Audio | ❌ none | `audioclocksyncd` exec, no codec driver | codec + audio stack port |
| USB link | ❓ | ssusb xhci0 present, link unconfirmed | confirm adb/peripheral path |
| Cellular/baseband | ❌ | no MTK modem stack in iOS | **research-grade, likely never** |
| Camera/sensors/NFC/GPS | ❌ | not ported | each a driver project |
| Sleep/wake, DVFS, thermal | ❌ | not validated | power-management bring-up |

**Critical path (ordered):**
1. **GPU** — get `mali` nub → `VivaGPUAccelerator` match (current
   diagnostic build dumps every createNub node name), power-on, then
   inject `VivaMTLDriver.bundle`. Gates ALL real UI. *Without this there
   is no visible GUI at all.* (SW-renderer shortcut exists but user
   declined it.)
2. **Touch** — fix the post-download `0x00` status read so contacts land.
3. **Wi-Fi + audio + real battery** — the "usable device" tier.
4. **Power/sensors/stability** — daily-driver polish.

**Honest distance:** visible+touchable GUI is *close* if the GPU match is
a small fix (days) but *weeks* if it's a deeper DT/driver issue; the full
userspace Metal stack is the long pole. A stable Wi-Fi-only daily driver
is realistically **months** of iterative on-device work; cellular is not
on the table. Current state ≈ **early bring-up / pre-GUI** — roughly the
"boots but can't yet show a desktop" stage.

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

Not done: kernel patches for athens display/input/power (0160+ extend
matching to `mt6853-*` and parametrize MT6359-vs-MT6366 — mostly landed);
athens fb console patch (equivalent of viva 0090 at the measured address —
landed via SweetFramebuffer); USB link (ssusb on MT6853 — viva's 0093 was
musb-style); iOS rootfs build + flash; **GPU bring-up** — driver ported
(0182/0183) but `mali` nub→`VivaGPUAccelerator` match still unconfirmed in
SWEETLOG (see NOTES.md 2026-11-14 handoff + `docs/ATHENS-GPU.md`).

Waiting on device (Phase 0, see docs/athens-flash.md): live FDT, GPT/LUN for
userdata, atag videolfb, which touch variant is populated, lk kernel-format
and `fastboot boot` behavior.

## Touch bring-up notes (2026-11-12, from linux drivers/spi/spi-mt65xx.c)

MTK SPI host `mediatek,mt6765-spi` @0x11018000 uses mt6765_compat:
need_pad_sel, must_tx, enhance_timing (timing in CFG2 not CFG0),
dma_ext, NO ipm_design. Reg window is only 0x100 bytes (dts reg size).

Registers (non-IPM path):
  CFG0 0x00 SCK_HIGH[7:0] SCK_LOW[15:8] CS_HOLD[23:16] CS_SETUP[31:24]
  CFG1 0x04 CS_IDLE[7:0] PACKET_LOOP[15:8] PACKET_LENGTH[25:16]
  TX_SRC 0x08 RX_DST 0x0c TX_DATA 0x10 RX_DATA 0x14 CMD 0x18 STATUS0 0x1c
  PAD_SEL 0x24 CFG2 0x28 (enhance_timing: SCK_HIGH[15:0] SCK_LOW[31:16])
  TX_SRC_64 0x2c RX_DST_64 0x30

CMD bits: ACT=1 RESUME=2 RST=4 PAUSE_EN=0x10 DEASSERT=0x20 SAMPLE_SEL=0x40
  CS_POL=0x80 CPHA=0x100 CPOL=0x200 RX_DMA=0x400 TX_DMA=0x800
  TXMSBF=0x1000 RXMSBF=0x2000 RX_ENDIAN=0x4000 TX_ENDIAN=0x8000
  FINISH_IE=0x10000 PAUSE_IE=0x20000

Transfer algo (FIFO/PIO path, xfer <= 32B chunks or poll STATUS0):
  div = spi_clk_hz / speed_hz (min 1); sck_time=(div+1)/2
  CFG2: SCK_HIGH=SCK_LOW=(sck_time-1)&0xffff   [enhance_timing]
  CFG1: PACKET_LENGTH=(min(len,1024)-1)<<16, PACKET_LOOP=(len/1024)-1<<8
  TX: iowrite32_rep TX_DATA; RX: read RX_DATA; CMD |= ACT to start
  CS/pad: need_pad_sel -> PAD_SEL reg + mediatek,pad-select=0 in dts
  must_tx: RX-only transfers still need dummy TX bytes clocked

STILL NEEDED before driver works:
  - spi_clk_hz: parent clock for spi4 (clk-mt6853: topckgen/infracfg SPI
    clocks; likely 26 MHz or 48 MHz source - MEASURE, no clock framework)
  - clock gating: CG bits enabling SPI4 in infracfg/topckgen
    (clk-mt6853.c has the gate map - research needed)
  - pinmux: GPIO12=MI 13=MO 97=CLK 98=CSB, drive 4; dts pinmux values
    <0xc02 0xd02 0x6102 0x6202>; decode via mt6853_pin_mode_range
    (pin n -> reg 0x300+8*(n/8)... pin80-87 at 0x3a0 etc, 4-bit fields)
  - NT36672C "noflash" protocol: NOT in mainline (OPPO/Novatek vendor
    driver). 139392-byte fw upload + report format TBD from OPPO
    kernel source (drivers/input/touchscreen/... or vendor blob).
  - EINT14 irq (edge), GPIO33 reset via VivaGPIO output-pins (added).

