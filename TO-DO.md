# TO-DO — athens (RMX2117 / MT6853) bring-up master list

Compiled 2026-11-15 from `docs/ATHENS-SUBSYSTEMS.md` (hardware facts +
per-subsystem plans), the port landscape survey, and the live NOTES.md
handoffs. Ordered by dependency: **GUI first** (it is the current
blocker), then infrastructure, then the usable-device tier, then
research-grade items.

Standing rules for every item (AGENTS.md): CI `verify_strings` → build →
review → temporary `fastboot boot` image only → recovery log pull →
update STATUS.md/NOTES.md. Preserve bootloader/recovery/modem/persist/
backups. No destructive ops without confirmation.

---

## P0 — GUI blocker (current critical path)

Latest ring analysis (handoff 2026-11-15al): panic fixed by 0203, kernel
survives, but **backboardd/SpringBoard never reach the display** — they
partial-init then mach-wait forever. Display driver exonerated (zero
`SWEET FB:` backboardd calls = never opened IOMFB user client).

- [ ] **Identify the blocked service.** backboardd[57]/SpringBoard[26] do
  partial init (HID gamepad plugins loaded, MobileGestalt display-size
  query answered) then hard-block in mach wait. Find which mach/XPC
  service they wait on — dyld symbolization of wait pc `0x1f606d030` /
  lr `0x1f607eb18`, or add check-in logging to suspect services.
- [ ] **Fix the common daemon crash.** accountsd/containermanagerd/tccd
  crash-loop at shared PC `0x1f6073198` (sig5/sig6) — likely a missing
  syscall/entitlement/service. SpringBoard depends on them; stabilizing
  them may unblock the wait directly. Check `sweetexit`/crash reports in
  the ring for the faulting library.
- [ ] **GPU path (still required for real rendering).** Once userspace
  unblocks: `mali` nub → `VivaGPUAccelerator` IOService match → power-on
  → inject `VivaMTLDriver.bundle` → Metal/IOSurface → compositor swaps
  (FBSTAT swaps>0 is the pass signal). Without it only CPU-rendered
  frames exist.
- [ ] Verify: sweetlog shows SpringBoard rendering + FBSTAT swaps>0 +
  touch works → **GUI milestone**.

## P1 — infrastructure (unblocks everything below)

- [ ] **pwrap / WACS2 finish** (patches 0185–0187 in flight). PMIC wrapper
  must reliably read/write MT6359. Gates: PMIC keys verification, GPU
  power rails, WiFi rails, MT6359 gauge path, charger.
- [ ] **USB device-mode link** — confirm enumeration (vivad). Needed for
  manual stepping of WiFi/touch/camera debug. ssusb xhci0 + usb0phy +
  tcpc_pd nodes verified present; link state unconfirmed.
- [ ] **Touch FW path** — NT36672C driver built (0180); FW downloads
  (~139 KB) but post-download status reads `0x00` → reset timeout, no
  contact reports. Run 0194 diag build, read stage markers, fix reset
  timing / FW binary source (use RMX2117 vendor FW, not generic) / SPI
  mode.
- [ ] **Buttons verify** — 0178 PMIC keys + 0179 GPIO vol-down built,
  untested on device. Confirm HID events in sweetlog.

## P2 — usable-device tier

- [ ] **Battery — i2c7 bq27411 path (do FIRST, no pwrap needed).**
  `i2c7@11d01000` has `mediatek,bq27411_gauge@55` + `oplus,bq27541-battery@55`
  at the same address — identify which ACKs, read voltage/current/
  capacity, publish `IOPMrootDomain` smart-battery nub (viva battery
  driver pattern, `ti,bq27z561` is the reference match to adapt).
  Fallback: MT6359 FGADC via pwrap once P1 lands.
