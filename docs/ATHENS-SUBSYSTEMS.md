# Athens (RMX2117) — per-subsystem plans

Research snapshot 2026-11-15. Hardware facts below are taken from the live FDT
dump (`research/rmx2117/live-dt/`) and the stock `mt6853.dts` +
`cust_mt6853_camera.dtsi` (techyminati/android_kernel_realme_mt6853).
Everything marked **[verified]** was read directly from a device-tree node or
source file; **[hypothesis]** is an inference to confirm before coding.

## How iOS exposes hardware (the model every plan below assumes)

- iOS has no Linux-style `udev`/`hwdb`. Userspace daemons talk to IOKit
  personalities published by kernel drivers.
- The athens/viva pattern that already works: a small IOKit nub matching a DT
  `compatible` string publishes the service iOS expects; a BSD-layer half
  (`viva_wlan.c`, `viva_wpa.c`, USB link, HID drivers) does the protocol work.
- So each subsystem plan = **(1) what the silicon actually is** →
  **(2) what iOS expects** → **(3) what we must write/port** →
  **(4) first probe to de-risk**.

---

## 1. Buttons — DONE (pending device test)

- Facts: PMIC keys via MT6359 `pwrap` eint (`0178-athens-mt6359-pmic-keys`),
  volume-down via GPIO key (`0179`), both publish `IOHIDEventService`s.
- iOS side: Home/vol keys arrive as HID events; wifid-style daemons unaffected.
- Remaining: verify on-device after next boot (sweetlog + `VIVA KEYS:` lines).
- Probe: boot 0187+ image, press keys, check `iPhone Accelerometer`-style HID
  event counters in sweetlog.

## 2. Touch — driver built, firmware path unverified

- Facts **[verified]**: `touch` node `goodix,touch`, status `okay` — Goodix
  NT36672C on SPI (`0180-athens-spi-nt36672c-touch`), `fpc_interrupt` +
  `swtp`/`swtp_1` eint nodes present for interrupt/reset.
- iOS side: publishes touch as HID digitizer — same path as viva gt9896
  (`0097`); iOS SpringBoard consumes it once events flow.
- Known gap: firmware download / reset-complete handshake times out —
  `0194-athens-touch-report-diag` added reporting to see how far it gets.
- Probe: run 0194 image, capture sweetlog, look for `ATHENS TOUCH:` stage
  markers (reset done? FW hdr accepted? FW tail checksum? first report?).
  Likely fixes: reset timing, FW binary must come from the RMX2117 vendor
  partition (not generic NT36672C), or SPI mode/clock.

## 3. Display / backlight

- Facts **[verified]**: full `dispsys` — `dsi@14013000`, `disp_*` overlays,
  `smi_larb*`/`smi_common`, `disp_mutex`, `mdp_*` video path, `disp_pwm0`,
  `disp_leds` (`mediatek,disp-leds` = backlight driver node), `dsi_te`.
  `0181-athens-fb-keep-display` keeps the panel up.
- iOS side: `IOMobileFramebuffer` scanout — viva `0109`/`0128`/`0135`/`0137`
  already solve scanout+vsync; athens needs its own DSI panel timing +
  backlight pwm/leds bring-up.
- Gap: panel shows black — likely DSI command/init sequence or backlight
  enable (`disp_leds` is the prime suspect; check whether `mediatek,disp-leds`
  needs a kernel driver or is handled by the panel driver).
- Probe: read panel `compatible` + init command blob from live-dt `dsi`/
  panel child node; check `disp_leds` reg/pinctrl; verify DSI lanes are
  muxed (pinctrl state) before DSI host init.

## 4. WiFi — researched; needs MT6853 port of the viva stack

See research notes (previous session). Summary:

- Facts **[verified]**: `wifi@18000000` (`mediatek,wifi`, SPI 377,
  1 MiB reg window, `memory-region` → 6 MiB `wifi_mem` pool),
  `consys@18002000` (`mediatek,mt6853-consys`, SPI 378/379/379, 12 reg
  ranges), `btif@1100c000` (`mediatek,btif`, SPI 152/153/158).
  `CONFIG_MTK_COMBO_CHIP_CONSYS_6853=y` → `SOC2_2X2`/`connac2x2`.
  MT6631-family radio, same generation as viva's MT6781 target.
