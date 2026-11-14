# GPU on athens: porting the viva Mali-G57 work (research only, 2026-11-12)

Status: **research, no code written.** Do not start implementation until
buttons and touch are confirmed working on device (user instruction).

## Hardware equivalence

| | viva (RMX3031) | athens (RMX2117) |
|---|---|---|
| SoC | MT6781 Helio G96 | MT6853 Dimensity 800U |
| GPU | Mali-G57 **MC2** (Valhall, 2 shader cores) | Mali-G57 **MC3** (Valhall, 3 shader cores) |
| Mali MMIO | 0x13000000 | **0x13000000 — identical** |
| topckgen | 0x10000000 | 0x10000000 — identical |
| apmixed | 0x1000c000 | 0x1000c000 — identical |
| scpsys/SPM | 0x10006000 | 0x10006000 — identical |
| mfgcfg | 0x13fbf000 | **0x13fbf000 — identical** (confirmed in mt6853 gpufreq debug prints 0x13fb_f130/0x13fb_f0b4) |
| PMIC | MT6366 | **MT6359 — different regulator map** |
| ADT gpu compatible | `mediatek,mt6781-mali` | `mediatek,mt6853-mali` (mkadt already emits) |

Every register block the Mali job-manager driver touches (GPU_ID, MMU,
JS, IRQs) is the same Valhall IP — the ~4200 lines of `VivaGPU.cpp`
(MMU address spaces, job slots, syncobj, fault recovery) port essentially
unchanged. GPU_ID will report MC3; the driver already reads
SHADER_PRESENT so core count should be dynamic — verify.

## What actually differs (the port surface)

1. **Match**: `VivaGPUAccelerator` matches only `mediatek,mt6781-mali`.
   Athens ADT emits `mediatek,mt6853-mali` → add match entry (or an
   AthensGPU subclass). KernelConfigTables one-liner.