- [ ] **WiFi — MT6853 port of the viva connac stack** (driver already
  compiled in; deltas only):
  1. ADT: add `mediatek,mt6853-wlan` to `VivaWLAN` IONameMatch.
  2. Memory: widen EMI/DMA alloc masks — athens highmem is
     `0x100000000+`, viva masks to <4 GiB → allocations fail. 36-bit
     capable hardware; use managed highmem pool, NOT carved regions
     (gpu8 carve hang precedent).
  3. Bus protection: update `prot[]` masks to MT6853 values
     (`clk-mt6853-pg.c`: STEP1_0 bits 13+18, STEP2_0 bit14 → PROT_SET;
     STEP2_1 bit10 → PROT1_SET).
  4. PMIC rails: MT6359 `VCN33_1_WIFI`/`VCN33_2_WIFI`/`VCN18` (addresses
     in `mt6359-regulator.c`); extend `VivaPwrap` whitelist. No VCN28.
  5. EMI MPU: configure `REGION_CONN` on `emimpu@10226000` for the EMI
     window (MT6853 sets CONSYS_ENABLE_EMI_MPU=1; viva skipped it).
  6. EMI remap: verify `topckgen_base + CONSYS_EMI_MAPPING_OFFSET`
     vs driver's `INFRA_EMI_MAPPING 0x10001380`.
  7. Firmware: extract `soc2_2_ram_{mcu,bt,wifi}_*_hdr.bin` +
     `WIFI_RAM_CODE_soc2_2_*.bin` + NVRAM `WIFI` record from RMX2117
     vendor/super or stock ROM → `/usr/share/firmware/wifi/`.
     RAM patches are version-locked to the RAM_CODE build.
  8. Port upstream `0192`/`0193` (RX block-ack/reorder, RX ring 128,
     WFDMA IRQ, rx-desc flush) before join testing.
  9. Sequence: `wifi status/detect` → `wifi on` (MCU idle
     `0x18002600==0x1D1E`) → `wmt` → `fw` → `cap` → `init`/`scan` →
     Settings WPA2 join → DHCP → sustained TX/RX.
- [ ] **Sensors** — enumerate `als/`/`gyro/` child compatibles + unclaimed
  i2c addresses; then HID-sensor bridge (same IOHIDEventService path as
  touch/buttons) for accel/gyro/ALS/prox → iOS motion sensor APIs.
- [ ] **Display finish** — panel black: check `disp_leds` backlight node
  (needs driver or panel-side enable?), DSI init sequence, pinmux state.
  Compositor path proven once userspace unblocks (P0).
- [ ] **Charging** — MT6360 (i2c5 subpmic) + MT6359 charger nodes;
  wall-charger input limit exists in viva (`0125`) as reference.

## P3 — research-grade (multi-month, do not schedule)

- [ ] **Cellular — MTK CCCI baseband bridge.** Proven architecture
  (QcomBaseband on Qualcomm: modem boots under XNU, AppleBaseband
  personalities, QMI/IPA data path, VoLTE on UniXNU-pong) but MT6853
  needs a from-scratch CCCI implementation — transport, MD firmware
  boot, NVRAM/EFS serving, data path. Largest project on the list.
  `modem`/`persist`/`nvram` partitions preserved = calibration data
  survives. Reference: github.com/UniXNU/QcomBaseband +
  hackios-web cellular docs.
- [ ] **Camera** — IMX576 48MP (i2c2 camera_main@1a) + 2 secondary +
  5 EEPROMs; camsys/seninf/camsv processors. Blocked on Apple's
  AppleH1CamIn/AppleISP contract — no public spec. Enumerate sensor
  compatibles + EEPROM contents first (cheap, do anyway).
- [ ] **Audio/mic** — MT6359 codec + `aw87339` smart PA (i2c6) +
  `smart_pa` node. Blocked on AppleAudioFamily contract. Smart-PA i2c
  driver alone is easy; iOS audio path is the wall.
- [ ] **Bluetooth** — hardware path free once WiFi/WMT works (BTIF
  `0x1100c000`); iOS side needs bluetoothd-acceptable controller
  personality — unproven, research-grade.
- [ ] **GPS** — MT6631 function via conninfra; custom NMEA→locationd
  injector conceivable after WiFi path works. Low priority.
- [ ] **Thermal (LVTS)** — port viva `0147` lvts driver; feeds thermal
  management once powerd path is stable.

## Excluded (iOS architecture, not effort)

- **Fingerprint** — Goodix on SPI5 exists but iOS binds biometrics to
  Secure Enclave. Impossible.
- **NFC payments** — requires AppleSE. Tag-read research only.
- **FM radio** — no iOS path (Radio app is US-carrier-only).
- **TEE/trusty/GZ, SCP/SSPM, video codecs (vdec/venc/vpu), cellular
  modem firmware internals** — no iOS consumer or separate-OS domain.

## Done / verified (for completeness)

- [x] Kernel→userspace boot (SpringBoard/backboardd/daemons exec)
- [x] UFS storage r/w (iOS root on userdata LUN2)
- [x] Display pipeline (Apple logo renders; compositor pending P0)
- [x] HFS write-path panic fixed (0203 clamps/quarantines)
- [x] WiFi ADT marker node + full driver compiled in
- [x] Buttons drivers built (0178/0179) — device test pending
- [x] Touch driver built (0180) — FW handshake pending