- What exists: complete viva connac driver (`0123`–`0154`) is already
  compiled into athens kernels — power/firmware/WFDMA/NIC/scan/join/en0/
  wifid integration. athens ADT already emits the `wlan` marker node.
- What iOS needs: `wifid` → `IO80211Controller` registry + `en0` ifnet —
  the viva `VivaWLAN`/`VivaWiFi`/`viva_wlan`/`viva_wpa` stack provides all
  of it once hardware runs.
- Known deltas to fix (in order):
  1. `IONameMatch` — `VivaWLAN` matches `mediatek,mt6781-wlan`; add
     `mediatek,mt6853-wlan`.
  2. Memory <4 GiB masks — athens highmem is `0x100000000+`; viva EMI/DMA
     allocs mask to <4 GiB and will fail. Hardware supports 36-bit; widen.
  3. Bus-protection bits — MT6853 `clk-mt6853-pg.c` uses different TOPAXI
     masks than the driver's MT6781 tables.
  4. PMIC rails — MT6359 `VCN33_1_WIFI`/`VCN33_2_WIFI`/`VCN18` (see §8);
     blocked until pwrap works.
  5. EMI MPU — MT6853 sets `CONSYS_ENABLE_EMI_MPU 1`; region `REGION_CONN`
     on `emimpu@10226000` must be configured.
  6. EMI remap register — conninfra writes `topckgen_base +
     CONSYS_EMI_MAPPING_OFFSET`; verify offset vs driver's
     `INFRA_EMI_MAPPING 0x10001380`.
  7. Firmware — need `soc2_2_ram_{mcu,bt,wifi}_*_hdr.bin` +
     `WIFI_RAM_CODE_soc2_2_*.bin` from RMX2117 vendor partition / fastboot
     ROM; RAM patches are version-locked to the RAM_CODE build.
  8. Port upstream `0192`/`0193` RX fixes before first join test.
- Probe (first, read-only): `wifi status`/`wifi detect` via vivad — needs
  USB link confirmed (§11) or the auto-path via wifid; check
  `CONN_VERSION`/A-die ID `0x6631` once rails are up.

## 5. Bluetooth — shares the conninfra path, iOS side is the hard part

- Facts **[verified]**: BT is a function of the same MT6631/connac chip —
  `btif@1100c000` (`mediatek,btif`) is the host interface; viva already
  implements WMT/STP-over-BTIF (`0130`/`0131`) which also carries BT.
- iOS side: `bluetoothd` expects Apple Bluetooth controller personalities
  (PCIe/USB HCI). There is no generic "HCI over vendor UART" path — a
  custom kernel HCI transport publishing whatever bluetoothd accepts is
  research-grade, not a port.
- Verdict: hardware path becomes free once WiFi works; iOS stack
  integration is unproven. Defer behind WiFi.
- Probe: after WiFi firmware runs, check whether the BT firmware image
  loads via the same WMT channel (viva `wifi wmt` logs show the chip
  enumerating functions).

## 6. Cellular — not feasible

- Facts **[verified]**: MT6853 has an integrated modem (the `lte`/`ccif`
  infrastructure exists), but the baseband runs its own RTOS and protocol
  stack.
- iOS side: CommCenter/baseband is Apple-proprietary end-to-end. No iOS-on-
  Android port has ever brought up a MediaTek/Qualcomm modem — the AP-side
  driver is only half the problem; the modem firmware speaks a different
  protocol entirely.
- Verdict: impossible without a from-scratch baseband stack. Exclude.

## 7. Camera — hardware is rich; iOS pipeline is the wall