2. **GPU power domains**: mt6853.dts gpufreq clocks list
   SCP_SYS_MFG0/1/2/3/**5** (five domains: ASYNC, MFG_TOP, Shader
   Stack0/2/4) vs MT6781's set — verify against athens live FDT which
   power-domains the mali node uses; SPM MTCMOS sequence order may differ.

3. **PMIC rails (the real work)**: MT6366 VGPU/VSRAM registers
   (0x1508/0x1526/0x1bc8/0x1bf4) are wrong for MT6359. Per
   `drivers/gpu/mediatek/gpufreq/v1/mt6853/mtk_gpufreq_plat.c` +
   mt6853.dts, the supplies are `_vgpu`/`_vsram_gpu` resolved to:
   - **VGPU = `buck_vproc1`** (mt_pmic_vproc1_buck_reg):
     EN `MT6359_RG_BUCK_VPROC1_EN_ADDR` = 0x1708 bit0;
     VOSEL `MT6359_RG_BUCK_VPROC1_VOSEL_ADDR` = 0x172e [6:0]
   - **VSRAM_GPU = `ldo_vsram_md`** (mt_pmic_vsram_md_ldo_reg):
     EN `MT6359_RG_LDO_VSRAM_MD_EN_ADDR` = 0x1f2c bit0;
     VOSEL `MT6359_RG_LDO_VSRAM_MD_VOSEL_ADDR` = 0x1b46 [6:0]
   - NOTE: vproc1/vgpu11 naming is confusing — vgpu11 feeds proc1 per
     the same dts (`proc1-supply = <&mt_pmic_vgpu11_buck_reg>`), while
     the gpufreq `_vgpu` maps to vproc1. **MEASURE on athens**: pull the
     gpufreq/mali node supplies from live FDT next recovery session;
     realme's dts may differ from xiaomi's.
   - Constraint differs: mt6853 wants **0 ≤ VSRAM−VGPU ≤ 350 mV**
     (vs MT6781's vsram ≥ vgpu + 0.1 V floor); slew rates 12.5 mV/µs
     rising, 5 mV/µs falling. These are regulator-framework calls in
     Linux; we poke pwrap registers directly like VivaGPU already does —
     but must add the MT6359 addresses to `VivaPwrap::writeAllowed`.

4. **OPP table**: `g_opp_table_segment_1/2/3` chosen by efuse
   devinfo index 134 — freq/vgpu/vsram triples. Extract for athens;
   start with ONE conservative OPP like viva did (vivagpufreq boot-arg,
   default 300 MHz — mt6853 max is higher, table TBD).

5. **Clocks**: MFGPLL in apmixed (0x1000c000, parent XTAL 26 MHz),
   mfg_sel mux in topckgen CLK_CFG_0[17:16] — same offsets as MT6781
   per the shared register layout; verify PCW/enable sequence against
   mt6853 clk driver (apmixed MFGPLL offset may differ — check
   clk-mt6853.c).

## What does NOT need porting

- The whole userspace Metal stack plan (`docs/PIANO-GPU.md` G3-G9):
  Mesa/Panfrost Valhall compiler + Gallium backend + AIR→NIR translator
  + `VivaMTLDriver.bundle` — **GPU-architecture-specific, identical for
  MC2/MC3**. This is the bulk of the work and it transfers wholesale.
- `VivaGPUUserClient` ioctl surface (DRM_PANFROST_* semantics +
  syncobj + IOSurface import) — unchanged.
- `IOAcceleratorES` publishing + `vivagpu=0` kill switch — unchanged.

## Suggested order (when unblocked)

1. Add `mediatek,mt6853-mali` match (verify GPU_ID reads MC3, IRQs fire)
2. Port power-on with MT6359 rails (extend pwrap whitelist) — G1
3. MMU/jobs — reuse as-is — G2
4. Then the shared Metal stack (PIANO-GPU G3+) applies to both devices.

## UPDATE 2026-11-14 — driver already in tree; hardware data pulled

**The whole viva kernel driver is already applied in athens** —
`xnu/patches/0100-viva-gpu-mali` … `0137-viva-gpu-dvfs-boost` ship
`iokit/Kernel/arm/VivaGPU.{cpp,h}` + `VivaGPUUserClient.cpp` +
`viva_gpu_uapi.h`, compiled into the kernel, all boot-args present
(`vivagpu`, `vivagpufreq`, `vivagpumv`, `vivagpucache`, `vivagpuwc`,
`vivagpudvfs`, `vivagpuboost`, `vivagpumem*`, `vivagpuprobe` …).
`AthensPMIC.cpp` (MT6359 on pwrap@0x10026000) and `VivaPMIC`/`VivaPwrap`
already exist. So this is NOT a from-scratch port — it is **hardware
adaptation of a driver that is already compiled in**.

**Userspace Metal stack exists and is proven on viva**: separate repo
`github.com/Nik300/viva-gpu` (cloned to `../viva-gpu`). Metal frontend
(`driver/metal/*.m`) + AIR→NIR (`vmg_air.c`) + static Mesa/Panfrost
(Valhall compiler — MC2/MC3 agnostic) + `libdrm-xnu`→`vgpu`→IOKit →
`VivaMTLDriver.bundle` (`MetalPluginName`/`VMDevice`). On viva it is
LIVE: backboardd creates `VivaGPUUserClient` BOs, Panfrost BO cache
present, SpringBoard/Settings GPU-accelerated. It builds against the
kernel uapi in `uapi/viva_gpu_uapi.h` — unchanged for athens.

**Why athens shows no IOAcceleratorES today** (all fixable):
1. ADT `/arm-io/gpu` compatible is `mediatek,mt6853-mali` but
   `VivaGPU` matches `mediatek,mt6781-mali` → add match.
   NOTE: the *real* athens FDT uses `mediatek,mali` + `arm,mali-valhall`
   (see `mali@13000000/compatible` in `research/rmx2117/live-dt/`) —
   our ADT string is synthetic; keep it consistent with the match.
2. `vivagpu` defaults to 0 → set `vivagpu=2` in `ATHENS_EXTRA`.
3. ADT gpu `reg` is minimal (Mali MMIO only). The driver also needs the
   MFG power blocks — viva's node carries mfgcfg/SPM/topckgen/apmixed/
   infracfg_ao. Port those `reg` ranges into the athens node.
4. PMIC rail defines are MT6366 (`VivaGPU.cpp` ~L204-212). athens needs
   MT6359 — and `VivaPwrap::writeRegulator` whitelist must accept them.
5. IRQs: athens gpufreq/mali use SPI 364-368 (mkadt comment) vs viva
   274-276 — confirm which the driver requests.

**Live device-tree data pulled (research/rmx2117/live-dt, 2026-11-13)**
- `gpufreq/clock-names`: `clk_mux clk_main_parent clk_sub_parent
  subsys_bg3d mtcmos_mfg0 mtcmos_mfg1 mtcmos_mfg2 mtcmos_mfg3
  mtcmos_mfg5` → **five MFG power domains** (mfg0/1/2/3/5), matching
  ATHENS-GPU.md; SPM MTCMOS sequence order must be ported.
- `gpufreq/_vgpu-supply` phandle **0x83 = `buck_vproc1`** (reg=vproc1);
  `gpufreq/_vsram_gpu-supply` phandle **0x84 = `ldo_vsram_md`**
  (reg=vsram_md) — CONFIRMED for this realme unit (the vgpu11 red
  herring is a different buck, phandle 0x41, feeds proc1 not GPU).
- `mali@13000000`: compatible `mediatek,mali`/`arm,mali-valhall`,
  minimal node (no clocks/power-domains/OPP in DT — all in gpufreq
  driver). `operating-points` empty → OPP comes from the MT6853
  gpufreq driver / efuse devinfo, still to extract.
- PMIC on `pwrap@0x10026000/mt6359-pmic/mt6359regulator` — regulator
  names confirmed; **register addresses are NOT in DT** (come from the
  MT6359 driver map). ATHENS-GPU.md candidates: VGPU `buck_vproc1`
  EN 0x1708 / VOSEL 0x172e[6:0]; VSRAM `ldo_vsram_md` EN 0x1f2c /
  VOSEL 0x1b46[6:0] — **verify against mt6359 register defs before
  writing** (this is the riskiest unknown).

## Concrete port checklist (ordered)

1. **mkadt gpu node**: add the MFG `reg` blocks (copy viva's list,
   keep athens MMIO base) + correct SPI IRQs; keep `mediatek,mt6853-mali`.
2. **VivaGPU match**: accept `mediatek,mt6853-mali` (KernelConfigTables).
3. **MT6359 rails**: add vproc1/vsram_md EN+VOSEL(+DA) addresses to the
   PMIC defines and to `VivaPwrap::writeRegulator` whitelist; port the
   power-on ordering (VSRAM then VGPU, voltage step limits).
4. **MFG power/clock**: port mt6859/mt6853 gpufreq MTCMOS domain order
   (mfg0,1,2,3,5) + MFGPLL (apmixed 0x1000c000) + mfg_sel mux; verify
   against `clk-mt6853.c`/`gpufreq_v1/mt6853`.
5. **OPP**: extract mt6853 segment table; start one conservative OPP
   (`vivagpufreq`), vsram−vgpu ≤ 350 mV constraint.
6. Boot `vivagpu=2` → `gpu on`/`selftest` via link → GPU_ID must read
   MC3 (SHADER_PRESENT=3 cores). Iterate on power faults.
7. **Userspace**: build `viva-gpu/ios` for athens (needs iOS SDK/Xcode —
   dev's Mac; this box has only CLT). Inject `VivaMTLDriver.bundle` +
   dylibs into rootfs; Metal auto-loads via the service properties.

## Honest scope

Steps 1-6 are kernel hardware bring-up (days, iterative on-device).
Step 7 is the userspace build+inject (the repo is ready; the blocker is
iOS SDK + rootfs packaging). Full GPU-accelerated GUI = both, plus the
viva display-sync patches (0111-0137) that make frames wait on GPU
fences — port those only after basic submit works.

## VERIFIED register data (2026-11-14, from MT6359/MT6853 kernel source)

Reference sources saved in `research/mt6853/`:
- `mt6359-registers.h` — full MT6359 pwrap register map
- `mt6359-regulator.c` — regulator voltage tables/ranges
- `mtk_gpufreq_plat.c` — MT6853 gpufreq power/clock/volt/OPP logic

**VGPU = buck_vproc1** (phandle 0x83, confirmed via live-dt):
- EN  `MT6359_RG_BUCK_VPROC1_EN_ADDR`    = 0x1708  (CON0, bit0)
- VOSEL `MT6359_RG_BUCK_VPROC1_VOSEL_ADDR` = 0x172e (ELR0, [6:0])
- DA_VOSEL `MT6359_DA_VPROC1_VOSEL_ADDR`  = 0x1726 (DBG0, [6:0])
- DA_EN `MT6359_DA_VPROC1_EN_ADDR`       = 0x1728  (DBG1, bit0)
- Range 0.4–1.194 V, step 6.25 mV → code = (uV−400000)/6250, linear

**VSRAM_GPU = ldo_vsram_md** (phandle 0x84, confirmed):
- EN  `MT6359_RG_LDO_VSRAM_MD_EN_ADDR`    = 0x1f2c  (CON0, bit0)
- VOSEL `MT6359_RG_LDO_VSRAM_MD_VOSEL_ADDR` = 0x1b46 (ELR, [6:0])
- DA_VOSEL `MT6359_DA_VSRAM_MD_VOSEL_ADDR`  = 0x1f32 (VOSEL1, [6:0]<<8)
- DA_EN(B) `MT6359_DA_VSRAM_MD_B_EN_ADDR`   = 0x1f2e (MON)
- Range 0.5–1.10 V (MT6359; MT6359P to 1.294 V), step 6.25 mV → code = (uV−500000)/6250

**Volt switch order** (mtk_gpufreq_plat.c __mt_gpufreq_volt_switch):
rising → set VSRAM then VGPU; falling → set VGPU then VSRAM; settle
~µs per mV (rising 12.5 mV/µs, falling 5 mV/µs). VGPU also has a
REGULATOR_MODE_FAST/NORMAL (PWM/auto) mode select.

**MTCMOS** (mt_gpufreq_mtcmos_control): power-on order mfg0, mfg1, then
shader-gated mfg2/mfg3/mfg5 by SHADER_PRESENT bits; power-off reverses.
MT6853 = 5 domains (vs MT6781's 4) → SPM_MFG_PWR_CON index map + status
bits differ; read clk-mt6853-pg.c / spm register defs for exact addrs.

**Still needed before power-on works:**
- SPM MTCMOS PWR_CON/status register offsets for the 5 MT6853 domains
- MFGPLL apmixed offsets for MT6853 (CON0/CON1/PWR_CON0 may differ)
- topckgen mfg_sel mux bits + CK_CFG_UPDATE for MT6853
- mfgcfg 0x13fbf000 sub-register offsets (ATHENS-GPU.md says same base)
- infracfg_ao bus-protection regs for MFG1 equivalent
- GPU IRQ numbers (gpufreq/mali SPI 364-368 per mkadt comment — verify)
- OPP table values (g_opp_table built from segment+efuse at runtime;
  not a static array in this file — find mt6853 opp table source)
- SHADER_PRESENT read for MC3 core count
