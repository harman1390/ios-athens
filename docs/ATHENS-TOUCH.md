# RMX2117 (Athens) Touch — Reversed Engineering from PitchBlack TWRP

Status: **driver implemented (`xnu/patches/0180-*.patch`) — build + on-device test pending**

## Verified live hardware (from running PitchBlack recovery)

| Item | Value | Source |
|---|---|---|
| Touch IC | Novatek **NT36672C** (`novatek,nf_nt36672c` bound driver) | `/sys/bus/spi/devices/spi4.0/driver` |
| SPI host | `spi4@0x11018000`, `mediatek,mt6765-spi`, reg 0x100 | live FDT `spi4@11018000` |
| SPI host IRQ | GIC SPI 163 (`interrupts = <0 0xa3 4>`) | live FDT |
| Chip-select | CS0 (`reg = <0>`) | live FDT |
| Bus speed | **9.6 MHz** (`spi-max-frequency = 0x927c00`) | live FDT |
| Touch IRQ | **EINT14, falling edge** (`interrupts = <14 2>`, `irq-gpio = <2 14 0x2002>`); live `/proc/interrupts` = `mt-eint 14 Edge touchpanel` | live FDT + procfs |
| Reset GPIO | **GPIO33** (`reset-gpio = <2 33 0>`) | live FDT |
| Panel | `lcm=1-nt36672c_fhdp_dsi_vdo_dphy_jdi_120_lcm_drv` → **JDI** panel, FHDP 1080×2400, project `androidboot.prjname=20686` → fw dir **20611** | `/proc/cmdline`, FDT `platform_support_project` |
| Coords | `display-coords` 1080×2400; `tx-rx-num` 16×36; max 10 contacts | live FDT |
| Supply | `vtouch-supply` → mt6360 `ldo2` "vtp", `regulator-always-on` (no XNU enable needed) | live FDT |
| pinctrl | default = `int1_active`(GPIO14 in/pu) + `reset1_active`(pin43 out-hi) + `spimode_default`(pins **12,13,97,98 func2**, drv-str 4); suspend = GPIO14 + pin43 out-low | live FDT pinctrl |
| Clocks | `topckgen` idx **9** (spi4 mux src), idx **0xb3** (179, parent), `infracfg_ao` idx **0x49** (73, bus gate `INFRA_SPI4`) | live FDT |
| SPI4 pins | **SCK=GPIO12, MISO=GPIO13, MOSI=GPIO97, CS=GPIO98** — all func2 | live FDT pinmux `<0xc02 0xd02 0x6102 0x6202>` |

## SPI controller registers (`spi-mt65xx.c`)

Base `0x11018000`. Layout:
```
0x00 SPI_CFG0   [sck_high:0-7 sck_low:8-15 cs_hold:16-23 cs_setup:24-31]
0x04 SPI_CFG1   [cs_idle:0-7 packet_loop:8-15 packet_len:16-25 get_tick_dly:29]
0x08 SPI_TX_SRC  (DMA addr)          0x0c SPI_RX_DST (DMA addr)
0x10 SPI_TX_DATA (PIO FIFO)          0x14 SPI_RX_DATA (PIO FIFO)
0x18 SPI_CMD    ACT=b0 RESUME=b1 RST=b2 PAUSE_EN=b4 DEASSERT=b5
                SAMPLE_SEL=b6 CS_POL=b7 CPHA=b8 CPOL=b9
                RX_DMA=b10 TX_DMA=b11 TXMSBF=b12 RXMSBF=b13
                RX_ENDIAN=b14 TX_ENDIAN=b15 FINISH_IE=b16 PAUSE_IE=b17
0x1c SPI_STATUS0  (busy=b0)          0x20 SPI_STATUS1
0x24 SPI_PAD_SEL                   0x28 SPI_CFG2
```
Limits: **PIO FIFO 32 B**, DMA packet **1024 B**, `packet_loop` for >1 KiB.
Driver config (from `mt_chip_conf`): cpol=0 cpha=0, MSB first, `high_time=low_time=5` (10 MHz @ 100 MHz ref), `cs_idletime=2`, `finish_intr`, DMA mode.

## Novatek NT36672C protocol (`nt36xxx.c/h`, `nt36xxx_fw_update.c`, `nt36xxx_mem_map.h`)