- Facts **[verified]**: full camera subsystem —
  `camsys@1a000000` (+ `_main/_rawa/_rawb/_a/_b/_c`), `cam1@1a030000`,
  `cam2@1a050000`, `cam3@1a070000` (+ `_inner`), `seninf_top` + `seninf1-6`,
  `camsv3-8`, `kd_camera_hw1`, `camera_af_hw_node` (`mediatek,camera_af_lens`).
  Sensors on i2c: `camera_main@1a` on i2c2 = **Sony IMX576** 48 MP
  (`imx576_mipi_raw` per cust dtsi); `camera_sub@1a` (i2c4),
  `camera_sub_two@1c` (i2c2), `camera_main_two@10` (i2c8) = secondary
  modules (2 MP class per device specs); 5 camera EEPROMs @ i2c2/i2c4/i2c8
  hold module calibration.
- iOS side: camera goes through `AppleH1CamIn` + `AppleISP` + a large
  camera-algorithm stack — one of the most proprietary pipelines in iOS.
  Feeding it requires implementing Apple's sensor→ISP→processor contract,
  which no public documentation exists for.
- Verdict: research-grade at best; do not plan near-term. The EEPROM data
  and AF VCM are also required for correct images — another layer.
- Probe (cheap, do anyway): enumerate the three sensor compatibles +
  EEPROM contents from live-dt to document exact modules; useful if camera
  is ever revisited.

## 8. Microphone / audio

- Facts **[verified]**: `sound` = `mediatek,mt6853-mt6359-sound` — MT6359
  has an integrated codec; `smart_pa` node + i2c6 children `aw87339@58`
  (Awinic smart PA), `speaker_amp@34`, `i2c_lcd_bias@3e`; `audio_sram`,
  `snd_audio_dsp`, `audio_extend` (`oplus,asoc-audio`) nodes present.
  Microphones route through the codec DMIC/AMIC paths + smart PA.
- iOS side: audio is `AppleAudioFamily` — iOS expects Apple's codec/engine
  personalities, not a generic ALSA-style codec. A custom kernel driver
  would need to publish whatever HAL interface iOS audio daemons bind to;
  no public contract exists.
- Verdict: like camera — research-grade. Speaker path additionally needs
  the smart-PA I2C driver (aw87339) which is a normal kernel i2c client —
  that part alone is easy; getting iOS to *use* it is the hard part.
- Probe: read `sound`/`audio_extend` DT for codec port map; identify mic
  pins (DMIC vs AMIC) — determines whether any userspace-injectable path
  exists.

## 9. Battery / charging

- Facts **[verified]**: `battery` = `mediatek,bat_gm30` (MTK gauge via
  MT6359 FGADC — **pwrap-dependent**); `charger` = `mediatek,charger`,
  `lk_charger`, `gauge_timer` nodes; i2c7 has `mediatek,bq27411_gauge@55`
  **and** `oplus,bq27541-battery@55` at the same address (one is the real
  gauge — likely bq27411-class fuel gauge, independent of pwrap); i2c5 has
  `subpmic@34`/`subpmic_ldo@64`/`subpmic_pmic@1a` (MT6360 charger/secondary
  PMIC per ATHENS.md).
- iOS side: needs `IOPMrootDomain` + a smart-battery nub publishing
  `AppleSmartBattery` data (voltage/current/capacity/cycle). The viva
  battery driver binds `ti,bq27z561` — athens needs either an MT6359-FGADC
  driver or a bq27411 driver emitting the same personality.
- Plan: prefer the **i2c7 bq27411 path** — it does not depend on pwrap
  bring-up (unlike keys/GPU/WiFi rails which all need WACS2). Read the
  gauge over i2c, publish capacity/voltage; charging control stays on
  MT6360/MT6359 charger later.
- Probe: i2c7 scan at 0x55 — does it ACK? Which compatible is live?
  Check `battery` node props for which gauge the stock kernel used.

## 10. GPS / FM radio

- Facts **[verified]**: neither has its own DT node — both are functions of
  the MT6631 connac chip, reached through the same conninfra/WMT path as
  WiFi/BT (§4/§5).
- iOS side: GPS feeds `locationd` (needs a location source — a custom NMEA
  injector is conceivable but research-grade); FM radio has no iOS path at
  all (Radio app is US-carrier-only and expects a specific stack).
- Verdict: GPS — possible long-term after conninfra works, low priority.
  FM — exclude.

## 11. NFC / fingerprint — iOS security model blocks both

