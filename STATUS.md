# Athens bring-up status board

**GOAL**: native iOS (xnu-8796, iOS 16 era) boot to GUI with working touch on
**realme Narzo 30 Pro 5G / realme 7 5G — RMX2117 "athens", Indian variant**
(MediaTek MT6853 / Dimensity 800U). Root lives in the existing `userdata`
partition (no GPT changes). Android user data is expendable; bootloaders,
recovery, modem, persist and `backup/` partition dumps must stay intact.

This file is the current-state matrix — what works, what is broken, what is
untested, and which commit/build last verified it. `NOTES.md` is the
chronological log; `ATHENS.md` is the hardware reference. Update this board
on every verified change so later work (touch, GPU, wifi, …) can spot
regressions immediately.

Legend: ✅ verified working · ⚠️ partially working/known-buggy ·
❌ broken/regressed · ⬜ not started/untested

Epistemic honesty: every ✅ means evidence exists on disk or in CI logs —
not "should work". Claims that are inference or hypothesis are marked
explicitly. If a row ever says ✅ without a pointer to the artifact that
proves it, treat it as unverified.

Audit of current claims (2026-11-12):
- OBSERVED: shim UFS writes land on disk (SHIMPRAM/SHIMFB headers + data
  in pull logs/athens-highmem-run4-pull.bin).
- OBSERVED: sdc59 = 13,049,848 blocks (52,199,392 KiB in /proc/partitions);
  records found at the corrected offset.
- OBSERVED: run-6 stray-write records (4 pages at 0xe0000000, tokd
  0xc25cc000, aend 0xffd60000) — decoded from disk records.
- OBSERVED: "Unaligned kernel data abort" panic, kernel_task tid 101 —
  from the photographed screen; esr/far digits are photo-transcribed and
  may contain read errors (treat the exact FAR as approximate).
- INFERRED (strong): kernel dies before panic-log init — pram region
  0x1bfeff000 contains only unwritten-DRAM garbage.
- HYPOTHESIS: the DRAMC/SPM dummy-read engine is the stray writer —
  fits the alloc-range evidence but NOT proven.
- HYPOTHESIS: the abort is post-physmap so patch 0176's mailbox fires —
  if it doesn't, that itself proves the abort is pre-arm_vm_init.
- ASSUMPTION REMOVED: fb dump can't recover panic screens (LK redraws
  fb every boot) — verified by rendering, kept in shim only because it
  costs nothing.

## Pipeline audit (whole image build path, 2026-11-12)

Per-file review of everything that produces `athens-boot-highmem.img`
(mkadt → mkpayload → shim objects → viva-bootimg repack):

VERIFIED BY EVIDENCE:
- mkadt constants: ATHENS_UFS 0x11270000 (dts + writes confirmed), FB
  0x77e20000 stride 4352 (dtb + rendered PNG), GIC 0x0c000000/0x0c040000,
  TIMEBASE 13 MHz, VTIMER 27 (dts + 8-core boot), dram windows (live-FDT
  reserved-memory dump), pram reg = two u64s, memory-map node minimal
  (XNU tolerates; lowmem reached launchd).
- mkpayload: chained-fixup resolution + payload header (boots XNU;
  header verified phys_base/mem_size on every image).
- shim loader.c: 64-bit clean audited; mmu.c identity map covers 64 GiB.
- shim ufs.c: UTRD/UCD/PRDT layout + READ/WRITE(10) — writes verified
  on hardware (SHIMPRAM landed).
- 0175/0176 patches: `git apply` clean against real CI tree (0176 was
  re-verified after LF normalization); verify_strings gates the binary.

DELIBERATE STAND-INS (known fakes, documented, not bugs):
- ATHENS_ECID, serial/MLB/UDID/MACs, region-info 'HN/A' (India — matches
  this variant), BOOT_MANIFEST_HASH (fixed sha384 stand-in so mount -P1
  passes), synthetic product props copied from the real D22AP ADT.
- display canvas 1125x2436 (presented as iPhone X panel; real panel is
  1080x2400 — presentation only, framebuffer is native).

UNVERIFIED ASSUMPTIONS (flagged; fix or prove before relying on them):
- athens-mkboot.sh payload-size bound uses VIVA's LK ramdisk/DTB addrs
  (0x47c80000/0x4bc80000), marked MEASURE, never confirmed on athens.
  Guard only; payload ~17 MiB works in practice — low risk.
- `ufsdma=0xfd000000` low-bank DMA carve: guessed PA, boot-arg
  relocatable, never exercised (kernel dies before ufs init).
- panic_scan region 0x1bdf00000: stale hardcoded PA, harmless scan.
- CKPT_MAGIC 0xc256bf00: lowmem-era PA, kernel never writes (dead diag).
- CPU clock-frequency props in ADT (2.4/2.0 GHz): descriptive only.
- athens_devices peripheral nodes: addresses from mt6853.dts, driver
  register semantics partly from viva MT6781 — untested until boot.
- 0176 mailbox itself: compiles/applies cleanly, hardware test pending.

## Boot chain