- **Framing:** write = `addr|0x80` + payload; read = `addr&0x7F` + 1 dummy byte, data lands at `rbuf[2]`. CS held per xfer (`deassert=0`).
- **Paging:** `nvt_set_page(a)` = SPI write `{0xFF, a>>15, a>>7}`; `nvt_write_addr(a,d)` = set_page + write `{a&0x7F, d}`.
- **Memory map** — the driver picks from `trim_id_table` after reading the 6-byte trim ID at `0x1F64E`. Two families: **NT36672A** (`EVENT_BUF=0x21C00`, `BOOT_RDY=0x3F10D`, ILM/DLM len+des `0x3F1xx`, G/R cks `0x3F1xx`, `BLD_CRC_EN=0x3F30E`, `hw_crc=1`) and the **no-flash family** (NT36525/NT36676F: `EVENT_BUF=0x11A00`, `BOOT_RDY=0x1F141`, `POR_CD=0x1F61C`, `R_ILM_CHECKSUM=0x1BF00`, `hw_crc=0`). Our blob's partition SRAM addrs (0x0–0x2B4A8) sit in the small-map range; the trim ID decides.
  Event-map bytes (both): host cmd `0x50`, handshake `0x51`, reset-complete `0x60` (values 0xA0 INIT→0xAF), fwinfo `0x78`, projectid `0x9A`.