- Facts **[verified]**: `goodix_fp` node (`goodix,goodix_fp`, okay) +
  `spi5@11019000/fingerprint@0` + `fpc_interrupt` — Goodix fingerprint on
  SPI5. `irq_nfc` = `mediatek,irq_nfc-eint` (eint only; the NFC controller
  itself is on an i2c bus — needs identification, likely NXP PN5x-class).
- iOS side: fingerprint is bound to the Secure Enclave (TouchID/FaceID) —
  a third-party fingerprint sensor cannot enroll or authenticate. NFC
  payments require AppleSE; tag reading would need a custom NDEF path.
- Verdict: fingerprint impossible; NFC exclude (or tag-read research only).

## 12. Sensors (ALS / proximity / motion / thermal)

- Facts **[verified]**: `als`, `gyro` nodes exist (children hold the actual
  sensor compatibles — needs enumeration); `thermal-sensor1/2/3` =
  `mediatek,mtboard-thermistor*` (board thermistors via auxadc); `therm_ctrl`
  + `lvts`-class infra present (viva `0147` LVTS driver is a port candidate);
  `subpmic_pmu_eint`, hall-sensor status needs checking.
- iOS side: motion/ALS/proximity sensors go through IOHIDFamily as HID
  sensor collections — same path as touch/buttons, so a custom driver can
  publish them. Board thermistors feed thermal management.
- Plan: enumerate `als`/`gyro` child nodes first (the compatibles are the
  real answer); accel/gyro likely on an i2c bus as standard parts
  (BMI/LSM/ICM-class) — an i2c HID-sensor bridge is medium effort.
- Probe: `ls als/ gyro/` child dirs + their `compatible` files; check i2c
  buses for unclaimed device addresses.

## 13. USB — needed regardless (vavad debug link + peripheral mode)

- Facts **[verified]**: `usb_xhci@11200000` + `usb0phy@11e40000` +
  `type_c_port0` + `tcpc_pd` (okay) + `extcon_usb` + `usb_boost_manager`.
- iOS side: viva already has USB device-mode (`0092`–`0094`, `0072`–`0077`
  sweet-* series) giving the vivad link used for all manual hardware
  stepping. athens needs the same for Synopsys DWC3 + Type-C PD.
- Status: athens USB link **unconfirmed** — this gates comfortable WiFi/
  touch/camera debugging. Highest-value infrastructure item after pwrap.
- Probe: check sweetlog for `VIVA USB:`/`ATHENS USB:` enumeration; verify
  `tcpc_pd` role detection; try device-mode bind.

## 14. Everything else — quick dispositions

| Subsystem | Node(s) | Verdict |
|---|---|---|
| UFS storage | `ufshci@11270000`, `ufs_mphy@11fa0000` | Works — iOS root boots from it |
| TEE/trusty/GZ | `trusty`, `tee_sanity` | Skip — iOS uses Apple SE, not MTK TEE |
| Video codecs | `vdec/venc/vpu_core0/1`, `vcu`, `wpe_a/b`, `mdp_*` | Research-grade; VideoToolbox wants Apple codecs — skip |
| SCP/SSPM | `scp@10500000`, `sspm@10400000` | MediaTek coprocessors — no iOS consumer; skip |
| Modem/ccif | (conninfra) | Cellular impossible (§6) |
| SIM | — | N/A without cellular |
| Barometer/mag | needs enumeration | Same HID-sensor path as §12 if present |
| FM/UWB | connac / none | Exclude |

## Suggested order (dependency-driven)

1. **pwrap/WACS2** (in flight, patches 0185–0187) — gates keys, GPU, and all
   PMIC rails incl. WiFi/charging.
2. **USB device link** — unblocks manual probing of everything below.
3. **Touch FW fix** (0194 diagnostics) — closest to done.
4. **Battery via i2c7 bq27411** — independent of pwrap; quick iOS-visible win.
5. **WiFi MT6853 port** — the big one; sequence in §4.
6. **Sensors enumeration + HID bridge** — medium effort, real iOS value.
7. **Display backlight/DSI** — panel bring-up.
8. Research-grade / excluded: camera, audio, BT, GPS, cellular, NFC, FP, FM.