| Item | Status | Evidence / last verified |
|---|---|---|
| Stock boot path | ✅ | `fastboot flash boot` reliable; `fastboot boot` silently fails on this device — always flash |
| Shim loads at LK handoff | ✅ | EL2 → EL1 drop, watchdog kick, con output on LK fb (all runs) |
| Shim 64-bit loader | ✅ | payload/segments/ADT/boot_args 64-bit clean (audited + highmem boot reached XNU) |
| Shim → UFS write | ✅ | MediaTek `ufshci@0x11270000` (NOT Qualcomm 0x1d84000); `SHIMPRAM`/`SHIMFB` headers verified on disk |
| Shim pram harvest | ✅ | `ufs_harvest_pram()` dumps pram regions to userdata [last-1280,last-1026] |
| Shim fb dump | ⚠️ | `ufs_dump_fb()` works mechanically but captures LK's *fresh* splash — LK always redraws fb before shim runs, so it CANNOT recover panic screens |
| Shim ba-page dump | ⬜ | `ufs_dump_ba()` in loader_boot, writes ba page [last-4352,last-4349] before zero64 — pending first capture |

## Kernel / memory

| Item | Status | Evidence / last verified |
|---|---|---|
| XNU reaches launchd (LOWMEM window) | ✅ | run-6-era boot: launchd tasks, fsck, mount-phase-1/2, FIPS POST in pram log |
| ZCHECK/POOLSCAN/STATICFREE diag | ✅ | CI 43212579684 verified strings; run-6 pull decoded clean records |
| Stray writer on LOWMEM | ❌ unfixed | run-6: 4 contiguous free pages dirtied at PA 0xe0000000 (~191 bad qwords each, t≈29 s) inside `dram_r1_dummy_read` alloc-range — suspect MTK DRAMC/SPM engine, roams per boot |
| HIGHMEM window (0x100000000–0x1bfeff000) | ❌ broken | unaligned kernel data abort, esr 0x96000061, kernel_task tid 101, BEFORE panic/debug-log/UFS init — fault PC unknown, trap-frame capture build 43232381650 in progress |
| HIGHMEM = writer containment? | ⬜ | can't evaluate until kernel survives the early abort |
| Trap-frame mailbox | ⬜ | patch 0176: `panic_with_thread_kernel_state` copies saved_state to ba page tail ("SWEETABR"), shim persists it — pending CI kernel + flash |
| UFS DMA carve | ⬜ | `ufsdma=0xfd000000` fallback for >4G pool; untested (dies before ufs init) |

## Logging / persistence (the discipline that must not regress)

| Item | Status | Notes |
|---|---|---|
| Kernel → UFS log tail | ✅ | 1025-block tail [13048823,13049847] (device LBA = first_block+nblocks−1025; sdc59 is partition-relative) |
| Shim → UFS harvest | ✅ | zones below kernel tail — see zone map in NOTES.md |
| Pull offsets | ✅ | **13,049,848 blocks exactly**; pull all zones: `dd if=/dev/block/sdc59 bs=4096 skip=13045495 count=4353` |
| Panic screen capture | ❌ | impossible across reboot — LK redraws fb; fb dump removed as a capture path (left in shim, harmless) |
| Screenshots | last resort only | all state should land in the UFS pull |

## Storage / filesystem

| Item | Status | Notes |
|---|---|---|
| `sweet_ufs` host driver | ⚠️ | works on lowmem boots (log tail writes verified); highmem path untested |
| userdata GPT discovery | ✅ | LUN 2, partition 58 (sdc59), first LBA 0x272800 |
| iOS root in userdata | ⬜ | iosroot/ios16-root.img exists; mount not yet exercised on highmem |

## Peripherals (not started — do not regress the above when adding)

| Item | Status | Reference |
|---|---|---|
| Framebuffer console | ✅ | LK fb 0x77e20000 1080×2400 stride 4352 (ARBG) — panic UI renders |
| IOMobileFramebuffer / CoreAnimation | ⬜ | ios-sweet upstream has the full software-render stack to adapt |
| Touch | ⬜ | GT9886 over i2c0@11e00000 (+apdma 0x10217080), SPI 112; populated node TBD on device |
| Keys (PWR/VOL) | ⬜ | MT6359 via pwrap@10026000, EINT 118 |
| Battery/charger | ⬜ | MT6359 FGADC + MT6360 |
| Wi‑Fi/BT | ⬜ | CONNSYS MT6781+MT6631 — viva has the registry work |
| GPU (Mali G57-MC3 @0x13000000) | ⬜ | out of scope until GUI stable; CPU rendering first |

## Non-regression rules

1. Writes stay inside `userdata` tail zones only — never other partitions.
2. `backup/` images restore Android: boot/recovery/dtbo/lk/vbmeta untouched.
3. Every build gets `verify_strings` in CI; every flash gets a recovery pull.
4. `git status` may show unrelated WIP (AGENTS.md/LICENSE/docs) — don't treat as intended changes; don't stage them into diag commits.
5. Pull offsets come from the 13,049,848-block count — recheck before trusting an "empty" read.