- **Control regs (DT props):** `SWRST_N8_ADDR`, `SPI_RD_FAST_ADDR` — read as `novatek,swrst-n8-addr`/`novatek,spi-rd-fast-addr` (not in the NF FDT → driver tries `0x03F0FE`/`0x01F01A`/`0x01C0BE`, ADT `swrst-addr` overrides).
- **Boot sequence (noflash — FW in RAM, must re-download every power-on):**
  1. `nvt_bootloader_reset` → `write_addr(SWRST_N8_ADDR, 0x69)`, delay 5 ms, clear `SPI_RD_FAST`.
  2. Parse fw blob header (`nvt_bin_header_parser`): ilm_dlm sections `[BIN_addr,SRAM_addr,size]` 12 B each at offset 0; others 16 B at offset `0x30 + 0x10*i`; `partition = ilm_dlm + ovly + info`.
  3. `nvt_write_sram` — burst-write each partition to its `SRAM_addr` via page+addr, ≤63 KB chunks (`NVT_TRANSFER_LEN`).
  4. **`hw_crc=1`:** `set_bld_hw_crc` (ILM/DLM sram+size+crc to `DES/LEN/G_CKS` regs) → `bld_crc_enable` (`BLD_CRC_EN|=0x80`) → `fw_crc_enable` (`RESET_COMPLETE=0`, `HOST_CMD=0xAE`) → `boot_ready` (`BOOT_RDY=1`) → poll `EVENT_BUF|RESET_COMPLETE` for `≥0xA0` (INIT, ≤10 tries); retry whole flow ≤2, `nvt_read_bld_hw_crc` dump on fail.
     **`hw_crc=0`:** `eng_reset` first, no bld regs; `boot_ready` also writes `BOOT_RDY=0` + `POR_CD=0xA0`; after the reset-state poll, compare `partition*4` bytes at `R_ILM_CHECKSUM` against the `CheckSum`-computed partition crcs.
  5. `nvt_get_fw_info` → read `EVENT_BUF|0x78` (17 B): fw_ver, x_num,y_num, abs_x/y_max, btn count; `nvt_read_pid` at `0x9A`.
  6. Probe also does `nvt_ts_check_chip_ver_trim` → trim ID bytes → mem map + `hw_crc` selection (our chip's ID unknown until first boot — both families are wired in).
- **IRQ path:** threaded ISR → `CTP_SPI_READ(point_data, 65+1)` — `point_data` starts zeroed, so `point_data[0]=0` reads xdata index 0 at the event-buf page. Then WDT/fw-recovery checks, checksum (65 B), per-finger 6-byte slots at `pos=1+6i`: `id=b0>>3`, `state=b0&7` (1 down/2 move/3 up), `x=b1<<4|b3>>4`, `y=b2<<4|b3&0xF`, `w=b4`, `p=b5` (+`b63+i` hi-byte for i<2). MT protocol B.

## Firmware blob

- Extracted **`FW_20611_NF_NT36672C_JDI`** (project dir 20611, JDI panel) from kernel `touch.h` → `research/rmx2117/touch/FW_20611_NF_NT36672C_JDI.bin` — **139,264 bytes**.
- The oplus `touch.c` framework picks this array by `get_project()`→`platform_support_project`→dir + `lcm=` cmdline match (`nt36672c` + `jdi` → JDI fw). Our unit: prjname 20686, JDI panel.
- Stage for XNU like the Wi-Fi fw: `iosroot`-visible path (see `tools/build_iosroot.py`), loaded at driver start and streamed over SPI.

## XNU implementation (patch `0180-athens-spi-nt36672c-touch.patch`)

**Driver source:** the live binding is `oppo,tp_noflash` / `novatek,nf_nt36672c` — that driver lives in `vendor/oplus/kernel/touchpanel/oplus_touchscreen` (symlink from `drivers/input/touchscreen/oplus_touchscreen`), **not in the public kernel repo**. The protocol below is the generic `nt36xxx` one the NF variant shares; every constant/flow is taken from `drivers/input/touchscreen/NT36672C/nt36xxx*`.

- **`iokit/Kernel/arm/AthensSPI.cpp/.h`** — mt65xx host on `spi4` (`mediatek,mt6765-spi`). PIO FIFO ≤ 32 B; the block's TX_SRC/RX_DST DMA for larger single-CS frames (SRAM bursts ≤ 63 KiB must be one frame — splitting restarts the frame address). Programs `spi_sel` mux (topckgen CLK_CFG_6 lsb16=3 → msdcpll_d4) + `ifrao_spi4` gate (+0xa4 bit25) via ADT regs 1/2; mode 0 MSB, sck 5+5 → ~9.6 MHz.
- **`iokit/Kernel/arm/hid/AthensNT36672C.cpp`** — `SweetHIDTouch` on `touch` (provider = `AthensSPI` via `VivaDTNub::publishChildren`, like `VivaI2C`→`VivaGT9896`).
  - **Map selection is hardware-verified, not guessed**: `chipTrim()` does `bootloader_reset` → `set_page(0x1F64E)` → reads the 6-byte trim ID → matches the `trim_id_table` (both families carried). NT36672A map = event buf `0x21C00`, bld regs `0x3Fxxx`, `hw_crc=1`; no-flash family = event buf `0x11A00`, `boot_rdy 0x1F141`, `por_cd 0x1F61C`, `r_ilm 0x1BF00`, `hw_crc=0`. SWRST-N8 addr is discovered too — candidates `0x03F0FE`/`0x01F01A`/`0x01C0BE` (mt6833-family dtsi + fallbacks), ADT-overridable via `swrst-addr`.
  - **Firmware blob verified**: `firmware/touch/nt36672c_jdi.bin` parses cleanly with `nvt_bin_header_parser` — header end `0x100` → 13 info + 0 ovly + ILM/DLM = 15 partitions; ILM `BIN 0x100→SRAM 0x0`, 77,447 B; DLM `BIN 0x18000→SRAM 0x27040`, 17,511 B; `NVT` end flag → `need_write_size 0x20000`. SRAM targets are the small-map range, consistent with the NF family — the trim ID is the final arbiter.
  - **Download = the real `nvt_download_firmware[_hw_crc]`**: hw_crc=1: `bootloader_reset` → partition writes (size+1, ≤63 KiB bursts) → `set_bld_hw_crc` (ILM/DLM reg banks) → `bld_crc_enable` (`BLD_CRC_EN|=0x80`) → `fw_crc_enable` (RESET_COMPLETE=0, HOST_CMD=0xAE) → `boot_ready` → `check_fw_reset_state(INIT)`, retry ≤2. hw_crc=0: `eng_reset` first, no bld regs, `boot_ready` adds POR_CD writes, then the `R_ILM_CHECKSUM` compare. `fwInfo` gates download: a running fw skips it; a blank chip retries `vnode_open` every second until the iosroot mounts (like the vendor's deferred boot-update).
  - **ISR = `nvt_ts_work_func` verbatim**: 66-byte read at event-buf page (byte0=0), `0x77`-in-bytes-1..6 → re-download, >10 consecutive all-`{0xFD,0xFE}` → WDT recovery, packet checksum `pd[65] == ~(sum pd[1..64])+1`, slots at `pos=1+6i`: `id=b0>>3`, `state=b0&7` (1/2=down/move), `x=b1<<4|b3>>4`, `y=b2<<4|b3&0xF` → `touch()`. Compile flags from the header: `HW_RST=0`, `CHECKSUM=1`, `WDT=1`, `ESD=0`, `KEY_NUM=0`.
- **`tools/mkadt.py`** — `spi4` node (reg0=0x11018000, reg1=topckgen, reg2=infracfg_ao, SPI163) + `touch` child (CS0, 9.6 MHz, EINT14 falling, reset-gpio 33, 1080×2400, `fw-path`).
- **Firmware** — `firmware/touch/nt36672c_jdi.bin` → push to `/usr/share/firmware/touch/nt36672c_jdi.bin` on-device. JDI panel confirmed by `touch.c` (`nt36672c` + `jdi` cmdline → 20611 dir, `prjname=20686`).

### Remaining verification gaps
- **Clock mux/gate values** — `spi_sel`/gate bits from `clk-mt6853.c`, never live-read. First suspect if SPI4 doesn't answer.
- **`nf`-driver deltas** — the exact noflash driver isn't public; if the trim/map/protocol diverges from generic `nt36xxx`, the trim read will report it in the boot log.
- **Nav buttons** — `touchpanel,button-type=4` in the board dtsi; report bytes 61-62 (`0xF8` flag) not implemented (`TOUCH_KEY_NUM=0` upstream too).

## Sources
- Kernel: `realme-mediatek-dev/android_kernel_realme_mt6853` @ `android-12.0` — `drivers/input/touchscreen/NT36672C/*` (protocol), `oplus_touchscreen` + `touch.c/.h` (panel select + fw store), `drivers/spi/spi-mt65xx.c`.
- Live: PitchBlack TWRP recovery on the unit (FDT, sysfs binding, cmdline).
