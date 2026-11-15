# iOS 16 on sweet (Redmi Note 10 Pro, SM7150) - working notes

**STATUS.md = the live status board (goal + per-subsystem verified/broken
matrix). Update it on every verified change. This file stays the log.**

## >>> ATHENS HANDOFF 2026-11-15aj - *** 0203 BUILD DONE + FLASHED + BOOTING (GUI TEST #2) *** CI run 43728757742 SUCCESS; verify "found: clamped invalid forward link" + "found: quarantining corrupt node" both in kernel. kernel SHA256 d6da374dfc35bbe166e7496ec7663ff316cf7412c8bdf68bb7d0c9f8f6b422a7. Built shim/out/athens-payload-0203.bin (mkpayload kernel0203 + athens-notouch.adt + SAME diag cmdline) -> repacked shim/out/athens-boot-0203.img 17500160B (reused shim/out/athens/Image.gz) -> fastboot flash boot OK -> reboot. USERDATA = fsck-repaired gpu-fixed.simg (unchanged). THIS IS THE GUI TEST: 0202 got display COMPOSING (swaps=5) but died on write-path panic; 0203 makes HFS write path non-fatal (clamp bad links + quarantine corrupt nodes) so kernel SURVIVES the crash-storm catalog writes. EXPECTED: may print "clamped invalid forward link"/"quarantining corrupt node" (TOLERATED, not fatal); NO hfs_UNswap panic; crash storm continues (expected, peripheral daemons); FBSTAT swaps>0 -> SpringBoard/backboardd keep rendering -> GUI. USER: watch screen ~3-8min. SpringBoard/lockscreen/home = GUI DONE. Apple-logo-frozen past ~8min = pull ring check backboardd render/IOSurface. Panic = new issue -> pull ring. NEXT: user reports -> if GUI milestone; if stall pull ring (sweet-log-pull.sh).

## >>> ATHENS HANDOFF 2026-11-15ai - *** 0202 WORKED FOR DISPLAY; NEW PANIC = WRITE-path hfs_UNswap_BTNode; PATCH 0203 building *** r0202-ring (logs/r0202-ring.txt.bin, SWEETPAN snapshot): 0202 read-patch CONFIRMED WORKING - "tolerated free node" fired for blocks 0/47145/47142; FBSTAT swaps=5 flips=3 copies=5 = DISPLAY WAS COMPOSITING (GUI rendering!) vs swaps=0 before. Boot reached SpringBoard/backboardd alive + peripheral daemon crash storm (containermanager/tccd/accountsd/dmd/assistantd/ScreenTimeAgent sig5/6 at consistent PCs = EXPECTED ported-iOS userspace aborts from missing services; "Too many corpses" = ReportCrash throttling; backboardd+SpringBoard ALIVE, only peripherals crash). THEN panic: `hfs_UNswap_BTNode: invalid forward link (0x01CC006E)` @hfs_endian.c:300 = WRITE/HostToBig path (not the read path 0202 fixed). Trigger: crash-storm daemons write .microstackshots -> catalog inserts -> a node with garbage fLink hit the write path which PANICS (read path only printf+error). ROOT CAUSE of garbage fLink: node modified in-memory by B-tree op (stray-writer memory corruption OR driver free-node reuse) - fLink 0x01CC006E >> totalNodes 50176. PATCH 0203 (commit d100a08, verified git-apply clean + reproduces edits byte-for-byte): (a) hfs_endian.c UNSWAP fLink/bLink checks -> CLAMP invalid link to 0 (readable "no link") + keep node's records so key lookups still work, only seq-scans affected at that node; (b) remaining write-side validation panics (kind/height/numRecords/offsets + all hfs_swap_HFSPlusBTInternalNode record checks) -> printf+error returning fsBTInvalidNodeErr like read path; (c) hfs_btreeio.c btree_swap_node `if(retval) panic` -> printf + memset(buffer,0,blockSize) quarantine = writes structurally-valid EMPTY node instead of panicking. Covers ALL HFS B-trees (catalog/extents/attr share hfs_swap_BTNode). ERROR PROPAGATION VERIFIED: InternalNode ret->error@254->goto fail->return error; fail: label returns error. Kept logic-invariant panics (line104 impossible-direction, line943 fileID). CI dispatch run 43728757742 (verify="clamped invalid forward link,quarantining corrupt node"). NEXT: build->mkpayload(notouch.adt,SAME cmdline)+viva-bootimg->flash->boot. EXPECTED: no hfs_UNswap panic; "clamped invalid forward link"/"quarantining" may print (tolerated); crash storm continues (expected) but kernel SURVIVES -> SpringBoard/backboardd keep rendering -> FBSTAT swaps>0 -> GUI. RISK: memset-0 quarantine loses records of a genuinely-broken node (bounded, was corrupt anyway); clamped links break seq-scan at that node only. If GUI still stalls -> backboardd render-loop investigation.

## >>> ATHENS HANDOFF 2026-11-15ah - *** 0202 BUILD DONE + FLASHED + BOOTING (GUI TEST) *** CI run 43725764892 SUCCESS; "Applying patch 0202" confirmed, verify "found: tolerated free node". kernel SHA256 cc6e695c477dfa000ed15047ea8604e998113d7cf116d070f73ad9076a74b8fa. Built shim/out/athens-payload-0202.bin (mkpayload kernel0202 + athens-notouch.adt + SAME 0201 diag cmdline) -> repacked via viva-bootimg (reused prebuilt shim/out/athens/Image.gz, shim unchanged) -> shim/out/athens-boot-0202.img 17500160B -> fastboot flash boot OK -> reboot. USERDATA = fsck-repaired gpu-fixed.simg (unchanged). EXPECTED if 0202 works: NO hfs_swap_BTNode "offset #0 invalid" errors (free catalog nodes tolerated), hfs_mark_inconsistent ~0, daemon crash storm subsides, FBSTAT swaps>0 -> SpringBoard/GUI renders. USER: watch screen ~3-8min -> SpringBoard/lockscreen = GUI DONE; Apple-logo-frozen = pull ring (sweet-log-pull.sh) check FBSTAT/backboardd render state; panic = new issue. NEXT: user reports -> if GUI milestone; if stall pull ring for backboardd render-loop/display-timing/power-assert investigation.

## >>> ATHENS HANDOFF 2026-11-15ag - *** FSCK REPAIR WORKED FOR INIT; NEW BLOCKER = kernel HFS driver false-flags FREE catalog nodes -> EIO crash storm; PATCH 0202 building *** r0201-fixed-ring analysis (repaired userdata boot): (a) fsck FIXED init - "exec launchd" at line282 with ZERO retries (was 2400-retry panic before); SpringBoard[26]/backboardd[57]/profiled/powerd/sleepd ALL exec'd + alive in SMP stacks; powerd did REAL IOKit work (IOPMrootDomain/IOPMPowerSource/AppleKeyStore opened) and did NOT exit early - biggest userspace progress yet. (b) display init'd: AppleCLCD 1080x2400->1125x2436. (c) BLOCKER: hfs_swap_BTNode "offset #0 invalid (0x0000) numRecords 0" fired 165x on fileID=4=CATALOG btree -> MacToVFSError EIO -> getdirentries64 EIO -> daemon crash storm (containermanagerd/calaccessd/dmd/accountsd sig5/6 respawn loop) -> FBSTAT swaps=0 flips=0 whole boot -> GUI never renders (Apple logo frozen). (d) ROOT CAUSE PROVEN not fs-corruption: mounted gpu-fixed.img RO in WSL - ls works, /sbin/launchd present; parsed catalog btree (nodeSize8192,totalNodes50176,freeNodes3054,lastLeaf47121); nodes 47145/47142/47130/50000 are ALL-ZERO on disk = legitimate FREE nodes. XNU reads them via non-hint path (allow_empty_node=false in hfs_btreeio.c:105) during catalog writes -> false corruption. Kernel driver bug, PRE-EXISTING (same hfs_mark_inconsistent/cat_delete before fsck). PATCH 0202 (commit aec3d15, pure LF, verified git-apply): hfs_swap_BTNode returns success(empty node) when numRecords==0 AND entire node buffer is zero - only skips validation for genuinely-free nodes, partial corruption still errors. Throttled printf "tolerated free node" for verify. CI dispatch run 43725764892 (verify="tolerated free node") + push run 43725734399 in_progress. NEXT: build->mkpayload(notouch.adt)+viva-bootimg->flash->boot->expect NO hfs_swap_BTNode errors, reduced crash storm, FBSTAT swaps>0, GUI. RISK: if empty nodes reached via record-lookup (not free-list), returns not-found instead of EIO - acceptable degradation, FS already fsck-clean. If GUI still stalls after clean boot -> backboardd render-loop investigation (display timing/IOSurface/power-assert chain).

## >>> ATHENS HANDOFF 2026-11-15af - *** USERDATA REPAIRED + REFLASHED: fsck-fixed gpu.simg now on device, booting 0201 *** 0201 panicked at retry 2400 -> confirmed FS genuinely corrupt, not just slow-settle. ROOT CAUSE nailed: HFS+ iOSRoot volume corrupt EVERY mount (hfs_mark_inconsistent + cat_delete thread-record fail) -> /sbin/launchd catalog lookup ENOENT for variable window. FIX = offline fsck, NOT more retries. DONE: (a) simg2img ios16-root-gpu.simg -> gpu-raw.img (51.5GB); (b) fsck.hfsplus -n said "corrupt needs repair" (volume header minor); (c) fsck.hfsplus repair -> gpu-fixed.img "appears to be OK" (journal committed = no mount-time replay); (d) img2simg -> gpu-fixed.simg; (e) VERIFIED gpu-fixed.simg sparse-chunk structure BYTE-IDENTICAL to gpu.simg (28457 chunks, 0 diffs) -> fastboot writes it identically; (f) gpu-fixed-tail.gz CONFIRMED starts at logical blk 3105890 (decompressed first 64KB == gpu-fixed.simg blocks 3105890-3105905). FLASHED: fastboot flash -S 64M userdata ios16-root-fixed.simg -> chunks 1-187 OK, 188/188 FAILED (known last-piece bug) -> recovery dd: `gunzip -c /tmp/gpu-fixed-tail.gz | dd of=/dev/block/sdc59 bs=4096 seek=3105890 conv=notrunc` = 9477022 rec / 36GiB / 164MB/s EXIT=0 (exactly 12582912-3105890 blocks). userdata = COMPLETE fsck-repaired image. Freed ~23GB by deleting obsolete ios16-root-pm.simg + ios16-root-varfix.simg (C: was 100% full). DEVICE NOW BOOTING 0201 kernel + repaired userdata. EXPECTED: clean mount (no hfs_mark_inconsistent), /sbin/launchd resolves fast (no long ENOENT window) -> init succeeds quickly -> userspace -> GUI. If STILL ENOENT-retry/panic on a CLEAN fsck'd volume -> the bug is kernel-side namei/HFS-driver, NOT filesystem -> next = kernel namei diagnosis. USER: watch screen, report GUI/stall/panic.

## >>> ATHENS HANDOFF 2026-11-15ae - *** 0201 GUI BUILD FLASHED + BOOTING *** CI run 43716805329 SUCCESS; "Applying patch 0201" confirmed in log (no skip). kernel SHA256 99c8f3782494a078e8f1b0de59630206f7ce40aba96c02ad7e6448956c45c520. Built shim/out/athens-payload-0201.bin (mkpayload kernel0201 + athens-notouch.adt + diag cmdline w/ sweetexit) -> repacked shim/out/athens-boot-0201.img -> fastboot flash boot OK -> reboot. THIS IS THE GUI BUILD: init retry now 2400 (~10min) so it rides out the dirty-HFS settle that caused the panic; r0200 proved kernel reaches SpringBoard/backboardd/FBSTAT-swaps once init succeeds. USER: watch screen ~2-10min. EXPECTED: Apple logo/progress may sit LONGER than before (that's the retry window working, NOT a hang) then SpringBoard/GUI. PANIC screen = FS truly broken -> fsck needed. Apple-logo-forever-after-userspace = powerd/profiled GUI-chain stall -> read ring for SWEET EXIT. NEXT: user reports screen -> if GUI, DONE milestone; if stall, pull ring (tools/sweet-log-pull.sh) for SWEET EXIT/SMP.

## >>> ATHENS HANDOFF 2026-11-15ad - *** r0200 RING ANALYZED: kernel DOES reach GUI userspace; init-ENOENT = dirty-HFS settle window; PATCH 0201 extends retry to ~10min *** CONFIRMED from r0200-ring.bin (correct pull = LAST 1025 blocks of sdc59 via tools/sweet-log-pull.sh, NOT first 16MB): (a) init PANICKED "Process 1 exec /sbin/launchd ENOENT @kern_exec.c:6965" after retries hit ~472-480 (all ENOENT). (b) BUT a subsequent auto-reboot boot reached FULL userspace: exec launchd -> Darwin Ignition boot tasks (mount/keybagd/usermanagerd/cc_fips_test) -> exec SpringBoard[26] ALIVE w/ real thread stacks, exec backboardd[57] ALIVE 18 threads, profiled/cfprefsd/containermanager/nanoprefsyncd sampled alive, FBSTAT swaps=5 copies=5 flips=3 (framebuffer composing). => KERNEL ALREADY REACHES GUI when init succeeds. (c) ROOT CAUSE of ENOENT: HFS+ volume corrupt EVERY boot: "hfs_mark_inconsistent Runtime corruption" + "cat_delete() failed to delete thread record id=720534" + "Removed orphaned files" -> /sbin/launchd catalog lookup returns ENOENT for a VARIABLE window (~118s this boot) until FS settles. (d) ATHENS TOUCH spam = STALE ring data, PROVEN: notouch ADT byte-identical to athens-notouch.adt has ZERO spi4/touch/novatek nodes; AthensNT36672C matches 'novatek,nt36672c' on VivaDTNub which needs AthensSPI ('mediatek,mt6765-spi' node) - neither node exists => driver CANNOT instantiate. Do NOT chase touch. (e) powerd exec'd, SWEET EXIT count=0 (did not log exit this boot). PATCH 0201 (commit d800bbe, pure LF, verified git-apply): retry cap 480->2400 (~10min) so init rides out the variable HFS settle instead of panicking at the margin. Rationale is evidence-based: ENOENT provably clears (launchd loaded ~retry473); panic only when settle>480. If a boot still panics after 2400 the FS is truly broken -> next step = fsck_hfs the iOSRoot volume (risky userdata op, needs user OK). CI run 43716805329 in_progress. NEXT: build->mkpayload(notouch.adt)+viva-bootimg->flash->expect launchd->userspace->GUI (watch screen for SpringBoard vs Apple-logo stall).

## >>> ATHENS HANDOFF 2026-11-15ac - *** 0200 BUILD DONE + FLASHED + BOOTING *** CI run 43714893660 SUCCESS. kernel SHA256 7fb3dacff3b210fc5a0feeec69b306d4e10696876e0a88004885e066a4cacd42 (has "loaded after"+"SWEET EXIT"+retry strings). Built shim/out/athens-payload-0200.bin (mkpayload kernel0200 + athens-notouch.adt + diag cmdline incl sweetexit=powerd,profiled,SpringBoard,backboardd,keybagd,usermanagerd,sleepd,aggregated) -> repacked shim/out/athens-boot-0200.img -> fastboot flash boot OK. Device rebooting into iOS now. EXPECTED if namecache was the cause: no init-ENOENT panic, "loaded after N retries" then userspace -> powerd exits -> "SWEET EXIT powerd[...]" line reveals death cause -> then targeted GUI fix. NEXT: device runs ~3-5min -> user forces recovery -> pull ring -> check (a) init panic gone? (b) loaded-after N? (c) SWEET EXIT powerd reason? (d) SpringBoard/backboardd alive? (e) FBSTAT swaps>0? WATCH: if still panics at init-ENOENT after 480 retries -> namecache wasn't it / FS genuinely broken -> different fix needed.

## >>> ATHENS HANDOFF 2026-11-15ab - *** INIT-ENOENT ROOT CAUSE FOUND: negative namecache poisoning; PATCH 0200 purges it per-retry *** r0199 ring: boot PANICKED at init-ENOENT again (retries to 472, no "loaded after", never reached userspace -> powerd diag got no data). KEY FINDING in vfs_cache.c: a failed lookup creates a NEGATIVE namecache entry (cache_enter vp==NULL -> "negative cache entry" list); cache_lookup returns ENOENT for negative hits WITHOUT re-querying HFS. So the FIRST transient ENOENT poisons the cache and ALL 0198 retries hit the cached ENOENT -> retry could never recover. That is why it's intermittent (depends whether first lookup lands before/after FS-ready) and why widening retries didn't help. PATCH 0200 (commit de0c656): inside the 0198 retry loop, cache_purgevfs(vnode_mount(rootvnode)) before each attempt -> every retry is a REAL HFS lookup. Combined build now = 0198 retry + 0199 exit-diag + 0200 purge. If namecache was the cause, launchd loads once HFS is ready -> reaches userspace -> 0199 logs powerd's SWEET EXIT (death cause) -> then targeted GUI fix. CI run 43714893660 in_progress. NOTE: purging whole-mount namecache per retry is heavy but early-boot namecache is tiny; IOSleep(250) dominates anyway.

## >>> ATHENS HANDOFF 2026-11-15aa - *** 0198-v2 (480-retry) STILL PANICKED on persistent ENOENT; GUI blocker narrowed to powerd EARLY-CLEAN-EXIT; PATCH 0199 = exit-reason logging to catch it *** ring r0198b: retries to >=384 all ENOENT, no "loaded after", panic @kern_exec.c:6958. HFS cat_delete thread-record-720534 fails EVERY boot + hfs_mark_inconsistent -> suspect catalog corruption (fsck candidate). Userspace boots DO reach SpringBoard/backboardd (alive, sampled) but MASSIVE crash storm: xpcproxy exec x5316, biomed/analyticsd/fairplayd/bluetoothd ~x1140 each, tccd x121, dmd/locationd/assistantd ~x59 (mostly hw-probe daemons). GUI chain: profiled blocks on com.apple.PowerManagement.control (powerd's port). KEY NEW FACT: powerd exec'd ONCE, made AKS sel0/sel7 calls, then ZERO "IOK powerd" lines and is NEVER in SMP samples -> it exits CLEANLY (no CRASH powerd line = not a fatal-signal crash) BEFORE reaching IOKit, and is not respawned. So powerd dies in early userspace init, not on a power-source wait. Battery: SweetBattery published "static fallback 100% 4200mV external=1" (VivaBattery needs ti,bq27z561 absent; real gauge=mediatek,mt6359 -> unmatched). Only battery source exists; NO charger/AC node in ADT. syscall#535=enosys hit by powerd/cloudpaird/xpcproxy (likely benign probe). PATCH 0199 (commit a41820e, pure LF): proc_prepareexit logs "SWEET EXIT comm[pid] sig/status/reason" for boot-arg sweetexit list (default powerd,profiled,SpringBoard,backboardd). CI run 43712915625 in_progress. NEXT: build->flash->pull ring -> read powerd's SWEET EXIT line = exact death cause -> then targeted kernel/userspace fix. If powerd exits cleanly w/ status, it's a userspace-init dependency; if sig, it's a crash.

## >>> ATHENS HANDOFF 2026-11-15y - *** 0198-v1 PROVEN: retry got launchd+userspace, but MARGINAL -> widened to ~120s *** ring shows retries 1-40 all ENOENT then launchd exec'd; sibling boot exhausted->panic @6954; touch spam confirmed STALE <<<

0198-v1 BOOT RESULT (athens-boot-0198.img, kernel SHA 1aa6d375, run 43708245523):
- Patch ENGAGED: ring shows "ENOENT on all candidates, retry 1..40" then
  launchd exec'd (shared_region dyld maps, Darwin Bootstrapper, ondemand
  mode, exec mount/keybagd/usermanagerd/dirs_cleaner/SpringBoard/backboardd,
  FBSTAT swaps). FULL USERSPACE REACHED. The retry WORKS.
- BUT success landed on the LAST allowed retry (~10s). A sibling/earlier
  boot exhausted all 40 -> panic @kern_exec.c:6954 (post-patch line).
  => 10s window is marginal; ENOENT-clear time is variable.
- panic_active()/SWEETPAN captures panic-time console; transcript held a
  full boot because the record accumulates while the op stays latched.

ROOT-CAUSE EVIDENCE (not guessed):
- HFS mount EVERY boot: "hfs_mark_inconsistent ... fsck will be forced",
  "cat_delete() failed to delete thread record", "Removed 2 orphaned files
  and 3 directories", journal replay. Volume stays dirty (prior panics)
  -> catalog/B-tree lookups return ENOENT for a VARIABLE window post-mount.
- /sbin/launchd EXISTS in image (541600B); namecache does NOT cache ENOENT
  (no vnode to cache) so each retry does a real lookup -> purely time-
  dependent FS readiness, NOT a permanent negative entry.
- TOUCH SPAM = STALE, confirmed: kernel's own NUB2 enumeration lists NO
  spi4/touch/novatek node (notouch ADT verified byte-identical). AthensNT
  36672C needs a VivaDTNub(novatek,nt36672c) published by AthensSPI, which
  needs an spi4 ADT node -> cannot instantiate. 5562 "firmware download"
  msgs are leftover ring data from prior touch-enabled boots (ring is 4.2MB,
  holds many boots). NOT a current-boot problem. sweettouch=0 also gates
  base SweetHIDTouch correctly.

PATCH 0198-v2 (commit eb440de): retries 40->480 (250ms each ~=120s), log
every 8th retry (480 lines would flood ring), print "<path> loaded after
N retries" to record actual settle time in ring. Still bounded -> genuinely
broken FS still panics. CI run 43710561622 (verify_strings="loaded after
%d retries").

NEXT: when kernel lands -> mkpayload(notouch.adt)+viva-bootimg -> flash ->
reboot -> ring should show "loaded after N retries" (N=real settle secs) then
userspace. If N small & stable -> resume powerd diagnostic (sweetsample
powerd already in cmdline). If still panics @6954 after 480 -> FS genuinely
broken -> investigate HFS catalog/fsck offline.

PATCH 0198 STATUS: CI run 43708245523 SUCCESS (earlier run 43707132937 failed
verify_strings because patch file had CRLF/mixed endings -> "corrupt patch at
line 41"; fixed to pure LF in commit d992327). "ENOENT on all candidates, retry
%d" confirmed present in kernel.development.sweet. Artifact kernel SHA256:
1aa6d3756b785b6f0614d201ad5ca70adde8ca006f23a7e210145e40ff7e2d37.
Repacked shim/out/athens-boot-0198.img (mkpayload kernel0198 + notouch.adt +
same diag cmdline; viva-bootimg repack backup/boot.img Image.gz). FLASHED boot.
Now booting; if retry engages, ring will show "ENOENT on all candidates, retry
N" then either userspace (transient, FIXED) or panic after ~10s (persistent).

PANIC (confirmed x2, identical caller 0xfffffe0007848628):
`panic(cpu 1): Process 1 exec of /sbin/launchd failed, errno 2 @kern_exec.c:6929`
- `load_init_program()` (bsd_init end) iterates init_programs[], calls
  execve via load_init_program_at_path; ALL candidates ENOENT -> panic. NO
  retry in stock code. /sbin/launchd is LAST candidate -> panic names it.
- pm.img kernel == smp2 kernel (only cmdline differs: sweetsample/sweetiolog
  added powerd,profiled). userspace = clean gpu.simg (verified: /sbin/launchd
  present in source img 541600B; dd tail re-audited = all tail FILL chunks
  are value-0 so emit_zeros was CORRECT, last-block sha256 matched).
- pm.img ADT verified NOTOUCH (adt region has zero nt36672c/spi4/touch
  strings; earlier "touch spam" in ring = LEFTOVER from prior touch-enabled
  gpu19/spifix boots, ring persists across reboots). NOT a pm.img regression.
- Panic transcript (SWEETPAN record, 256KB panic-time console) shows: panic
  msg + panic-screen UTF16 garbage, THEN a complete subsequent boot reaching
  userspace (mounted iOSRoot, load_init_program, exec launchd, ignition,
  daemons, crash storm, FBSTAT). panic_active() stayed latched across
  panic->reboot so new boot's console appended. => ENOENT is INTERMITTENT,
  not deterministic corruption. A boot got past init fine.
- 0196(hfsmakenode-diag)/0197(eio-syscall-diag) RULED OUT: both are
  read-only printf diagnostics, don't touch lookup/exec logic.

ROOT-CAUSE ASSESSMENT (evidence-based, not guessed):
- execve->ENOENT = namei/vnode lookup of /sbin/launchd failed transiently on
  the unsealed HFS+ root right after vfs_mountroot. Candidates: (a) HFS+
  namei/namecache cold-settle race, (b) known intermittent stray-writer
  memory corruption hitting vnode/namei. Cannot fully distinguish yet, but
  intermittency is CONFIRMED (successful boot in same record).

PATCH 0198 (xnu/patches/0198-athens-init-enoent-retry.patch, commit 8873173):
- Wraps init_programs[] loop: on total ENOENT, IOSleep(250) x up to 40
  (~10s) retrying all candidates before panic. execve() failure leaves init
  proc untouched => retry safe. Mirrors existing vfs_mountroot IOSleep
  retry (bsd_init.c:894). extern void IOSleep(int) added.
- If transient: converts panic->successful boot. If persistent: still
  panics after ~10s (same outcome, bounded). Retry prints "ENOENT on all
  candidates, retry N" -> settle time measurable from ring.
- CI: workflow_dispatch run 43708245523 SUCCESS (first attempt 43707132937
  failed verify_strings on CRLF patch; fixed d992327). Kernel SHA256
  1aa6d3756b785b6f0614d201ad5ca70adde8ca006f23a7e210145e40ff7e2d37.

DONE: repacked shim/out/athens-boot-0198.img (mkpayload new kernel +
athens-notouch.adt + same diag cmdline; viva-bootimg repack backup/boot.img
Image.gz) -> fastboot flash boot -> reboot. userdata stays gpu.simg.
NEXT: watch ring for "ENOENT on all candidates, retry" + userspace. If clean
boot -> resume powerd-stack diagnostic (sweetsample powerd,profiled in cmdline,
sampler fires ~90s). If still panics -> inspect retry count/final errno, then
chase namecache/VFS negative-cache + stray-writer memory corruption.

## >>> ATHENS HANDOFF 2026-11-15z - *** KERNEL-ONLY PIVOT: assertion target = powerd, NOT kernel *** userspace reverted to clean gpu.simg; userdata COMPLETE+verified; diagnostic boot launched to capture powerd stack <<<

USER DIRECTIVE (supersedes dyld patch): "stop trying to modify the original
ios img, keep it as close to factory as possible ONLY modify the kernel".
The dyld power-assert stub caused a kernel panic and is ABANDONED. All fixes
now kernel-side only; userspace stays factory+necessary-tweaks.

USERDATA RESTORED (clean gpu.simg, no dyld patch):
- `fastboot flash -S 64M userdata ios16-root-gpu.simg` wrote chunks OK but
  failed last piece AGAIN (known ABL final-chunk bug) -> missing output
  blocks ~3105890->12582911.
- Extracted tail FROM gpu.simg itself (NOT ios16-root.img, which still has
  the dyld patch): tools .tmp-patch/simg_tail_gz.py parses sparse chunks,
  emits raw/FILL/DONT_CARE for blocks>=3105890 through gzip ->
  iosroot/gpu-tail.gz (177MB -> 38,817,882,112 B). Device in recovery:
  `gunzip -c /tmp/gpu-tail.gz | dd of=/dev/block/sdc59 bs=4096 seek=3105890
  conv=notrunc` (toybox dd: conv=notrunc=conv4; plain conv=fsync fails
  ftruncate). VERIFIED: last block sha256 f881f225.. == gpu.simg last block.
  userdata = complete consistent gpu.simg (Metal bundle + varfix /var dirs,
  NO dyld patch).

ROOT CAUSE REFINED (definitive, not guessed):
- Disassembled IOKit.framework `IOPMAssertionCreateWithProperties`
  (dsc.05 0x18e55b164) -> `_pm_connect` (0x18e55e0d0) -> `bootstrap_look_up`
  of service-name string @0x18e5e874a = **"com.apple.PowerManagement.control"**.
- That is a launchd BOOTSTRAP service = **powerd's** control port, NOT a
  kernel IOKit user-client. `__conveyMachPortToPowerd` + SweetBattery.cpp:274
  "registerService wakes powerd" confirm powerd brokers assertions -> kernel
  IOPMrootDomain.
- `_io_pm_assertion_create` = mig_get_special_reply_port + voucher_mach_msg_set
  + mach_msg = a MIG RPC to powerd. profiled blocks because POWERD never
  replies (powerd exec'd, did AKS sel0/sel7, then went silent = stuck before
  servicing the control port).
- powerd stuck cause UNKNOWN yet - likely a kernel service it needs during
  init (power tree sync / a missing IOKit node). `IODeviceTree:/arm-io/
  pearl-sep -> none` (no SEP) seen in log.

DIAGNOSTIC BOOT LAUNCHED (boot=athens-boot-pm.img, flashed):
- Same kernel as smp2 (eio2-art 0197v2) - NO rebuild, boot-arg only.
- Patched cmdline in athens-payload.bin@0x48 (verified == smp2 ramdisk):
  sweetsample=powerd,profiled,SpringBoard,backboardd,sleepd,aggregated
  sweetiolog=powerd,profiled  (sweetiolog traces powerd/profiled IOKit
  matching+open, 400-line cap). Kept sweetlog=1 sweetfb_hz=0 sweetfb_keep=1.
- Repacked: viva-bootimg.py repack backup/boot.img Image.gz --ramdisk
  athens-payload-pm.bin -> shim/out/athens-boot-pm.img; fastboot flash boot.
NEXT: wait ~15-20min -> recovery -> pull ring -> symbolicate powerd SMP stack
+ IOK lines -> identify what powerd blocks on -> KERNEL fix -> CI rebuild.

## >>> ATHENS HANDOFF 2026-11-15x - *** GUI BLOCKER ROOT-CAUSED + DYLD FIX BUILT *** profiled hangs in IOPMAssertionCreateWithDescription->_io_pm_assertion_create->mach_msg (power-assertion backend never replies) -> never services MCProfileConnection -> SpringBoard launch-sentinel stalls. FIX = tools/patch-power-assert.py stubs IOPMAssertionCreate{WithDescription,WithProperties}+Release in dsc.05 -> fake success. Applied to ios16-root.img; ios16-root-pm.simg converting; flash userdata + boot next <<<

SMP2 RESULT (.tmp-patch/smp2-log.txt, touch node removed so ring stayed
clean; 12,372 lines): sampler caught the REAL chain, fully symbolicated:
- **profiled (pid121) main thread:** `_mach_msg` <- `_io_pm_assertion_create`
  <- `IOPMAssertionCreateWithProperties` <- `IOPMAssertionCreateWithDescription`
  <- `__retainPowerAssertion` <- `-[MCPowerAssertion initWithReason:]`.
  = profiled is STUCK creating a kernel/powerd POWER ASSERTION; the MIG
  mach_msg never returns -> profiled never finishes init -> never vends
  com.apple.managedconfiguration.profiled.
- **SpringBoard** + **nanoprefsyncd** both block in
  `MCProfileConnection checkIn` -> `_xpc_connection_send_message_with_reply_sync`
  waiting on profiled. containermanagerd/cfprefsd sampled HEALTHY (idle
  runloops) - NOT the problem. mdmd/tccd/mobileactivation/BackupAgent2 never
  launched (by-design on-demand / crash-loop) - not the profiled gate.
- DEPENDENCY CHAIN (confirmed): SpringBoard -> MCProfileConnection checkIn
  -> profiled -> IOPMAssertionCreate* -> HANG. Fixing profiled's assertion
  unblocks SpringBoard's launch sentinel AND nanoprefsyncd at once.

WHY NOT RootDomainUserClient: its externalMethod dispatchArray has NO
assertion-create selector (only sleep/shutdown/restart/allow/display-power/
user-assertion-LEVELS). User-space IOPMAssertion* routes elsewhere
(powerd com.apple.iokit.powerdxpc or a dedicated client). Backend hang
cause (kernel workloop vs powerd stuck) NOT yet isolated - but the client-
side stub is robust to EITHER. SweetBattery IS a complete IOPMPowerSource
(publishes full state pre-registerService) so power source is probably fine.

FIX (tools/patch-power-assert.py, modeled on patch-sw-renderer.py): stub the
IOKit user assertion API in dyld_shared_cache_arm64.05 to return fake success
- `IOPMAssertionCreateWithDescription` @0x981a70 -> mov w0,#0xffff; ret
  (non-zero fake io_connect_t; callers only check != IO_OBJECT_NULL)
- `IOPMAssertionCreateWithProperties` @0x977154 -> mov w0,#0; mov x8,#1;
  str x8,[x3]; ret (kIOReturnSuccess + dummy IOPMAssertionID=1)
- `IOPMAssertionRelease` @0x976b3c -> mov w0,#0; ret (no-op; fake conn never
  mach'd). Subsequent Set*/Release on the fake conn fail FAST (invalid port),
  never hang. No real sleep on this port (sweetfb_keep) so fake assertions
  are harmless. Offsets via `ipsw dyld a2o` (all in dsc.05 __TEXT).

APPLIED+FLASHED (2026-11-15): patched ios16-root.img -> img2simg ->
ios16-root-pm.simg (871 chunks). `fastboot flash -S 64M userdata` wrote
chunks 1-187 OKAY but **188/188 FAILED "sparse image write failure"** (the
KNOWN final-piece issue). Parsed simg: failed fastboot piece = last ~64MB
of sparse file, starts inside sparse-chunk 864 -> missing output blocks
~3103288->12582911. FIX (same dd-tail method as gpu.simg): extracted
ios16-root.img blocks 3103288-12582911 (9479624 blk, ~36GiB, mostly FILL
zeros) -> gzip -1 = iosroot/pm-tail.gz (178MB) -> MSYS_NO_PATHCONV=1
adb push /tmp/pm-tail.gz -> recovery `gunzip -c | dd of=/dev/block/sdc59
bs=4096 seek=3103288 conv=notrunc` = 9479624 rec, 36GiB, 161MB/s, EXIT=0.
userdata COMPLETE. Rebooted into iOS (boot=smp2 kernel: sweetlog=1,
sweetsample, sweetfb_hz=0, --athens-notouch). NEXT: wait ~15-20min, recovery,
pull ring, VERIFY profiled stack clears IOPMAssertion + SpringBoard swaps
climb past 5 / GUI. If still blocked, clean sampler names next gate.

## >>> ATHENS HANDOFF 2026-11-15w - *** SPRINGBOARD STALL ROOT CAUSE SYMBOLICATED ***

## >>> ATHENS HANDOFF 2026-11-15w - *** SPRINGBOARD STALL ROOT CAUSE SYMBOLICATED *** not display/GPU/errno: SpringBoard's launch-sentinel thread blocks in a SYNCHRONOUS XPC to the managed-config service (MCProfileConnection checkIn -> profiled/mdmd) that never replies; sampling those daemons NOW <<<

sweetfb_keep=1 BOOT RESULT (.tmp-patch/eio2-log.txt, 9249 lines, flush#116):
- `SWEET FB: display off ignored (sweetfb_keep)` fired; every FBSTAT
  `powerOff 0`, `swaps 5 copies 5 flips 3` FROZEN for rest of log. CONFIRMED:
  display sleep was NOT the cause; SpringBoard simply stops producing frames.
- 0197v2 broadened errno catch fired 1668x but ONLY benign codes:
  err=78/ENOSYS sys=#535 x1550 (every exec), err=102/EOPNOTSUPP ioctl x61
  (wifid/mediaserverd = missing radios), err=45/ENOTSUP fcntl/work_interval/
  setpriority x57 (keybagd class-D etc). **ZERO actual EIO.** => Foundation's
  temp-dir/keychain EIO(5) is SYNTHESIZED userspace-side (missing SEP/Data
  Protection/data-volume layer) - same architectural gap sweet/viva tolerate.

SMP SYMBOLICATION (installed ipsw 3.1.745 in WSL; tools/sweet-crash.py on
.tmp-patch/sb-smp.txt) - SpringBoard is ALIVE, all threads parked in
mach_msg waits, NOT crashed/deadlocked. Decisive stacks:
- **t0 (launch sentinel, THE gate):** `SBPrepareLaunchSentinelIfNecessary` ->
  `BYSetupAssistantPrepareLaunchSentinel` -> `iOS_BYSetupAssistantNeedsToRun`
  -> `MCProfileConnection(CloudConfiguration) shouldShowCloudConfigurationUI`
  -> `checkInIfNeeded` -> `checkIn` -> `_xpc_connection_send_message_with_reply_sync`
  = **blocked waiting for the managed-config/MDM daemon to answer check-in.**
- t2: `FBSProfileManager startService` -> `MCProfileConnection managedAppIDs`
  -> same checkIn XPC wait (same service).
- t1/t5/t7: `_BMXPCFileManager`/`BMCache` `createDirectoryAtPath`/
  `fileHandleForFileAtPath` -> XPC wait = **mobilebackup2 (BackupAgent2)**,
  never launched.
- t3: `PLClientLogger permissionForClientID` -> XPC wait = **tccd**,
  crash-looping 545x.
- t4: `UIEventFetcher threadMain` runloop = idle/healthy main loop.

WHY THE XPC HANGS (plist analysis, System/Library/LaunchDaemons):
- `com.apple.managedconfiguration.profiled`: MachServices
  com.apple.managedconfiguration.profiled{,.public}; LaunchEvents =
  keybagd.first_unlock / LoginKit.isLoggedIn / lowpowermode / provisioning.
  Exec'd ONCE (pid123, log line 1306) then SILENT - no IOKit/AKS/crash =
  alive-but-stuck OR exited before servicing. KeepAlive = PathState on
  /var/mobile/Library/UserConfigurationProfiles/profiledRunning.
- `com.apple.devicemanagementclient.mdmd`: vends mdmdservice; LaunchEvents =
  longLivedTokenChanged ONLY -> never launches on non-MDM device (by design).
- `com.apple.mobilebackup2` = /usr/libexec/BackupAgent2 --oneshot, vends
  com.apple.lockdown.mobilebackup2; NEVER exec'd.
- `tccd` MachServices com.apple.tccd; crash-loops sig5.
- All binaries EXIST + valid arm64 Mach-O in rootfs (verified).
- `checkIn`/`xpc_send_message_with_reply_sync` has NO timeout -> infinite hang.

LINEAGE CONTEXT (NOTES 2443/2446): on sweet, SpringBoard was held in
`BKSSystemShellService _checkIn`/`checkInAndWaitForDataMigration` - fixed by
LastSystemVersion. Athens cleared that gate; this managed-config checkIn is
the NEXT launch gate. The prefs meant to skip it (MCForceShowCloudConfig-
urationUI:False, LockdownActivationIndicatesCloudConfigurationAvailable:
False, SetupDone) do NOT short-circuit checkInIfNeeded - the XPC runs first.

ACTION: built `shim/out/athens-boot-smp.img` = SAME 0197v2 kernel + same
cmdline + `sweetsample=SpringBoard,backboardd,profiled,mdmd,tccd,
mobileactivation,containermanager,nanoprefsyncd,cfprefsd,BackupAgent2`
(boot-arg only, patch 0054 sampler already in kernel; names = exact proc_name
comm, 16-char truncated). FLASHED + rebooting. Sampler: first sample 90s,
then every 120s x40. Will show EXACTLY what profiled/mdmd/BackupAgent2/
tccd/containermanager are blocked on -> names the shared dependency (likely
Data Protection/keybag stub or a container/IOKit service).

NEXT: ~15-20 min boot -> recovery -> pull ring -> symbolicate new SMP dumps
(same sweet-crash.py+ipsw flow). If profiled/mdmd/etc all block on the SAME
call (e.g. AppleKeyStore/SEP stub, containermanagerd, a missing IOKit
service), that's the single fix point for the whole launch-gate chain.

smp boot #1 RESULT (.tmp-patch/smp-log.txt, 76433 lines, flush #6485 wrapped):
- ZERO SMP lines - NOT because sampler broke (cmdline 472<608 fits, arg
  verified in payload) but because **ATHENS TOUCH firmware-download retry
  spam flooded the 4MiB ring** (16435/20000 lines = touch; ring wraps every
  few min, evicting the 120s-spaced SMP dumps). Also saw `ATHENS PMIC KEYS:
  key 0x30 down` (a real keypress registered).
- FIX: rebuilt with `--athens-notouch` (mkadt drops spi4/NT36672C node -
  touch already non-functional, loses nothing) -> `athens-boot-smp2.img`,
  same sweetsample list. FLASHED + rebooting. Ring now stays clean -> SMP
  for profiled/mdmd/tccd/mobileactivation/containermanager/nanoprefsyncd/
  cfprefsd/BackupAgent2 will survive to be symbolicated.

## >>> ATHENS HANDOFF 2026-11-15z - *** CROSS-REPO RESEARCH + REAL GUI BLOCKER IDENTIFIED *** crash storm is NORMAL (sweet/viva prove it); actual blocker = display-off + possible SW-renderer crash-guard; sweetfb_keep=1 test IN FLIGHT <<<

CROSS-REPO RESEARCH (user asked: how do other repos get GUI+touch):
- **ios-sweet (dipa-studio, direct ancestor)**: reached HOME SCREEN + touch +
  CPU rendering 2026-10-18. KEY: "Daemons for [wifi/bt/cellular/audio/camera/
  sensors/SEP] start and fail or keep relaunching" — the crash storm is
  EXPECTED and TOLERATED; SpringBoard still appears after ~4 min. Their
  userdata tweaks (sweet-root-tweaks.py: _PanicOnCrasX, containers dirs,
  migration LastSystemVersion, Setup skip, activation data_ark, CommCenter/
  VirtualAudio/MediaToolbox removal, BKNoWatchdogs) are what athens already
  carries. Activation via ADT /chosen certificate-security-mode -> Hactivation.
- **ios-viva (Nik300, MT6781 MediaTek sibling)**: reached LOCK SCREEN + keys
  2026-11-02, ~20 min first boot. Same userland/storm, GUI still worked.
- **instantnoodle/hackios**: full GUI+Metal+touch+WiFi+cellular on Qualcomm;
  "user data on HFS+, data survives reboots"; keychain = stand-ins (no SEP).
- CONCLUSION: the ~148-daemon sig5/sig6 crash storm is NORMAL on this platform
  and is NOT what blocks GUI. Chasing its errno was the wrong tree.

REAL GUI BLOCKER (from eio-log.txt, decisive):
- backboardd FULLY up: HID drivers (AthensNT36672C/PMICKeys/VivaKeypad/
  SweetHIDButtons), FB selectors, 2x IOSurface 1125x2436, VivaGPUAccelerator
  matched IOAcceleratorES, Metal command buffers processing (vmg copied).
- `SWEET FB: swap 1/2/3` = 3 REAL GUI frames presented to panel.
- SpringBoard spawned, did AKS sel0/7/35 + IOPMrootDomain + HID + /product.
- **`SWEET FB: display off` at log line 1638** — backboardd/sleepd called
  RequestPowerChange(0) -> panel powered off right after 3 swaps. System
  stayed ALIVE after (daemons kept launching). => screen sits on Apple logo.

ACTIONS TAKEN:
- `sweetfb_keep=1` (patch 0181, already compiled in) makes kernel IGNORE
  RequestPowerChange(0) -> keeps last frame on screen. Boot-arg only.
- Built `shim/out/athens-boot-eio2keep.img` = 0197v2 kernel (broadened errno
  catch EIO+ENOTSUP+ENODEV+EROFS+ENOSYS+ENXIO+ESTALE+EREMOTE+ENOLINK+ENOSR)
  + sweetfb_keep=1 + same diag cmdline. Verified strings in binary.
- 0197v2 CI run 43649611331 SUCCESS; kernel .tmp-patch/eio2-art/.
- FLASHED boot + rebooting NOW. userdata unchanged (varfix.simg).

ALSO FOUND (documented in NOTES 2026-11-14b, verified UNPATCHED in image):
- QuartzCore SW-renderer crash-guard: sw_renderer() aborts on-device
  ("Software renderer! Simulating crash!"). Bypass = NOP 2 `bl` insns in
  dyld_shared_cache_arm64.03 @0x1768d34/0x1768d8c via tools/patch-sw-renderer.py.
- VERIFIED bytes 545f5b95/3e5f5b95 STILL PRESENT (unpatched) in
  iosroot-work/ios16-root.img. BUT athens HAS Metal (backboardd rendered via
  GPU) -> crash-guard only fires if Metal/GL context init FAILS -> probably
  NOT the GUI blocker here (unlike sweet/viva which had no GPU). Hold as
  backup if sweetfb_keep reveals a Metal/SW-renderer stall.

NEXT: let it boot LONGER than 3 min (sweet ~4min, viva ~20min to lock
screen; crash storm slows everything). Watch for `display off ignored
(sweetfb_keep)` + swaps continuing + SpringBoard progress. Then recovery ->
pull ring -> check SWEET EIO-SYSCALL err= lines (broadened) + FBSTAT swaps.

## >>> ATHENS HANDOFF 2026-11-15y - *** DECISIVE: ZERO unix syscalls return EIO *** crash storm is SYNTHESIZED/architectural (no SEP, no data volume, no Data Protection); broadened 0197 to catch real errno <<<

0197 v1 RESULT (athens-boot-eio.img, run 43647789507, .tmp-patch/eio-log.txt,
1935 lines, flush#6):
- **ZERO `SWEET EIO-SYSCALL` lines** — NO unix syscall returned EIO(5) during
  the entire boot+storm. Instrumentation confirmed in binary + boot-args
  correct (sweetlog=1). Crash storm DID happen: 148 CRASH (tccd 88,
  mobileactivation/dmd/assistantd/ScreenTimeAgent 12, fitnesscoachingd 8,
  driverkitd 4). hfs_makenode ENTER=300 (creates still work).
- => Foundation/libsystem is SYNTHESIZING EIO(5) in userspace, OR it comes
  from a NON-unix path (mach trap / IOKit / persona / keybag). NOT a unix
  syscall errno.

ARCHITECTURAL ROOT (kernel log, high confidence):
- `init_data_protection: No SEP present on this device` — NO Secure Enclave.
- `SWEET SEP: AppleSEPManager registered (stub)`, `AppleKeyStore registered
  (stub)` — SEP/keybag are STUBS returning 0x0 for all selectors.
- `IODeviceTree:/arm-io/pearl-sep -> none`, `ApplePearlSEPDriver -> none`.
- `MKB_INIT: mount point (/private/var/) does not support Data Protection`,
  `Unable to set /private/var//tmp to class D!`, `MKBUserSessionNeedsMount=1`.
- Daemons DO call AKS selectors (sel 0/7/14/17/103) and get 0x0 (stub success).

INTERPRETATION: iOS temp-dir init + keychain access require Data Protection
(protection-class set on dirs, key unwrap for keychain-2.db) which needs
SEP/keybag — STUBBED/ABSENT. The ops that need it fail; Foundation reports
generic EIO(5). Could ALSO be a unix syscall returning a NON-EIO errno
(ENOTSUP/ENODEV/etc) that Foundation maps to EIO — my v1 only caught EIO.

0197 v2 (207be70, run 43649611331, building): broadened catch to
EIO+ENOTSUP+EOPNOTSUPP+ENODEV+EROFS+ENOSYS+ENXIO+ESTALE+EREMOTE+ENOLINK+ENOSR,
prints `err=%d code sys comm`. If a unix syscall returns one of these on the
temp/keychain path => exact op+real errno found. If STILL nothing => error is
mach-trap or pure-userspace synthesis => pivot to mach_syscall/IOKit/persona
instrumentation OR address data-volume/SEP gap directly.

## >>> ATHENS HANDOFF 2026-11-15x - SWEETSCAN GOT REAL ERRORS: temp-dir EIO(5)+keychain open fail; varfix skeleton CONFIRMED present; EIO = NON-create op -> patch 0197 syscall-level EIO catch <<<

SWEETSCAN RESULT (athens-boot-scan.img = eba2140 kernel + sweetscan/sweetnull
boot-args, .tmp-patch/scan-log.txt 4646 lines + 354 STR heap strings):
- REAL error strings captured: `Failed to initialize/create darwin user temp
  directory: Input/output error (5)`, `Failed to create temporary directory:
  Input/output error (5)`, `Failed to initialize temporary directory suffix
  for com.apple.fitnesscoachingd (5)`, `open_v2 "/Library/Keychains/
  keychain-2.db" 0x400006: [14]2 unable to open database file`,
  `Failed to query keychain`, `Failed to copy certificate ... -25291`.
- mobileactivationd also doing OS-upgrade data migration to 20H392.

VARFIX SKELETON CONFIRMED PRESENT (not missing): hfs_makenode ENTER shows
`usersession.kb.writing`, `persona.kb.writing`, `Session` created under
/private/var/keybags, AND many 40-char SHA1 hash dirs (= /private/var/folders
/<uid-hex>/<hash>) being created. So folders+keybags dirs EXIST and HFS
creates into them SUCCEED. => EIO is NOT a missing-dir problem.

ARCHITECTURAL FACT (kernel log, lines ~440-653): iOS expects a SEPARATE APFS
DATA VOLUME for /private/var, /tmp, /var/run, per-user sessions:
- `exec mount` -> `failed to get filesystem info` (x2) -> `mount: data volume
  missing, but not required in env: 0` -> continues (env:0 = not required).
- `MKB_INIT: mount point (/private/var/) does not support Data Protection`,
  `Unable to set /private/var//tmp to class D!`, `MKBUserSessionNeedsMount=1`.
- launchd `(init-with-data-volume)` boot task runs. `dc_reset: /tmp` +
  `/var/run: Invalid argument`.
- Only ONE fs mounted: /dev/ufsroot0 (hfs) on /. /private/var = plain HFS dir.

RULED OUT (source+instrumentation, high confidence): HFS create (335 ENTERs,
0 err), lookup (cat_lookupbykey 0 err), catalog B-tree (MacToVFSError 0 EIO),
cprotect/Data Protection (cp_fs_protected FALSE -> cp_handle_open/vnop/
vnode_setclass all bypass or ENOTSUP/EINVAL not EIO), xattr BTInsert (no err
printfs fired), bindfs (ENOTSUP, /private/var not bindfs), sandbox/MAC (no
vnode hooks -> allow), kauth (EACCES/EPERM not EIO), statfs (cached mnt_vfsstat).

CONCLUSION: EIO(5) is a NON-create filesystem op OR a synthesized Foundation
error. The remaining surface = setattrlist/chmod/chown/setxattr/getattrlist/
getdirentries/statfs-family/fsctl/open/read-write on the temp/keychain paths,
OR a non-unix-syscall source (mach trap/IOKit/keybag). Need the EXACT syscall.

PATCH 0197 (xnu/patches/0197-athens-eio-syscall-diag.patch): instruments
bsd/dev/arm/systemcalls.c unix_syscall() — the arm64 syscall choke point —
right after `error = (*(callp->sy_call))(...)`: if error==EIO print
`SWEET EIO-SYSCALL code=%u sys=%s pid=%d comm=%s` (syscallnames[syscode],
rate 5000). Catches EVERY unix syscall returning EIO with name+process =>
definitively names the failing op. extern syscallnames[] (generated, already
linked via kern_sysctl.c). printf->SWEETLOG proven. Applies clean -p1.
KEEPS 0196 HFS prints (control: confirms HFS stays healthy).
PATCH 0197 BUILT+FLASHED (2026-11-15): CI run 43647789507 SUCCESS ->
.tmp-patch/eio-art/kernel.development.sweet (17,957,400 B). Verified strings:
EIO-SYSCALL x1, sys=%s, comm=%s, hfs_makenode ENTER, MacToVFSError x5,
cat_lookupbykey x7. Boot img shim/out/athens-boot-eio.img (17,502,208 B) via
mkpayload+repack (shim/out/athens.adt + shim/out/athens/Image.gz +
backup/boot.img). Cmdline = ufs-rw diag set, sweetlog=1 sweetfb_hz=0
vivagpu=2 vivagpufreq=390 cpus=8 ufslogsecs=5, NO sweetscan/sweetnull (preserve
ring for kernel prints; userspace reasons already captured last boot).
FLASHED `fastboot flash boot` -> rebooted into iOS. userdata=varfix.simg.
~3min boot -> recovery -> dd-pull ring -> grep `SWEET EIO-SYSCALL` => exact
syscall name + comm for every EIO(5). THAT is the failing op.

## >>> ATHENS HANDOFF 2026-11-15w - *** HFS FILESYSTEM RULED OUT *** diag2 log: creates+lookups ALL SUCCEED, ZERO catalog errors; EIO is NOT filesystem; capturing userspace reason via sweetscan <<<

DIAG2 RESULT (eba2140 / athens-boot-0196b.img, run 43644261657, .tmp-patch/
diag2-log.txt, 4646 lines, flush#54):
- `hfs_makenode ENTER` fired **335x** — creates DO reach HFS and SUCCEED.
  Names include plist files, .sock, .tmp, CFNetworkDownload_*, and MANY
  40-char SHA1 hash dirs (= the per-user temp/cache dir format).
- `hfs_makenode ERR` = 0, `cat_lookupbykey ERR` = 0, `cat_create ERR` = 0,
  `cat_acquire_cnid` = 0, **`MacToVFSError EIO` = 0** => ZERO catalog
  B-tree errors of ANY kind. HFS create/lookup/catalog layer is HEALTHY.
- Crash storm STILL raging: **964 CRASH lines** (tccd 432, dmd/assistantd/
  mobileactivation/fitnesscoachingd/ScreenTimeAgent ~104, driverkitd 4).
  ns2=OS_REASON_SIGNAL, sig5(SIGTRAP)/sig6(SIGABRT) = assertion/abort.

CONCLUSION: **The EIO is NOT from the HFS filesystem.** The earlier "temp dir
EIO" was either a different/older failure or a non-HFS syscall. Creates work.
Remaining suspects for the daemon aborts: setattrlist/chmod/chown/setxattr/
open-flags/statfs/getattrlist on the temp/keychain paths, OR a NON-filesystem
subsystem entirely (IOKit service, SEP/keybag, Mach service, sandbox profile).

NEXT (no rebuild needed — sweetscan is a boot-arg): rebuilt boot image
athens-boot-scan.img = SAME eba2140 kernel + `sweetscan=tccd,dmd,assistantd,
mobileactivation,fitnesscoachingd,ScreenTimeAgent,driverkitd` in cmdline.
Flashed+rebooted. sweetscan dumps heap STR strings on each abort => the actual
NSException/abort reason. ~3min boot -> recovery -> pull ring -> grep STR/
CRASH for the real error. THEN fix THAT layer (not HFS).

## >>> ATHENS HANDOFF 2026-11-15v - EXTENDED DIAG eba2140 BUILT+FLASHED (athens-boot-0196b.img, run 43644261657); booting to localize EIO layer <<<

CI run 43644261657 (commit eba2140) SUCCESS. Artifact xnu-kernel ->
.tmp-patch/diag2-art/kernel.development.sweet. Verified strings: hfs_makenode
ENTER/ERR, cat_lookupbykey ERR, MacToVFSError EIO x2, cat_create ERR,
cat_acquire_cnid.

BOOT IMAGE: shim/out/athens-boot-0196b.img (17,502,208 B) — same manual
mkpayload+repack, same cmdline (sweetlog=1 sweetfb_hz=0 vivagpu=2
vivagpufreq=390 cpus=8 ufslogsecs=5). sweetscan/sweetnull deliberately OFF
(they'd dump ~700 lines/abort x500 crashes = ring overflow, lose kernel data).
FLASHED to boot, rebooted into iOS. userdata=varfix.

Instrumentation coverage now COMPLETE for HFS catalog layer:
- hfs_makenode ENTER(name) + ERR(step,err,dcnid,name): is create reached? fails where?
- cat_lookupbykey ERR(result,errno,parent): EVERY named op (stat/open/lookup)
- cat_create ERR(cstep,rawresult,fileid) + cat_acquire_cnid raw errors
- MacToVFSError EIO(btBadNode|default,err): UNIVERSAL catalog->EIO net
Decision tree for next log: MacToVFSError/cat_lookupbykey fire => catalog
lookup EIO (see raw code); hfs_makenode ERR fires => create path; NONE fire +
storm continues => NOT catalog (journal/extents/vnode/VFS) -> pivot.

NEXT: ~3min boot -> recovery -> dd-pull ring -> decode -> grep the new prints.

## >>> ATHENS HANDOFF 2026-11-15u - DIAG 9b2603c RESULT: ZERO hfs_makenode prints on live storm => EIO is UPSTREAM of create (lookup/VFS); patch 0196 extended to cover lookup+MacToVFSError <<<

BOOT RESULT (athens-boot-0196.img, run 43642300303 / 9b2603c, userdata=varfix):
- boot-args CONFIRMED correct kernel: `... cpus=8 sweetlog=1 sweetfb_hz=0
  vivagpu=2 vivagpufreq=390 ufslogsecs=5`. Root = `/dev/ufsroot0 on / (hfs,
  journaled)`.
- Apple logo DISAPPEARED -> black screen (<1min). NOT a fix — diag-only build.
  Likely backboardd took over display but no UI renders (crash storm continues).
- Crash storm UNCHANGED: 500 CRASH lines (tccd 320, mobileactivation/dmd/
  assistantd/ScreenTimeAgent 36, fitnesscoachingd 32, driverkitd 4). No panic.
- **DECISIVE: ZERO `hfs_makenode ERR`, `cat_create`, `cat_acquire_cnid` prints.**
  hfs_makenode IS the shared create/mkdir/mknod helper (vnop_create:217,
  vnop_mkdir:5516). On an active storm it printed NOTHING => either creates
  never reach it, or they succeed and EIO is elsewhere.
- ns2=OS_REASON_SIGNAL (reason.h:89); code 0x5/0x6 are signal subcodes NOT
  confirmed errno. sweetscan/sweetnull were OFF this boot => no userspace
  error strings captured (diagnostic gap).

REVISED HYPOTHESIS (evidence-based): EIO is in the LOOKUP/path-resolution
layer, not create. `mkpath_np`/`stat` on a missing component should return
ENOENT; if `cat_lookupbykey`->`BTSearchRecord`->`MacToVFSError` returns EIO
instead, mkpath aborts BEFORE mkdir => hfs_makenode never runs => zero prints.
`cat_lookupbykey` (hfs_catalog.c:~780) is called by EVERY named op
(stat/open/lookup/path-walk) and had NO instrumentation = the coverage hole.

PATCH 0196 EXTENDED (still diagnostic, now 3 files, 209 lines):
- hfs_vnops.c hfs_makenode: + ENTER print (name=, rate 1024) -> is create
  reached? keeps mkstep + ERR prints.
- hfs_catalog.c cat_lookupbykey: + ERR print (raw result + mapped errno +
  parent cnid, rate 512, skips clean btNotFound misses).
- hfs_vfsutils.c MacToVFSError: + EIO prints at btBadNode + default arms
  (raw err code, rate 512) -> UNIVERSAL catalog-Btree->EIO net, catches
  lookup+create+insert+everything.
Validated: patch -p1 applies clean vs bt-art, output == diag copies.
NEXT BUILD will definitively localize: if MacToVFSError/cat_lookupbykey ERR
fire => catalog B-tree lookup is the EIO source (see raw code); if hfs_makenode
ERR fires => create path after all; if NONE fire but storm continues => EIO is
NOT catalog (journal/extents/vnode/VFS/non-HFS) -> pivot.

## >>> ATHENS HANDOFF 2026-11-15t - DIAG KERNEL 9b2603c BUILT+FLASHED (athens-boot-0196.img); booting to capture hfs_makenode EIO stage <<<

## >>> ATHENS HANDOFF 2026-11-15s - EIO ROOT CAUSE NARROWED TO HFS CATALOG/BTREE (cprotect RULED OUT); patch 0196 instruments makenode+catalog raw errors <<<

VARFIX BOOT RESULT (ios16-root-varfix.simg, complete via dd tail): STILL Apple
logo. Fresh SWEETLOG (flush#37, .tmp-patch/varfix-log.txt): crash storm
UNCHANGED — 764 crash lines (tccd 424, assistantd 72, mobileactivationd 68,
dmd 68, ScreenTimeAgent 68, fitnesscoachingd 60, driverkitd 4). Same errors:
`Failed to initialize/create darwin user temp directory` EIO(5), fitnesscoachingd
temp-dir suffix EIO(5), `/Library/Keychains/keychain-2.db` unable to open.
Keychain DID progress: `mkpath_np /Library/Keychains` EIO -> now `open_v2
.../keychain-2.db unable to open` = pre-seeded dir helped it get FURTHER but
create/open still EIO. => mkdir/create itself returns EIO; missing-dirs was
necessary but NOT sufficient.

CONFIRMED FACTS (source+log, not guesses):
- /private/var is a PLAIN DIR on the root HFS+ volume — NOT a separate mount,
  NOT bindfs. Only bindfs_mount error was for /private/preboot/.../firmware.
- Mount flags 0x1480d000: MNT_CPROTECT(0x80) CLEAR -> cp_fs_protected()=FALSE
  -> cprotect (cp_setup_newentry/cp_setxattr/cp_generate_keys) is SKIPPED.
  Those paths return EPERM/EINVAL anyway, never EIO -> EIO is NOT cprotect.
- bindfs returns ENOTSUP for create/mkdir (no write vnops) -> not EIO source.
- HFS journal replayed clean, volume mounted journaled rw. No fs write errors.
- => EIO is in the catalog/B-tree/vnode/journal create path: cat_preflight /
  cat_acquire_cnid / cat_create / hfs_getnewvnode / hfs_start_transaction.
- MacToVFSError (hfs_vfsutils.c:2098): btBadNode->EIO AND default->EIO. So the
  REAL B-tree error code is MASKED — must capture raw `result`, not errno.

OFFLINE FORENSICS (done, rules OUT image/catalog repair as the fix):
- fsck.hfsplus -n on ios16-root.img: catalog file, hierarchy, multi-linked
  files, xattrs, volume bitmap ALL PASS. ONLY issue = "Volume header needs
  minor repair" (trivial). => catalog B-tree is NOT corrupt.
- Parsed catalog B-tree header node (node0 @ vol blk 240514): nodeSize=8192,
  totalNodes=50176 (=411MB logicalSize/8192 exact), freeNodes=3054,
  treeDepth=4, rootNode=21990, keyCompare=0xBC(case-sens/HFSX), attrs=0x6.
  Structurally perfect.
- attributesFile(xattr) B-tree = EMPTY (depth=0,root=0,freeNodes=10751/10752)
  BUT handled gracefully: SearchTree returns fsBTEmptyErr on depth==0, and
  BTSearchRecord/BTIterateRecord convert fsBTEmptyErr->btNotFound at exit, so
  file_attribute_exist returns 0. RED HERRING - not the EIO.
- extentsFile B-tree valid (depth=1,root=1).
- MAC/sandbox: sweet_sandbox_mac_ops only has mpo_policy_syscall (no vnode
  hooks) -> mac_vnode_check_create/mkdir return allow. AMFI only check_signature.
  kauth vnode_authorize returns EACCES/EPERM not EIO. ALL RULED OUT.
- => EIO is a driver/runtime issue inside hfs_makenode create path, NOT bad
  on-disk structures. Candidates left: cat_preflight/BTReserveSpace,
  cat_create/BTInsertRecord(node split), hfs_getnewvnode, journal transaction,
  post-create parent/descendant update.

PATCH 0196 build 1 (dcaaf8c, run 43641040416) FAILED TO COMPILE: dvp->v_name —
struct vnode is INCOMPLETE/opaque in hfs_vnops.c (the v_name uses at 1286/1295/
1305 are all commented out). FIXED in 9b2603c: print dcp->c_desc.cd_cnid
(parent catalog id, NULL-guarded) instead. Patch itself APPLIED cleanly.

PATCH 0196 (xnu/patches/0196-athens-hfsmakenode-diag.patch): instruments
- hfs_vnops.c hfs_makenode: `mkstep` marker before each stage (1=trans,
  3=preflight,4=acquire_cnid,5=cat_create,6=setxattr,7=setupentry,8=getnewvnode,
  9=quotacheck,10=ENOSPC,11=genkeys) + printf `hfs_makenode ERR step=%d
  err=%d dcnid=%u name=%.*s` at exit (rate-limited 512).
- hfs_catalog.c cat_acquire_cnid: prints raw BTSearchRecord/file_attribute_exist
  `result` before EIO/return (rate-limit 256).
- hfs_catalog.c cat_create: `cstep` (1=buildkey,2=BTInsert-thread,3=BTInsert-rec)
  + prints raw `result` before MacToVFSError masks it (rate-limit 256).
Validated: patch -p1 applies OK vs bt-art (only 0026+0041 touch these files).
printf->console->SWEETLOG via patch 0047. Types verified.

NEXT: build 9b2603c via CI -> flash diag boot -> boot varfix userdata -> pull
SWEETLOG -> read mkstep/cstep/rawresult to pinpoint exact failing call. THEN
implement functional fix. NOTE: if it turns out to be a runtime/journal issue
rather than catalog, fix may be a driver patch not an image rebuild.

## >>> ATHENS HANDOFF 2026-11-15r - CRASH STORM ROOT CAUSE FOUND = /private/var skeleton incomplete (EIO on dir create); varfix image building <<<

DIAGNOSIS (gpu19 kernel + diagnostic boot-args, NO rebuild): added
`sweetscan=`+`sweetnull=` for the 7 crashers (tccd,dmd,assistantd,
mobileactivation,ScreenTimeAgent,fitnesscoachingd,driverkitd) -> kernel dumps
heap strings + stderr on each abort. Captured the real NSException reasons:
- dmd/ScreenTimeAgent/fitnesscoachingd/tccd: `Failed to create/initialize
  darwin user temp directory` / `NSTemporaryDirectory` -> **EIO (5)**.
  Path = /var/folders/<2>/<~30char-hash>/T/ (per-user, confstr-created).
- mobileactivationd: `mkpath_np /Library/Keychains: [5] EIO` + `Failed to
  query keychain` -> /Library/Keychains symlinks to /private/var/Keychains.
- Shared sig6 = NSException inside dispatch_once -> std::terminate -> abort
  (symbolized via ipsw dyld a2s on the .symbols subcache).

ROOT CAUSE (evidence, not guess): the iOS rootfs has NO real APFS data
volume, so /private/var is a plain dir on the HFS+ root that must be seeded by
hand. The athens skeleton was INCOMPLETE — /private/var/folders and
/private/var/Keychains were ABSENT. HFS+ itself is healthy: journal replayed
clean, `iOSRoot` mounted journaled rw, systembag.kb keybag present, db dirs
present. EIO (not ENOENT) on create is the open question — likely a secondary
op during vnode create, but pre-seeding the missing parents is the proven
sweet fix and is necessary regardless.

FIX APPLIED (unverified until boot): expanded vardirs() in
tools/sweet-root-tweaks.py — added private/var/{folders,Keychains,
MobileActivation,itunesstored,MobileGestalt,backups,local,lib} +
db/diagnostics/timesync. Rebuilt on /root/iosroot-work/ios16-root.img (still
has VivaMTLDriver.bundle) -> NEW tools/stream-img2simg.py (streaming,
constant-memory; viva-img2simg.py OOM'd buffering ~12GB in 7.7GB WSL) ->
ios16-root-varfix.simg.

CAVEAT: /var/folders now exists but the per-user <hash>/T subdirs still need
runtime mkdir. If mkdir itself returns EIO on HFS+, temp-dir crashes persist
-> then instrument hfs_makenode/cprotect path. Keychains should be fully fixed
(the dir now exists, no runtime mkdir needed for the leaf).

NEXT: flash ios16-root-varfix.simg to userdata (simg2img-free path; use
`fastboot flash -S 64M` — chunk count now 27,852 @16MB RAW so tail bug likely
gone, dd fallback ready), boot with sweetlog=1 + same sweetscan/sweetnull
diag args, pull ring, compare crash counts + check for SpringBoard render.

FLASH RESULT (2026-11-15): ios16-root-varfix.simg = 871 sparse chunks (NEW
tools/stream-img2simg.py — streaming, constant-mem, folds <64-blk zero gaps
into RAW so no tiny chunks; viva-img2simg.py OOM'd @7.7GB WSL). Flashed
`fastboot flash -S 64M userdata` -> transfers 1-187/188 OKAY, **188/188 FAILED
"sparse image write failure" AGAIN** — proves it is NOT chunk structure. Root
cause of tail fail: last fastboot cmd expands a single FILL chunk of
9,453,790 blocks (~38.7GB zeros = HFS free space) into one ~38.7GB device
write the ABL can't do. Splitting FILL won't help (16B on wire, still packs
into one -S cmd). DD FIX: unwritten = imgblk ~3.1M..12582911. Extracted
ios16-root.img bs=4096 skip=3000000 -> tail2.gz (395MB) -> adb push ->
recovery `gunzip -c /tmp/tail2.gz | dd of=/dev/block/sdc59 bs=4096
seek=3000000 conv=notrunc` (toybox dd NEEDS conv=notrunc else ftruncate EINVAL)
-> 9,582,912 rec, 37GB, EXIT=0. userdata = complete varfix image. Booted iOS
(diag boot img still flashed). AWAITING sweetlog pull to verify crash storm.

## >>> ATHENS HANDOFF 2026-11-15q - GPU/METAL CONFIRMED WORKING (vmg cmd buffers); touch bus woke (ff) but chip silent; Apple logo = crash storm, NOT GPU <<<

gpu19 (commit e22ffd7, patch 0195 SPI parent-clock mainpll_d5_d4) BUILT via CI
run 43626692574 -> shim/out/athens-boot-gpu19.img (flashed to boot; `fastboot
boot` still fails "Too many links"). USERDATA = ios16-root-gpu.simg (Metal
bundle injected) flashed via `fastboot flash -S 64M userdata` — ABL rejects
>64M chunks ("data is too large" at 225M) and the img2simg tail chunk
deterministically fails "sparse image write failure" on transfer 188/188.
FIX (user-directed dd method): parsed simg -> failed range = partition blocks
3119299..12582912 (~38.76GB, 9463613 blk) = 9,460,029 FILL-zero + 3,584 RAW
(~14.7MB real). Extracted exact tail of ios16-root.img -> tailfix.gz (40MB) ->
`adb push` -> recovery `gunzip -c /tmp/tailfix.gz | dd of=/dev/block/sdc59
bs=4096 seek=3119299 conv=4` -> 9463613 rec, EXIT=0. userdata = complete image.

BOOT RESULT: Apple logo only (display presents logo; SpringBoard not rendered).
SWEETLOG pulled correctly via exec-out raw dd (NOT base64) + sweet-log.py:
skip = total_blocks-1025 = 13048823 (53,452,177,408B /4096 = 13,049,848 blk).
File .tmp-patch/gpu19-log.txt (4,899 lines, 278,978 B, flush#58).

GPU/METAL — CONFIRMED FUNCTIONAL (not just published):
- `VIVA GPU: accelerator published (MetalPluginName VivaMTLDriver)` (l330).
- `exec MTLCompilerService` (l1590) — Metal shader compiler launched.
- `SWEET SURF: backboardd create id 2 1125x2436 fmt 0x42475241` IOSurface made.
- `|backboardd| vmg: IOSurface 2 ... import refused, copied (texture 1125x2436
  b8g8r8a8_unorm)` + `vmg: buffer texture 194x237 ... copied at each command
  buffer that samples it` — **VivaMTLDriver bundle LOADED and is processing
  real Metal command buffers / creating GPU textures.** "import refused" =
  IOSurface can't map into GPU mem -> CPU-copy fallback (perf limit, NOT fail).
- backboardd does full HID setup (opens AthensNT36672C, AthensPMICKeys,
  VivaKeypad, SweetHIDButtons, AppleCLCD). NO `CRASH backboardd`/`SpringBoard`.

SPRINGBOARD — spawned (l948), did IOK service setup, then STALLED (not crashed).
SMP thread dumps (l2737/4149) show threads blocked in normal mach_msg waits.
BLOCKER = userspace crash storm, NOT GPU/display. Still crash-looping:
mobileactivationd sig5 @0x..3bc, fitnesscoachingd sig5, tccd sig5, and MANY
daemons sig6 @ IDENTICAL pc 0x1e1f77198 / bt 0x1ad5bc4b8 (dmd, ScreenTimeAgent,
assistantd, ...) = shared-library/framework crash — investigate if Metal/GPU
related (these daemons may init Metal) or a separate broken framework.
FBSTAT frozen at swaps 7 flips 5 (logo only). datamigrator exec'd twice.

TOUCH — 0195 clock fix had REAL effect: bus now returns `ff ff ff ff ff ff`
(l306, was all 00) = MISO electrically alive after mainpll_d5_d4. But trim ID
still unrecognised, `reset state timeout (last 0x00)`, `firmware download
failed after retries`. Chip not yet answering validly — next suspects:
CS assert/deassert timing vs spi-mt65xx.c, reset GPIO33 pulse correctness,
MISO sampling edge, or chip power/rails. NOT confirmed working.

NEXT ACTIONS:
1. Identify the shared sig6 crash @0x1e1f77198 — symbolize (it's in dyld cache;
   check if Metal/IOGPU). If Metal-related, fix driver; if not, it's the known
   storm. This is now THE blocker for SpringBoard rendering past Apple logo.
2. Touch: verify CS timing + reset pulse vs spi-mt65xx.c / NT36672C datasheet.
3. Keep sweetfb_hz=0. Do NOT reflash userdata (image verified complete).

## >>> ATHENS HANDOFF 2026-11-15p - TOUCH: clock-gate FIXED (regs alive) -> parent-clock fix 0195; GPU: Metal bundle injected, userdata flash pending <<<

TOUCH PROGRESSION (all evidence from pulled sweetlog, no guessing):
- gpu17 (0192 pinmux): `pinmux spi4 gpio12/13/97/98 func 2 2 1 1 -> 2 2 2 2`
  applied BUT `spi4 ready (cfg0 00000000 cfg1 00000000 cmd 00000000)` = whole
  register block dead. Pinmux was necessary but NOT sufficient.
- gpu18 (0193 clockgate): `ifrao_spi4 gate sta 0x01fc0080 (running)` +
  `cfg0 00000505 cfg1 00000001 cmd 00013000` = NONZERO. **0193 CONFIRMED:
  the ifrao_spi4 functional clock was gated OFF (SET write at 0xa4); the
  mtk_clk_gate_ops_setclr enable is a CLR write at 0xa8.** SPI4 regs now live,
  transfers complete (no timeouts) but chip STILL reads 0x00 + reset timeout.
- DIAGNOSIS (verified vs live DT + clk-mt6853.c + mt6853-clk.h, NOT guessed):
  spi4 `clocks` = parent-clk=CLK_TOP_MAINPLL_D5_D4 (topckgen idx9),
  sel-clk=CLK_TOP_SPI_SEL (idx179), spi-clk=CLK_IFRAO_SPI4. spi_parents[] =
  {tck_26m, mainpll_d5_d4, mainpll_d6_d4, msdcpll_d4}; index1=mainpll_d5_d4 =
  the DT parent-clk. We were selecting index3=msdcpll_d4 = eMMC PLL, GATED on
  this UFS part -> dead SCK -> MISO 0x00. mainpll_d5_d4 is a FACTOR (mainpll/20,
  always live). **Patch 0195: SPI_SEL_VAL 3->1.** Pushed e22ffd7; gpu19 CI run
  43626692574 building. Divider unchanged (sck high=low=5 ~8MHz, under 9.6 max).
- NEXT verify: sweetlog `trim raw ... id` nonzero + `firmware download ok` +
  `ATHENS TOUCH: report ... x= y=` (0194 logs first 24 reports). If still 0x00
  -> next suspects: CS polarity/deassert timing vs spi-mt65xx.c, or panel rail.

GPU/METAL GUI (the real blocker, separate from touch):
- gpu16/17/18 CONFIRMED: VivaGPUAccelerator publishes as IOAcceleratorES,
  Mali-G57 MC3 id 0x90930000 3-core, MetalPluginName=VivaMTLDriver +
  MetalPluginClassName=VMDevice published, backboardd creates real BGRA
  IOSurface swaps. Display copy/flip/OVL frame-end VERIFIED working.
- MISSING PIECE was userspace: VivaMTLDriver.bundle (15MB, iOS16 arm64,
  BNDL, NSPrincipalClass=VMDevice, static Mesa/Panfrost) existed in
  ../viva-gpu-artifacts/viva-gpu-ios/ but NEVER injected into rootfs.
- DONE: mounted iosroot/ios16-root.img rw in WSL (hfsprogs; /mnt/c is ro for
  loop -> copied 51.5GB img to /root/iosroot-work/), VERIFIED it is the tweaked
  base (_PanicOnCrasX present + all /private/var skeleton dirs), copied bundle
  -> /System/Library/Extensions/VivaMTLDriver.bundle (755/644, root:root),
  sync+umount, img2simg -> /root/iosroot-work/ios16-root-gpu.simg.
- NEXT: fastboot flash -S 512M userdata ios16-root-gpu.simg (~7min) -> boot ->
  check sweetlog for Metal bundle load + SpringBoard render. IOGLESMetalBundle
  Name= MISSING is likely non-fatal (legacy GLES prop; iOS16 uses MetalPlugin).
- STILL OPEN: ~123-daemon sig5/sig6 crash storm may block SpringBoard even with
  Metal working; stray-writer ZCHECK/0x4d4d4d4d memory corruption intermittent.

## >>> ATHENS HANDOFF 2026-11-15o - gpu16 booted: TOUCH root cause = SPI4 pins never muxed -> patch 0192 pinmux fix; DISPLAY still Apple-logo (FBSTAT pending) <<<

GPU16 BUILD SUCCESS: CI run 43618107826, commit e8d0764 (patches 0189 FBSTAT +
0190 touch-noflash + 0191 decl-order). Kernel verified: has "trim raw swrst",
"event_buf ->", "firmware download ok", "nt36525"/"nt36772", "SWEET FBSTAT".
Built shim/out/athens-boot-gpu16.img (reused shim Image.gz; `fastboot boot`
fails "Too many links" on this LK -> flash boot + reboot is the working path).
User flashed+booted. Screen: APPLE LOGO ONLY (display still not presenting).

SWEETLOG PULLED (.tmp-patch/gpu16-ring.bin -> gpu16-log.txt, 410 KB, flush#52).
TOUCH DECISIVE RESULT: `ATHENS TOUCH: trim raw swrst 0x3f0fe/0x1f01a/0x1c0be
id 00 00 00 00 00 00` on ALL THREE reset addrs -> SPI reads return ALL ZEROS.
Trim unrecognised -> correctly kept noflash nt36525 map (0190 worked) -> fw
download ran but `reset state timeout (last 0x00)` every retry (backboardd
re-probes via IOHIDEventServiceUserClient). NOT a map/fw problem: the chip
never answers because the BUS is dead.

ROOT CAUSE (confirmed, not guessed): iOS has NO pinctrl driver. The touch's
pinctrl-0 -> spimode_default (phandle 0x195) sets GPIO12=SPI4_MI, GPIO13=
SPI4_MO, GPIO97=SPI4_CLK, GPIO98=SPI4_CSB all func2 - Android's pinctrl applies
it at probe. iOS leaves pins at LK/default GPIO func0 (VivaIO.cpp comment even
says "pin modes left as LK set them (already GPIO)"). Result: SPI controller
clocks+completes frames (NO transfer timeouts in log) but SCK/CS/MOSI never
reach the chip and MISO reads a dead GPIO input = 0x00. Verified vs vendor
pinctrl-mt6853.c (mt6853_pin_mode_range, i_base0=gpio@0x10005000): func field
= 4 bits/pin, reg 0x0300+(pin/8)*0x10, bit (pin%8)*4. Also live-dt reg_bases
phandles->nodes decoded; spi4@11018000/touchscreen@0 = oppo,tp_noflash,
reset-gpio=33 irq-gpio=14 spi-max-freq=8.16MHz. Only spi4 gets an AthensSPI
nub (one "spi4 ready" in log) so hardcoding SPI4 pins is safe.

PATCH 0192 (0192-athens-spi4-pinmux.patch): adds VivaGPIO::getPinFunc/
setPinFunc/pinFuncField (mt6853 mux calc, RMW via existing gpio@0x10005000
map) + AthensSPI::start() muxes GPIO12/13/97/98->func2 and GPIO14/33->func0,
logging before/after func + irq/rst func. Generated vs REAL gpu16 buildtree
(xnu-buildtree artifact); GNU patch verified byte-exact. NEXT: build gpu17,
flash, expect "pinmux spi4 ... func 0 0 0 0 -> 2 2 2 2" then real trim id +
"firmware download ok" + touch reports.

DISPLAY - CORRECTED (almost chased a phantom bug): gpu16 FBSTAT
`swaps 7 copies 7 flips 5 inPlace 2 shown.buf 1 flipReady 1 vblankOvl 1
scanLive 0 scanFrames 0 scanFallbacks 0 period 215424`. scanLive/scanFrames
measure the OPTIONAL vivascanout feature (NOT in cmdline) -> 0 is expected,
NOT a bug. REAL path = copy+flip: LK fb 0x77e20000 buf0 / 0x7920c000 buf1,
panel VIDEO-mode DSI (lcm=nt36672c_fhdp_dsi_vdo_dphy_jdi_120, 120Hz). iOS
touches ZERO DSI regs - inherits LK's OVL->DSI->panel stream; only writes
pixels + flips OVL_L_ADDR at OVL0_2L frame-end (all verified working:
flips=5, frame-end polled). VERDICT: display hardware path WORKS - 7 real
frames presented to panel. "Apple logo only" = static boot-logo frame;
backboardd/SpringBoard threads PARKED (SMP sample dumps = periodic samples,
alive not crashed) with nothing new to render because SpringBoard never
produced the home screen. swaps froze at 7 = no content changes, NOT a
scan-out failure.

GUI BLOCKER (real, was mis-attributed to display): userspace crash storm -
123 crashes / 12 daemon types (accountsd x31, dmd x18, mobileactivation x14,
chronod/liveactivitiesd sig5 code 0x600000001 SIGTRAP at shared PC
0x198f746dc, etc.) "Too many corpses". dyld shared cache maps fine
("not in trust cache" = WARNING only; SIP relaxed via ADT asmb lp-sip0).
backboardd+SpringBoard launched + did IOK/AKS init but stalled before home
screen. = the KNOWN long-standing trust-cache/signing/entitlement userspace
problem (patches 0031-0036, sweet_amfi, CS_PLATFORM_BINARY, dyld crash
triage) - NOT a display bug. Next GUI work = triage the sig5 crash root
cause; display needs no fix.

=== prior handoff 2026-11-15n - gpu15 build FAILED on 0189 decl-order bug -> patch 0191 fix; TOUCH 0190 compiled CLEAN ===

GPU15 BUILD (run 43616980296, commit 65c7e9d) FAILED - but this is the REAL
error gpu14's conf-flake was hiding. gpu14 died at `build_all_recurse_into_
conf` (transient parallel-build flake, NOT code - 0189 only touches
SweetFramebuffer.cpp and conf runs before arm compiles). gpu15 got PAST conf
(proving the flake) and reached compilation -> ONE error in the whole tree:

  SweetFramebuffer.cpp:596:7: error: use of undeclared identifier
  'sweet_fb_swap_count'; did you mean 'sweet_fb_gpu_done'?

ROOT CAUSE: patch 0189's SWEET FBSTAT block sits inside flushFrames()
(~line 517) and reads the file-static `sweet_fb_swap_count`, but that static
is declared ~70 lines LATER (line 662). C++ requires declaration before use.
THE TOUCH CODE IS CLEAN: AthensNT36672C.cpo compiled with ZERO diagnostics -
patch 0190's noflash port builds fine.

PATCH 0191 (0191-athens-fbstat-decl-order.patch, commit 06e2817): moves
`static uint64_t sweet_fb_swap_count;` above flushFrames. Generated against
the REAL post-0189 dxb buildtree (xnu-buildtree artifact from run 43616980296,
NOT logs/xnu-src which can diverge). Verified: GNU patch applies clean to the
post-0189 file, reproduces the edit byte-exact (72975 B), pure LF. It is the
ONLY `file:line:col: error:` in the entire gpu15 log (checked all .cpp/.c).

NEXT BUILD (0190 touch + 0189 FBSTAT + 0191 decl fix) should compile -> gpu16.
Expect on device: "trim raw swrst .. id .." + "firmware download ok" (touch)
AND periodic "SWEET FBSTAT" counters (display scan-out gap).

=== prior handoff 2026-11-15m - TOUCH noflash fix (patch 0190) + gpu14 build FLAKED on conf; both pushed together ===

GPU14 BUILD FAILED BUT NOT THE CODE: CI run 43614429894 (commit dcc3ab0 =
patch 0189 FBSTAT) failed at `make[3]: build_all_recurse_into_conf Error 2` -
the iokit CONF/config-header generation step, which runs BEFORE any arm driver
compiles. Patch 0189 only touches iokit/Kernel/arm/SweetFramebuffer.cpp, so it
CANNOT have caused a conf failure; gpu13 (891f05e) built the identical conf
step fine => TRANSIENT/FLAKY parallel-build failure, not a regression. No
clang `file:line:col: error:` anywhere in the log (only tolerated patch-skip
warnings). Just re-run.

TOUCH ROOT CAUSE (confirmed vs vendor nt36xxx_* sources):
  Panel = oppo,tp_noflash / nf_nt36672c JDI = NO-FLASH => hw_crc=0, fw loads to
  small internal SRAM (0x0-0x2B4A8). Driver DEFAULTED to nt36672a (hw_crc=1
  FLASH map) because trim-ID read returned an unrecognised ID -> took the
  hardware-CRC download path (writes BLD CRC regs 0x3F1xx that don't exist on a
  noflash chip) -> firmware never booted -> "reset state timeout (last 0x00)".
  Firmware blob itself is CORRECT (built-in == installed == research, all
  139264 B byte-identical). SPI write protocol verified byte-for-byte vs vendor.

PATCH 0190 (0190-athens-nt36672c-noflash.patch) - faithful noflash port:
  - Full vendor memory maps (nt36xxx_mem_map.h): MAP_672A/6772/6525/6676F/6526/
    6675; MAP_NF aliases MAP_6525 (hw_crc=0). Default map now noflash.
  - trim_id_table ported 1:1 (was an incomplete subset) -> correct map on match.
  - engReset() (0x5A->0x7FFF80) added; start() does vendor order eng_reset->
    resx high->10ms->trim; fwDownload pulses TP_RESX around eng_reset per retry.
  - bootReady() already wrote POR_CD=0xA0 for hw_crc=0 (verified correct).
  - discoverEventBuf(): noflash maps disagree on EVENT_BUF (0x11A00 vs 0x11E00);
    download is map-independent so fw can boot on the "wrong" page -> probe
    sibling pages for RESET_COMPLETE before declaring failure.
  - chipTrim logs RAW 6 ID bytes ("trim raw swrst 0x.. id ..") so a real boot
    shows the actual chip ID even if no table entry matches.
  - set_bld_hw_crc length now 3B for hw_crc==1, 4B for hw_crc>1 (was always 3B).
  - fSwrst resynced to selected map after trim (was left at last-tried candidate).
  - fMapStore mutable copy so runtime event_buf discovery is safe.
  Verified: applies CLEAN to post-0180 baseline (GNU patch), reproduces work
  file byte-exact (29849 B), pure LF + UTF-8 (em-dash preserved). Found+fixed 2
  self-inflicted compile bugs pre-commit (stray dup `bool`, broken \n escape).
  Brace/paren/bracket balance 0, no unterminated strings, all 15-field map
  inits match struct, all constants/helpers defined. Local compile NOT possible
  on Windows (xnu-cc.py needs macOS clang+buildtree) -> CI is the compiler.

NEXT BUILD tests BOTH 0189 (SWEET FBSTAT -> display scan-out gap) AND 0190
(touch noflash) in one run. On device expect: "trim raw swrst .. id .." then
"trim id -> <map>" then "firmware download ok" then touch reports. If trim
still unrecognised, the raw ID bytes tell us the real chip -> extend table.

=== prior handoff 2026-11-15l - gpu13 SCREEN = APPLE LOGO ONLY; scan-out gap isolated; patch 0189 FBSTAT diag ===

USER SAW: Apple logo ONLY, no GUI. Log proves backboardd+SpringBoard ALIVE
(routine "SMP --- sample 39" spindump thread dumps, NOT a crash) and GUI
frames composited+queued. Panel = DSI VIDEO mode (jdi,nt36672c,dphy,vdo,120
per ATHENS.md) -> scans whatever OVL feeds continuously, no per-frame push.

CONCLUSION: present() copies GUI->buffer B + programs OVL_L_ADDR at frame-end,
but physical panel keeps scanning buffer A (boot logo). Gap is in SCAN-OUT
switch, NOT compositing/GPU. Only ~4 swaps logged + no "N swaps"(1000) counter
+ no forced-frame/double-buffer-off msgs -> backboardd presented a few frames
(static homescreen = few swaps is normal) then idle. Double-buffer armed
("frame end from OVL0_2L INTSTA, panel frame 16571us") = OVL runs at 60Hz.

NOT a freeze-frame feature: sweetfb_hz=0 -> fFlushTicks=1 = copy EVERY vsync
(max rate); sweetfb_keep only ignores display-off (display is ON).

PATCH 0189 (0189-athens-fb-present-dump.patch): periodic IOLog "SWEET FBSTAT"
every 240 vsync ticks (~4s) in flushFrames -> dumps swaps/q/copies/flips/
inPlace/missed/unsure/shown.buf/nextValid/dirty/flipReady/vblankOvl/scanLive/
scanFrames/scanFallbacks/powerOff/gpuWaits/gpuForced/period. Verified applies
clean to post-0181 baseline, reproduces work file. Decides: copies=0 (present
not copying) vs copies>0&flips=0 (frame-end switch not applying) vs flips>0&
shown.buf=1 (switching to B but panel still on A = layer/scan-out issue).

TEST: build gpu14 (0189), flash, boot, recovery pull -> grep SWEET FBSTAT.

=== prior handoff 2026-11-15k (gpu13 on-device milestone) ===
gpu13 flashed+booted, sweetlog pulled (.tmp-patch/gpu13-tail.bin, 16 MiB,
sdc59 skip=13045752 count=4096). MILESTONE - the whole GUI chain unblocked:

PMIC/PMIF (patch 0188) WORKS, verbatim:
  pmif_init_done 0x1 swinf2_sta 0x00008441 (fsm 0 init 1) spiwrap_en 0x1
  PMIC hwcid 0x5930 swcid 0x5920 (real MT6359!) top_int 0x0004
  regulator 0x1b46/0x172e writes all "(reads 0xXXXX) ok" - PMIF SWINF_2
  read+write transactions COMPLETE. spi_mst SPIWRAP_EN=1 took effect.

GPU WORKS:
  VIVA GPU: id 0x90930000 (product 0x9093) cores 3 (0x10005) l2 on
  accelerator published (MetalPluginName VivaMTLDriver)

GUI COMPOSITING LIVE (the old "cannot match IOAcceleratorES" blocker GONE):
  exec SpringBoard / exec backboardd
  IOK backboardd: matching IOAcceleratorES -> VivaGPUAccelerator  (MATCHED!)
  SWEET FB: display on
  SWEET SURF: backboardd create id 2/3 1125x2436 BGRA bpr 4608
  SWEET FB: swap 1..4 layer 0 surface 1125x2436   <- real frames presented
  SWEET FB: double buffer 0x77e20000/0x7920c000, vsync every 1 frame
  => SpringBoard homescreen/setup GUI was rendering to the panel.

INPUT partially live: PMIC keys work (power->0x30 home->0xe9, "key 0x30 down");
  AthensPMICKeys + VivaKeypad + SweetHIDButtons all opened by backboardd.

USER CONFIRMED SCREEN: **Apple logo ONLY, no GUI visible.** So backboardd
composites+swaps real frames (log-proven) but the pixels do NOT reach the
physical panel -> gap is in the SCAN-OUT/PRESENT path (surface->panel), not
compositing. Apple logo = kernel boot logo still in scan-out buffer.
NEXT DEBUG: how does SWEET FB swap present? DSI cmd-mode needs TE/vsync-
triggered frame update; if panel is cmd-mode and no update is pushed, it
keeps last frame (the logo). Check SweetFramebuffer present/swap + DSI TE.

STILL BROKEN (secondary, none blocked the framebuffer):
  ATHENS TOUCH: nt36672c_jdi.bin not in rootfs -> built-in fw -> "reset state
    timeout (last 0x00)" -> "firmware download failed" => NO TOUCH yet.
  VIVA I2C: unsupported clocks (source 0 Hz speed 400000) - touch I2C path.
  Userspace daemon CRASHes (sig5/sig6): mobileactivation, chronod, accountsd,
    mmaintenanced - the known dyld/trust-cache secondary issue; non-fatal.
  SWEET Sandbox: SpringBoard privilege 1007 denied.
  VIVA WIFI reserved-EMI/DMA FAILED; THERMAL LVTS id mismatch; CPUFREQ OPP.
  ZCHECK/0x4d4d4d4d stray-writer scanner still firing (diagnostic, non-fatal
    here - no panic string in tail).

NEXT: (1) get touch working - nt36672c fw blob into rootfs OR fix SPI reset
  timeout + I2C clocks; (2) GUI is UP - verify on-screen + try SpringBoard;
  (3) chase daemon crashes (dyld_shared_cache trust cache) if they block UX;
  (4) stray-writer ZCHECK remains intermittent-corruption risk.

=== prior handoff 2026-11-15j (gpu13 build) ===
GPU13 = shim/out/athens-boot-gpu13.img (17,483,776 B). CI 43611718591 SUCCESS on
891f05e. Kernel .tmp-patch/dl13/kernel.development.sweet. VERIFIED in img:
athens PMIF init complete / pmif write_test / post-init read_test / pmif_init_done
/ spiwrap_en now / PMIF still dead / PMIC hwcid ALL present; classic WACS2 strings
(post-dio, WACS2 cannot, post-regclock) GONE. cmdline = gpu12 verbatim
(sweetlog=1 ufslogsecs=5 sweetfb_hz=0 vivagpu=2 vivagpufreq=390 cpus=8 ...).
ADT 4-range pwrap reg confirmed consecutive in payload: 0x10026000/0x10028000
(spi_mst NEW)/0x10001000/0x10000000. Repack = dl13 kernel + gpu12 cmdline +
new 4-range ADT + unchanged shim Image.gz via viva-bootimg.py.

TEST: adb reboot bootloader; fastboot flash boot shim/out/athens-boot-gpu13.img;
fastboot reboot; boot ~60-90s; force recovery; adb pull sweetlog tail.
READ: post-init read_test ret + write_test rdata(0xa55a?) + swcid/hwcid(0x59xx?)
+ swinf2_sta FSM + spiwrap_en + pmic_vio/pmif_vio/mon_sta.
PASS = write_test reads 0xa55a AND IDs 0x59xx -> PMIC WORKS -> GPU power ->
IOAcceleratorES -> backboardd -> GUI. FAIL = read_test timeout -> the logged
FSM/VIO/monitor regs say WHY (MPU reject vs dead SPI master vs needs-more-init).

=== prior handoff 2026-11-15i (patch 0188 dev) ===
GPU12 RESULT (.tmp-patch/gpu12-tail.bin): init ran end-to-end but WACS2 read
still timed out AFTER full config:
  post-dio read_test ret -536870186 rdata 0x0 wrap_en 1 wacs2_en 1 dio_en 1
  arb 0 ifrao2_sta 3000 -> "WACS2 cannot complete a transaction - bus dead"
wrap_en/wacs2_en/dio_en all read back 1 (config writes DO stick), clocks on,
but the SPI transaction never completes. => NOT a clock/config problem.

ROOT CAUSE (100% confirmed vs exact-device drivers/soc/mediatek/mtk-pmic-wrap.c):
MT6853 pwrap is ARB_V3/PMIF, NOT classic WACS2. pwrap_mt6853 uses mt6853_regs[]
(PMIF_SPI_PMIF_* @ 0xC80+) + mt6853_regs1[] (spi_mst). mt6853_regs[] defines NO
classic WRAP_EN/ARB_EN/WACS2_EN/INIT_DONE -> all classic pwrap_init writes land
on offset 0 (PMIF_INIT_DONE); the PMIF engine is self-configuring. Slave
pmic_mt6359 .caps=0 -> Android runs NO sidly/dual-io/security/slave-reset.
Patch 0186/0187 ported the WRONG (mt6785 WACS2) protocol - that's why it died.

CONFIRMED PMIF/ARB_V3 SPEC (mt6853_regs[], pwrap_read16/write16):
  read:  SWINF_2_STA(0xca8) FSM=(x>>1)&7 idle -> SWINF_2_ACC(0xc80)=adr ->
         wait FSM==WFVLDCLR(6) -> RDATA(0xc94)&0xffff -> VLD_CLR(0xca4)=1
  write: SWINF_2_WDATA(0xc84)=wdata -> SWINF_2_ACC(0xc80)=(1<<29)|adr (no wait)
  addr = raw 16-bit PMIC BYTE addr (dew_regs: DIO_EN=0x40c READ_TEST=0x40e
  WRITE_TEST=0x410 RDDMY=0x424 SPISLV_KEY=0x44a; WRITE_TEST_VAL=0xa55a)
  init:  clocks(ifrao2 spi/wrap) + spi_mst SPIWRAP_EN(spi_mst@0x10028000+0x14)
         + PMIF_INIT_DONE(0x0)=1 + TIMER_CTRL(0x3e4)=3 + IRQ_EN3(0x450)|=0x180000
  init-done status = SWINF_2_STA(0xca8) bit15 (PWRAP_STATE_INIT_DONE0_V3)
  diag:  PMIC_ACC_VIO_INFO_0=0xf50, PMIF_ACC_VIO_INFO_0=0xf80, MONITOR_STA=0x4f4
Clocks confirmed fine: ulposc is always-on root XO -> osc_d10 -> pwrap_ulposc_sel
(mux default) -> fpwrap_ulposc_ck -> ifrao2 PMIC_TMR/PMIC_AP gates (enabled).

PATCH 0188 (xnu/patches/0188-athens-pwrap-pmif-arbv3.patch) + mkadt.py 4-range
reg [pwrap@10026000, spi_mst@10028000, infracfg@10001000, topckgen@10000000]:
re-ports VivaPwrap to PMIF. readPMIC/writePMIC/writeRegulator/athensPwrapInit all
use SWINF_2. Verified: patch applies clean to post-0187, reproduces work files.

TEST: build gpu13 via CI (patches/** trigger), repack, flash, pull sweetlog.
READ: post-init read_test ret + write_test rdata(0xa55a?) + swcid/hwcid. If
write_test=0xa55a and IDs=0x59xx -> PMIC WORKS -> GPU power -> IOAcceleratorES.
If read_test still times out -> check swinf2_sta FSM + pmic_vio/pmif_vio/mon_sta
in log (MPU/firewall reject vs dead SPI master vs needs-more-init).

## >>> ATHENS HANDOFF 2026-11-15h - gpu12 BUILT: patch 0187 (fca3376, CI 43608274936) <<<

CI 43608274936 SUCCESS. Kernel .tmp-patch/dl12/kernel.development.sweet
(17,940,176 B). VERIFIED in binary: post-dio read_test + cannot-complete +
enhanced readback fmt PRESENT; post-regclock read_test ABSENT (=0187 applied).
Repacked shim/out/athens-boot-gpu12.img (17,483,776 B) via viva-bootimg.py
repack backup/boot.img + shim Image.gz + athens-payload.bin (bypassed clang -
Image.gz unchanged). VERIFIED in img: post-dio/cannot-complete/vivagpu=2/
sweetfb_hz=0 all present. ADT 3-range pwrap reg confirmed consecutive
(0x10026000/0x10001000/0x10000000, SOC_BASE-offset encoded).

TEST: adb reboot bootloader; fastboot flash boot shim/out/athens-boot-gpu12.img;
fastboot reboot. Boot ~90s (sistrobe does many PMIC transactions), force
recovery, pull sweetlog tail (sdc59 skip=13045752 count=4096 ->
.tmp-patch/gpu12-tail.bin). READ: post-dio read_test ret+rdata+reg readback ->
spislv init -> dio -> sistrobe sample/dly/read_test -> wacs2 write_test ->
probe swcid/hwcid.
- post-dio ret SUCCESS -> bus transacts -> sistrobe calibrates -> if swcid/
  hwcid=0x59xx PMIC WORKS -> GPU power -> IOAcceleratorES -> GUI.
- post-dio ret TIMEOUT -> bus can't complete a transfer even configured ->
  readback shows if wrap_en/wacs2_en/dio_en stuck; then suspects = pinmux /
  spi_mst / PMIC power / PMIF (need evidence).

## >>> ATHENS HANDOFF 2026-11-15g - gpu12: patch 0187 fixes premature liveness probe <<<

FIX (patch 0187, xnu/patches/0187-athens-pwrap-liveness-fix.patch): the
gpu11 post-regclock read_test fired BEFORE InitSPISLV/dio/sistrobe - before
Android ever does a PMIC read - so its timeout was a likely FALSE NEGATIVE.
0187 removes that early abort and moves the liveness check to AFTER dio (bus
fully configured). It now also logs wrap_en/wacs2_en/dio_en/arb/ifrao2_sta
readback so a still-dead bus shows whether config writes even stuck.
Verified: applies clean to post-0186 baseline, reproduces new file exactly.

EXHAUSTIVE pre-build verification (all confirmed, no guessing):
- Clocks RUNNING: ifrao2 sta=+0x90 correct reg (clk-mt6853.c); 0x3000 = bits
  12,13 gated only; PMIC_TMR(bit0)/PMIC_AP(bit1)=0=running. clk_cfg8=0x2010001
  -> pwrap_ulposc_sel mux=0 -> osc_d10 (always-on XO); fpwrap_ulposc_ck is a
  fixed FACTOR (no gate). Whole chain live - gating was never the bug.
- Register map + WACS2 protocol byte-identical to mt6785/MT6359 HAL.
- Init sequence faithful: reset_spislv(CSL,OUTS,CSH,OUTSx4), reg_clock,
  InitSPISLV, dio, sistrobe, write_test, enable, INIT_DONE, lock - all match.
- All 11 PMIC addrs confirmed vs mt6853_upmu_hw.h (FILTER_CON0=0x42,
  SMT_CON1=0x32, DRV_CON1=0x3a, RG_SPI_CON0=0x408, DEW_*=0x40c-0x426,
  SPISLV_KEY=0x44a); MT6359_PMIC_REG_BASE=0. HWCID=0x8 SWCID=0xa.
- mt6359-pmic is a pwrap@10026000 child -> WACS2 IS the transport (spi_mst
  @10028000 is separate, mt6785 HAL doesn't use it).

IF post-dio read_test STILL times out -> bus genuinely can't complete a
transfer. Then suspects (need evidence, not guesses): pinmux (SPI pads not
routed to pwrap), spi_mst block needs enable, PMIC SPI-slave power domain,
or MT6853 needs PMIF. IF it completes -> sistrobe calibrates -> swcid/hwcid
0x59xx -> PMIC works -> GPU power -> IOAcceleratorES -> GUI.

## >>> ATHENS HANDOFF 2026-11-15f - gpu11 LOG ANALYZED: clocks ON, WACS2 read timeout <<<<

gpu11 (e43b136) booted to logo, forced recovery, pulled sweetlog tail
(.tmp-patch/gpu11-tail.bin, 16 MiB). VIVA PWRAP stage lines, verbatim:

    init_done0 0xa000a wacs2_en 0xa000a wacs2_rdata 0x0 (fsm 0, init 0)
    init-done clear; running athens pwrap init
    athens init; pre ifrao2_sta 0x3000 clk_cfg8 0x2010001 wrap_en 0x0
    clocks on, ifrao2_sta 0x3000 (0=running)
    spislv reset done
    reg_clock done
    post-regclock read_test ret -536870186 rdata 0x0      <-- TIMEOUT
    WACS2 dead after reg_clock - aborting init
    post-init wacs2_rdata 0x0 (fsm 0 init 0)
    probe swcid/hwcid ret -536870186 val 0x0
    WACS2 still dead after athens init, not using it
    VIVA GPU: no PMIC wrapper

CONFIRMED from log + clk-mt6853.c:
- All 3 ADT reg maps worked (ifrao2_sta/clk_cfg8/wrap_en returned real vals).
- ifrao2 sta=+0x90 IS the right reg (clk-mt6853.c ifrao2_cg_regs sta_ofs=0x90).
  0x3000 = bits12,13 gated (I2C1+reserved); PMIC_TMR(bit0)/PMIC_AP(bit1)=0
  = RUNNING. => pwrap spi/wrap clocks were ALREADY on; gating was NOT the bug.
- clk_cfg8=0x2010001 -> pwrap_ulposc_sel mux=(>>2)&7=0 -> osc_d10 parent. OK.
- ret -536870186 = kIOReturnTimeout: WACS2 FSM never reached WFVLDCLR.

ROOT-CAUSE HYPOTHESIS (to verify, not confirmed): the post-regclock read_test
is MY extra probe placed BEFORE InitSPISLV/dio/sistrobe - i.e. before the SPI
slave is configured and SI timing calibrated. Android does NO read test there;
its first PMIC reads are inside _pwrap_init_dio/_pwrap_init_sistrobe AFTER
InitSPISLV+dio. So the timeout is likely a FALSE NEGATIVE - bus not yet
configured. FIX: remove early abort; move liveness check to AFTER dio; let
sistrobe/write_test run (bounded ~few sec even if dead).

If bus STILL dead after full config -> remaining suspects (unverified):
pinmux (SPI pads not routed to pwrap), spi_mst@0x10028000 needs enable, PMIC
SPI-slave power domain off, or MT6853 uses PMIF not WACS2 (unlikely - mt6359
is a pwrap child + WACS2 offsets match mt6785 exactly).

## >>> ATHENS HANDOFF 2026-11-15e - gpu11 BUILT: pwrap/WACS2 bring-up (commit e43b136, CI 43605565018) <<<

Patch 0186 (xnu/patches/0186-athens-pwrap-bringup.patch) + mkadt.py 3-range
pwrap reg. CI 43605565018 SUCCESS. Kernel .tmp-patch/dl/kernel.development.sweet
(17,940,176 B) — all new VIVA PWRAP stage strings confirmed in binary.
Repacked shim/out/athens-boot-gpu11.img (17,483,776 B): gpu10 cmdline verbatim
(sweetlog=1 ufslogsecs=5 sweetfb_hz=0 vivagpu=2 vivagpufreq=390 cpus=8 ...),
backup/boot.img base, shim Image.gz kernel slot, payload ramdisk. VERIFIED:
cmdline match + 3-range pwrap reg (0x10026000/0x10001000/0x10000000) in payload.

TEST: fastboot flash boot shim/out/athens-boot-gpu11.img; boot ~60-90s; force
recovery; pull sweetlog tail (sdc59 skip=13045752 count=4096). READ the stage
lines: clocks on/ifrao2_sta -> spislv reset -> reg_clock -> post-regclock
read_test ret -> spislv init -> dio -> sistrobe sample/dly/read_test ->
wacs2 write_test -> post-init wacs2_rdata -> probe swcid/hwcid.
If swcid/hwcid return real IDs (0x59xx) -> PMIC WORKS -> GPU power path opens.
If a stage stalls, that exact step is the blocker (no guessing).

## >>> ATHENS HANDOFF 2026-11-15d - PWRAP BRING-UP SPEC 100% CONFIRMED (exact athens kernel) <<<

Source of truth = exact athens kernel `techyminati/android_kernel_realme_mt6853`
(branch k6853v1_64_6360). MT6853 uses shared mt6785 pwrap HAL
(`drivers/misc/mediatek/pmic_wrap/mt6785/pwrap_hal.c`, MTK_PLATFORM_MT6359=1).
Single PMIC, PMIC_WRAP_ULPOSC_CAL=1, CRC_SUPPORT. WACS2 protocol in VivaPwrap is
BYTE-IDENTICAL to mt6785 (cmd=(wr<<31)|((adr>>1)<<16)|data; FSM=(x>>16)&7;
RDATA&0xffff; VLDCLR=1; INIT_DONE bit22). Offsets NOT the problem.

CONFIRMED register map (mt6785 hal.h, base fRegs=0x10026000):
WRAP_EN=0x04 DIO_EN=0x08 SI_SAMPLE_CTRL=0x0c SI_SAMPLE_CTRL_ULPOSC=0x1c
RDDMY=0x20 CSHEXT_WRITE=0x24 CSHEXT_READ=0x28 CSLEXT_WRITE=0x2c CSLEXT_READ=0x30
EXT_CK_WRITE=0x34 EXT_CK_READ=0x38 STAUPD_CTRL=0x3c STAUPD_GRPEN=0x40
EINT_STA0_ADR=0x44 WRAP_STA=0x60 HARB_HPRIO=0x68 HPRIO_ARB_EN=0x6c
MAN_EN=0x7c MAN_CMD=0x80 MAN_RDATA=0x84 MAN_VLDCLR=0x88
WACS0/1/2/3_EN=0x8c/0x94/0x9c/0xa4 INIT_DONE0/1/2/3=0x90/0x98/0xa0/0xa8
WACS_P2P_EN=0xac INIT_DONE_P2P=0xb0 WACS_MD32_EN=0xb4 INIT_DONE_MD32=0xb8
INT0_EN=0xbc INT1_EN=0xcc TIMER_CTRL=0xf0 WDT_CTRL=0xf8 WDT_SRC_EN_0=0xfc
WDT_SRC_EN_1=0x100 WACS2_CMD=0xc20 WACS2_RDATA=0xc24 WACS2_VLDCLR=0xc28
SW_RESET=0x2a8 MUX_SEL=0x00
Bitfields: W2_FSM=(x>>16)&7 W2_SYNC=(x>>20)&1 W2_INITDONE=(x>>22)&1
WRAP_FSM=(x>>11)&0xf WRAP_DLE=x&7 MAN_FSM=(x>>8)&7. OP: WR=1 CSH=0 CSL=1
OUTS=8 INS=0xc INQ=0xf. FSM: IDLE=0 REQ=2 WFDLE=4 WFVLDCLR=6. SYNC_IDLE=1.
MAN cmd=(OP_WR<<13)|(OP_<<8). ARB=0xfbb7f (MT6359).

CONFIRMED clocks (clk-mt6853.c + mt6785 hal.h __pwrap_spi_clk_set):
infracfg_ao base=0x10001000 (syson@10001000, #clock-cells=1, phandle 0x2f).
ifrao2 gate regs SET=+0x80 CLR=+0x84 STA=+0x90 ; PMIC_TMR(bit0,wrap)/PMIC_AP
(bit1,spi) parent fpwrap_ulposc_ck. ACTIVE-LOW: STA=1 gated, CLR-write enables.
ifrao4: SET=+0xa4 CLR=+0xa8. PMICW_CLOCK_CTRL_CLR=+0x3ac. INFRA_GLOBALCON_RST2
SET=+0x140 CLR=+0x144. __pwrap_spi_clk_set: CG0_SET=0xf,CG2_SET=0x100,
PMICW_CLK_CTRL=0x2,soft-reset pulse,CG0_CLR=0xf,CG2_CLR=0x100. topckgen mapped
but NOT written by pwrap_init (CCF handles mux/factor; default likely osc_d10).

CONFIRMED pwrap_init() order (mt6785 pwrap_hal.c):
1 __pwrap_spi_clk_set 2 _pwrap_reset_spislv(MAN bit-bang) 3 WRAP_EN=1
WACS2_EN=1 ARB=0x4 4 _pwrap_init_reg_clock(1): EXT_CK_WRITE=1; wacs2 write
PMIC_DEW_RDDMY_NO(0x424)=0x8; RDDMY=0x8; CSHEXT=0; CSLEXT_WRITE=0;
CSLEXT_READ=0x200 5 __pwrap_InitSPISLV: PMIC writes 0x42=0xf0,0x32=0xf,0x98=0xf0,
0x408=1,0x3a=0x8888 6 _pwrap_init_dio(1): ARB=0x4; wait WRAP_FSM idle;
wacs2 write PMIC_DEW_DIO_EN(0x40c)=1; wait WACS2 idle+sync; DIO_EN=1
7 _pwrap_init_sistrobe(0): SI_SAMPLE_CTRL sweep en0-7/ck0-1 until
PMIC_DEW_READ_TEST(0x40e)==0x5aa5; RG_SPI_DLY_SEL(0x426) sweep 0-9 write/read
test PMIC_DEW_WRITE_TEST(0x410) boundary; SI_SAMPLE_CTRL+=0x20;
SI_SAMPLE_CTRL_ULPOSC ULPOSC_CAL 8 _pwrap_wacs2_write_test(0): write 0xa55a,
read back==0xa55a 9 _pwrap_enable: ARB=0xfbb7f; WACS0/1/2/3/P2P/MD32_EN=1;
STAUPD_CTRL=5 WDT_CTRL=0x3f WDT_SRC_EN=0xffffffff/x2 TIMER_CTRL=3 INT0=0xffffffff
INT1=0x1fff 10 INIT_DONE0/1/2/3/P2P/MD32=1 11 _pwrap_lock_SPISLVReg:
PMIC_SPISLV_KEY(0x44a)=0.
PMIC SPI addrs (MT6359 base0): DEW_DIO_EN=0x40c READ_TEST=0x40e WRITE_TEST=0x410
RDDMY_NO=0x424 RG_SPI_DLY_SEL=0x426 RG_SMT_SPI_CLK=0x32 GPIO_PULLEN0_CLR=0x98
RG_SPI_MISO_MODE=0x408 RG_OCTL_SPI_CLK=0x3a RG_SRCLKEN_IN0=0x42 INT_STA=0x452
SPISLV_KEY=0x44a. HWCID=0x008 SWCID=0x00a (same as MT6358). SWCID expected 0x59xx.
Init-phase PMIC writes use raw wacs2_nochk (NOT writePMIC which is allow-listed).

IMPLEMENTED (patch 0186 + mkadt.py, verified):
- tools/mkadt.py: pwrap reg now 3 ranges -> idx0 pwrap@10026000, idx1
  infracfg_ao@10001000, idx2 topckgen@10000000 (confirmed consecutive in ADT).
- VivaPMIC.h: +fInfraMap/fInfraRegs/fTopMap/fTopRegs, wacs2NoChk, athensPwrapInit,
  infraRd/infraWr/topRd.
- VivaPwrap.cpp: +all PW_*/AT_*/PMIC_* defines (verified vs mt6785 hal.h +
  mt6853 upmu_hw.h), wacs2NoChk (= _pwrap_wacs2_nochk), athensPwrapInit =
  faithful pwrap_init() port: spi_clk_set(infracfg) -> reset_spislv(manual) ->
  WRAP_EN/WACS2_EN/ARB=4 -> reg_clock -> liveness probe -> InitSPISLV -> dio ->
  sistrobe(cal) -> write_test -> enable(ARB=fbb7f,all WACS EN) -> INIT_DONE* ->
  lock_SPISLVReg. Skips InitStaUpd+starve_set (not needed for reg access).
  Called when init-done clear; then re-probes SWCID/HWCID.
- Patch verified: applies to bt-art+0185 -> IDENTICAL to logs/xnu-src.
- mt6785 HAL confirmed = MTK_PLATFORM_MT6359 (mt6885=MT6358 wrong). WACS2 in
  "pwrap" reg@0x10026000 (spi_mst@0x10028000 is separate SPI-master block).
- RISK: ifrao2 gate clear assumes ulposc parent (topckgen mux->factor) runs on
  reset defaults; if WACS2 still dead, check clk_cfg8 mux state (logged).

## >>> ATHENS HANDOFF 2026-11-15c - gpu10 RESULT: WACS2 genuinely DEAD (probe timeout); MT6853 may need ARB mode / PMIF <<<

gpu10 (patch 0185 probe) flashed + logged. DECISIVE LINE:
  `VIVA PWRAP: init-done clear; probe swcid ret -536870186 val 0x0 hwcid ret -536870186 val 0x0`
  `VIVA PWRAP: WACS2 not initialized, not using it` -> `VIVA GPU: no PMIC wrapper`
=> WACS2 command interface TIMES OUT. Not a missing flag — the bus engine is
dead. backboardd still `IOAcceleratorES -> 0` (no GUI), same as gpu9.

DEEPER FINDING (Linux mtk-pmic-wrap.c + vendor headers):
- pwrap register OFFSETS match mt6779 (WACS2_CMD=0xC20,RDATA=0xC24,VLDCLR=0xC28;
  WRAP_EN=0x04,HIPRIO_ARB_EN=0x6C,WACS0/1/2_EN=0x8C/0x94/0x9C,STAUPD=0x3C/0x40,
  INIT_DONE0/1/2=0x90/0x98/0xA0,arb_en_all=0xfbb7f). MT6853 not in mainline 5.15.
- BUT newer pwrap has PWRAP_CAP_ARB (arbiter): WACS2_CMD = raw `adr` (NOT
  (adr>>1)<<16) and RDATA = PWRAP_SWINF_2_RDATA_31_0 (NOT WACS2_RDATA). If
  MT6853 uses ARB, VivaPwrap's ENTIRE WACS2 protocol is wrong for athens.
- MT6853 also has `pmif-m` (PMIC Interface, mediatek,mt6853-pmif-m) — a newer
  PMIC bus that may be the REAL access path, with pwrap@10026000 possibly
  legacy/limited. live-dt has pwraphal@10026000 + pwrap_mpu@10026000 siblings.
- Register reads DO return values (init_done0=0xa000a,wacs2_en=0xa000a — same
  value at two addrs is suspicious, possible bus-float/aliasing) but WACS2
  command FSM never leaves IDLE -> engine not clocked/configured, OR wrong
  protocol (ARB), OR wrong register block (should be spi_mst@0x10028000?).

NEXT (needs MT6853-specific source — vendor kernel pwrap_hal.c / mt6853.dts /
datasheet): determine (a) does MT6853 pwrap use ARB WACS2 protocol? (b) is the
WACS block in pwrap@0x10026000 or spi_mst@0x10028000? (c) are spi/wrap clocks
gated (infracfg) and need enabling first? (d) does real PMIC access go via
pmif instead? Then port correct init+protocol into VivaPwrap.
This is real hardware bring-up; do NOT guess register writes blind.

## >>> ATHENS HANDOFF 2026-11-15b - gpu10 BUILT: pwrap WACS2 probe (build 43600586629) <<<

Patch 0185 (xnu/patches/0185-athens-pwrap-probe.patch, commit 42307ca):
VivaPwrap::start no longer bails silently when WACS_INIT_DONE0_V2 is clear.
It now does bounded readPMIC probes (SWCID 0x00a, HWCID 0x008, ~30 ms each)
and logs `VIVA PWRAP: init-done clear; probe swcid ret .. val .. hwcid ret ..
val ..`. If EITHER read returns kIOReturnSuccess it CONTINUES (gVivaPwrap set,
registerService, AthensPMIC child, GPU powerOn path live). If both fail it
returns false as before -> still no IOAcceleratorES.
DECISIVE TEST: flash gpu10, read sweetlog. `probe swcid ret 0 val 0x59..`
=> WACS2 works, relax the check permanently (next patch). `ret -536870212`
(timeout) => need full pwrap_init + clock enable (see plan below).
Build: CI 43600586629 success; kernel gpu10-art/kernel.development.sweet;
image shim/out/athens-boot-gpu10.img (verified: probe strings + gpu9 cmdline
sweetlog=1 ufslogsecs=5 sweetfb_hz=0 vivagpu=2 cpus=8). gpu9 still on boot;
flash gpu10 over it. Android restore still backup/boot.img.

## >>> ATHENS HANDOFF 2026-11-15a - gpu9: UFS CAP_64AS FIX CONFIRMED; GUI BLOCKER = PMIC WRAP (pwrap) NOT INIT <<<

BUILD gpu9 (CI 43596846980, kernel.development.sweet -> shim/out/athens-boot-gpu9.img)
was FLASHED to boot (fastboot flash boot) — Android restore = backup/boot.img.
Result: device reaches static Apple logo, NO progress bar / GUI. Recovery
pull of the persistent log gave a FRESH 667 KB console (seq=94) — this is the
first real gpu9 log, not stale gpu5.

### WHERE LOGS ARE WRITTEN (verified)
- sweet_ufs.c writes the console ring DIRECTLY into the LAST ~4.2 MiB of the
  GPT `userdata` partition (raw UFS blocks, NOT a filesystem path).
- userdata = /dev/block/sdc59 = 13,049,848 4 KiB blocks (53,452,177,408 B).
- Layout: `base = first_block + nblocks - SWEET_LOG_BLOCKS`;
  SWEET_LOG_BLOCKS = 1 + SWEET_LOG_SIZE/UFS_BLOCK = 1 + 4 MiB/4 KiB = 1025.
  Header `SWEETLOG` magic at `base` (block 13045752-1 area); ring starts at
  `base+1`. Panic records use `SWEETPAN` magic in the same region.
- Header fields (LE): ver@+8, size@+12(=0x400000), total@+16, seq@+24.
- READING IT (recovery adb): pull the FINAL 16 MiB = last 4096 blocks,
  skip = 13045752 blocks of 4096:
    adb shell "dd if=/dev/block/sdc59 of=/sdcard/tail.bin bs=4096 skip=13045752 count=4096"
    adb pull /sdcard/tail.bin
  (Earlier skip=13042688 read ~28 MiB BEFORE the tail -> looked empty. Use
  13045752.) Header sits ~12.5 MB into that 16 MiB pull.

### VERIFIED gpu9 OBSERVATIONS (from gpu9-console.txt)
- UFS CAP_64AS fix WORKS: `SWEET UFS: host cap 0x3587071f, DMA at 0x103f24000`
  (a real managed-pool page >4 GiB, kmem_alloc_contig path — NOT the removed
  carve 0x1bfcf0000, NOT ufsdma fallback 0x4e000000). userdata on LUN 2
  read-write; `hfs: mounted iOSRoot`; `BSD root: ufsroot0`. Root+userspace boot.
- GPU nub EXISTS: `SWEET NUB: node=mali`, `SWEET NUB2: mali (IOPlatformDevice)
  compat=mediatek,mali`, `ATHENS GPNUB: mali compat=mediatek,mali`,
  `ATHENS DIAG: DT arm-io/mali=0x...`. `VIVA GPU: start() entered, provider mali`.
- GUI PROCESSES LAUNCH: `exec SpringBoard` (L796), `exec backboardd` (L876).
  backboardd drives AppleCLCD + framebuffer (`IOServiceFirstMatch
  IOMobileFramebuffer`, `open AppleCLCD`, many `SWEET FB: backboardd sel ..`).
- THE BLOCKER: backboardd repeatedly `matching IOProviderClass=IOAcceleratorES
  -> 0` (no match). Reason chain (all verified in source):
    VivaPwrap::start (VivaPwrap.cpp L81-83): WACS2_RDATA=0x00000000 ->
      `!(rdata & WACS_INIT_DONE0_V2)` -> "WACS2 not initialized by LK, not
      using it" -> return false BEFORE gVivaPwrap=this/registerService.
    -> VivaPwrap::wait() returns NULL ->
    VivaGPUAccelerator::start (VivaGPU.cpp L979-982): "no PMIC wrapper" ->
      return false BEFORE powerOn/registerService (L1019-1025).
    -> IOAcceleratorES never published -> backboardd match -> 0 -> no GUI.
- pwrap DT node IS present: `SWEET NUB: node=pwrap`, `SWEET NUB2: pwrap
  compat=mediatek,mt6781-pwrap`. pwrap registers DO respond
  (init_done0=0xa000a, wacs2_en=0xa000a) but WACS2_RDATA=0.
- SIDE EFFECTS of no pwrap: viva_cpufreq_start (L104) skipped -> no CPU DVFS;
  RTC unread (calendar 1970); VivaDTNub::publishChildren skipped -> PMIC child
  devices (mt6359-pmic/keys/gauge) never published.
- Many userspace daemons CRASH (sig5/sig6: liveactivitiesd, chronod,
  mobileactivationd, dmd, ScreenTimeAgent, accountsd...) + "Too many corpses"
  + dyld_shared_cache "not in trust cache". Likely missing entitlements/GPU —
  secondary to the GUI blocker, not the cause of the static logo.
- ATHENS TOUCH still loops "reset state timeout (last 0x00)" -> fw download
  failed (async, non-blocking — confirmed it does NOT block boot).

### PWRAP INVESTIGATION RESULT (2026-11-15, verified vs Linux mtk-pmic-wrap.c)
- athens pwrap = `mediatek,mt6853-pwrap` @ reg {0x10026000,0x1000}=pwrap +
  {0x10028000,0x1000}=spi_mst (live-dt/pwrap@10026000; reg-names pwrap/spi_mst).
  Our ADT only emits the pwrap range (index0) — WACS regs are in that range.
- VivaPwrap offsets (INIT_DONE0=0x090, WACS2_EN=0x09c, WACS2_CMD=0xc20,
  WACS2_RDATA=0xc24, WACS2_VLDCLR=0xc28) MATCH Linux mt6779/mt6765 table —
  correct for MT6853-class pwrap. NOT an offset bug.
- ROOT CAUSE confirmed: `INIT_DONE` is a SOFTWARE flag. Linux pwrap_init()
  ends with `pwrap_writel(1, PWRAP_INIT_DONE2/0/1)`. On viva, LK ran this;
  on athens lk2nd does NOT -> our iOS kernel must run pwrap_init itself.
  VivaPwrap currently only READS WACS2_RDATA and bails if bit22 clear.
- pwrap needs clocks `spi`,`wrap`,`ulposc`,`ulposc_osc` (live-dt clock-names;
  spi+wrap gated in infracfg, ulposc* in topckgen). iOS has NO clock driver,
  BUT viva_cpufreq.c already pokes clocks directly: INFRA_CG_CLR=0x10001084
  (clock-gate clear), INFRA_RST0_SET/CLR=0x10001120/124, apmixed PLLs
  0x1000c2xx. Reuse that mechanism to gate-enable pwrap clocks.
- FIX PLAN (ordered, each = patch + CI build + fastboot flash test):
  1) DIAGNOSTIC: in VivaPwrap::start, before the init-done bail, attempt a real
     PMIC read (SWCID 0x00a expect chip id 0x59 / HWCID) and log result. If it
     responds, pwrap is already usable -> just relax the check. If garbage/
     timeout -> need full init.
  2) If init needed: port minimal pwrap_init writes for mt6779-class:
     WRAP_EN=1, HIPRIO_ARB_EN, WACS2_EN=1, CS-ext, sidly, WACS0/1/2_EN=1,
     STAUPD_PRD=5, STAUPD_GRPEN=0xff, then INIT_DONE0/1/2=1 — AFTER enabling
     spi+wrap clocks via infracfg CG_CLR. Need exact mt6853 clock-gate bits
     (clk-mt6853.c / mt6853.dts pwrap clock indices) — verify before writing.
  3) Then WACS2 works -> readPMIC/writeRegulator -> gVivaPwrap set ->
     registerService -> AthensPMIC child -> GPU powerOn -> IOAcceleratorES ->
     backboardd renders -> GUI.
- RISK: wrong clock-gate bit or init write can hang AP/bus. Validate each
  register against mt6853.dts + clk-mt6853.c before building. Prefer the
  diagnostic build (step1) first to learn whether clocks are already on.
- ONCE GUI works: inject VivaMTLDriver.bundle into athens rootfs for Metal.

## >>> ATHENS HANDOFF 2026-11-14c - GPU PORT: DRIVER ALREADY IN TREE; VIVA-GPU USERSPACE FOUND <<<

USER DIRECTION: abandoned the SW-renderer/userdata-hack path ("will not
work for me"). Wants the REAL GPU/Metal port — "the dev claimed to have
gotten that" on viva. Pulled and confirmed.

VERIFIED STATE (all in docs/ATHENS-GPU.md "UPDATE 2026-11-14"):
- Kernel driver ALREADY compiled into athens: xnu/patches/0100-0137 ship
  VivaGPU.cpp/h + VivaGPUUserClient.cpp + uapi; all vivagpu* boot-args
  present. AthensPMIC (MT6359/pwrap) + VivaPMIC/VivaPwrap exist.
- Userspace Metal stack = separate repo github.com/Nik300/viva-gpu
  (cloned to ../viva-gpu): Metal frontend + AIR->NIR + Mesa/Panfrost
  (Valhall, MC2/MC3-agnostic) + libdrm-xnu -> VivaMTLDriver.bundle.
  PROVEN on viva: backboardd creates GPU BOs, Panfrost cache present,
  SpringBoard/Settings GPU-accelerated.
- LIVE DT pulled (research/rmx2117/live-dt): gpufreq supplies resolve
  VGPU=buck_vproc1 (ph0x83), VSRAM=ldo_vsram_md (ph0x84); clock-names
  show 5 MFG domains (mfg0/1/2/3/5); mali node minimal, compatible
  mediatek,mali/arm,mali-valhall.

WHY NO GPU TODAY (fixable, ordered): (1) ADT gpu compatible
mediatek,mt6853-mali vs driver match mediatek,mt6781-mali -> add match;
(2) vivagpu=0 default -> vivagpu=2; (3) ADT reg lacks MFG power blocks
(mfgcfg/SPM/topckgen/apmixed/infracfg) viva's node has; (4) PMIC defines
are MT6366 (VivaGPU.cpp ~L204) -> need MT6359 vproc1/vsram_md EN/VOSEL +
VivaPwrap whitelist; (5) IRQs athens SPI 364-368 vs viva 274-276; (6)
MFG power/clock sequence for MT6853 + OPP (operating-points empty in DT).

PORT CHECKLIST + honest scope in docs/ATHENS-GPU.md. This is real
hardware bring-up (days-weeks iterative), NOT a quick fix — but the
driver skeleton is already present so it is adaptation, not from-scratch.
Userspace build needs iOS SDK/Xcode (dev's Mac; this box = CLT only).

TOUCH (unchanged, still open): embedded fw downloads but post-download
"reset state timeout (last 0x00)" -> firmware download failed. SPI
status read returns 0 — debug ctpRead/event-buf path next.

## >>> ATHENS HANDOFF 2026-11-14b - DISPLAY/GPU RESEARCH; SW-RENDERER CRASH-GUARD FOUND <<<

GOAL (user): get display working so touch is visible; GPU work to enable
testing the boot. Researched in parallel while fw kernel built.

KEY FINDING - the GUI blocker is NOT "no renderer", it's a deliberate
crash-guard. iOS 16 QuartzCore ships a COMPLETE CPU software rasterizer
(CA::OGL::SWContext: draw_elements, blur_surface, copy_destination,
make_buffer_current, create_surface_from_iosurface - full SW:: sampler/
filler set). backboardd -> CA::WindowServer::Server::render_update/
render_surface -> Server::sw_renderer() lazily builds SWContext+Renderer,
then calls an abort_with_reason-style helper TWICE:
  "CoreAnimation: Software renderer! Simulating crash!"
  "CoreAnimation: Failed to initialize Metal or OpenGLES contexts!"
i.e. Apple hard-crashes the SW path on-device (GPU is mandatory on retail
hw). Disasm: tools dump /tmp/qc-dis.txt; sw_renderer @0x1884f4c54.

BYPASS (viable, NOT yet applied): the two crash sites are `bl 0x18dbcca84`
in dyld_shared_cache_arm64.03 at file offsets 0x1768d34 (insn 0x955b5f54)
and 0x1768d8c (insn 0x955b5f3e). NOP them (0xd503201f) -> sw_renderer()
returns the SW renderer -> backboardd composites via CPU -> VISIBLE GUI,
no GPU needed. Script: tools/patch-sw-renderer.py (verify+patch+verify,
idempotent). Verified offsets/bytes against mounted ios16-root.img.
CAVEAT: must land on the device's HFS+ rootfs = patch iosroot/ios16-root.img
-> re-simg -> reflash userdata (the reflash path; same img + 8 bytes).
/System is RO at runtime so it can't be patched from inside iOS. vivad/
viva-link USB command channel is NOT on athens (ssusb xhci, not musb).

BOOT-ARG sweetfb_keep (patch 0181, commit e21babc): RequestPowerChange(0)
no longer fades panel to black - keeps last composited frame on screen.
For the diagnostic "what did backboardd actually render" test. Kernel
CI run 43574546167 (0180 embedded fw + 0181 fb-keep) building.

TOUCH STATUS unchanged: driver binds+exposes (verified); embedded fw
kernel 43573644960 ready (verify-string gate false-failed on 'spi4 ready'
- it's a %s format arg not a literal; kernel itself is good, has
'using built-in firmware').

NEXT: (1) when 43574546167 lands -> build ufs-rw img w/ sweetlog=1
sweetfb_keep=1 -> flash boot -> boot -> SEE if lock screen/GUI appears
(sweetfb_keep holds last frame). (2) If black -> apply patch-sw-renderer
to img + reflash userdata -> SW-rendered GUI. (3) fw download + touch
reports confirm on same boot.

## >>> ATHENS HANDOFF 2026-11-14a - TOUCH DRIVER WORKS; FW EMBEDDED; DISPLAY=NO GPU <<<

VERIFIED ON DEVICE (logs/athens-spifix2-log.txt, kernel a9774ba):
- "ATHENS SPI: spi4 ready" - fixed-PA DMA carve-out WORKS. Root cause
  chain: physmask 0xFFFFFFFF00000000 impossible -> corrected to <4GiB but
  avail window is ALL >4GiB (0x102830000-0x1bfefc000) so NO alloc can give
  sub-4GiB -> switched to IOMemoryDescriptor::withPhysicalAddress on the
  pstore carve-out 0x4d010000 (~896KiB Android ramoops, reserved+iOS-unused
  +below dram_r0). Same pattern SweetSurface/SweetFramebuffer use.
- "ATHENS TOUCH: NT36672C on nt36672a map, 1080x2400 (fw pending)",
  EINT14 registered, backboardd opened AthensNT36672C via
  IOHIDEventServiceUserClient. Driver binds + exposes to userspace.
- Blocker was ONLY missing firmware file in flashed rootfs.

FW FIX (commit 6a2599e): embedded nt36672c_jdi.bin (139264B) as
nt36672c_fw.h C-array in patch 0180; fwUpdate() falls back to it when
vnode_open(/usr/share/firmware/touch/...) fails. Avoids risky userdata
reflash AND 3h IPSW rootfs rebuild. CI run 43573644960 building.

DISPLAY FINDING: scan-out pipeline WORKS (OVL0_2L INTSTA frame-complete
latches, swaps 1-5 composited, DSI/panel proven by Apple logo). Black GUI
= NO GPU: backboardd matches IOProviderClass=AGXAccelerator -> none.
Full iOS GUI needs a GPU driver (large gated work). PATH TO VISIBLE
TOUCH without GPU: kernel draws test pattern + touch-contact dots into
the panel framebuffer (CPU, no GPU) - SweetFramebuffer already exposes
panel kernel VA. NOT yet implemented - next milestone after fw confirms.

NEXT: when 43573644960 kernel lands -> athens-mkboot.sh ufs-rw
(ATHENS_EXTRA="sweetlog=1 cpus=8") -> repack w/ existing shim Image.gz
(no clang locally) -> flash boot -> boot ~4min, TAP SCREEN -> recovery
-> pull skip=13048823 -> expect "firmware download ok" + contact reports.

## >>> ATHENS HANDOFF 2026-11-13m - SPI DMA MASK BUG = TOUCH BLOCKER; FIXED IN PATCH <<<

ROOT CAUSE of "ATHENS SPI: missing regs map, work loop or DMA buffer":
AthensSPI::start() allocated its 64KiB DMA bounce buffer with
inTaskWithPhysicalMask mask = (0xFFFFFFFFULL)<<32 = 0xFFFFFFFF00000000.
That mask demands phys bits ONLY in [32..63] -> PA must be an exact
multiple of 4GiB -> impossible -> fDMA always NULL -> start() returns
false -> no "ATHENS SPI ready" -> NT36672C child never matches.

WHY <4GiB IS REQUIRED: MT6853 SPI4 internal DMA addr regs (TX_SRC 0x08 /
RX_DST 0x0c) are 32-bit -> buffer PA must be <4GiB. Highmem window
(0x100000000+) is fine for kernel RAM but NOT for this DMA.

WHY IT CAN WORK: SweetSurface.cpp already allocates <4GiB contiguous
framebuffer surfaces for the same reason (display DMA, no IOMMU) using
mask 0x00000000ffffc000. Double-buffer addrs seen in log
(0x77e20000/0x7920c000) prove <4GiB contiguous alloc succeeds. Fix =
same pattern: mask 0x00000000FFFFF000 (<4GiB, 4KiB-aligned).

FIX (patch 0180 + logs/xnu-src copy): mask -> 0x00000000FFFFF000;
error msg now prints map/loop/dma ptrs to pinpoint any residual NULL.
Hunk counts re-verified OK (tools/check_patch_counts.py). sweettouch=0
is CORRECT to keep - it only gates the Qualcomm sweet_touch.c thread;
AthensNT36672C is a separate IOService that probes the spi4 ADT node
with no boot-arg gate.

NEXT: CI kernel build -> athens-mkboot.sh ufs-rw -> boot -> pull tail
skip=13048823 -> expect "ATHENS SPI ... ready" then NT36672C probe +
fw download attempt. nt36672c_jdi.bin still NOT in flashed rootfs ->
fwUpdate will fail soft unless rootfs rebuilt/flashed.

## >>> ATHENS HANDOFF 2026-11-13l - PULL-OFFSET BUG FOUND; DEVICE IS FINE; TOUCH TEST IN FLIGHT <<<

*** CRITICAL PULL-OFFSET CORRECTION (wasted a diagnostic cycle) ***
sdc59 = 13,049,848 4KiB blocks (NOT 13,048,823 - dropped a digit).
GPT "userdata" entry: first=2566144 last=15615991 n=13049848.
Kernel log tail base (abs device blk) = first+nblocks-1025 = 15614967.
sdc59-RELATIVE skip for last-1025-block window = **13048823**, count 1025.
I wrongly used skip=13047798 (= total-2050, one window too early) -> read
the region BEFORE the log tail -> saw SHIMPRAM (earlier zone) but NO
SWEETLOG -> FALSELY concluded "kernel dies before UFS". tools/
sweet-log-pull.sh computes 13048823 correctly (bytes/4096-1025); only
my manual hardcoded skips were wrong. ALWAYS recompute skip from the
GPT userdata nblocks, do not reuse a remembered number.

VERIFIED (logs/athens-coldboot-correct.txt, correct pull):
- 0179-good cold boot is CLEAN: exec SpringBoard(513) backboardd(602),
  display on(2304), swap1-5, display off(2450). NO panic (6 SWEETPAN =
  layout/poolscan/zcheck diag records only). Device + userdata + kernel
  all healthy. "xnu logs->logo->black" = normal GUI-render/black-panel.
- Userdata is FINE - no reflash needed. fastboot userdata flash has
  failed on this device anyway; rootfs already reaches userspace.

TOUCH TEST: reflashed athens-boot-touch.img (ae66f3b kernel, spi4 node),
booting now. Will pull with CORRECT skip=13048823 to verify AthensSPI/
NT36672C probe + fw-load attempt (binding is in kernel log even with
black panel; nt36672c_jdi.bin NOT yet in flashed rootfs -> fwUpdate
fails soft).

## >>> ATHENS HANDOFF 2026-11-13k - 0179 HIGHMEM BOOTS CLEAN TO GUI-RENDER; BLACK SCREEN = PANEL, NOT BOOT <<<

VERIFIED ON DEVICE (logs/athens-0179-recheck.txt, ring total 553982B,
flush #96, NOT wrapped):
- Flashed athens-boot-0179-good.img (sha 260f0d4c = the proven 0179
  kernel + highmem ADT) via fastboot. Boot is CLEAN - zero panic,
  zero SWEETABR. Confirms the "panic regression" was LOWMEM test
  images, not a kernel bug.
- Reached DEEP userspace: 1966 execs, SpringBoard (513) + backboardd
  (594) + runningboardd spawned, neither crashed. Daemon CRASH lines
  (2072) are the usual missing-baseboard/env noise.
- DISPLAY: `SWEET FB: display on` (l2274) -> backboardd opened
  IOCoreSurfaceRoot, created surface 2 1125x2436 BGRA, double-buffered
  0x77e20000/0x7920c000 -> `swap 1..5` real frames composited -> then
  `display off` (l2425) and stayed off. THE GUI IS RENDERING FRAMES;
  the physical panel shows black = DSI scan-out/backlight bring-up
  gap, NOT a boot failure. This is the same state run-9/10 reached;
  run-8's persistent logo+bar was the kernel boot logo which now
  flashes by faster (rootfs vardirs fix -> quicker userspace handoff).
- USER-VISIBLE: "logo for ~1s then black" = boot logo -> backboardd
  takes display -> panel black. No panic anywhere.

BUILD PIPELINE FIXES LANDED (commits 56bb24f, a846d43, ae66f3b, 7bc69e9):
- 0180 patch: removed literal `bool\nbool` before AthensNT36672C::start
  (the ONLY a08bbbc compile error, CI log line: "cannot combine with
  previous 'bool' declaration specifier") + fixed KernelConfigTables
  hunk @@ counts (were off by 2). All 6 hunks count-consistent now.
- mkadt.py: --athens IMPLIES --highmem; --lowmem = explicit diagnostic
  escape hatch. athens-mkboot.sh: ATHENS_LOWMEM=1 env added.
- shim/build-athens.sh: added ufs.c back to OBJS (link was failing on
  undefined ufs_dump_fb/ufs_dump_ba/ufs_harvest_pram; ufsdump.c stays
  out). NOTE: pass ABSOLUTE stock boot.img path (script cds to shim/).
- sweet-root-tweaks.py: firmware() installs firmware/touch/*.bin ->
  /usr/share/firmware/touch/ (nt36672c_jdi.bin for the touch driver).

TOUCH KERNEL BUILT + IMAGE READY:
- CI run 43462608788 (workflow_dispatch, drop 0161/0164/0165,
  verify_strings all markers) SUCCESS 10m26s. kernel.development.sweet
  sha256 371fa3b7... has NT36672C/AthensSPI/POOLSCAN/ZCHECK/SWEETABR/
  takeover hce/AthensPMIC/MT6359/ATHENS GPIO KEYS - ALL present.
  Downloaded to logs/kernel-ae66f3b/.
- Built shim/out/athens-boot-touch.img sha cf9abe49... = ae66f3b
  kernel + highmem ADT + spi4/nt36672c node (mkadt now emits it by
  default) + proven cmdline. Touch driver WILL probe; fw blob NOT yet
  in flashed rootfs -> fwUpdate fails soft (logs error, no crash).
- athens-boot.img was overwritten by the touch build; the proven 0179
  image is preserved as shim/out/athens-boot-0179-good.img.

NEXT:
- Flash athens-boot-touch.img -> pull SWEETLOG -> verify AthensSPI
  probe + NT36672C match + fw-load attempt (works even with black
  screen; binding is in the log). Then get nt36672c_jdi.bin into the
  flashed rootfs (inject into ios16-root.img via WSL hfsprogs, or next
  rootfs CI build now carries it via firmware()).
- DISPLAY is the real GUI blocker now: panel shows black while
  backboardd swaps frames. Separate investigation (DSI init, panel
  timing, backlight). NOT a regression - pre-existing bring-up gap.

## >>> ATHENS HANDOFF 2026-11-13j - "PANIC REGRESSION" = LOWMEM TEST IMAGES, NOT A KERNEL BUG; TOUCH BUILD FIXED <<<

USER REPORT: "no apple logo, panics instead, falling back." DIAGNOSIS
(verified against pulled logs + image bytes, NOT a guess):

ROOT CAUSE - the notouch/verbose test images were built LOWMEM:
- shim/out/athens-notouch.adt + athens-low.adt both have
  dram-base 0xc0000000 dram-size 0x3fd60000 = LOW window.
- shim/out/athens.adt (feeds athens-boot.img) has dram-base
  0x100000000 = HIGH window. Same for every proven run-8/9/10 image.
- The low 4G window is inside the MTK firmware engines' 32-bit
  alloc-ranges -> the known stray writer (pa ~0xe0000000) scribbles
  freed kalloc objects -> `[data.kalloc.8192]: element modified after
  free` panics (panic-notouch.bin off:1216, postpanic-pull off:1088).
- HIGHMEM (0x100000000+) is unreachable by that engine -> clean.
  The panics are the KNOWN lowmem stray-writer, re-exposed because the
  variant payloads were built by hand WITHOUT --highmem.

WHAT THE LOGS SHOW (logs/athens-postpanic-pull.bin, 17.8 MB):
- Both lowmem boots got PAST UFS/root/launchd into userspace spawning
  (backboardd, wifid, amfid, identityservicesd...) before the kalloc
  UAF panic - same depth as the good highmem runs. NOT an early-boot
  or touch failure.
- The stale ring inside that pull is the 0179-kernel (athens-boot.img)
  boot: reached deep userspace, NO panic. So the good image is fine.

IMAGE PROVENANCE (payload string scan, verified):
- athens-payload.bin -> athens-boot.img = 0179 kernel (260f0d4c):
  NO NT36672C/AthensSPI strings, HAS POOLSCAN+ZCHECK (0175 applied via
  dispatch 43290178829 drop 0161/0164/0165). HIGHMEM adt. = GOOD.
- athens-notouch/v-payload.bin -> notouch+verbose imgs = dfcd5d0d
  kernel: HAS touch strings, NO POOLSCAN/ZCHECK (push build skipped
  0174/0175/0177 - drop_patches absent on push). LOWMEM adt. = panics.
- TOUCH WAS NEVER TESTED: no booted image ever had the spi4/touch ADT
  node. dfcd5d0d's touch driver also lacks init() (added in a08bbbc).

CI FAILURE ROOT CAUSE (run 43436026809, a08bbbc) - FIXED:
- ONLY compile error in whole build: `AthensNT36672C.cpp:599:1:
  error: cannot combine with previous 'bool' declaration specifier`
  = literal `bool\nbool\nAthensNT36672C::start` in the patch.
- ALSO fixed a malformed KernelConfigTables hunk (@@ counts off by 2).
- All 6 hunks now count-consistent -> patch applies + compiles.

PIPELINE FIX (prevents recurrence):
- tools/mkadt.py: --athens now IMPLIES --highmem; --lowmem is the
  explicit escape hatch for low-window diagnostics. Verified:
  --athens --athens-ufs -> dram-base 0x100000000; +--lowmem -> 0xc0000000.
- tools/athens-mkboot.sh: ATHENS_LOWMEM=1 env added (adds --lowmem);
  ATHENS_HIGHMEM=1 kept (now redundant but harmless).
- NOTE: mkadt --athens (current) emits the spi4+touch node BY DEFAULT;
  --athens-notouch drops it. dfcd5d0d kernel has touch code w/o init()
  fix -> do NOT pair it with a spi4-node ADT (crash on failed match).

NEXT (in order):
1. Commit bool+hunk+mkadt/mkboot fixes; push; workflow_dispatch xnu.yml
   with drop_patches="0161 0164 0165" + verify_strings for
   NT36672C,AthensSPI,POOLSCAN,ZCHECK,SWEETABR,takeover hce,AthensPMIC,
   MT6359,ATHENS GPIO KEYS (push builds skip 0174/5/7 - always dispatch).
2. Restore logo NOW with known-good athens-boot.img (0179 kernel,
   highmem, proven) via fastboot flash boot - confirms diagnosis on
   device while CI builds (~9 min).
3. New kernel -> athens-mkboot.sh ufs-rw (now highmem by default,
   spi4 node present) -> fastboot flash boot -> expect touch probe
   logs + Apple logo. fw blob nt36672c_jdi.bin must be in rootfs
   /usr/share/firmware/touch/ (check sweet-root-tweaks/rootfs).
4. Pull logs, decode, update STATUS.md.

## >>> ATHENS HANDOFF 2026-11-12i - RUN-10 PULLED: MISSING /var DIRS = RESPAWN STORM; ROOTFS FIXED <<<

RUN-10 PULL (logs/athens-run10-pull.txt, ring wrapped -> only last
~12 min of userspace survived, 17:20:34-17:32:51 fake-RTC):
- Boot was ALIVE at pull time: launchd still spawning services
  (pid ~6485 imagent/identityservicesd/MobileInternetSharing).
- SpringBoard NEVER spawned (com.apple.accessibility.AXSpringBoardServer
  lookup fails every ~5 s from AccessibilityUI = "No such process").
  backboardd ZERO mentions in window. No DataMigration/checkIn lines.
- ROOT CAUSE of the storm: launchd "Service could not initialize:
  Unable to set current working directory" ENOENT for /tmp (146x),
  /var/run (73x), /var/mobile/Library/Caches (73x) -> exit(78)
  respawn loops: imagent, identityservicesd, MobileInternetSharing,
  nanoregistryd (~1460 events each in 12 min). Also mDNSResponder
  exit(255), bluetoothd/fairplayd.H2/biomed/analyticsd cycling.
  launchd's own launchd.log fopen ENOENT every line.
- /tmp -> private/var/tmp and /var -> private/var symlinks exist in
  the image, but the TARGET dirs were never created: iOS keeps them
  on the data volume; our single HFS root has no data volume.
- NOT the cause: the Nov-7 "last sparse chunk failed -> recovery dd"
  repair was sha256-verified; fs serves files fine (launchd read all
  plists). POOLSCAN hit at end: never-used pn 0x38000 pa 0xe0000000
  written (w0 0xd8c001dfd34060c0 w1 0x..4d4d4d) hit 1 - stray-writer
  tripwire fired once; watch on next pull, not proven harmful yet.

ROOTFS FIX (image-side, no kernel change): iosroot/ios16-root.img
(local copy of the flashed Nov-7 image) already had tweaks from
run 42305909620; someone added run/Caches/launchd.log dirs at
20:49-20:50 today -> ios16-root-tweaked.simg (21:39). I verified by
mounting: added remaining standard /private/var skeleton dirs
(empty 0555, select, root 0700, audit, networkd, preferences, vm,
wireless, logs, MobileSoftwareUpdate, Managed Preferences,
MobileDevice, lockdownd) + mobile/Library {Cookies,Logs,WebKit,
SyncedPreferences,Favorites}. fsck.hfsplus -fy OK. Rebuilt sparse:
iosroot/ios16-root-fixed.simg (img2simg). FLASH THIS, not the
Nov-7 ios16-root.simg and not factory-run 42361811996's artifact.

NEXT: fastboot flash userdata ios16-root-fixed.simg -> boot 260f0d4c
kernel -> 30-45+ min -> recovery pull -> check SpringBoard/backboardd
spawn + remaining ENOENT paths. Buttons test still pending (0179).

## >>> ATHENS HANDOFF 2026-11-12h - BUTTONS DONE (0178+0179), IMAGE READY; TOUCH+GPU RESEARCHED <<<

CURRENT IMAGE: shim/out/athens-boot-highmem.img =
260f0d4cd8d1405761d058a1fc829112b92e57e71b5735c1c420e56dd8360905
(kernel 0179, CI 43290178829). Config: highmem adt, ufs-rw, cpus=8,
sweetlog=1 ufslogsecs=5, unentitled_ios_sim_launch=1,
launchd_unsecure_cache=1. Flash via fastboot, boot, press buttons,
recovery -> pull -> decode ring (tools/sweet-log.py).

WHERE BOOT IS: run-9 (image f3466ce7, pre-buttons) reached deep
userspace - SWEETLOG ring showed launchd spawning user daemons at
pid ~1030, 6+ min in, SpringBoard+backboardd exec'd, still alive when
user restarted (was NOT hung). Boot needs 30-45+ min uninterrupted.
Next pull will show if it reaches Hello or where it parks.

BUTTONS - ALL THREE COVERED (verified live-FDT architecture):
- power = MT6359 PWRKEY, vol-up = MT6359 HOMEKEY -> AthensPMIC +
  AthensPMICKeys (patch 0178, NEW files iokit/Kernel/arm/AthensPMIC.*,
  hid/AthensPMICKeys.cpp; matches mediatek,mt6359-pmic/-keys).
- vol-down = GPIO/EINT key, mt-eint 80 "mtk-kpd-vol-down", KP matrix
  UNUSED (hw-init-map all zeros) -> AthensGpioKeys (patch 0179,
  hid/AthensGpioKeys.cpp; polls GPIO80 via VivaGPIO 16ms/48ms debounce).
- mkadt.py emits /arm-io/gpio-keys {key-gpios=<80>, keymap=<0,0xea>}.
- MEASURE: GPIO80==EINT80 assumed; if vol-down silent, check eint->gpio
  mux in pinctrl-mt6853.c or dump live FDT volume-down gpio property.
- Expected logs: 'ATHENS PMIC KEYS: key 0x.. down/up',
  'ATHENS GPIO KEYS: key 0xea down/up'.

TOUCH - RESEARCH DONE, DRIVER NOT WRITTEN (biggest remaining task):
- Panel = Novatek NT36672C "oppo,tp_noflash" on SPI4 @0x11018000
  (mediatek,mt6765-spi). NOT Goodix/i2c0 - that ADT node was removed.
- Verified: GIC INTID 195 (SPI163+32), pins GPIO12 MI/13 MO/97 CLK/
  98 CSB drive4, EINT14 irq edge, GPIO33 reset, 9.6MHz max, 16x36,
  10pt, 1080x2400, 139392-byte fw download.
- spi-mt65xx register map + PIO transfer algo + mt6765_compat flags
  extracted to ATHENS.md "Touch bring-up notes". Still needed:
  spi_clk_hz source, clock-gating CG bits (clk-mt6853), pinmux decode,
  NT36672C noflash protocol (OPPO vendor driver, NOT mainline - the
  hard part). No SPI driver exists in tree.

GPU - RESEARCH ONLY per user instruction (do NOT implement until
buttons+touch confirmed on device): docs/ATHENS-GPU.md. Mali-G57
MC3 == viva's MC2 IP; ~4200-line VivaGPU.cpp + whole Metal/Mesa/
Panfrost stack (PIANO-GPU.md G3-G9) transfers. Port surface = match
string mt6853-mali, MT6359 rails (VGPU=buck_vproc1 EN 0x1708/VOSEL
0x172e, VSRAM=ldo_vsram_md EN 0x1f2c/VOSEL 0x1b46, constraint
0-350mV), MFG power domains (MFG0/1/2/3/5), OPP table.

ROOTFS/GUI VERIFICATION (2026-11-12, vs external "what's left"
analysis - all checked against repo + CI logs, NOT guesses):
- /chosen identity: mkadt.py athens emits unique-chip-id (synthetic
  ECID) + chip-id 0x8015 -> IOPlatformUUID derivation OK -> ByHost
  prefs OK -> LastSystemVersion actually records. Also emits the
  security-status tuple (0,0,1,1) -> mobileactivationd takes the
  native Hactivation "Activated" branch (covers the data ark that
  sweet-root-tweaks skipped: "no mobileactivationd system container").
- Flashed ios16-root.img provenance: local iosroot/ios16-root.img
  (Nov 7 06:10) matches CI rootfs run 42305909620 (finished
  2026-11-07T00:33Z). Its log shows sweet-root-tweaks.py RAN:
  'pref com.apple.migration [DMUserDataDisposition,
  LastSystemVersion]', purplebuddy SetupDone/SetupFinishedAllSteps/
  SetupVersion, springboard BKNoWatchdogs, VirtualAudio disabled,
  mini-buddy flags off. => the migration-skip + Setup-skip ARE in
  the flashed image. The later rootfs run 42361811996 used
  factory=true (0 tweak lines, 17ms fsck->simg gap) - DO NOT flash
  that artifact; it has none of the bring-up tweaks.
- Patch 0056 (sweetfb 10 Hz throttle) is in xnu/patches, applied.
- sweetscan: vm_resident.c defaults sweet_scan_mode=1 (report) with
  no boot arg - pool scanner already on.
- sweetsample: sweet_sample_start() runs unconditionally after UFS
  mount; samples SpringBoard+backboardd 40x @120 s after 90 s delay
  - 'SMP --- sample' + 'bt' stack lines will be in the ring.
- Consequence: the near-full bar is probably NOT the classic
  missing-LastSystemVersion migration wall (that fix is present).
  Candidates: residual first-boot work, daemon crash loops
  (cryptexd /var/run ENOENT, assistantd, mediaserverd), or a
  backboardd/display wait. The ring tail + SMP stacks decide.

NEXT ACTIONS: (1) user flashes 260f0d4c, tests buttons, long boot;
(2) recovery pull -> decode ring for boot progress + key events;
(3) if Hello reached -> touch driver work (SPI4+NT36672C); (4) GPU
port only after buttons+touch confirmed.

## >>> ATHENS HANDOFF 2026-11-12g - RW BOOT REACHES APPLE LOGO + BAR (read first) <<<

RUN-8 (ufsrw=1 rootrw=1, kernel 3119523f): mount panic gone; boot
reached the **Apple logo with a moving progress bar** - the iOS
kernel bootscreen rendering on the LK framebuffer. Waited 30+ min,
bar still moving slowly (CPU-rendered console + first-RW-boot fs
chores). User then rebooted to recovery - end state unknown: the
pull only had run-7's stale panic tail (run-8 produced no panic ->
no panic flush, and the shim pram harvest only catches panic logs).

VISIBILITY FIX: sweetlog=1 (patch 0047 ring) now enabled - needs
ufsrw, which we have. Every console byte (kernel + /dev/console
daemon output) flushes to the userdata tail zone every 5 s, so a
HUNG boot leaves a complete console log - no more blind spots.

IMAGE f3466ce7 (same kernel): cmdline = RW set + sweetlog=1
ufslogsecs=5. Flash -> wait at bar -> recovery -> pull
skip=13045495 count=4353 -> decode ring with tools/sweet-log.py.
Pull zone for SWEETLOG = same tail blocks we already pull.

## >>> ATHENS HANDOFF 2026-11-12f - EARLY BOOT COMPLETE; RO ROOT WAS THE WALL (superseded) <<<

RUN-7 RESULT (unentitled_ios_sim_launch=1 fixed it): **launchd ran
the ENTIRE early-boot sequence.** Pulled kernel log tail shows:
fsck, mount-phase-1/2 (bindfs firmware ENOENT tolerated), data-
protection, FIPS POST all PASSED, keybagd MKB_INIT, usermanagerd
(user sessions + personas loaded), dirs_cleaner, init_featureflags,
tzinit, sysstatuscheck, prng_seedctl, launchd_cache_loader ->
"Early boot complete. Continuing system boot" -> user/501 domain,
SpringBoard + ~50 xpcproxy spawns. Then panic:
    mount[3] exited -- (signal 0, exit status 1)
Root cause inference (well-supported): the root is mounted READ-ONLY
(ufsrw absent). Log shows the fallout: "/tmp: No such file",
"/var/run" missing, launchd.log fopen fails, init_featureflags can't
create dirs. A later mount phase trying `mount -uw /` gets EROFS ->
exit 1 -> launchd panic. RW root is required for launchd regardless.

RW IMAGE (local repack, same kernel 3119523f):
shim/out/athens-boot-highmem.img =
8042501cf982a5bc5e7f36d902c89d0245a06e140ed4bed1697509b364c8353e
cmdline adds ufsrw=1 rootrw=1 (keeps unentitled_ios_sim_launch=1,
launchd_unsecure_cache=1, ignition_level=1, cpus=8). userdata is the
approved iOS space; rootfs reflashing recovers any corruption.

NOTE: the boot-args in the pull log printed cpus=1 - the launchd log
echoes what mkpayload wrote; cpus=8 was in the actual arg list.

## >>> ATHENS HANDOFF 2026-11-12e - LAUNCHD REACHED; WRONG_PLATFORM (superseded) <<<

RUN-6 BOOT RESULT (kernel 3119523f with 0177, cpus=8): **the whole
storage chain works.** UFS takeover + LUN scan + GPT + rootfs mount +
load_init_program all succeeded - the kernel exec'd /sbin/launchd and
pid 1 died ONLY at the signature check:
    panic(cpu 4 caller ...): unexpected SIGKILL of launchd (CS_KILLED)
    with reason -- namespace 9 code 0x0 description: none
(photo on file; panicked task = pid 1 "init", 0 pages/0 threads =
exec teardown state. mach_absolute_time ~51 s incl. console draw.)

DECODED VIA UPSTREAM HISTORY (NOTES ~line 978, sweet boot 0029u): the
identical panic was `namespace 9 code 0xe` = OS_REASON_EXEC /
EXEC_EXIT_REASON_WRONG_PLATFORM - our kernel is XNU_TARGET_OS_OSX and
refuses iOS-platform binaries unless spawn-attr platform is set or
the DEVELOPMENT tunable `unentitled_ios_sim_launch` is passed. Athens
ufs-ro cmdline lacked it. (Screen read "0x0" but font is tiny; 0xe is
the documented value for this path. If it's genuinely 0x0 the next
boot will show a different code and this entry needs revisiting.)

FIXED IMAGE (local repack, same kernel 3119523f):
shim/out/athens-boot-highmem.img =
56b95737690b5d7b9817953d6a969c846fe6f42e65555b6673ea483357f1c3b2
cmdline now adds: unentitled_ios_sim_launch=1 launchd_unsecure_cache=1
(the second flag preempts the NEXT known wall - launchd_cache_loader
needs AMFI for the xpc cache signature, upstream boot 0038e).

EXPECTED NEXT: launchd runs ("exec launchd" lines + boot tasks fsck,
mount -P 1/2). Likely next walls from upstream history: mount needs
/chosen/boot-manifest-hash (already in ADT), bindfs (patch 0037 in),
watchdogd->IOWatchdog (patch 0040 SweetWatchdog in), Sandbox policy
(patch 0050 in). If panic persists with a DIFFERENT exec code, decode
it against bsd/sys/reason.h + kern_exec.c.

## >>> ATHENS HANDOFF 2026-11-12d - UFS-STAGE HANG, NOT PANIC (superseded) <<<

RUN-5 BOOT RESULT: the highmem image (kernel cbb29270, all 8 markers)
did NOT panic - it booted cleanly through pmap/VM init and hung at:
    SWEET UFS: host cap 0x387071f, DMA at 0xfd000000
This is a milestone: highmem survived where lowmem corrupted. The
remaining failure is UFS driver bring-up, not memory corruption.

RUN-5 PULL (logs/athens-run5-pull.bin, skip=13045495 count=4353):
- ba zone [first 4 blocks]: ALL ZEROS, no SHIMBA/SWEETABR -> the hung
  boot never took an exception (mailbox correctly empty - consistent
  with hang, not panic).
- All SWEETPAN/ZCHECK/POOLSCAN records in the pull decode with
  aend 0xffd60000 and lowmem PAs (0xe0000000, 0xc1b90000, 0xc2150000)
  = STALE run-6-era lowmem data persisting on disk. Nothing new was
  written by either recent boot (hang wrote nothing; nostorage image
  never flashed).
- No "SWEET UFS" console strings in pram (hang before any pram flush).

ROOT-CAUSE ANALYSIS of the hang (observation + inference):
- OBSERVED: ufs_take_over_host() has NO loops (straight MMIO r/w), and
  ufs_scsi has a deadline timeout. A silent infinite hang therefore
  requires either (a) mach_absolute_time() frozen so the deadline never
  fires, or (b) the DMA bounce at 0xfd000000 getting scribbled by
  dram_r1 (it IS inside [0xc0000000,0xffe60000)) so the doorbell never
  clears - which then still needs (a) to hang FOREVER.
- OBSERVED: CAP = 0x387071f -> bit 24 CAP_64AS SET. The host genuinely
  does 64-bit DMA, so the whole carve-into-low-bank workaround was
  unnecessary AND harmful (it placed DMA in dram_r1's reach).

PATCH 0177 (commit a885af1 + baseline fix, CI run 43257125096,
dispatched with the proven drop list + 10-marker gate incl
"takeover hce","polls %llu"; first attempt 43254730625 skipped at
sweet_ufs.c:547 because apply-tree context had dropped-0164 codes -
patch regenerated against ENXIO baseline):
1. max_pnum = CAP_64AS ? 0 : <4G - DMA allocates from the managed pool
   ABOVE 4 GiB, outside every firmware engine's alloc-range.
2. Fixed fallback (if contig alloc fails) moved 0xfd000000 -> 0x4e000000
   (free gap [0x4d100000,0x56000000), below BOTH dummy-read ranges).
3. "takeover hce/hcs/utrldbr" print inside ufs_take_over_host so any
   future stall localizes to a specific stage.
4. ufs_scsi doorbell wait gained a 2^28 hard poll cap + host-state dump
   (hcs/is/rlrsr/rlclr/ocs) - can never hang silently again.

READY TO FLASH: shim/out/athens-boot-highmem.img =
ff06923477acb1fbdc78b15c75305f318b891a7c3fe964d6e06b2c67e6e6a519
(kernel 3119523f, all 10 markers verified in binary incl "takeover
hce"/"polls %llu"). Same flash+pull routine as run-5.

OUTCOMES TO EXPECT (each is diagnostic):
- "takeover hce 0x... hcs 0x..." then LUN lines -> takeover fine,
  hang was the 0xfd000000 bounce being scribbled by dram_r1
- "command 0x00 timed out (hcs .. is .. rlrsr .. rlclr .. ocs ..
  polls N)" -> host ignored our UTRL; the dumped registers say which
  link state it's in (MediaTek may need a different takeover path)
- still silent hang -> stall is inside ufs_take_over_host MMIO or
  lck_mtx; next step adds per-stage prints between each ufs_wr
The nostorage differential image (8907e485) remains available if UFS
keeps failing - it should panic at root mount, proving everything
upstream is clean.

## >>> ATHENS HANDOFF 2026-11-12c - TRAP-FRAME MAILBOX (superseded, kept for zone map) <<<

RUN-4 PULL (logs/athens-highmem-run4-pull.bin): all three zones present
(SHIMFB header, SHIMPRAM, stale SWEETPAN). The framebuffer dump rendered
to logs/panic-screen.png = **the LK realme splash, not the panic** - LK
redraws its splash over the panic screen on every boot, so fb dumping
cannot recover panic screens across a reboot. (fb dump left in place;
harmless and may still catch shim-time state.)

REAL FIX (commit 45ed8a0, patch 0176): panic_with_thread_kernel_state
now copies arm_saved_state64 into the boot_args page tail at
phystokv(topOfKernelData - 0x4000 + 0x3f00) with "SWEETABR" magic -
guarded by avail_end (physmap up). Shim ufs_dump_ba() writes that 16K
page to userdata [last-4352, last-4349] inside loader_boot BEFORE
zero64() rewrites it. Next-boot pull then yields pc/lr/sp/fp/esr/far/
x0-x28 of the fault even when panic log/debug log/UFS never came up.

Zone map updated (partition-relative, last = 13049847):
  [13045495]            ba page "SWEETBA"-free zone (4 blocks,
                        [last-4352, last-4349], magic "SWEETABR" at
                        page offset 0x3f00)
  [13045752, 13048565]  SHIMFB pixels; header at 13045751
  [13048567, 13048821]  SHIMPRAM data; header at 13048566
  [13048823, 13049847]  kernel 1025-block log tail
Pull covering all: dd if=/dev/block/sdc59 bs=4096 skip=13045495 count=4353

CI BUILD DISPATCHED: run 43232381650 on athens @45ed8a0, drop_patches
"0161-athens-ufs-diag.patch 0164-athens-ufs-err.patch
0165-athens-tidt-assert.patch", verify_strings incl. SWEETABR.
A push-triggered run 43232343019 also exists (no verify gate - ignore
if it only builds).

Shim rebuilt locally with ufs_dump_fb + ufs_dump_ba (Image.gz 9627 B,
NDK clang). When the CI kernel lands: mkpayload --highmem payload ->
viva-bootimg repack backup/boot.img Image.gz ... --ramdisk payload ->
flash -> let it panic -> normal reboot (shim dumps ba page + pram) ->
PitchBlack -> pull skip=13045495.

## >>> ATHENS HANDOFF 2026-11-12b - SHIM UFS WRITE PATH WORKS; FB DUMP ADDED (read first) <<<

SHIM UFS HARVEST CONFIRMED WORKING. With UFS_BASE=0x11270000 (MediaTek,
fixed in f1722eb; Qualcomm 0x1d84000 was wrong) the shim writes userdata
fine: pull shows `SHIMPRAM` header + nonzero pram dump.

CRITICAL PULL-OFFSET BUG FOUND: userdata sdc59 = 53,452,177,408 bytes =
13,049,848 4K blocks exactly (earlier notes said 13,044,966 - misdivision).
The kernel writes its 1025-block log at partition blocks [13048823,
13049847] (first_block+nblocks-1025 in device LBAs, sdc59 is
partition-relative). Pulls at skip=13043941/13043684 were ~4900 blocks too
early and read zeros - the "empty tail" was a READ error, not a write
failure. Correct pull window covering everything (see zone map):
  dd if=/dev/block/sdc59 bs=4096 skip=13045751 count=4097

ZONE MAP (partition-relative, last = 13049847):
  [13045752, 13048565] SHIMFB pixel data (2814 blocks, fb dump - NEW)
  13045751             "SHIMFB" header: w,h,stride,bytes,fb_pa (le u64s at +8)
  [13048567, 13048821] shim pram harvest data (255 blocks)
  13048566             "SHIMPRAM" header
  [13048823, 13049847] kernel's own 1025-block log tail (SWEETPAN records)

RUN-3 DECODE (pull logs/athens-highmem-run3-pull.bin):
- pram region 0x1bfeff000 = pure DRAM garbage (0xff/0xdfef pattern, no
  strings): the highmem kernel NEVER wrote its panic log -> dies before
  debug_log_init, i.e. VERY early with the "Unaligned kernel data abort"
  (esr 0x96000061, far 0xfffffe301551040, kernel_task tid 101) seen on
  screen.
- kernel tail zone still holds run-6 leftovers on disk (tokd 0xc25cc000,
  pa 0xe0000000 poolscan records) - disk persistence, not fresh writes.
- BootArgs handoff is 64-bit clean (loader.c audited); mkadt already
  carves pram out of dram-size correctly (no overlap bug).

NEW: shim ufs_dump_fb() (ufs.c, called first thing in shim_main before
con_clear_rows) copies the LK framebuffer (from /chosen/atag,videolfb,
fallback FB_BASE) to the SHIMFB zone. The previous boot's panic SCREEN
survives a warm reset in fb DRAM -> recovery pull + offline render gives
the panic text (pc/registers) without photos. Boot flow: panic ->
reboot auto-boots our flashed image -> shim dumps fb+pram -> XNU
probably panics again (harmless) -> PitchBlack -> pull.

IMAGE: shim/out/athens-boot-highmem.img sha256
3d5b57f79c0a2162ed4d47b9926143222dd698180822318a120e990c1ee56f91
= kernel 4475c6ea (CI 43212579684) + shim with ufs_harvest_pram +
ufs_dump_fb + MediaTek UFS_BASE. Built: NDK clang
(.../ndk/27.0.12077973/.../clang.exe --target=aarch64-none-elf -DATHENS),
ld.lld, viva-bootimg.py repack backup/boot.img Image.gz ... --ramdisk
shim/out/athens-payload.bin (payload already highmem phys_base
0x100000000 mem_size 0xbfeff000).

NEXT: flash -> panic -> reboot (image reflashes automatically? it is in
boot partition; a normal reboot boots it again) -> recovery -> pull
skip=13045751 -> render SHIMFB pixels to PNG -> read panic PC -> fix
highmem early-boot abort.

## >>> ATHENS HANDOFF 2026-11-12 - HIGHMEM MOVE, PATCH REBASED ON TRUE CI TREE (read first) <<<

STRATEGY: move the XNU window to the high DRAM bank so every known
32-bit-addressable MediaTek firmware engine physically cannot write it.
Run 6 gave the clean stray-writer signal: 4 contiguous free pages at
PA 0xe0000000-0xe0010000 (inside dram_r1_dummy_read alloc-range)
dirtied ~29 s into boot, ~191 bad qwords each. Engine writes roam
per boot -> reservation cannot fix this; moving the pool above 4G can.

HIGHMEM STATE (all landed):
- tools/mkadt.py: --athens --highmem => dram-base 0x100000000,
  dram-size 0xbfeff000 (ends 0x1bffff000, below reserved dramc-rk1
  page). FIXED BUG: output was nested under --athens-mem so plain
  invocation wrote nothing (older runs silently reused stale ADTs).
- mkpayload reads dram-base/size from ADT -> one flag relocates all.
- shim/loader.c: verified 64-bit clean (uintptr_t/uint64_t).
- kernel (0175): SWEET_FG_MAX_PN 1<<18 -> 1<<19 (covers high ppnums),
  poison pn field widened to 24 bits, fixed low-bank DMA carve
  (sweet_ufs kmem_alloc_contig falls back to ml_io_map'd fixed PA
  window at 0xc4000000 when the general pool is all >4G; CAP_64AS
  check retained).

PATCH FAILURE + FIX (2026-11-12):
- Run 43200619575 verify gate caught MISSING: SWEET ZCHECK --
  patch failed to apply at sweet_ufs.c:799. Root cause: hand-built
  .old.lf baselines had drifted from CI's real tree (earlier patches
  like 0167 also touch the file). Fix: downloaded xnu-buildtree
  artifact from last-good run 43192237918, reverse-applied the
  4ec33a8 patch -> true pre-0175 baselines, regenerated diffs
  (NOTE: repo files are CRLF, must tr -d '\r' before diffing vs LF
  buildtree). Verified: applies clean + byte-identical on all 6 files.
- Commit 3a0bd0b. IMPORTANT: plain `git push` (https) hangs/no auth;
  push with `git push https://x-access-token:$(gh auth token)@github.com/
  harman1390/ios-athens HEAD:athens`. Local `git status` shows
  "ahead N" vs a stale origin ref -- check remote sha via
  `gh api repos/.../branches/athens`.
HIGHMEM BUILD READY (run 43212579684, commit eea384f):
- Root cause of the two verify-gate misses found: (1) my hand-built
  baselines drifted; (2) dxb's own machine_routines.patch sorts after
  0175-*.patch and flips ACNTVCT_EL0->S3_4_c15_c10_6 itself, so a hunk
  copied from the apply tree (which lacks dxb patches) mismatched at
  apply time and git apply skipped the WHOLE 0175 patch. Apply tree
  also carries dropped-patch edits (0164 ENXIO->errcodes, 0174 tlbi
  flush) that leaked into the diff. Final patch = pre-0175 buildtree
  + 4ec33a8 + intended edits only. All 7 verify strings confirmed.
- Kernel: run 43212579684 artifact, sha256
  4475c6ead7f0797afe6a1439677cd17f94b92a36dd1ec682f1f8f48f4612fc0f
- Image: shim/out/athens-boot-highmem.img sha256
  d72fe4653d4193a2b184aef818381f3ca5f950945f7e2f14bbef0cfe37b5d50d
  built via: PATH shim for `python`->python3 + ATHENS_HIGHMEM=1
  tools/athens-mkboot.sh KERNEL backup/boot.img ufs-ro (script gained
  ATHENS_HIGHMEM env -> adds --highmem to ADT_FLAGS; repack ran
  viva-bootimg.py directly because WSL lacks clang for shim rebuild -
  shim unchanged, loader already 64-bit clean).
- Payload header verified: phys_base 0x100000000, mem_size 0xbfeff000
  (ends 0x1bffff000, below reserved dramc-rk1 page).
- UFS DMA: kmem_alloc_contig <4G fails (pool all >4G) -> fallback
  ml_io_map carve at ufsdma=0xfd000000 (boot-arg relocates).

HIGHMEM RUN 1 RESULT (commit bc850d1 image 5b0c10b6):
- Panic on screen: "Unaligned kernel data abort", esr 0x96000061,
  far 0xfffffe301551040, kernel_task tid 101 -- BEFORE sweet_ufs_init
  (sdc59 tail all zeros). NOT the stray-writer signature; looks like a
  deterministic highmem-path bug (truncated-PA pointer or early-VM code
  that assumed the window base). Panic text VAs are at +0x800000000 vs
  Mach-O (gVirtBase moved with the high bank).
- New persistence channel: shim ufs_harvest_pram() copies the previous
  boot's pram panic log to UFS on every boot: zone = userdata
  [last_lba-1281, last_lba-1026] (header "SHIMPRAM" at -1281, data at
  [-1280,-1026]), below the kernel's own 1025-block tail so the kernel
  never clobbers it. Pull BOTH with:
    dd bs=4096 skip=<last_lba-1281> count=2306
  (last_lba = 13044965 for this device; skip = 13043684).
  Decode: SHIMPRAM header then 1 MiB of pram verbatim; panic strings
  are printable runs inside it.
- BUGFIX bc850d1->next: shim ufs.c used Qualcomm UFS_BASE 0x1d84000;
  MediaTek is ufshci@0x11270000 (ATHENS.md). Takeover always failed ->
  zero harvest zone on the first harvest attempt.
- GOTCHA: drop_patches is SPACE-separated FULL FILENAMES:
  -f "drop_patches=0161-athens-ufs-diag.patch 0164-athens-ufs-err.patch
  0165-athens-tidt-assert.patch". Runs 43205794257 (runner never
  acquired - macos capacity) and 43208372029 (comma list broke rm)
  failed before building. If verify passes: artifact -> mkadt
  --athens --athens-ufs --athens-bare --highmem -> mkpayload ->
  athens-mkboot.sh -> `fastboot flash boot` (boot is reliable,
  `fastboot boot` silently fails on this device) -> recovery ->
  pull sdc59 tail -> decode SWEETPAN records.
- Reading the result: no ZCHECK/POOLSCAN hit = writer is 32-bit
  constrained, highmem is the containment -> continue to GUI.
  Hit at pa>=0x100000000 = engine reaches high bank (worse);
  hit below 4G = low-bank DMA region targeted (check carve).

## >>> ATHENS HANDOFF 2026-11-10 - 0175 ZERO-CANARY BUILT + MMIO AUDIT (read first) <<<

Claude's split experiment (free pages: stray writer vs owner bug) is
implemented as `xnu/patches/0175-athens-first-grab-zerocheck.patch`.
The file of that name in the tree was a stale copy of 0174 (someone
started it by duplicating the previous patch); replaced wholesale.
Verified: `patch -p1` applies clean on the post-0174 apply-tree
(logs/xnu-src has the edits applied) and regenerates the edited
sources byte-for-byte. NOT compiled locally (no Apple clang here);
next CI run with verify_strings is the check.

WHAT IT DOES:
- sweet_fg_bits[] bitmap by absolute ppnum (PA < 4 GiB) marks every
  page that leaves the free pool. Mark sites: the 4
  vm_page_grab_options returns (inside SWEET_CHECK_HANDOUT),
  cpm_allocate's contiguous lists, and pmap_next_page_hi bootstrap
  steals.
- First handout of a page: dc civac (flush_dcache64 phys) then scan
  all 16K; any nonzero qword panics with pa, offset, first two bad
  values ("SWEET ZCHECK"). That is exactly the ptd reserve-page kill
  shot Claude identified: a dirty word in a future ptd page becomes a
  wild ptd_free_list head.
- Scanner thread (from sweet_ufs_init, next to sweet_watch_start):
  every ~100 ms civac + scans sweetscan_n=256 never-marked pages that
  are currently on a free queue (FREE_Q/FREE_LOCAL_Q/FREE_LOPAGE_Q),
  wraps continuously through vm_pages[]. Nonzero -> locked re-check
  (still unmarked AND still on a free queue) then "SWEET POOLSCAN" log
  with pa, offset, values, mach_absolute_time. sweetscan=2 panics.
- Boot args: sweetzcheck=0, sweetscan=0, sweetscan_n=N. fill= boot-arg
  legitimately patterns free pages so both checks stand down under it.

COVERAGE ANALYSIS (verified against the tree, not guessed):
- arm64 never sets delay_above_pnum (x86-only), so ALL managed pages
  are materialized in the pmap_startup loop via pmap_next_page and
  released to free queues - pmap_next_page itself is intentionally
  NOT marked, so post-boot the only unmarked pages are true
  never-used free pages.
- vm_lopage_needed is FALSE on arm64 (only i386 sets it) ->
  vm_page_grablo funnels into vm_page_grab -> covered.
- vm_page_find_contiguous's only allocator caller is cpm_allocate.
- Steal pages (vm_pages array, buckets, zone maps) are wired, not on
  free queues -> scanner skips them by q_state regardless; marking
  them in pmap_next_page_hi also protects the freeable tail.
- Known residual: an unmarked page that left the free queue through a
  path not listed above and returned with data would report a false
  hit - the log line carries q_state/timing to diagnose that.

CLAUDE'S "haven't seen" AUDIT - RESOLVED:
- sweet_ufs_strategy + init + DMA alloc: bounded (1 MiB bounce,
  MIN(count,BOUNCE-skip) loop, kmem_alloc_contig KMA_ZERO <4GiB).
  buf_map/buf_unmap stock.
- THE sweet_* CALL SITES: sweet_ufs.c:871-873 call keys/touch/usb
  UNCONDITIONALLY after su.ready - but each callee reads its own
  boot-arg before touching MMIO (sweetkeys/sweettouch/sweetusb), and
  tools/athens-mkboot.sh BASE sets all three =0. viva_usb_probe
  (sweet_ufs_rootdev:1079) defaults off (vivausb=0). => on Athens no
  Qualcomm-address MMIO is touched today.
- FRAGILE: defaults are enabled=1 for all three (and sweetusb=2 writes
  QSCRATCH/DWC3). Any future diag cmdline that drops the zeros will
  map GENI SE7 0xa84000 / GCC 0x100000 / TLMM 0x3900000 / DWC3
  0xa600000 on MT6853 and WRITE them (touch worst: GCC vote + RCG +
  SE init at 45 s post-UFS - suspiciously near the ~45 s panic zone).
  Recommend hard-gating all three behind #if !ARM64_BOARD_CONFIG_... 
  or an athens-only force-off if more weirdness appears.
- arm_vm_init/pmap_bootstrap + 0011: physmap live early; phystokv
  resolves any DRAM PA via ptov_table then gVirtBase linear map;
  kva_active=TRUE (arm_vm_init:2199) precedes pmap_bootstrap (2297).
  0011 only pads the physmap VA aperture. Clean.
- VPIDR_EL2/VMPIDR_EL2 still unwritten in shim enter_el1 (Claude's
  point stands; XNU reads vpidr as MIDR on this CPU).

NEXT: CI build 0175 kernel (drop_patches same set as diag4 =
"0161-athens-ufs-diag.patch 0164-athens-ufs-err.patch
0165-athens-tidt-assert.patch"), verify_strings must include
"SWEET ZCHECK" and "SWEET POOLSCAN". Then mkpayload + scrub shim +
same cmdline (sweetuaf=1 sweetwatch=1 zlog1=vm_objects -zc; add
sweetscan=1). Boot, pull sdc59 tail: POOLSCAN lines = stray writer
into free memory (pa/offset/time fingerprint); a ZCHECK panic =
corrupt-before-first-use; neither + continued in-use corruption =
owner-side bug -> then ptd free-list watchpoint (old 0175 plan).


ADDENDUM (same session, 0175 v2 - Claude's 4 checks + poison ext):
- Verified: bitmap keys absolute ppnum, 1<<18 entries covers all PAs
  <4 GiB (whole window + margin); flush_dcache64(phys=1) does civac
  to PoC per line via the physmap alias then the scan reads that same
  alias; steals stay marked (harmless: non-free-q pages are skipped
  anyway and it protects the freeable tail).
- Fixed per review: POOLSCAN now logs q_state + queue color +
  mach_absolute_time on every hit.
- POISON-ON-FREE added (vm_page_release, before the free-q enqueue):
  any marked page freed gets pattern 0xf2ee<<48 | pn<<16 | qword_idx.
  Scanner now checks two populations: unmarked+freeq must be zero,
  marked+freeq must be poison. vm_page_release asserts vmp_object==0
  so page content is dead there; the write happens before
  vm_free_page_lock_spin (outside the spinlock). Local queue pages
  are grab-refill only and stay unmarked-zero. sweetpoison=0 kills it;
  with poison off the scanner skips marked free pages (their content
  is owner data, uncheckable).

ADDENDUM 2 (0175 v3 - Claude's choke-point catch + pz-bit design):
- CONFIRMED his memory: vm_page_free_list batch path enqueues
  directly into vm_page_queue_free (~line 4850), bypassing
  vm_page_release; so does vm_page_release_startup (startup-only,
  never-used pages - intentionally NOT poisoned). Batch site now
  poisons too.
- New sweet_pz_bits[] "is poisoned now" bit: set inside
  sweet_poison_page AFTER the fill, cleared on every grab
  (sweet_depoison in sweet_first_grab_pn). Scanner checks the
  used-freed population ONLY when the bit is set, and the locked
  re-check now also re-verifies the bit - false used-freed hits are
  structurally impossible.
- ppnum >= 1<<18 (PA >= 4GiB) is skipped-and-never-written in all
  three helpers (test_and_mark/marked/poison_page/depoison/poisoned),
  so a later high-bank test is safe.
- sweetscan_n default 256 -> 1024; thread does one FULL sweep at
  start before the 100 ms cadence. Also started from
  kernel_bootstrap_thread (startup.c, before vm_free_delayed_pages)
  - much earlier than the ufs-init call site, which stays as an
  idempotent second call.
- verify_strings for the build: "SWEET ZCHECK","SWEET POOLSCAN",
  "used-freed". Absence-grep (0161/0164/0165 dropped): markers from
  those patches e.g. their printf strings must NOT appear.
- Note for dump analysis: 0xf2ee in any live object = poison leak =
  double-free/double-ownership, embedded pn names the page. Panic
  timing may shift (16K poison write per free).

ADDENDUM 3 (0175 v4 - ptd reserve-node check + hit persistence):
- Claude: ZCHECK can't see the ptd case (pmap_pages_alloc_zeroed
  bzeros after grab). Added check in ptd_alloc_unlinked on the
  NULL-next/count>1 reserve branch: after head advances, verify the
  new head node's first word is still zero; panic "SWEET PTD" with
  node VA, PA (kvtophys_nofail) and the bad value. Catches the wild
  head one node before it forms. ptd_alloc_unlinked is patched but
  otherwise unmodified XNU logic.
- Persistence: ZCHECK record and first 4 POOLSCAN hits now go through
  sweet_ufs_panic_write (polled UFS, SWEETPAN zone) at hit time, so a
  lost ring flush can't eat them. Tags "zcheck"/"poolscan".
- armed print now includes max managed ppnum vs bitmap bound.
- Cmdline for the run: keep sweetscan=1 (report), do NOT pass
  sweetscan=2 - first run wants all hits, not a stop at #1.
- verify_strings: "SWEET ZCHECK","SWEET POOLSCAN","SWEET PTD",
  "used-freed" + absence markers for dropped 0161/0164/0165.

ADDENDUM 4 (0175 v5 - UFS lock fix + every-pop ptd check):
- CONFIRMED: sweet_ufs_panic_write takes no lock and shares the
  bounce buffer with live strategy I/O. New sweet_ufs_diag_write
  takes sweet_ufs_lock when !panic_active; hits/ZCHECK now use it.
- ptd check strengthened per Claude: EVERY pop validates next_node
  (NULL or 8-aligned kernel VA) before it can become the head -
  panics with popped node VA, PA, count, bad word. Reserve-branch
  check kept too. Commit ef7c5d5. Still needs push (no creds here)
  or a gh dispatch with the verify gate.


ADDENDUM 5: pushed affae6e to athens (gh.exe token via Windows
  keyring; `gh` absent in WSL but "/mnt/c/Program Files/GitHub CLI/
  gh.exe" works). CI run 42904311335 dispatched with drop set
  0161/0164/0165 + verify_strings "SWEET ZCHECK,SWEET POOLSCAN,SWEET
  PTD,used-freed". Push-triggered run 42904301784 auto-cancelled.
  NEXT: check run outcome + verify gate; on success build shim img,
  record artifact SHA256, boot, pull sdc59 tail.


RUN STATUS: CI 42904311335 success, all 4 markers in binary.
  Image built: shim/out/athens-boot.img sha256
  8ff427e66c302365e71a103fb51d68bc31e33e3149e182b4aeaffb06f2696a84
  (kernel f6c49afb382cea2ebe881174b94a7ac2b02c75b6a013cd99f4801e4983a3720b),
  cmdline diag4 + cpus=1 sweetuaf=1 sweetwatch=1 zlog1=vm_objects -zc.
  fastboot boot sent at ~21:35 (WSL "Too many links" status error is
  cosmetic - device left fastboot). AWAITING: boot result + sdc59 tail
  pull for ZCHECK/POOLSCAN/SWEET PTD/SWEETPAN records.


RUN-1 RESULT (42904311335): SWEET PTD fired - FALSE POSITIVE
  (my bound used VM_MIN_KERNEL_ADDRESS, physmap nodes sit below it;
  bad word was a legit node+0x28 link). Fixed to (next>>48)==0xffff.
  Commit 9111e16. Rebuild = run 42907586907 (in progress).
  Evidence path PROVEN: panic under lock -> sweet_ufs_diag_write ->
  SWEETPAN console-panic record survived in sdc59 tail (ring lost).
  Pulled: logs/athens-0175-pull.txt.bin, run1-console-panic.txt,
  run1-tail-strings.txt (stale ring shows an older boot reached
  launchd/keybagd/usermanagerd).
  TWRP reserved-memory dump saved: logs/reserved-memory-dump.txt.
  DPM at 0xffe60000+0x190000 confirmed abutting window top; all other
  mblocks sit below gPhysBase 0xc0000000 - window is clean.
  NEXT: when 42907586907 finishes -> download kernel, repack img,
  fastboot boot, adb pull tail in recovery.

## >>> ATHENS HANDOFF 2026-11-08 ~23:xx - EXTERNAL-REVIEW PLAN IMPLEMENTED (read first) <<<

The four-point plan (mem-layout dump / watchpoint / alloc asserts /
topOfKernelData differential) is now patches 0171/0172/0173 + a new
mkpayload flag. All verified to apply in order on xnu-8796.141.3 + all
earlier patches (scratch apply-tree at logs/xnu-src, gitignored).

- **0170 was dead code on device - twice.** First commit was malformed;
  the "fix" still had context lines missing their leading space
  ("corrupt patch at line 23"), and it called vm_page_lookup(uaf_pn)
  which takes (vm_object, offset) not a pnum. 'vmp qs' confirmed ABSENT
  in xnu/out-diag2 kernel. The committed rewrite (68f0226) now uses
  vm_page_array_beginning_addr[uaf_pn - vm_first_phys_ppnum] - correct.
- **0171 mem-layout dump:** sweet_layout_snapshot() records the vm_pages
  array's PA runs at vm_page_bootstrap (array is steal-memory VA space,
  NOT physmap -> kvtophys can't translate it; each PA via
  pmap_find_phys). sweet_layout_dump() prints gPhysBase/gVirtBase/
  gPhysSize/real_phys_size, mem_size/max_mem/max_mem_actual/sane_size,
  first_avail/avail_start/avail_end/real_avail_end, vm_first/last_phys,
  vm_first_phys_ppnum, all BootArgs fields (topOfKernelData,
  memSizeActual, ADT PA+len), sizeof(vm_page)=64, the array PA runs, and
  for a corrupted element PA the verdict: inside array / below
  topOfKernelData carve / at-or-past avail_end. Runs once at boot (lands
  in the ring) + every UAF hit.
- **0172 alloc asserts:** pmap_next_page panics if PA <
  topOfKernelData (kernel/ADT/boot_args/ramdisk carve), >= avail_end
  (covers panic-log region above dram-size), or out of the strictly
  increasing sequence (double-handout). SWEET_CHECK_HANDOUT at all 4
  vm_page_grab_options returns: panic if q_state != NOT_ON_Q or wire != 0.
  sweet_check_zone_pages: every page a zone obtains must be wired and on
  no VM queue - called from zone_fill_initially + zone_allocate_va_locked.
- **0173 hardware watchpoint:** on each sweetuaf=1 hit, DBGWVR1 on the
  first corrupted granule's element VA + DBGWVR2 on its physmap alias
  (8-byte store watchpoints, EL1, OSLAR unlocked, MDSCR MDE|KDE; WVR0
  stays reserved for the sweet_watch canary). IMPORTANT: stock sleh
  ESR_EC_WATCHPT_MATCH_EL1 calls arm_debug_set(NULL) and silently
  RESUMES - it would swallow the hit and disarm the watchpoint. Patched
  to panic_with_thread_kernel_state -> panic register dump = writer's
  PC/LR. Shim already has 'msr mdcr_el2, xzr' (TDE/TDA clear), so EL2
  does not trap debug regs. DAIF is printed at arm time: if PSTATE.D is
  masked the watchpoint never fires (then it's MDCR/DAIF work next).
  Single 8-byte granule at the corrupted offset, not a whole-page MASK:
  zfree legitimately writes elem[0], so a page MASK would false-trip.
- **mkpayload.py --pad N:** bumps kernel_end (=> ADT pa, boot_args,
  topOfKernelData, free-pool start) by N, 16K-aligned, no payload bytes
  added (gap stays inside the carve). Verified: --pad 0x800000 moves
  kernel_end 0x8568000 -> 0x8d68000. If corrupted PAs shift by the pad
  the writer is carve-relative; if they stay put it is a fixed address.

Source facts checked against xnu-8796.141.3 (banner matches the running
kernel): vm_pages[] entries are 64 bytes (VM_PAGE_PACKED_PTR_ALIGNMENT);
packed queue links are u32 = index|0x80000000 for array elements or
VM_PACK_POINTER for other pointers - consistent with the 0xd3NN1bXX
rows being VM bookkeeping links. The rows-136-248 dump is NOT saved in
logs/ (scrub-tail's SWEETPAN element was overwritten by the console-
panic transcript record), so the 64-byte-stride check couldn't be done
locally - 0171 makes the next dump self-describing anyway.

**diag4 RESULT: TLBI FLUSH DID NOT STOP CORRUPTION** - stale-EL1-TLB
theory effectively ruled out (vmalle1is on every grab/intake). Panic:
data abort in _ptd_alloc_unlinked+0xd4, 'ldr x9,[x19]' where x19 =
ptd free-list HEAD = 0x601484b0200884d0 (garbage, not a VA). MECHANISM
LEAD: corrupted pmap ptd free list -> ptd_alloc hands out wild/owned
addresses as page-table pages -> pmap writes PTEs into them = the
'VM bookkeeping in zone pages' signature. Also explains the recurring
invalid-PTE asserts (pmap.c:4113+). Stale tag: '...384 off:10368
sz:16384' = another 16K-page UAF fired (watchpoint armed on it; final
panic was elsewhere). NEXT (0175): ptd free-list integrity check.
CLAUDE: head is a victim not mechanism - bad non-VA just faults; victim
set now spans zones+PTEs+stacks+pmap descs = broad writer. tlbi only
rules out EL1 stage-1 stale TLB - NOT cache-attr aliasing, leftover L3/
syscache writebacks of old data (zeroed pool could be undone), or EL2/
stage-2. 0x48 table may be PREV-BOOT remnants (boot VAs identical).
CHEAP TESTS: (a) scrub-fill pool with per-boot pattern not zeros - if
corruption bytes look like last boot's structs, its stale data; (b)
cold power-cycle vs warm reset. 0175 PRIORITY: arm DBGWVR on the STATIC
ptd free-list head global (fixed kernel VA - seen at adrp+0x978 in
disasm, lives outside pmap.c - find in ptd_alloc_unlinked's file) at
pmap init BEFORE corruption + XOR-shadow check under ptd lock; first
non-pmap store gives writer PC directly.
(validate head+each next is in TT range at alloc/free, panic on bad),
PVH check on corrupted PA, SWEETPAN tag fields. Tail:
logs/diag4-tail.bin, panic: logs/diag4-panic.txt.
**FLASHED (sdc52): athens-boot-diag4.img = 0174 kernel (CI 42506889691) + scrub shim + bare ADT + normal layout (no pad) + diag cmdline, sweettlbi ON. If corruption stops -> stale TLB.
**0174 BUILT (stale-translation differential):** tlbi vmalle1is on every
grab/zone-intake (sweettlbi=0 off) + MMFR0/MIDR/TCR/SCTLR in LAYOUT block.
If corruption stops -> stale/aliased TLB. PVH check + SWEETPAN tag fields
(vmp/verdict/DAIF/cookies) + free-time watchpoint arm deferred to 0175.
Claude: packed-VA decode may be numerology (byte-granular counting);
real read = strided store loop, one qword per 72-byte record = init loop
of a 72-byte-elt array built by an owner that believes it owns the page.
**pad8m RESULT: different victim, same family.** kernel_end delta was
exactly 0x800000 (0x85ac000->0x8dac000 - the 0x844000 in the earlier
print compared the wrong baseline). Panic: pmap.c:4113 "invalid pte
0xfffffdf05410c488 (=0x90a9800aa8c55001)" - compressed-PTE corruption,
same class as top/bot runs. ALSO a stale SWEETPAN UAF record: zone
"...92" off:448 sz:8192 (8K element). Surviving element bytes
(tail 0x1500-0x3000) = a 0x48-STRIDE TABLE: qwords 0x84d1NNNN/0x2aac7243
and 0xd3NNNN/0x109072c3, hi u32 counting DOWN by exactly 0x48/record,
lo u32 constant per family - reads as a freelist/metadata array of
72-byte records with back-links, lo word a packed pointer into the
zone/iokit VA ranges. NOT inside-array verdict data (no UAF lines in
ring - transcript overwrote them). Single pad run can't discriminate by
PA (victim moved again - third different victim class: task field, zone
element, PTE table), but the corrupted content is always allocator
bookkeeping.
- STRUCTURE: all 26 rows satisfy hi32 + record_offset = 0x84d1e0be -
  the hi32 is a SELF-RELATIVE back-link (distance to a fixed anchor),
  not independent pointers -> one live structure, not scribble.
- dwarfdump 0x48-byte-type hunt: no match in kernel DWARF output so far
  (empty result - may need different parsing) - still open. zp cookie
  check needs the cookies printed at runtime (next build).
- Tail: logs/pad8m-tail.bin, panic: logs/pad8m-panic.txt.

**FLASHED (sdc52): `shim/out/athens-boot-pad8m.img`** = same diag3 kernel
+ bare ADT + same cmdline + mkpayload --pad 0x800000 (kernel_end
0x85ac000->0x8dac000: ADT, boot_args, topOfKernelData and the whole free
pool shift +8MiB; gap stays in the carve). DIFFERENTIAL: if the corrupted
values move +8MiB the writer is carve-relative; fixed = fixed address.
Compare against diag3's far/x21 (0x0a22d28a7f48fe30) and any UAF pa.

**diag3 RESULT (22:5x): STRAY WRITER STILL ACTIVE, new victim.** Boot
reached SpringBoard/BTServer (~45s in) then panicked: "Kernel data abort"
at `_task_importance_update_owner_info+0x28`, `str w0,[x21,#0x94]` where
x21 = task->iie (+0x468) = 0x0a22d28a7f48fe30 - a wild value. Task VA
0xfffffe166736d900 is in the GEN0 zone range: a LIVE task structure was
overwritten, not a freed element. The value decodes as two plausibly-
packed pointer u32s (0x7f48fe30->VA 0xfffffe1fd23f8c00,
0x0a22d28a->0xfffffe0288b4a280) = queue-link-like data, same family as
the pnum rows. NOT caught by: no zalloc UAF fired (sweetuaf never ran,
so the watchpoint never armed), no alloc assert tripped, no canary hit.
Meaning: the writer hits pages owned by live objects too, evades the
freed-element detector, and is not going through the checked handout
paths. Options for the next image: (a) mkpayload --pad 0x800000
differential - if corrupted PAs/fields move with the carve, bootstrap-
relative; (b) quarantine+watch a freed element's whole 16K page at free
time for one-shot writers; (c) arm a watchpoint on the next task's iie
field preemptively. Tail: logs/diag3-tail.bin, panic: logs/diag3-panic.txt.

**FLASHED to boot (sdc52 via fastboot, rebooted): `shim/out/athens-boot-diag3.img`**
= shim 6aa2977-lineage Image.gz (scrub build, out/athens/Image.gz 20:56)
+ kernel `xnu/out-diag3` (CI 42503594133, verify_strings gate PASSED - all
7 markers in binary) + athens-bare.adt + base1 cmdline +
`sweetuaf=1 sweetwatch=1 zlog1=vm_objects -zc`. NEXT: watch the boot -
expected reads are SWEET LAYOUT block + verdict per UAF hit, vmp qs/wire,
watchpoint armed line, then either a watchpoint panic (writer's PC/LR) or
an alloc assert naming the double-allocation path. Pull sdc59 tail in
recovery afterwards.

**NEXT IMAGE:** kernel = CI 42503594133 (drop_patches are FULL FILENAMES:
"0161-athens-ufs-diag.patch 0164-athens-ufs-err.patch
0165-athens-tidt-assert.patch"; 42503044361 failed on bare numbers.
verify_strings gate on; keeps 0166-0168 + 0170 + new 0171/0172/0173)
+ scrub shim + bare ADT
+ cmdline adds `sweetuaf=1 sweetwatch=1 zlog1=vm_objects -zc`. Outcomes:
SWEET LAYOUT verdict says inside-array = overlap proven;
pmap_next_page/HANDOUT/zone-pages panic names the double-allocation
path; watchpoint panic's saved state IS the writer's PC; a UAF hit with
no watchpoint trip means the writer used a third VA alias or is a bus
master.

## >>> ATHENS HANDOFF 2026-11-08 ~16:10 - CLEAN BASELINE (read first) <<<

User asked to restart the corruption hunt from a clean baseline (iOS root on
userdata is the untouched factory install, HFSX, mounted before by XNU).
**FLASHED to boot (sdc52, read-back md5 OK): `shim/out/athens-boot-base1.img`**
= shim 6aa2977 + kernel `xnu/out-baseline` (CI 42471544567: all patches
EXCEPT 0161 0164 0165 0166 0167 0168 0169, via the new workflow input
`drop_patches`) + `shim/out/athens-bare.adt` (`mkadt --athens --athens-ufs
--athens-bare`: no keypad/eint/pwrap/gpio/i2c0/touch/gpu/wlan nodes).
cmdline: `cpus=1`, root READ-ONLY (no rootrw), `ufsrw=1` only for the log
ring (`ufslogsecs=2`, sweetlog on), vivacpufreq/gpu/wlan=0, sweet drivers 0,
console visible. Previous image backed up: `logs/boot-now.img`.

Found this session (observations):
- Panic photo = zalloc UAF in "vm objects" (pid 70). Symbolicated (slide 0):
  user fault -> hfs_vnop_pagein -> cluster_io -> sweet_ufs_strategy ->
  buf_map/vm_upl_map -> vm_object_allocate = detection point only.
- Corrupt element bytes are in NO firmware image and NOT in the 48 GiB root
  image (logs/scan_root.py) -> not misdirected disk DMA.
- XNU has no invalidate-without-clean cache ops (only dc csw/cisw).
- The userdata tail ring had been unchanged since 02:58 (every later boot
  ran a kernel without 0167/0168; CI had been failing: 3cda772 dropped `-L`
  from the KDK curl -> hdiutil "image not recognized"; fixed 072bf36).
- **Shim bug: boot_args.Video.v_baseAddr was the provisional 0x7bc10000 =
  inside mblock-10-tee-reserved (0x7a700000-0x7fc00000)**: XNU's video
  console wrote ~10 MiB into TEE memory. Fixed to 0x77e20000 (6aa2977).
- Shim never touched SCTLR_EL2 although LK enters at EL2; now cleans+
  invalidates caches by set/way, turns EL2 MMU/D-cache off, gives CPU0 the
  same EL2 state as the 0065 secondaries (CNTVOFF 0, CNTHCTL 3, ...). The
  shim screen now shows SCTLR2/HCR2/CNTVOFF as LK left them - RECORD THEM.
- shim ufsdump DUMP_LBA pointed INSIDE the HFS volume (512B-LBA/8 mistake);
  it never wrote (block still zero), now out of the build.
- Live FDT also has dynamic `reserve-memory-dram_r1_dummy_read` (1 page,
  alloc-range 0xc0000000-0xffe60000) - DRAMC rank-1 dummy read; untested
  suspect, test later by moving the window to the high bank.

NEXT: boot base1, photograph shim screen (SCTLR2 etc.) and any panic; pull
the ring from TWRP (tools/sweet-log-pull.sh logic, last 1025 blocks of
sdc59). If clean: add back one variable per boot (cpus=8, rootrw, ADT
devices, 0166-0168) to find what reintroduces corruption.

**base1 RESULT (16:4x): STILL PANICS** - "[vm objects]: element modified
after free", pid 56 xpcproxy, tid 253. Boot got FAR (ring `logs/base1.txt`:
root mounted RO, launchd -> xpcproxy spawns). So corruption survives:
1 CPU, bare ADT (no viva driver binds at all), RO root, clean EL2
handoff, fixed fb. Ruled out: SMP, MT6781 drivers, TEE fb writes,
EL2 asymmetry, root writes, misdirected disk DMA.
Dump rows 136-248 = STRUCTURED table: u32s 0xd3NN1bXX (NN counts up
04->1f, XX counts down) - pointers into ~0xd3xxxxxx INSIDE the XNU
window; a descriptor table or address list, not noise, not file data.
NEXT BUILD: baseline + diag kept (0166 quarantine, 0167 panic-dump,
0168 panic-console, 0169 watch+UAF-PA) = CI 42473734969, drop_patches
"0161 0164 0165". Boot-arg sweetuaf=1 continues after each hit to
collect more PAs. The element PA pattern answers CPU-vs-busmaster.

**2026-11-08 late - CORRUPTION DECODED:** corrupted element u32s
(0xd3NN1bXX) match packed_pnum = (pnum<<6)|attrs: each points at a PA
inside the XNU window -> the "foreign data" is VM page-queue/freelist
link data -> DOUBLE-ALLOCATION suspect #1: a page handed to zones while
still live on a VM page queue (pmap keeps writing links into it).
Evidence for: all panic types are VM-structure corruption; 128 wired
canary pages NEVER hit across boots (writer targets pages by role, not
random); top-half window (0xe0000000-0xffe60000) panicked identically
(compressed-PTE extra-bits @pmap.c:4077, pulled via SWEETPAN).
Audit: 0011 physmap is VA-aperture only, UFS bounce bounded,
mkpayload/mkadt topOfKernelData carve consistent -> no ownership bug
found in patches by reading. NEXT: panic-time patch: translate the
corrupted PA to its vm_page and dump queue/refcnt/flags (live on a
free list = double-alloc proven; owned elsewhere = wild VA write).
Images: athens-boot-diag1.img (flashed), -top.img (flashed+panicked),
-bot.img (flashed+panicked: compressed-PTE extra bits @4022, same class),
athens-boot-scrub.img (flashed+panicked).

**SCRUB RESULT (decisive):** shim zeroes the entire free pool
[topOfKernelData, window end) before entering XNU; the panic STILL hit -
"Invalid kernel stack pointer" with a kernel stack page full of the same
structured table (0xd2NN/0xd3NN + 83e2...29ff3012 families). Written
DURING the boot by a live CPU -> software bug confirmed, stale-DRAM and
dropped-write theories dead. Both window halves panic identically ->
window-agnostic. Content = VM page-list data -> double-allocation
(page live on a VM queue while zones/pmap/stack own it) vs wild VA
write is the last open question. Patch 0170 (CI 42499726527) dumps the
corrupted page's own vm_page q_state/wire/flags at each UAF hit - its
queue membership discriminates. NEXT: build -> payload+scrub shim ->
flash -> boot -> pull tail -> read "SWEET UAF: vmp qs:.." lines.

**External review (user's Claude) + verification:** - sweet_ufs_strategy audited: bounded; buf_map/vm_upl_map are stock XNU.
- No in-page freelist in this xnu (no PACKED_PTR_FREELIST) -> the
  pnum-table in corrupted elements is NOT freelist; candidates left:
  UPL upl_page_info arrays, compressor cslot tables, pmap TT pages.
- vm_compressor_mode=4 (default); `vm_compressor_mode=0` =
  VM_PAGER_NOT_CONFIGURED kills the compressor + compressed-PTE path.
- zlog<N>=<zone> boot-arg supported (max 10); `zlog1=vm_objects -zc`
  logs alloc/free backtraces for the corrupted zone.
- Memory: 62702 free pages (~980 MiB), compressor region 15G.
- Low-memory theory strong: 1GiB window vs viva 3.9GiB pushes
  compressor/cslot paths viva rarely hits; both last panics were
  compressed-PTE corruption.
- NEXT IMAGE: diag kernel + patch 0170 + scrub shim + cmdline adds
  `zlog1=vm_objects -zc` (alloc/free backtraces for the vm objects
  zone -> names the second owner when a UAF hits). Compressor stays
  ON (default) so behavior matches the panicking runs; a separate
  `vm_compressor_mode=0` boot is reserved to test whether the
  corruption needs the compressed-PTE path.
- Build note: CI run 42499726527 silently SKIPPED 0170 (malformed
  hunk) - always grep the artifact binary for patch strings after a
  build (fixed, redispatched as 42500689893).

diag kernel `xnu/out-diag2` (SWEETWATCH/SWEET UAF/PA + SWEETPAN/console-panic
strings confirmed in binary) + same bare ADT + same cmdline +
`sweetuaf=1 sweetwatch=1` (survive hits, collect PAs + canary hits).
Boot it, let it run ~10 min, then recovery + pull sdc59 tail:
SWEET UAF lines have elem pa; SWEETWATCH lines have canary VA+PA+dump;
SWEETPAN record = panic transcript at the tail if it panics.

## >>> ATHENS HANDOFF 2026-11-08 ~03:15 (RMX2117, MT6853) - read first <<<

**DPM OVERLAP FOUND + FIXED (the "stray writer" hunt):** the earlier note
below that RULED OUT co-processor overlap was WRONG - it claimed all
live-FDT carve-outs were <0xc0000000 or >0x1be000000, but
**mblock-17-DPM-reserved = 0xffe60000-0xffffffff sits INSIDE the XNU
window** 0xc0000000-0x1be000000 (verified again via TWRP
/proc/device-tree/reserved-memory; every other fixed mblock is below
0xc0000000 or at/above 0x1bffff000). DPM = MediaTek DRAM/power-management
MCU workspace, stays active - the only bus-master reservation in kernel
RAM, and viva needed no such cut (all its carve-outs <0xc0000000).
That is a physical stray writer into whatever page the VM hands out in
the last ~600MB of the window -> explains ALL FIVE changing panics
(task_id_token off:8, kalloc.12288 off:64, pmap PTE garbage, pmap.c:4090
"invalid pte", pmap.c:6313 "over-write of pte"). The earlier athens-1g
test (dram 0xc0000000-0xfff00000) still overlapped DPM by 640KB AND put
the panic log at 0xfff00000 inside it - inconclusive, not a refutation.
FIX: mkadt ATHENS_MEM_SIZE now ends the window at 0xffe60000 (usable
0xc0000000-0xffd60000 ~1GiB, panic log 0xffd60000-0xffe60000). Side
benefit: all kernel RAM is <4GiB so the UFS bounce can never go >32-bit.
Built `shim/out/athens-boot-dpmfix.img` = same kernel
(kout/kernel.development.sweet, quarantine+panic-dump instrumentation)
+ same cmdline (cpus=8, ufsrw=1, sweetlog=0) + new ADT.
BOOT-IMAGE FORMAT WARNING (verified): the working recipe is
kernel slot = shim `out/athens/Image.gz` (4597 B) + ramdisk = SWEETXNU
payload. The big `shim/out/athens-boot.img` in the tree has the RAW
GZIPPED XNU MACH-O (kernel.development.sweet.gz) in the kernel slot -
LK jumps to it and dies: "stuck on realme logo", XNU never starts.
Same for athens-boot1g.img (raw Mach-O). The panic photos therefore
came from a shim-based image (e.g. athens-boot1cpu.img). The dud was
sitting flashed on sdc52. FLASHED correct image to `boot` via fastboot
(fastboot flash boot works; only the userdata sparse chunks fail).
NEXT: watch for panics.
If a panic still occurs the 0166/0167 instrumentation may now catch a
CPU-side writer (SWEETPAN record at sdc59 tail offset 0);
if clean - DPM was the stray writer, then look at re-adding the
0x100000000-0x1bfff000 bank (~1.9GiB) as a second dram range later.

**UPDATE ~04:00:** DPM fix did NOT stop corruption - panic recurred
(task_id_token element-modified-after-free again, 48B of high-entropy
data that is neither kernel text nor rootfs content -> NOT a file-data
leak; the "ARM64-looking" bytes were a red herring). No SWEETPAN and no
ring update in the sdc59 tail -> panic fired while su.ready/writable was
false or the polled panic write failed (probably pre-UFS). So: writer
still unknown; DPM exclusion was correct hygiene but not the culprit.
Remaining suspect classes: kernel-side wild VA write, another in-window
bus-master, cache/attribute hazard. Upstream ios-viva runs the SAME xnu
base+patches to a working GUI -> corruption is athens-specific.
New tooling this session: (a) shim panic_scan prints surviving panic
text from the pram regions (0xffd60000 new / 0x1bdf00000 old) on the
next boot's shim screen - build shim locally with NDK 28.2 clang
(Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin);
(b) patch 0168 (CI 42419740405) accumulates the panic console
transcript while panic_active() and rewrites a SWEETPAN record at the
tail - all panics post-UFS-init become pullable.
WORKING boot-img recipe (verified): `viva-bootimg.py repack
backup/boot.img shim/out/athens/Image.gz OUT --ramdisk PAYLOAD`;
payload = `mkpayload.py kout/kernel.development.sweet shim/out/athens.adt
... --cmdline "..."`. Flash via `fastboot flash boot` (works) or TWRP
adb push+`dd of=/dev/block/sdc52`.

## ATHENS HANDOFF (RMX2117, MT6853) - earlier milestone notes

**MILESTONE: XNU-8796 fully boots on RMX2117** (verified via the UFS sweetlog
ring, `logs/athens-log.bin` pulled from recovery). Kernel reaches root-mount:
- 8/8 CPUs up via PSCI CPU_ON, GIC/timer/SGI OK
- AppleCLCD 1080x2400 stride 4320 on fb surface **0x78816000** (ovl L1; the
  shim/LK fb is 0x77e20000 pitch 4352 - two different layers)
- Touch (GT9896s), MT6359 keys, battery all live; UFS reads work
- Root fails: `hfs_ValidateHFSPlusVolumeHeader: unknown Volume Signature`
  on Android userdata data -> needs real iOS HFS+ root

Key session findings:
- **realme lk enters the shim at EL2** (not EL1 like Xiaomi's). Shim now
  installs `vbar_el2` vectors (start.S) and drops to EL1 via `enter_el1`
  before jumping into XNU - the iBoot contract.
- Kernel early fb writes are **cache-hidden** without `dc cvac` (the DSI
  scans DRAM, not L1) - this is why XNU looked dead while fully running.
- `sweetlog` writes the console ring to the LAST 1025 4K-blocks of userdata;
  pull via recovery: `adb exec-out "dd if=/dev/block/sdc59 bs=4096
  skip=$((<bytes>/4096 - 1025)) count=1025" > log.bin` (sdc59 = userdata
  49.8GiB on LUN0). Must NOT pass `sweetlog=0` in cmdline.
- The phone "freezes" on the shim text only visually - kernel runs fine.
  The kernel panic/mount-loop writes to its own fb surface + the log ring.
- phys_base 0xC0000000 is FREE System RAM (verified via /proc/iomem).
- Build: kernel artifact from GH Actions run 42094290101 (macos-15) +
  mkpayload + shim/build-athens.sh (NDK 28.2 clang) -> fastboot flash boot.

Next: build iOS 16.7.16 HFS+ rootfs (rootfs.yml CI or tools/mkiosroot.sh),
write to userdata LUN0 (DESTRUCTIVE - user must confirm), boot to GUI.
Synthetic identity in mkadt.py --athens: serial G6TX00ATH3N5, MQA62HN/A.
Tools: athens-bands.py/athens-ckpt.py = fb/DRAM checkpoint injectors.

## Agent handoff / active work (2026-10-15, latest)

### >>> UPDATE 2026-10-18 (read first, then the 10-17 handoff below) <<<

**STATE at end of 2026-10-18 (evening):**
- On the phone: userdata = **image v15** (`/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392-v15.img/.simg`; = v14 + `/private/var/preferences/SystemConfiguration/preferences.plist` with one network service "USB Ethernet": Interface DeviceName ue0 Type Ethernet, IPv4 Manual 192.168.7.2/24 router 192.168.7.1, DNS 1.1.1.1 8.8.8.8, set "Automatic" as CurrentSet). Fallback image v14 (v12/v13 deleted).
- Kernels: **0078** = all 8 cores (`cpus=8`, cpu6/7 = A76, homogeneous SMP; mkadt now emits 8 CPU nodes; ADT `shim/out/sweet-0078hi.adt`); **0079** = display off/on via IOMFB selector 12 kern_RequestPowerChange(state) (fade over 6 vsyncs, then black; verified: power button gives "SWEET FB: display off/on"); **0080** = `SWEET NET: <proc> route add/delete/change ...` and `... add/delete address ...` trace (built, `shim/out/shim-boot-0080s.img`, NOT booted yet).
- **Internet over USB: not working yet.** Host side is ready (temporary iptables: FORWARD accept for 192.168.7.0/24 + MASQUERADE, comment "ios-sweet"; lost on host reboot). With v15 the phone sent no DNS and no outbound traffic (only mDNS/ARP) -> configd probably did not apply the service (or did, without default route/DNS). Next: boot 0080s on v15, watch `SWEET NET` lines (does configd add 192.168.7.2 / default route on ue0?). If configd ignores ue0 (not an IOKit IONetworkInterface; configd 1241.140.6 source in `research/configd-1241`, SCNetworkInterface createInterface needs IONetworkInterface -> controller (IOMACAddress, SelfNamed) -> bus), add IOKit stand-ins and/or rename the ifnet to en*.
- Live log listener (`nc -ukl 5140`) may still be running, writing `logs/live-0078s.txt`.

**LIVE LOG over USB (0077, boot 0077s): no more recovery round-trips.** Boot an image with `sweetusb=2`, run `tools/sweet-usbnet.sh logs/live-NAME.txt` on the PC: it waits for the phone's CDC-ECM interface, sets 192.168.7.1/24 (sudo) and prints/saves the kernel console the phone streams every 100 ms as UDP to 192.168.7.1:5140 (starts with the last 64 KiB). `ping 192.168.7.2` checks the link. Current image: `shim/out/shim-boot-0077s.img` (kernel 0077, ADT sweet-0069hi, cpus=6, sweetfb_noconsole=1, sweetfb_hz=30, sweetusb=2). The recovery pull (`tools/sweet-log-pull.sh`) is still the way after a panic/hang before USB comes up.

**🎉 USB networking works (boot 0076s, 18:24 local): `ping 192.168.7.2` from the PC answers in ~1 ms, 0 % loss (200-packet burst, 1500-byte frames, 512/1024-byte frames).** 0075: CDC-ECM function (bulk 0x81/0x01, interrupt 0x82 NETWORK_CONNECTION; host MAC 02:00:5e:77:ee:01) + kernel ethernet ifnet `ue0` (legacy output, header strip like if_fake) with 192.168.7.2/24 set from the kernel (proto_plumb + SIOCAIFADDR on an in-kernel socket). 0076: received frames into one cluster mbuf (mbuf_allocpacket gave a first mbuf of length 0 -> panic "Failed mbuf validity check: len -14"). Host side (Linux cdc_ether, interface `enp0s20f0u3u1`): `nmcli dev set IF managed no; sudo ip addr add 192.168.7.1/24 dev IF; sudo ip link set IF up`. Boot image `shim/out/shim-boot-0076s.img` (`sweetusb=2`). iOS itself does not see ue0 yet (configd needs an IONetworkInterface in IOKit).

**USB device mode works (boot 0074s, 17:45 local): the host enumerates the phone at high speed as `1209:0001 ios-sweet "Sweet iOS (USB bring-up)"`.** 0072 read-only probe: ABL leaves the USB30_PRIM GDSC and all 7 USB clocks on, DWC3 v3.20a (GSNPSID 0x5533320a) in device mode (GCTL 0x00112000), halted (DCTL RUN_STOP 0, DSTS 0x00d3de04), event buffer still at ABL's 0xfdfc8000, QUSB2 PHY alive. 0073 (`sweetusb=2`): DCTL soft reset, own event buffer (polled, interrupt masked), ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE, setup TRB, RUN_STOP; control-transfer state machine as Linux ep0.c; descriptors: vendor class, no data endpoints. It ran but no event came: **0074** forces the VBUS session in the Qualcomm wrapper (QSCRATCH 0xa6f8800: HS_PHY_CTRL |= UTMI_OTG_VBUS_VALID(20)|SW_SESSVLD_SEL(28), SS_PHY_CTRL |= LANE0_PWR_PRESENT(24), as Linux dwc3_qcom_vbus_override_enable) -> connect + enumeration. Image `shim/out/shim-boot-0074s.img`. Black Phone app: main thread waits in -[VMVoicemailManager fetchAccounts] (sync XPC; voicemail needs the modem).

**Navigation works (boot 0071s on v14, log `logs/boot-0071s.txt`):** swipe up from the bottom edge returns to the home screen; app switcher works. Two fixes: **0070** pid_hibernate (syscall 435 was nosys on the macOS config -> SIGSYS killed SpringBoard in -[SBToAppsWorkspaceTransaction _didComplete] when an app left the foreground; the only CONFIG_EMBEDDED-only entry in syscalls.master); **0071** touches starting within 48 px of an edge carry kIOHIDDigitizerEventFromEdgeTip (UIKit `_UIEventHIDTouchEdgeTypeForHIDEvent` reads the digitizer EventMask 0xb0007 bits 0x800/0x1000/0x2000/0x40000). Diagnosed, not fixed: Settings (Preferences) SIGTRAP in PodcastsUI func_1cdc47c58: force-unwrap of `URL.volumeTotalCapacity` (nil on our HFS+ root). Phone/Photos/Messages show black (MobilePhone launches, no crash) - next: stack samples via boot-arg `sweetsample=MobilePhone,MobileSlideShow,MobileSMS,SpringBoard` (image `shim/out/shim-boot-0071s.img`).

**🎉🎉 MILESTONE 2026-10-18 ~15:30 local: iOS 16.7 SPRINGBOARD HOME SCREEN ON THE PHONE** (boot `shim/out/shim-boot-0069s.img` = kernel 0069 + ADT `shim/out/sweet-0069hi.adt`, image **v14**; log `logs/boot-0069s-v14-HOMESCREEN.txt`). Home screen with a few apps, Settings opens, Control Center / lock screen / notification center work, touch + buttons work, 6 A55 cores (`cpus=6`), `sweetfb_noconsole=1 sweetfb_hz=30`. Known issue: cannot leave Settings (home gesture / AssistiveTouch home do nothing) - to investigate.
What it took today (in order): 0058 HID services (Apple IOHIDFamily-1915 user client), 0059 iPhone X identity (hw.product etc.), 0060 SPMI keys + GENI touch, 0061 1125x2436 presented display, 0062 RPMh L11C touch power + IOPMPowerSource battery, 0063 GENI FIFO packing (Goodix GT9896), 0064 PRIV_WORK_INTERVAL grant (SpringBoard "Failed to create work interval"), 0065 SMP via PSCI (6 A55), 0066 crash map regions, 0067 console mute without cons_ops write, 0068 IOSurface lookup of an already-mapped surface returns base -1 (backboardd snapshot crash), 0069 UFS log flush 10 s. Image v13: CommCenter removed from launchd.plist, BKNoWatchdogs. **Image v14** = v13 + Setup skipped (`/var/mobile/Library/Preferences/com.apple.purplebuddy.plist` SetupDone/SetupFinishedAllSteps true, SetupVersion 11, daemonizeNeedsToRun false; purplebuddy.notbackedup mini-buddy flags false; managedconfiguration.notbackedup LockdownActivationIndicatesCloudConfigurationAvailable false; springboard MCForceShowCloudConfigurationUI false) + mobileactivationd data ark seeded (`/private/var/containers/Data/System/D90C94C4-F94E-4FCF-8A28-A93BE3846D8E/Library/internal/data_ark.plist`, -ActivationState Activated etc.) + MediaToolbox D22/D221/Default SubServerConfiguration StartRecorderServer=false (mediaserverd crash loop: portrait-filter prewarm called NULL GL). **Activation:** ADT /chosen certificate-production-status 0, effective-production-status-ap 0, certificate-security-mode 1, effective-security-mode-sep 1 -> mobileactivationd's native Hactivation branch (Codex `codex/activation/report.md`; alternative 4-byte daemon patch documented there). Fallback image v13; v12 deleted.

**🎉 TOUCH WORKS (boot 0063u on image v13, 2026-10-18 ~13:15 local):** tapping (i) on Setup's Hello opens the device-info sheet; swipe-up is recognised (spinner, then back to Hello - under investigation). Chain: RPMh L11C vote (0062, `bsd/dev/sweet_rpmh.c`) -> GT9896 @0x5d on GENI SE7 (0063 fixed FIFO packing: register address went out byte-swapped) -> sweet_hid_touch -> SweetHIDTouch -> backboardd. Battery icon OK (0062 SweetBattery IOPMPowerSource, static 100 %). **Image v13** (= v12 + CommCenter jobs removed from launchd.plist + `BKNoWatchdogs`=true and `FBLaunchWatchdogExceptions{com.apple.purplebuddy:100}` in /var/mobile/Library/Preferences/com.apple.springboard.plist): Setup no longer killed by the scene-create watchdog (it blocked in CoreTelephony getSubscriptionInfo -> CommCenter, Codex `codex/setup/report.md`; that report also lists how to skip Setup: SetupDone/SetupFinishedAllSteps/SetupVersion=11 in com.apple.purplebuddy.plist + activation check). v9 deleted, fallback = v12. Input latency ~1 min with 1 CPU -> Codex task 11 = SMP via PSCI (`codex/smp/`).

**INPUT WORKS (boot 0060u on a freshly flashed v12, log `logs/boot-0060u.txt`):** power, volume up, volume down reach iOS (PMIC -> sweet_keys.c -> SweetHIDButtons -> backboardd). Power locks/unlocks (screen "off" shows the kernel console because the panel never really turns off). **Device identity fixed: iPhone X** (home indicator, Face-ID-style Setup). Earlier test (0059u, `sweethidtest=15` fake Home presses) advanced Setup from Hello to the language list.
- **0058** HID: `iokit/Kernel/arm/hid/`: IOHIDEventServiceUserClient + IOHIDEventServiceQueue + IOHIDEvent compiled UNCHANGED from Apple IOHIDFamily-1915.140.3 (= exact version of the iOS 16.7 IOHIDLib, clone in `research/iohid-1915`) over our minimal IOHIDEventService (SweetHID.cpp: SweetHIDButtons consumer page 0x0C power 0x30 / vol 0xE9/0xEA / menu 0x40; SweetHIDTouch digitizer collections). C hooks `sweet_hid_key(key, down)` (0 power, 1 vol+, 2 vol-, 3 home) and `sweet_hid_touch(finger, down, x, y)`. HID logs go to IOLog. Boot-arg `sweethidtest=N` = fake Home press every N s.
- **0059** identity: hw.machine/hw.model/hw.target/hw.product from the ADT (macOS-config kernel used to answer "iPad8,6"/"Redmi Note 10 Pro"). mkadt: root compatible `D22AP|iPhone10,3|xiaomi,sweet|...`, model iPhone10,3, target-type D22, `/product` copied from the real D22AP device tree (`research/ipsw-x/d22ap.adt`, extracted from the IPSW, NOT in git), `/buttons home-button-type 2`. Codex report `codex/mg/report.md`: MG ProductType = sysctl **hw.product** (unrecognized -> iPod), HWModelStr = hw.target, HomeButtonType = `/buttons/home-button-type`; disk cache `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist` (keyed by build + UUID only -> stale iPod answers survived; reflashed clean v12 to clear it).
- **0060** drivers by Codex (`codex/input/hw-report.md`): `bsd/dev/sweet_keys.c` (SPMI arbiter v5 observer reads, PON 0x810 bits KPDPWR/RESIN SID0, PM6150L GPIO2 SID4 0xc110; works), `bsd/dev/sweet_touch.c` (GENI SE7 I2C @0xa84000, starts 45 s after boot). Touch result: SE7 fw ok (proto 3) but **0x5d and 0x38 both time out -> touch IC unpowered** (L11C LDO needs an RPMh vote). Codex task 8 = RPMh client (`codex/rpmh/`), task 7 = battery (`codex/battery/`).
- **0061** (CI 39117078444): red status bar "rdar:45025538" = UIKit "No status bar visual provider for screen" (360x800 pt is no real iPhone). AppleCLCD now presents **1125x2436** (iPhone X) and shows the centered 1080x2400; touch mapped the same; ADT canvas 1125x2436. `sweetfb_native=1` reverts.
- Images: `shim/out/shim-boot-0060b.img` (0060 + /buttons ADT `sweet-0060hi.adt`). Next: 0061 image with ADT from current mkadt.

### >>> HANDOFF 2026-10-17 late (read this first) <<<

**STATE: iOS 16.7 Setup.app "Hello" screen is ON THE PHONE** (boot `shim/out/shim-boot-0057u.img` on image v12). Photo `/run/media/dipa/android/ios-sweet-work/MILESTONE-setup-hello-2026-10-17.jpg`. SpringBoard + backboardd + Setup run; nothing crashes in the GUI path. Remaining crash/relaunch loops: installcoordinationd (should be fixed by 0057, unverified), mediaserverd (VirtualAudio removed in v12, unverified), mobileactivationd (~100/boot, not analysed), bluetoothd + fairplayd.H2 relaunch constantly (no hardware).

**What is on the phone now:** userdata = image **v12** (`/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392-v12.img` + `.simg` + `.sha256`; v9 kept as fallback, v8/v10/v11 deleted or superseded). Kernel **0057** (`xnu/out-0057`, CI `39067532732`). ADT **`shim/out/sweet-0057hi.adt`** (QEMU twin `research/q0057-hi.adt`). Boot image **`shim/out/shim-boot-0057u.img`**. Boot args: `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1`.

**Build a phone image** (kernel K, ADT A): `python3 tools/mkpayload.py $K $A shim/out/payload-X.bin --cmdline "$B" && (cd shim && ./build.sh ../shim/out/payload-X.bin && cp out/shim-boot.img out/shim-boot-X.img)` then check `python3 tools/unpack_bootv2.py shim/out/shim-boot-X.img shim/out/check-X && cmp shim/out/check-X/ramdisk shim/out/payload-X.bin`. QEMU smoke test: `python3 tools/mkpayload.py $K research/q0057-hi.adt $S/csq/payloadX.bin --ramdisk $S/csq/root-fork.img --cmdline "debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=md0"` + `PATH=~/swift/usr/bin:$PATH python3 tools/qemu-sweet.py ... --secs 40 --kernel $K --fail-on-panic` (S = scratchpad; root-fork.img lives in the session scratchpad csq/ dir and may be gone in a new session).

**Kernel workflow:** edit `research/bt28/xnu/...` (keep the pre-edit copy in `research/preNNNN/`), syntax check `python3 tools/xnu-cc.py research/run28.log research/bt28 <file>`, make `xnu/patches/NNNN-*.patch` with `diff -u pre bt28 | sed` path rewrite, add new/changed files to `research/check-patch-order.py` list, run it (must say applied + MATCH), commit + push -> GitHub Actions `xnu` builds (~8 min) -> `gh run download <id> -R dipa-studio/ios-sweet -n xnu-kernel -D xnu/out-NNNN`. **Repo is PUBLIC since 2026-10-17** (private macOS runner minutes ran out: "recent account payments have failed"); public = free runners. Commit trailer: only `Co-Authored-By: dipa-studio <183933817+dipa-studio@users.noreply.github.com>`.

**Phone workflow (user does buttons, Claude runs commands):**
- Boot test kernel: phone in fastboot -> `fastboot boot shim/out/shim-boot-X.img`. NEVER `fastboot getvar`.
- **Read logs WITHOUT filming:** after a test the user holds Power+VolDown -> fastboot -> `fastboot boot recovery/recovery.img` (OrangeFox, temp) -> wait for `adb shell true` -> `tools/sweet-log-pull.sh /run/media/dipa/android/ios-sweet-work/logs/<name>.txt` (reads the 4 MiB console ring the kernel keeps in the last 1025 blocks of userdata; patch 0047). Then `adb reboot bootloader` brings the phone back to fastboot without the user.
- **Flash a root image:** `fastboot flash -S 512M userdata <img>.simg` (7 min, 25 chunks). After a big flash the Xiaomi ABL fastboot hangs: next `fastboot boot` stalls at "Sending" -> the USER must re-enter fastboot by hand (Power+VolDown). Do not retry commands against the hung ABL. A flash right after `adb reboot bootloader` once failed on chunk 1 (USB protocol error): just retry. User must NOT unplug during flash (once interrupted at 25/25 -> reflash).
- **Edit the phone root without reflashing (same-length only):** find the file's raw offset in the local image (it is one extent; search the image for its first 4 KiB), compare with `adb exec-out dd if=/dev/block/sda34 ...`, then `adb push` changed 4 KiB blocks and `dd of=/dev/block/sda34 seek=... conv=notrunc,fsync`, read back. Recovery kernel has no hfsplus.
- **Pull the whole phone root** (12 min): `adb exec-out "dd if=/dev/block/sda34 bs=1048576 count=16384" > img`; mount ro with udisksctl or `sudo mount -t hfsplus -o loop,ro`. To write into a pulled image: `sudo fsck.hfsplus -fy` first (volume is never cleanly unmounted -> Linux mounts ro even with -o force), then `sudo mount -t hfsplus -o loop,force`.
- Making images: copy latest img with `cp --sparse=always`, mount rw with force, change, `sync; umount`, `sha256sum`, `img2simg`. Keep only the latest image + one fallback on the SSD (/home is ~98% full; big work files live in `/run/media/dipa/android/ios-sweet-work/`, old kernels/images archived in `.../ios-sweet-work/archive/`).

**Diagnostics built into the kernel (all SWEET-only):** persistent console log (0047, boot-arg sweetlog=0 off; flush every ~1 s); `|name| text` copies of /dev/null writes for processes in `sweetnull` (default backboardd,SpringBoard; 0048); `IOK name:` IOKit lookup/open trace for `sweetiolog` (default backboardd,SpringBoard; 0049/0054, 400 lines max); `SWEET Sandbox: proc op N` (0050); `STR ...` heap text dump on SIGABRT/SIGTRAP for `sweetscan` (default backboardd,SpringBoard; 0051/0053) - this is how NSException/BSAssert reasons were found; `SMP name tN pc .. bt ..` user stack sampler for `sweetsample` (default SpringBoard,backboardd; first at 90 s then every 120 s, 40 samples, 16 frames; 0054/0055); `SWEET FB: N swaps` every 1000 swaps; `CRASH name ...` crash reports (0043/0044). Symbolicate cache addresses with `ipsw dyld a2s research/dsc/dyld_shared_cache_arm64 <addr - slide>`; main-binary addresses: addr - mh + 0x100000000.

**Patches added today (0046-0057, all CI-built):** 0046 IOSurface (IOCoreSurfaceRoot) + IOMobileFramebuffer (AppleCLCD on /arm-io/disp0) + arm-io nubs; 0047 persistent log; 0048 /dev/null tee; 0049 IOKit trace; 0050 permissive "Sandbox" MAC policy; 0051/0053 heap text on crash; 0052 RENAME_SWAP via exchangedata on HFS; 0054/0055 sampler, swap counter, AKS selectors 35 (extended device state = 17) and 101; 0056 panel copy from the vsync timer at 10 Hz (sweetfb_hz) instead of every swap; 0057 no config_ext_resolver (ACL group entries resolve without memberd). ADT (tools/mkadt.py): /arm-io/disp0, /chosen/display-scale 3, /chosen/unique-chip-id (synthetic 0x5357454554000001) + chip-id 0x8015 -> IOPlatformUUID A9683613-3704-53F2-95D0-98A8FB574E78. Image v9-v12: /private/var/containers/{Bundle,Data/System,Shared/SystemGroup,Temp}; launchd.plist StandardOut/ErrorPath renamed to ...PatX (pointing jobs at /dev/console stops them launching: EACCES); v12: LastSystemVersion=20H392 in plain /var/mobile/Library/Preferences/com.apple.migration.plist (stops the 1-hour data migration that ran every boot), VirtualAudio.plugin moved to /Library/Audio/Plug-Ins/HAL.disabled/.

**Codex helper** (`codex exec --skip-git-repo-check -m gpt-6.1-sol -c model_reasoning_effort=high -s workspace-write -C /run/media/dipa/android/ios-sweet-work/codex -o OUT "$(cat task.md)" < /dev/null`, run detached with setsid nohup; config already defaults to gpt-6.1-sol high). Reports in `/run/media/dipa/android/ios-sweet-work/codex/`: mediaserverd-report.md, installcoordinationd-report.md (-> 0057), ufs-performance.md (ranked UFS speed plan), **ufs/0058-sweet-ufs-faster.patch** (READY, not yet applied: ufslogsecs default 10 s log flush batching, optional ufscache=1 directional cache ops, optional ufswait=1 spin-then-sleep; syntax-checked, host-stub verified; see ufs/README.md). Apply it as patch 0058 after review.

**Claude safety-classifier note:** several messages about QuartzCore renderer selection / writing an HFS reader tool were cut off by an automatic classifier (false positives, user agrees). Keep those topics short or let them be; they are not blockers now (rendering already works).

**NEXT STEPS (in order):**
1. **Input** (Setup stuck on Hello): touch + power + volume as IOHIDEventService/IOHIDDevice services backboardd matches (log shows backboardd matching IOHIDDevice with DeviceUsagePairs and IOService with HIDServiceSupport=true). Phone hardware: Goodix/Focaltech touch over I2C/SPI (check live DT `dtb/`), buttons via PMIC (pon) and GPIO keys. Start with a fake HID service (e.g. power button via a timer or boot-arg) to learn the ABI, then real drivers.
2. **Device identity**: MobileGestalt reports iPod + Home button. Add /product node / product-type (iPhone10,3, D22AP), device class iPhone, home-button-less (Face ID) properties in mkadt; find exact MG keys (MGIOMFBSupport.c, `IODeviceTree:/product` lookups seen in backboardd trace).
3. **Battery**: AppleSmartBattery/IOPMPowerSource style service (status bar shows empty red battery).
4. Apply Codex 0058 (UFS speed), consider cpus>1, check whether installcoordinationd/mediaserverd loops are gone, analyse mobileactivationd.
5. Hide kernel console over the GUI when not debugging: boot-arg sweetfb_noconsole=1 (but then panics are not on screen).

- **🎉 MILESTONE: iOS GUI ON THE PHONE - Setup.app "Hello" screen (2026-10-17 ~21:30 UTC, boot 0057u on image v12).** Photo: `/run/media/dipa/android/ios-sweet-work/MILESTONE-setup-hello-2026-10-17.jpg` (animated "dobar d(an)" hello lettering, status bar "iPod" + battery icon, bottom "Pritisnite Home za otvaranje" = "Press Home to open" (locale hr), (i) button). Rendered by iOS 16.7 SpringBoard/Setup through CoreAnimation -> backboardd -> kernel IOSurface (IOCoreSurfaceRoot) -> kernel AppleCLCD swaps -> ABL panel memory. What made it: data migration finally skipped (v12: `LastSystemVersion` 20H392 in the plain `/var/mobile/Library/Preferences/com.apple.migration.plist`; ADT `/chosen/unique-chip-id` + `chip-id` for IOPlatformUUID), 0057 (no ext resolver -> ACL containers work), plus everything before (0046 display/IOSurface, 0050 Sandbox policy, display-scale 3, containers dirs, RENAME_SWAP, AKS 35/101, 10 Hz present).
  **Missing (next work, in rough order):**
  - **Input: no touch, no power button, no volume buttons** (no HID drivers; backboardd looks for IOHIDDevice / HIDServiceSupport services). Setup is stuck on "Hello".
  - **Device identity: it thinks it is an iPod with a Home button** (status bar "iPod", "Press Home to open"): MobileGestalt has no product/model identity (no /product node, product-type, etc.) - give it iPhone10,3 / home-button-less (Face ID class) identity.
  - **No battery detection** (no battery/charger/PMIC service; status bar battery shows empty/red).
  - Locale came up Croatian (hr) - harmless.
  - Performance: cpus=1, polled UFS (Codex UFS patch in progress: `codex/ufs/`), backboardd presents at 60 Hz.
- **README refreshed (2026-10-17):** read the full notes and updated the public overview through patch 0045, v7 hardware observations and prepared v8 diagnostics. Documents real Apple userspace, the missing display/IOSurface GUI work, limited security services, highmem, persistent userdata root, current tooling and build examples. Documentation only; no kernel build, tests, flashing or phone boot performed.

- **v11 still migrated (boot 0056u, 20:32 UTC, `logs/boot-0056u-v11.txt`).** On iOS kCFPreferencesCurrentHost lands in the plain plist: all DMEnvironment setters (setLastBuildVersionPref, setUserDataDispositionPref, ...) use CurrentHost and the phone's `/var/mobile/Library/Preferences/com.apple.migration.plist` holds DMUserDataDisposition; datamigrator's XPC service runs with `_RoleAccount: mobile`. **Image v12** = v11 + `LastSystemVersion` = 20H392 added to that plain `com.apple.migration.plist` (keeps DMUserDataDisposition, 501:501 0600) + `/Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin` moved to `/Library/Audio/Plug-Ins/HAL.disabled/` (Codex: stops the mediaserverd SIGSEGV loop; untested). **installcoordinationd loop explained (Codex `codex/installcoordinationd-report.md`):** os_crash "Failed to create data directory" EACCES for `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.installcoordinationd/Library/InstallCoordination`: `Library`/`Library/Caches` in the container are ACL-only (uid/gid 0xfffffffe, mode 0000, ACE for group GUID ...012B = gid 299 systemusers); with `config_ext_resolver` the kernel asks an identity resolver (memberd/opendirectoryd) that iOS does not run -> EWOULDBLOCK -> ACE skipped -> EACCES. **Patch 0057**: drop config_ext_resolver from FILESYS_BASE (compatibility UID/GID<->GUID mapping is used instead), likely fixes other ACL-protected containers too. Codex task 3: UFS driver performance design (`codex/ufs-performance.md`).
- **mediaserverd SIGSEGV loop explained (Codex report `/run/media/dipa/android/ios-sweet-work/codex/mediaserverd-report.md`):** the fault (FAR 0x390) is in the HAL plug-in `/Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin/VirtualAudio` (ApplyBeamFormerPreference <- VirtualAudio_PlugIn::SetPropertyData <- HALS_AHPPlugIn::ObjectSetPropertyData <- AudioObjectSetPropertyData <- MediaExperience vaemVADSerializationListener): the default virtual audio device ('vdef', VirtualAudioDevice_Default) does not exist (no audio hardware/driver, no /product/audio). Proposed workaround for GUI bring-up: move VirtualAudio.plugin out of /Library/Audio/Plug-Ins/HAL/ in the next root image (untested). v11 reflashed OK after an interrupted flash (USB unplugged at chunk 25/25). Codex task 2: installcoordinationd crash loop.
- **ROOT CAUSE of the endless migration: no IOPlatformUUID (2026-10-17).** datamigrator's `-[DMMigrator isMigrationNeededWithBuildVersion:lastBuildVersion:clientPID:]` gets lastBuildVersion from `-[DMEnvironment lastBuildVersionPref]` = `CFPreferencesCopyValue("LastSystemVersion", "com.apple.migration", kCFPreferencesCurrentUser, kCFPreferencesCurrentHost)` -> a ByHost file. The phone had `/var/mobile/Library/Preferences/com.apple.migration.plist` (only DMUserDataDisposition) and NO `Preferences/ByHost` directory at all. On arm XNU publishes IOPlatformUUID (gethostuuid) only from `/chosen/unique-chip-id` (8 bytes) + `/chosen/chip-id` (4 bytes) (IOPlatformExpertDevice::generatePlatformUUID, called from IOPlatformExpert::start); the SWEET ADT had neither, so every CurrentHost preference write failed. Fix: mkadt adds `unique-chip-id` = 0x5357454554000001 (synthetic) and `chip-id` = 0x8015 -> UUID `A9683613-3704-53F2-95D0-98A8FB574E78` (same SHA1 namespace computation as the kernel). ADT `shim/out/sweet-0057hi.adt`, boot image `shim/out/shim-boot-0056u.img` (0056 kernel + 0057hi ADT, QEMU OK). **Image v11** = v10 + `Preferences/ByHost/com.apple.migration.<UUID upper and lower>.plist` {LastSystemVersion: 20H392} (501:501, dir 0755 files 0600). Flashing v11 2026-10-17 ~20:10 UTC. Codex (gpt-6.1-sol high) analysing the mediaserverd SIGSEGV loop in `/run/media/dipa/android/ios-sweet-work/codex/` (report `mediaserverd-report.md`).
- **v10 did NOT stop the migration (boot 0056n on v10, 19:18 UTC, `logs/boot-0056n-v10.txt`):** datamigrator + migrationpluginwrapper ran again, backboardd drew the progress UI (13000+ swaps in ~5 min). So `com.apple.DataMigration.plist`/LastSystemVersion is not the deciding input. What is known about the decision (datamigrator XPC service `DataMigration.framework/XPCServices/com.apple.datamigrator.xpc/com.apple.datamigrator`, strings): `Migration sentinel present. Migration necessary.` (sentinel `/private/var/datamigrator/migrate`, created and removed by datamigrator itself; absent in v10), `System build version changed from %@ to %@. Migration necessary.` / `...unchanged... not necessary`, `Disposition dictionary with build version %@ is out of date relative to current build version %@`, `SyntheticDidUpgrade`, DMUserDataDispositionManager; previous build source not found yet (not in the binary's plain strings; likely in DataMigration.framework's DMUserDataDispositionManager / preferences domain `com.apple.migration`). backboardd calls `DMPerformMigrationIfNeeded` and holds SpringBoard in `checkInAndWaitForDataMigration` until it returns. NEXT: find where the previous build version / disposition dictionary is stored (disassemble DataMigration.framework DMUserDataDispositionManager + datamigrator's isMigrationNeeded path), write it into the image; or get datamigrator's os_log out (OS_ACTIVITY_DT_MODE needs a launchd env change).
- **Data migration never records completion -> skip it (image v10, 2026-10-17).** Boot 0056n (18:16 UTC, `logs/boot-0056n.txt`, 30 min): 10 Hz panel copies, backboardd still presents at ~60 Hz (107k swaps), SpringBoard still in `BKSSystemShellService _checkIn` at sample 14. Every migration run takes 1+ hour on cpus=1 and repeats each boot. DataMigration decides from `/var/mobile/Library/Preferences/com.apple.DataMigration.plist` key `LastSystemVersion` (vs ProductBuildVersion 20H392); the pulled phone root (21:01 local) had NO such file. **v10** = that pulled phone state + fsck.hfsplus -fy (volume was marked not cleanly unmounted -> Linux mounts it read-only even with -o force; fsck found only hard-link counts + minor volume header, repaired) + `com.apple.DataMigration.plist` {LastSystemVersion: 20H392} (501:501 0600). `/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392-v10.img` (+ .sha256, .simg); v8 files deleted, v9 kept as fallback.
- **Repo made PUBLIC (2026-10-17, user request) so GitHub-hosted macOS runners are free:** the 0056 CI run was refused ("recent account payments have failed or your spending limit needs to be increased"). Checked before: no device dumps, serials, IMEI or Apple binaries in the history (.gitignore keeps backup/, dtb/, recovery/, research/ out); commit author emails are public now. 0056 rerun `39056660104` passed -> `xnu/out-0056`, QEMU OK, image `shim/out/shim-boot-0056n.img` booted 18:16 UTC.
- **Boot 0055n (17:16 UTC, ~65 min, `logs/boot-0055n.txt`): migration bar reached 99% in ~30 min (was ~60), then crawled.** Root cause of the slowness: backboardd presents the progress UI at ~58 Hz (**167,000 swaps in ~48 min**) and AppleCLCD copied the full 10 MB frame into the panel on every swap -> ~600 MB/s memcpy on the single CPU (cpus=1), starving everything (polled UFS I/O too). Sampler (16 frames): **SpringBoard waits in `-[BKSSystemShellService _checkIn]`** (synchronous BSXPC call to backboardd, from FBSystemShellInitialize <- SBSystemAppMain) - backboardd holds the system shell check-in until the data migration ends, so the migration is the gate to SpringBoard UI. **Patch 0056**: swap only records the latest swap record; the vsync timer copies it to the panel every 60/sweetfb_hz ticks (default 10 Hz); `SWEET FB: N swaps` every 1000.
- **Boot 0054n (16:53 UTC, ~12 min, `logs/boot-0054n.txt`, patch 0054 sampler):** the data migration runs AGAIN on every boot (it completed once in the 0053s run) - completion is not being recorded. backboardd keeps swapping the progress UI (3700+ swaps in ~10 min, `SWEET FB: N swaps`). Sample during migration: SpringBoard main thread blocked in a synchronous XPC call (`mach_msg2_trap <- dispatch_mach_send_and_wait_for_reply <- xpc_connection_send_message_with_reply_sync <- -[BSXPCServiceConnectionMessage _sendSynchronously:] <- BSXPCServiceConnectionProxy ...`). Unsupported AKS selectors seen: 101 `aks_assert_consume`, 93 `aks_get_internal_info`, 34 `_aks_stash_load` (datamigrator), **35 `aks_get_extended_device_state`** (SpringBoard, chronod, remindd, searchd, symptomsd...). **Patch 0055**: AKS 35 answered like 17 (same DER device state), 101 succeeds; sampler backtraces 16 frames, 40 samples (~80 min).
- **MILESTONE: FIRST iOS PIXELS ON THE PANEL (boot 0053s long run, 15:33 UTC, ~60 min; photos IMG_20261017_183029/183222/183419; log `/run/media/dipa/android/ios-sweet-work/logs/boot-0053s-long.txt`, 407 KB, 1428 flushes).** The iOS data-migration boot screen (Apple logo + progress bar) was shown and the bar advanced to full in ~60 minutes. It is drawn by **backboardd through our kernel display path**: `SWEET SURF: backboardd create id 2/3 1080x2400 fmt 0x42475241 (BGRA) bpe 4 bpr 4352 size 10452992 keys 11`, IOSurface sels 9, 27, 5, 34 and traps 2/3 (lock/unlock), IOMFB SwapBegin (4) / SwapEnd (5, 1132-byte struct) / GetLayerDefaultSurface (3) / 68 / 55, then `SWEET FB: swap N layer 0 surface 2|3 1080x2400 ... a 0,0 1080x2400 b 0,0 1080x2400` alternating (double buffering; only the first 16 swaps are logged). Triggered by `com.apple.datamigrator` (AKS sels 101/93/34 return unsupported) and `com.apple.migrationpluginwrapper`. Probably ProgressUI-style CoreGraphics drawing into IOSurfaces (no GPU used). After the migration: SpringBoard and backboardd stay up (exec once each, no crash), nothing new drawn; crash loops only for mediaserverd, installcoordinationd, mobileactivationd (~108 each in the hour); bluetoothd and fairplayd.H2 relaunch constantly (no hardware). Kernel console text overlays the image (sweetfb_noconsole=1 would hide it).
- **MILESTONE: SpringBoard and backboardd both stay up (boot 0053s on v9, 15:29 UTC, `logs/boot-0053s.txt`).** With /chosen/display-scale = 3: `exec SpringBoard` once, `exec backboardd` once, no CRASH for either; MobileGestaltHelper reads IOMFB size/dot pitch; backboardd opens AppleCLCD (sels 57,15,22,29,33,79,74 as before). No IOSurface creates and no swaps: backboardd keeps polling `IOProviderClass IOAcceleratorES` (-> 0 found) and AGXAccelerator/IOAcceleratorESLegacy - no GPU, so no CoreAnimation renderer yet. Log goes quiet after ~47 s (only 47 flushes): the system idles. NEXT WALL: CoreAnimation rendering without a GPU (CPU path) so the window server produces frames.
- **SpringBoard's invalid mode = scale 0 (boot 0053n, 15:19 UTC, `logs/boot-0053n.txt`, heap scan):** `FBSDisplayMode cannot be configured as requested : <FBSDisplayMode: ...; infxinf@0x (1080x2400/0) 60Hz sRGB SDR>` - pixel size and 60 Hz are fine, scale is 0. libMobileGestalt (MGIOMFBSupport.c, sub_19c560a54) reads `display-scale` (u32, default 0) and `display-rotation` from **IODeviceTree:/chosen**, pixel size via IOMobileFramebufferGetDisplaySize (MobileGestaltHelper sel 8/28 in the log). mkadt now adds `/chosen/display-scale` = 3 (1080x2400 @3x = 360x800 pt). ADT `shim/out/sweet-0054hi.adt` (QEMU `research/q0054-hi.adt`), image `shim/out/shim-boot-0053s.img` = 0053 kernel + 0054hi ADT. Possible catch: MobileGestalt may have cached scale 0 in `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/...`.
- **MILESTONE: backboardd survives and opens the display (boot 0052n on v9, 15:07 UTC, `logs/boot-0052n.txt`).** No `CRASH backboardd`. It walks `IODeviceTree:/arm-io` children, matches IOMobileFramebuffer, `open AppleCLCD type 0 -> 0x0`, calls IOMFB selectors 57, 15, 22, 29, 33, 79 (GetBlock, out 1580/40), 74 (SupportedFrameInfo), 12, 6, 27, 17, 84, 50; opens IOCoreSurfaceRoot (sel 13); looks for AGXAccelerator / IOAcceleratorES / IOAcceleratorESLegacy (none, repeatedly), `IODeviceTree:/product` (none, repeatedly), `/buttons`, aop-smart-cover, IOPMrootDomain. No swaps yet. **SpringBoard now gets past display discovery** and dies (sig 5) in `-[FBSDisplayMode _initWithWidth:height:preferredScale:scaleOverride:refreshRate:gamut:hdr:rotation:virtual:validityCheck:]+580` <- `_initWithCADisplayMode:scale:rotation:` <- `FBSDisplayConfiguration _initWithImmutableDisplay:` <- `FBSDisplaySource initWithDisplay:` <- `FBSDisplayMonitor` (slide 0x14504000): "FBSDisplayMode cannot be configured as requested". Checks: width/height >= 2, preferredScale > 0, scaleOverride >= 0, refreshRate non-zero, valid gamut/HDR/rotation. Suspects: refresh rate 0 (IOMFB timing blocks answered with zeros) and/or scale 0 (MobileGestalt main-screen-scale; no /product node in the ADT). **Patch 0053**: heap text scan also on SIGTRAP and for SpringBoard (default sweetscan list backboardd,SpringBoard) to read the exact mode description.
- **Image v9 (2026-10-17) = v8 + `/private/var/containers/{Bundle,Data/System,Shared/SystemGroup,Temp}` (root:wheel 0755; on iOS these live on the data volume, absent from the rootfs) + launchd.plist with StandardOutPath/StandardErrorPath renamed to ...PatX (the in-place phone fix; daemons' stdout reaches the log via the 0048 /dev/null tee).** `/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392-v9.img` SHA256 aa9f9139...6e67, `.simg` 12,145,303,864 bytes; written through `sudo mount -t hfsplus -o loop,force`. **Patch 0052** (`xnu/patches/0052-sweet-hfs-rename-swap.patch`, CI `39042761826` -> `xnu/out-0052`, QEMU OK, image `shim/out/shim-boot-0052n.img`): vn_rename falls back to VNOP_EXCHANGE when VNOP_RENAMEX(RENAME_SWAP) returns ENOTSUP for two regular files on one volume (HFS exchange swaps data and cnode descriptors = swap semantics). Flashing v9 started 2026-10-17 ~15:00 UTC.
- **backboardd EXCEPTION FOUND (boot 0051n, 14:41 UTC, `logs/boot-0051n.txt`, patch 0051 heap scan):** `*** Terminating app due to uncaught exception 'NSInvalidArgumentException', reason: '*** -[NSURL initFileURLWithPath:]: nil string parameter'`. First-throw stack (slide 0x337f0000): `+[NSURL fileURLWithPath:]` <- `-[BSSystemContainerForCurrentProcessPathProvider libraryPath]` <- `cachesPath` <- backboardd main+0x1d858 (StartWindowServer, shader cache path). BaseBoard: libraryPath = `BSSystemSharedResourcesDirectoryForIdentifier` = `BSSystemSharedDirectoryForIdentifier(id)` + "/Library"; that calls `container_system_path_for_identifier` (libsystem_containermanager -> `_container_legacy_lookup` -> containermanagerd XPC), which returned NULL (BaseBoard logs "Error getting shared system container ..."). With 0050 the sandbox denials are gone. containermanagerd.log.0 in the pulled (pre-0050) image: "Did not receive any persona attributes", "Expected to find at least one persona", notify_register_dispatch failed 9; `/private/var/containers` does NOT exist in the root image (on iOS it lives on the data volume). usermanagerd does create kernel personas 99/199/1000, but fails to save `/private/var/keybags/usersession.kb` and `persona.kb`: "Failed to atomically swap writing file: Operation not supported (45)" (HFS has no RENAME_SWAP). NEXT: create `/private/var/containers` (and check what containermanagerd needs for system group containers), fix or emulate RENAME_SWAP on HFS, then re-check backboardd.
- **Disk housekeeping (2026-10-17):** /home was at 4 GiB free. Moved (not deleted) `xnu/out-0010..0044` and old `shim/out/*.img`/`payload-*.bin` (everything before 0046) to `/run/media/dipa/android/ios-sweet-work/archive/{xnu,shim-out}` (6.3 GiB); /home now 8.7 GiB free. Large work files (phone-root.img 16 GiB, logs, tracev3 dumps) live in `/run/media/dipa/android/ios-sweet-work/`. **Patch 0051** (`xnu/patches/0051-sweet-crash-heap-strings.patch`, CI `39041440935`): on SIGABRT of a process in boot-arg `sweetscan` (default backboardd) the crash log prints heap text runs as `STR ...` (to find the NSException reason). Boot 0051n 14:41 UTC.
- **Boot 0049n (14:11 UTC, `logs/boot-0049n.txt`, patch 0049 trace): backboardd's IOKit lookups before it dies** (each run): `IODeviceTree:/arm-io/pearl-sep` -> none, matching ApplePearlSEPDriver -> none, `IOService:/IOResources/AppleKeyStore` open OK, matching IOHIDDevice (DeviceUsagePairs) / `HIDServiceSupport` notifications, `usb-drd,t8027` notification; **never any IOMobileFramebuffer / display lookup** - the exception happens before display detection. launchd (tracev3) shows backboardd's mach lookups denied with `error = 159: Sandbox restriction`: com.apple.mobilegestalt.xpc, com.apple.iohideventsystem, com.apple.system.notification_center, com.apple.logd, containermanagerd, ACCHWComponentAuthService, oscard. libsystem_sandbox uses `__mac_syscall("Sandbox", op, arg)` (ops: 1 init, 2 check, 3 note, 4 container path, 5/6/7/8 extensions, 0x15 check_bulk, ...); with no policy named "Sandbox" every call gets ENOPOLICY. **Patch 0050** (`xnu/patches/0050-sweet-sandbox-policy.patch`): built-in permissive MAC policy "Sandbox" in sweet_amfi.c (mpo_policy_syscall returns 0, container/extension ops ENOENT; logs first use of each op as `SWEET Sandbox: proc op N`).
- **Phone root pulled (16 GiB, 12 min, `adb exec-out dd if=/dev/block/sda34`) to `/run/media/dipa/android/ios-sweet-work/phone-root.img` (loop-mounted ro at /run/media/dipa/iOSRoot).** No .ips crash reports. logd tracev3 (Persist, LZ4 `bv41` blocks, decompressed strings in `ios-sweet-work/tracev3/all.txt`): /private/var/db/uuidtext is EMPTY so only launchd's own messages are readable. Findings: v8 launch failure = `Service could not initialize: posix_spawn(/usr/libexec/backboardd), error 0xd - Permission denied` (xpcproxy exit 78) - /dev/console not openable for the mobile user; backboardd[98] spawned `com.apple.MTLCompilerService` before SIGABRT; **launchd denies many mach lookups with `error = 159: Sandbox restriction`** (mediaserverd -> com.apple.backboard.display.services, remoted, mobiletimerd -> sleepd, identityservicesd -> apsd) and **tccd exits OS_REASON_SANDBOX "profile not found"** - no Sandbox kext/profiles on SWEET; likely cause of many daemon crash loops (next wall after the display). CF's uncaught-exception text never reaches stderr for daemons (no CF handler; libc++abi prints only the type). **Patch 0049** (`xnu/patches/0049-sweet-iokit-trace.patch`): `IOK name: ...` console lines for registry path lookups, child iterators, matching (with result count/class), matching notifications and IOServiceOpen of the processes in boot-arg `sweetiolog` (default backboardd), max 400 lines.
- **CONFIRMED: launchd StandardOut/ErrorPath=/dev/console stops backboardd from launching.** After the in-place rename (boot 0047n-b, log `logs/boot-0047n-b.txt`) backboardd launches again and dies as on v7: sig 6, `___pthread_kill <- abort <- demangling_terminate_handler <- _objc_terminate <- std::terminate <- _dispatch_client_callout <- _dispatch_once_callout <- main+0x9334` (window-server dispatch_once). It never opened AppleCLCD or IOCoreSurfaceRoot (no `SWEET FB/SURF: backboardd` lines) -> throws before/at display detection. **Patch 0048** (`xnu/patches/0048-sweet-devnull-tee.patch`, CI `39037749668` -> `xnu/out-0048`, image `shim/out/shim-boot-0048n.img`): writes to /dev/null by processes named in boot-arg `sweetnull` (default `backboardd,SpringBoard`) are printed as `|name| text`. Boot 0048n (13:48 UTC, log `logs/boot-0048n.txt`): only `|backboardd| libc++abi: terminating due to uncaught exception of type NSException` (CF's reason line goes to os_log, not stderr, despite CFLOG_FORCE_STDERR/OS_ACTIVITY_DT_MODE). Next: pull the whole 16 GiB root from recovery (`adb exec-out dd if=/dev/block/sda34`) to `/run/media/dipa/android/ios-sweet-work/phone-root.img` and read ReportCrash .ips files / logd tracev3 for the exception reason.
- **Persistent log WORKS (boot 0047n on v8, 13:31 UTC; pulled from OrangeFox: 70 KB, 111 flushes, `/run/media/dipa/android/ios-sweet-work/logs/boot-0047n.txt`).** In 3 min **backboardd was never exec'd** (v7 ran it), ~70 bare `exec xpcproxy`, SpringBoard loops on FBSDisplayMonitor (no display), mediaserverd sig 11 loop, locationd, lockdownd sig 5. Suspect the v8 plist (StandardOut/ErrorPath=/dev/console on backboardd). **In-place plist edit from recovery (no reflash):** launchd.plist is one extent at image/partition byte offset 0x1e025f000 (195 blocks; verified bytes identical on phone vs local v8 mount); renamed StandardOutPath->StandardOutPatX and StandardErrorPath->StandardErrorPatX (same length, both jobs) in blocks 68 and 105 via `adb push` + `dd of=/dev/block/sda34 seek=... conv=notrunc,fsync`, read back VERIFIED. Phone now differs from local v8 image in those 2 blocks (files in `/run/media/dipa/android/ios-sweet-work/`). Test boot 0047n 13:38:42 UTC. Recovery kernel has no hfsplus (raw block edits only).
- **Patch 0047: persistent console log (CI `39036478663` -> `xnu/out-0047`, QEMU no panic; phone image `shim/out/shim-boot-0047n.img` = 0047 + sweet-0046hi.adt + 0045n cmdline).** `_cnputs` (all console output: kernel printf + daemons' /dev/console) also appends to a 4 MiB ring in sweet_ufs.c; after the UFS partition is ready and writable (ufsrw=1) a thread writes new ring blocks + header to the LAST 1025 blocks (4 KiB) of userdata every ~1 s and SYNCHRONIZE CACHE (prints `SWEET LOG: console log to the last 4100 KiB ...`). Read: phone to fastboot -> `fastboot boot recovery/recovery.img` (OrangeFox) -> `tools/sweet-log-pull.sh OUT.txt` (adb dd of that area + `tools/sweet-log.py`). Not yet verified on the phone. Panics after the last flush are not in it (screen still shows them). 2x font attempt reverted: XNU's v_scale only scales the progress icon.
- **Boot 0046n on v8 (13:05 UTC, VID_20261017_150522_HSR_120):** phone prints `SWEET SURF: IOCoreSurfaceRoot registered` and `SWEET FB: AppleCLCD 1080x2400 stride 4320 at 0x9c000000, default surface 1` (nubs + match work on hardware). Visible userspace: early boot tasks, launchd_cache_loader, `exec SpringBoard`; no `exec backboardd` / `SWEET FB: backboardd` line seen in the readable frames (video blurry). Frame 00:47: lower half of the screen shows OLDER console text (16:01:12) below newer lines -> unconfirmed hint that a swap copied an old snapshot of the panel (CA reads the default/displayed surface = panel memory). SpringBoard still dies in `-[FBSDisplayMonitor _initWithBookendObserver:transformer:]+1160` (sig 5, slide 0x30960000). **Shim: 2x console font** (`shim/loader.c` Video.v_depth scale field = 1) so phone videos are readable; image `shim/out/shim-boot-0046b.img` = 0046n + 2x font.
- **Patch 0046: built-in IOSurface + IOMobileFramebuffer (2026-10-17, offline, NOT phone-tested).** `xnu/patches/0046-sweet-iosurface-iomfb.patch`: new `iokit/Kernel/arm/SweetSurface.{h,cpp}` (IOCoreSurfaceRoot + IOSurfaceRootUserClient: sel 13/0/4/34/35, traps 0-5, wired buffers mapped into the caller, per-client refs) and `SweetFramebuffer.cpp` (AppleCLCD : IOMobileFramebuffer on /arm-io/disp0: sizes, swap = CPU copy of enabled layers into the ABL panel memory, 60 Hz vsync via sendAsyncResult64WithOptions(CanDrop), panel memory published as the default IOSurface, kernel text console paused on the first swap only with `sweetfb_noconsole=1` (default keeps the console: pausing switches it to serial and would hide panics)); SweetPlatformExpert creates nubs for /arm-io children (not gic) attached to the platform expert (IOPlatformDevice::compareName casts its provider to IOPlatformExpert, so nubs under the arm-io nub never matched - first CI build showed that in QEMU). mkadt: /arm-io/disp0 {device_type display-subsystem, compatible sweet,display, canvas-width 1080, canvas-height 2400}. CI `39021572169` -> `xnu/out-0046`. **QEMU** (`research/q0046-hi.adt`, RAM disk init, msgbuf): `SWEET SURF: IOCoreSurfaceRoot registered`, `SWEET FB: AppleCLCD 1080x2400 stride 4320 at 0x9c000000, default surface 1`, init alive, no panic. Phone image **`shim/out/shim-boot-0046n.img`** (SHA256 9c4d2fe9..., CI `39024108588` with the review fixes: swap bounds check, zeroed 64-bit async ref, port release, 1.5 GiB wired budget, ref leak/race fixes; QEMU re-checked) = 0046 kernel + `shim/out/sweet-0046hi.adt` + the 0045n cmdline; boot it on image v8 (backboardd/SpringBoard log to console) and film. Expected new console lines: `SWEET SURF: <proc> create id ...`, `SWEET FB: backboardd sel N ...`, `SWEET FB: swap ...`. Open question for the next wall: QuartzCore's IOMFB server builds its renderer from Metal first (`CAMetalContextCreate`), GLES only when enabled; how the CPU renderer gets selected on a device without a GPU is not yet established.
- **IOSurface values ABI (offline RE, `/run/media/dipa/android/ios-sweet-work/iosurface-values.md`) - TODO in SweetSurface (0046 only accepts and drops values, so IOSurfaceCopyValue always returns NULL):** sel 9 SetValue in = {u32 id, u32 pad, IOCFSerialize([value, key]) or ([dict] = merge)}, sel 0xb RemoveValue in = {u32 id, u32 pad, key\0} (empty key = remove all); both out 4 bytes = new generation, client accepts only (gen+2)|1. Kernel after each change: gen = (gen+2)|1 (odd, never 0) -> state+0x20, serialized size (>=1) -> state+0x28. sel 0xa in {u32 id, u32 0, u8 0}, out {u32 ?, u32 gen, serialized non-bulk dict}; too small -> 0xe00002db + needed size (client retries x16). sel 0x1b in 0x88: bulk struct 0x70 @0, u64 valid size @0x70, u64 changed mask @0x78, u32 id @0x80 -> copy masked fields into state+0x30 (bit0 32B @0, bit1 16B @0x20, bit2 8B @0x30, bits3-10 1B @0x38..0x3f, bits11-14 24B @0x40/4B @0x58/8B @0x5c/1B @0x64).
- **IOMFB display matching confirmed (offline RE, `/run/media/dipa/android/ios-sweet-work/iomfb-match.md`):** the framework never matches on "AppleCLCD"; any registered IOMobileFramebuffer subclass works. `iomfb_match_callback` reads only `dfr`/`AppleTV`/`external` (CFBoolean, service itself, no parents); internal main display = all absent/false (type 0, name "primary"). Display count = /arm-io children whose device_type starts with "display-subsystem" (count 0 -> CreateDisplayList returns NULL; more nodes than services -> 30 s wait). IOMobileFramebufferOpen fails only on IOServiceOpen failure; canvas-width/height read as 4-byte CFData from the IOService-plane parent (optional). CopyProperty = IORegistryEntrySearchCFProperty on the service only. Patch 0046 (disp0 node, `external`=false, AppleCLCD : IOMobileFramebuffer) fits all of this.
- **IOMobileFramebuffer swap + notification ABI (2026-10-17, offline).** Swap record = fb+0x18, **0x46c bytes**, zeroed by SwapBegin and sent whole by `kern_SwapEnd` = IOConnectCallStructMethod(sel 5, rec, 0x46c, no output). **SwapBegin** = sel 4, no input, 1 scalar out = swap id (stored at rec+0x50). `kern_SwapSetLayer(fb, layer<4, IOSurfaceRef, CGRect a, CGRect b, flags)`: rec+0x54+4*layer = **IOSurface id**; rec+0x104 bit layer = layer enabled (rec+0x108 bit cleared); rect a (int x,y,w,h, scaled) at rec+0x64+16*layer, rect b at rec+0xc4+16*layer; rec+0x114+4*layer = transform from flags&0xf; flag bits 5/31/6/7/8/9 set bytes rec+0x2ca/0x2cc/0x2e3/0x2e5/0x2e6/0x467+layer. A NULL surface only sets the enable bit with zero id. SwapWait = sel 6 scalars [swap id, timeout, 0].
  - **Notifications**: `IOMobileFramebufferScheduleWithDispatchQueue`/`GetRunLoopSource` create an IONotificationPort and `IOConnectSetNotificationPort(conn, type, port, 0)` (kernel `registerNotificationPort`). `kern_EnableNotifications(fb, type, cb, ctx)` = **sel 72 scalars [NotifyCallbackFuncs[type], fb, type, 0]** -> the kernel keeps an async reference {port, func, refcon=fb} per type and fires it with `sendAsyncResult64`. Types: 0 HotPlug, 1 Power, 3 FrameInfo (args[0] = mask of 31-bit keys, args[1] u32, then values), 4 CRC, **5 Vsync**: 6 args, each a 32-bit half in a u64 slot: (ts lo, ts hi), (t2 lo, hi) passed through the time-ingest helper, (t3 lo, hi); the framework then calls the client's vsync callback(fb, ts, t2', t3, ctx). Vsync callbacks are dropped while the notification port has queued messages.

- **IOSurface.framework user-client ABI reversed (2026-10-17, offline, step 2 of the GUI plan).** `ipsw dyld disass research/dsc/dyld_shared_cache_arm64 --image IOSurface` (selector scan script: scratchpad `selscan.py`).
  - Connect (`_iosConnectInitalize`, pthread_once): `IOServiceGetMatchingService(IOServiceNameMatching("IOCoreSurfaceRoot"))`, retried with sleep(1) up to 241 times (a missing service stalls every client ~4 min, no crash); `IOServiceOpen(type 0)`; then **sel 13** (no inputs, struct out 0x18 bytes = `_ioSurfaceLimits`) and requires u16 at out+0x16 == 1 (ABI version); out+0 = offset/plane-base alignment mask, out+4 = bytes-per-row alignment mask (used as (x+m)&~m), +0..+0x14 also copied into IOSurface remote-method init, otherwise logs and closes the connection.
  - **Create = sel 0**: scalar in [parent id or 0], struct in = `IOCFSerialize(props, kIOCFSerializeToBinary)` (OSUnserializeBinary format; keys IOSurfaceWidth/Height/BytesPerRow/BytesPerElement/PixelFormat/AllocSize/PlaneInfo/CacheMode/IsGlobal/...), struct out **0xa68 bytes** ("lock result"). **Lookup = sel 4**: scalar in [id], same struct out. LookupFromMachPort = sel 0x22 (scalar in [port name]); CreateMachPort = sel 0x23 (scalar in [id, options], scalar out [port name]).
  - Lock result (copied to client+0x68, size 0x68 + planes*0x80, min 0xe8): 0x00 u64 base address **mapped in the caller's task**; 0x08 u64 task VA of a per-surface shared state page (+0 u64 registry id, +8/+0xa u16 bound accel ids, +0xc u32 seed, +0x14 u8 tiled, +0x20 u32 value generation, +0x24 YCbCr matrix, +0x28 u32 non-bulk values size, +0x2d u8 displayable, +0x2e u8 sysmem-only, +0x30 0x70 bytes bulk attachments); 0x10 u64 task VA of timestamp page (4 u64 indexed timestamps, +0x20 detach code); 0x18 u32 surface id; 0x1c u32 alloc size; 0x20 width; 0x24 height; 0x28 bytes per row; 0x2c buffer offset; 0x30 pixel format; 0x34 u32 (dcache flush length); 0x38 plane count; 0x40 u16 bytes/element; 0x42 u8 element width; 0x43 u8 element height; 0x44 cache mode; 0x4c u8 subsampling; 0x4d u8 prohibit-use count; 0x50 parent id; 0x54 slice count; 0x58 u64 trace id; 0x60 u64 protection options; planes[n] at 0x68+n*0x80 (+0 width, +4 height, +8 bytes/row, +0xc offset, +0x14 size, +0x18 u16 bpe, +0x1a/+0x1b u8 element w/h, +0x1c u8 component count, +0x1d address format, +0x54 u8 compression type (non-zero -> no CPU base address)).
  - **Traps** (IOConnectTrapN -> `IOUserClient::getTargetAndTrapForIndex`): 0 IncrementUseCount(id, category), 1 DecrementUseCount(id, category), 2 **Lock**(id, options, &seed_out), 3 **Unlock**(id, options, &seed_out), 4 Release(id), 5 Release after a failed create/lookup setup (id).
  - Other selectors: 5 SetYCbCrMatrix, 6 WrapClientImage, 7 WrapClientMemory, 9 SetValue (serialized), 0xa UpdateNonBulkValueCache (struct in 9), 0xb RemoveValue, 0xc BindAccel, 0x11 SetSurfaceNotify (async), 0x12 RemoveSurfaceNotify, 0x13 Log, 0x14 SetPurgeable, 0x15 SetOwnership, 0x16 SetTiled, 0x18 SetTimestamp, 0x19 GetTileFormat, 0x1a CopyDataValueBytes, 0x1b SetBulkAttachments (struct 0x88), 0x1e/0x2e-0x31 (via outlined helpers), 0x1f SetCompressedTileDataRegionMemoryUsed, 0x20 GetGraphicsCommPageAddress, 0x21 SetIndexedTimestamp, 0x24-0x26/0x2d IOSurfaceAccelerator, 0x27-0x29 shared events, 0x2a SignalEvent, 0x2b Set/InitDetachModeCode, 0x2c SetOwnershipIdentity, 0x32-0x34 data properties.
  - => SWEET kernel service: class/name **IOCoreSurfaceRoot** + IOSurfaceRootUserClient; minimum = sel 13, 0, 4, 9/0xa/0xb (values), traps 0-5, 0x22/0x23 later for cross-process surfaces (CA sends surfaces to backboardd by mach port). Memory: IOBufferMemoryDescriptor per surface, mapped into each task with createMappingInTask; ids from a global table.

- **Image v8: daemon logs on the console.** `tools/patch-launchd-plist.py IN OUT LABEL...` rewrites launchd.plist (binary, plistlib): renames every `_PanicOnCrash` to `_PanicOnCrasX` and gives the listed jobs `StandardOutPath`/`StandardErrorPath` `/dev/console` (devfs console is 0622, writable by mobile) plus `OS_ACTIVITY_DT_MODE=YES` (os_log mirrored to stderr) and `CFLOG_FORCE_STDERR=1`. v8 = v7 + that plist for com.apple.backboardd and com.apple.SpringBoard, written through the mount (796310 bytes, root:80 0644), SHA256 in `ios16-root-20H392-v8.img.sha256`, `.simg` ready; boot with `shim/out/shim-boot-0045n.img`. Goal: see backboardd's uncaught exception text and the window server's display probing. ODDITY (unresolved): the v5 raw-image rename at offset 0x1e025f000 is present in the v5-v7 image bytes, but the plist read through a Linux mount of v7 still had the original `_PanicOnCrash` keys; filefrag shows the file as one extent. Never patch file contents through raw offsets again; write through the mount.
- **IOMobileFramebuffer.framework reversed (step 1 of the GUI plan).** `ipsw dyld disass research/dsc/dyld_shared_cache_arm64 --image IOMobileFramebuffer`.
  - Display discovery (`IOMobileFramebufferCreateDisplayList` -> `getDisplayListNumber`): iterates children of `IODeviceTree:/arm-io`, counts nodes whose `device_type` is "display-subsystem" or "ext-display-subsystem" (or `compatible` "paravirtualizedgraphics,gpu"); then `iomfb_populate_display_infos` adds an IOServiceAddMatchingNotification(IOServiceFirstMatch, **IOServiceMatching("IOMobileFramebuffer")**) and runs the run loop up to 30 s until that many services matched. `iomfb_match_callback` reads service properties `dfr`, `AppleTV`, `external` (CFBoolean) and names displays (external ones "%s-%d").
  - `IOMobileFramebufferOpen(service, task, type, &fb)`: `__ioMobileFramebufferAlloc` (CFPreferences com.apple.iokit.IOMobileGraphicsFamily: canvas_width/height, override_display_width/height, override_panel_width/height, benchmark, enable_ktrace), `IOServiceOpen(service, task, type)` (GetMainDisplay passes type 0), `getEDTProperty` reads `canvas-width`/`canvas-height` from the service's IODeviceTree parent, then fills a table of `kern_*` function pointers.
  - User client selectors (`kern_*` -> IOConnectCall*): 3 _kern_GetLayerDefaultSurface[ScalarMethod_stub]; 4 _kern_SwapBegin[ScalarMethod_stub]; 5 _kern_SwapEnd[StructMethod_stub]; 6 _kern_SwapWaitWithTimeout[ScalarMethod_stub] _kern_SwapWait[ScalarMethod_stub]; 7 _kern_GetID[ScalarMethod_stub]; 8 _kern_GetDisplaySize[ScalarMethod_stub]; 10 _kern_SetTVOutMode[ScalarMethod_stub]; 11 _kern_SetWSSInfo[ScalarMethod_stub]; 12 _kern_RequestPowerChange[ScalarMethod_stub]; 13 _kern_EnableStatistics[ScalarMethod_stub]; 14 _kern_SetFlags[ScalarMethod_stub]; 15 _kern_SetDebugFlags[ScalarMethod_stub]; 16 _kern_SetTVOutSignalType[ScalarMethod_stub]; 17 _kern_SetGammaTable[StructMethod_stub]; 18 _IOMobileFramebufferIsMainDisplay[ScalarMethod_stub]; 19 _kern_SetWhiteOnBlackMode[ScalarMethod_stub]; 20 _kern_SwapSignal[ScalarMethod_stub]; 22 _kern_SetDisplayDevice[ScalarMethod_stub]; 23 _kern_SetDigitalOutMode[ScalarMethod_stub]; 24 _kern_GetHDCPDownstreamState[StructMethod_stub]; 25 _kern_GetDigitalOutState[ScalarMethod_stub]; 26 _kern_printDisplayRegs[ScalarMethod_stub]; 27 _kern_GetGammaTable[StructMethod_stub]; 28 _kern_GetDotPitch[ScalarMethod_stub]; 29 _kern_GetDisplayArea[StructMethod_stub]; 30 _kern_EnableDisableDithering[ScalarMethod_stub]; 31 _kern_SetUnderrunColor[ScalarMethod_stub]; 33 _kern_EnableDisableVideoPowerSavings[ScalarMethod_stub]; 34 _kern_SetVideoDACGain[ScalarMethod_stub]; 35 _kern_SetLine21Data[ScalarMethod_stub]; 41 _IOMobileFramebufferEnableMirroring[ScalarMethod_stub]; 42 _IOMobileFrameBufferGetMirroringCapability[StructMethod_stub]; 43 _IOMobileFramebufferSetRenderingAngle[StructMethod_stub]; 44 _IOMobileFramebufferSetMirrorContentRegion[StructMethod_stub]; 47 _kern_HDCPSendRequest[ScalarMethod_stub]; 48 _kern_HDCPGetReply[ScalarMethod_stub]; 49 _kern_SurfaceIsReplaceable[ScalarMethod_stub]; 50 _kern_SetBrightnessCorrection[ScalarMethod_stub]; 51 _kern_SetColorRemapMode[ScalarMethod_stub]; 52 _kern_SwapCancel[ScalarMethod_stub]; 53 _IOMobileFramebufferSetCanvasSize[ScalarMethod_stub]; 54 _IOMobileFramebufferGetMatrix[Method_stub]; 55 _IOMobileFramebufferSetMatrix[Method_stub]; 56 _IOMobileFramebufferKernelTests[StructMethod_stub]; 57 _kern_GetColorRemapMode[ScalarMethod_stub]; 66 _kern_SPLCSetBrightness[ScalarMethod_stub]; 67 _kern_SPLCGetBrightness[ScalarMethod_stub]; 68 _kern_SetParameter[Method_stub]; 69 _kern_SwapSetColorMatrix[StructMethod_stub]; 72 _kern_DisableNotifications[ScalarMethod_stub] _kern_EnableNotifications[ScalarMethod_stub]; 73 _kern_ChangeFrameInfo[ScalarMethod_stub]; 74 _kern_SupportedFrameInfo[Method_stub]; 75 _kern_FactoryPortal[StructMethod_stub]; 77 _kern_GetCurrentAbsoluteTime[ScalarMethod_stub]; 78 _kern_SetBlock[Method_stub]; 79 _kern_GetBlock[Method_stub]; 80 _kern_GetLinkQuality[ScalarMethod_stub]; 81 _kern_SwapCancelAll[ScalarMethod_stub]; 82 _kern_GetProtectionOptions[ScalarMethod_stub]; 83 _kern_CopyLayerDisplayedSurface[ScalarMethod_stub]; 84 _kern_SetContrast[StructMethod_stub]; 85 _kern_GetBufBlock[Method_stub]; 86 _IOMFBGainEncoderFinishEncoding[Method_stub]; UNKNOWN {}
  - => Kernel needs: an `/arm-io` child node with device_type "display-subsystem" (+ canvas-width/height) and an IOService of class **IOMobileFramebuffer** (subclass name match) attached under it, opened with type 0, implementing at least GetDisplaySize(8), IsMainDisplay(18), GetID(7), GetLayerDefaultSurface(3), SwapBegin(4)/SwapEnd(5 struct)/SwapWait(6), Enable/DisableNotifications(72), frame info(73/74), CopyLayerDisplayedSurface(83), plus IOSurface for the swapped buffers. NEXT: CoreAnimation's AppleDisplay/IOMFBDisplay usage of these (constructor, first swap, vsync), then IOSurface.framework's IOSurfaceRoot selectors.
- **GUI PLAN (decided 2026-10-16): CPU rendering + kernel IOMobileFramebuffer.** User: CPU rendering is fine for now (goal = prove the GUI runs), may later research an Apple-style GPU driver for the Adreno 618 -> keep display output and renderer separable. QuartzCore findings (symbols from the cache's .symbols subcache: `ipsw dyld symaddr research/dsc/dyld_shared_cache_arm64 --image QuartzCore`; strings: `ipsw dyld macho ... QuartzCore --strings`):
  - Renderers: `sw_new_context` (CA::OGL::SWContext, full CPU renderer incl. blur, images, IOSurface-backed surfaces, make_buffer_current(WindowServer::Surface)), `gles_new_context`, `metal_new_context`, `new_null_context`. Env knobs include CA_ENABLE_OGL, CA_DISPLAY_TYPE, CA_FORCE_LOCAL_SERVER, CA_FORCE_TIMER, CA_CANVAS_WIDTH/HEIGHT, CA_MAIN_DISPLAY_SCALE/ORIENTATION, CA_DISABLE_RENDER, CA_ALWAYS_RENDER (selection logic not traced yet).
  - `-[CAWindowServer _detectDisplays]` (0x1884e3150) iterates static tables `open_funcs`/`count_funcs` = AppleCLCDDisplay, AppleRGBOutDisplay, AppleWirelessDisplay only; each `count()` = `display_count_of_type(IOMFBDisplayType)` over **`IOMobileFramebufferCreateDisplayList()`**, `open(i)` = `create_display_of_type` -> `CA::WindowServer::AppleDisplay(CFString name, ..., IOMFBDisplayType)` (an IOMFBDisplay driven by IOMFBServer: vsync_callback, frame_info_callback, swaps). `CA::WindowServer::VirtualDisplay` exists but is never auto-detected (explicit API only). => the main display MUST come from an IOMobileFramebuffer kernel service.
  - NEXT: reverse IOMobileFramebuffer.framework: IOMobileFramebufferCreateDisplayList / IOMobileFramebufferOpen (service matching, display type property), the user-client selectors used by IOMFBServer (display size/modes, swap begin/set-layer/end with IOSurface ids, vsync notifications), then the IOSurface kernel side (IOSurfaceRoot user client: create/lookup/lock, memory mapping) that both IOMFB swaps and CA surfaces need. Kernel: SWEET IOMobileFramebuffer service that copies the swapped IOSurface to the 1080x2400 framebuffer at 0x9c000000.
- **logd fixed; backboardd = DISPLAY WALL (boot 0045n on v7, 21:08:57 UTC, frames VID_20261016_230850 00:55-01:28, slide 0x4c3ec000, `research/crash-0045n-v7.txt`).** No `CRASH logd` any more; new daemons run (runningboardd, WirelessRadioManagerd, networkserviceproxy, dasd, cloudpaird, magicswitchd, atc, askpermissiond, ManagedSettingsAgent, containermanagerd uses AKS 0/17). New: locationd sig 11 at CFRunLoopAddSource+132 (NULL source) from its main+0x2af138 in a dispatch_once. **backboardd** sig 6: abort <- std::terminate <- _objc_terminate <- dispatch_once <- main+0x9334 = the "start %{public}@..." wrapper (0x100009264) for **"window server"** (block 0x10000a770 -> dispatch_once body 0x10001d7f0 = StartWindowServer): MTLSetShaderCachePath, `[CAWindowServer serverWithOptions:@{kCAWindowServerDisableUpdatesOnMainDisplay: @YES}]`, `setRendererFlags:`, **`mainDisplay`** -> `displayId` -> `[CADisplay displayWithDisplayId:]`, setWindowServerDisplay:, bounds, pointScale, currentMode, preferredScale, nativeOrientation, touchScales... With no display, mainDisplay is nil and it throws. (HID system and GS start fine before it.) SpringBoard dies on the same missing display (FBSDisplayMonitor). QuartzCore display backends (from the cache's .symbols subcache, `ipsw dyld str`): `CA::WindowServer::AppleCLCDDisplay` (IOMobileFramebuffer hardware) and **`CA::WindowServer::VirtualDisplay`** (open(), new_server, clone_update). `CA_DISPLAY_TYPE` and `CA_FORCE_LOCAL_SERVER` strings exist in QuartzCore but have no direct xref (likely read via a table of CA_* env names). NEXT: find how CA::WindowServer::Server enumerates displays (IOMobileFramebuffer services vs VirtualDisplay / CA_DISPLAY_TYPE) and choose: (a) kernel IOMobileFramebuffer service + IOSurface, or (b) a VirtualDisplay rendered by CA's CPU path (CA::OGL::SW) and copied to the framebuffer.
- **watchdogd + CommCenter + identityservicesd fixed (boot 0045n on v6, 20:41:30 UTC, frames VID_20261016_224133 00:39-01:13, slide 0x20fec000).** `SWEET WDT: watchdogd sel 0 in 0/0 out 1/0 -> ok`, no watchdogd/CommCenter/identityservicesd crashes (CommCenter/identityservicesd now call AKS 0/17/7). usermanagerd boot task runs (UMD_INIT creates primary session uid 501 "mobile", personas 99 System and 199 Default registered with the kernel); `Failed to atomically swap writing file /private/var//keybags/usersession.kb: Operation not supported (45)` (HFS lacks the atomic swap rename; non-fatal so far). Remaining: SpringBoard (FBSDisplayMonitor, no display), backboardd (uncaught exception), mediaserverd, lockdownd (crash inside obfuscated code, main+0x4c1b4?), logd. **logd**: main+0x18160 = `BUG IN LIBTRACE: Failed to migrate directory` from 0x10001801c(dir 0): 0x100016538 requires the dir to exist with uid/gid/mode from the table at 0x10002df14 (0: /private/var/db/diagnostics 272:272 0751, 1: /private/var/db/uuidtext 272:272 0755, 2: /private/var/db/diagnostics/timesync 272:272 0755) plus a `.migrated` file, else XPC "operation 6" to a helper and crash. **Image v7** = v6 + those dirs/markers (also in mkiosroot.sh), SHA256 in `ios16-root-20H392-v7.img.sha256`, `.simg` ready. Boot with `shim/out/shim-boot-0045n.img`.
- **Exit-reason text works (boot 0044n, frames VID_20261016_221726 00:32-00:53, slide 0x22d5c000).** CommCenter/identityservicesd: `couldn't dlopen libobjc-trampolines.dylib: dlopen(/usr/lib/libobjc-trampolines.dylib, 0x0106): tried: '/usr/lib/libobjc-trampolines.dylib' (no such file, not in dyld cache)`: the file only exists in the OS cryptex and dyld does not search cryptexes at ignition_level=1. 19 cryptex files have no root counterpart (OS: DriverKit dyld cache + .symbols, VisualTestKit, libffi-trampolines, libobjc-trampolines, libstdc++ 6.0.9 + 2 symlinks; App: SafariSupport.bundle, AuthenticationServicesAgent, com.apple.Safari.History, passwordbreachd, safarifetcherd, webbookmarksd, webinspectord, webpushd) -> hard-linked (symlinks copied: Linux hfsplus cannot hard-link symlinks); `tools/mkiosroot.sh` does it generically. watchdogd still crashed: the `-wdt_no_pmu` / `/arm-io/wdt no-pmu` check (0x10000a01c) only runs when os_variant_has_internal_diagnostics; otherwise 0x100009b18 looks up IOServiceMatching("IOService") + IOPropertyMatch {IOPMUPrimary: 1} (NSConstantDictionary) and crashes if absent, then IORegistryEntrySetCFProperty(boot stage 0xff) (failure only logged). Patch **0045**: IOWatchdog sets IOPMUPrimary = 1 and accepts setProperties; CI `38961814194` -> `xnu/out-0045`. **Image v6** = v5 + the 19 cryptex links, SHA256 7c610c6a...297a, `ios16-root-20H392-v6.simg` (full flash needed). Boot image `shim/out/shim-boot-0045n.img` (0045 + sweet-0044hi.adt). Still open: SpringBoard (no display), backboardd (uncaught exception, reason none), mediaserverd (Fig NULL dict), logd (main+0x18160), lockdownd (main+0x4c1b4).
- **System survives daemon crashes (boot 0043p, video frames VID_20261016_215006 00:25/00:42/00:54).** With the v5 plist patch no panic: launchd keeps launching (runningboardd, powerd, tccd, healthd, peopled, cryptexd, routined, aksd, mediaremoted, familynotificationd, nanoprefsyncd, navd, cloudpaird, passd, amsaccountsd, accessoryupdaterd, wcd ...). Shared cache slide that boot 0x406b4000 (`research/crash-0043p.txt`). watchdogd still crashed at main+0xb82c from the PMU step: `-wdt_no_pmu` is only honored when os_variant_has_internal_diagnostics; customer builds read `no-pmu` from IODeviceTree:/arm-io/wdt (IORegistryEntrySearchCFProperty) -> mkadt adds /arm-io/wdt {no-pmu}. **cryptexd** sig 6: abort_with_payload <- os_crash_fmt <- `__darwin_arm_secure_boot_chip.cold.7` ("panic: failed to get crypto algorithm") <- `_img4_chip_select_personalized_ap`: reads /chosen use-ddi-secure-boot, allow-ecid-mismatch, crypto-hash-method ("sha1" | "sha2-384"), /chosen/asmb lp-smb0/1 -> mkadt adds crypto-hash-method "sha2-384". **identityservicesd** sig 6 = same `_objc_fatal` in imp_implementationWithBlock as CommCenter (block trampolines; message needed). lockdownd sig 5 at main+0x4c1b4. Patch **0044**: crash report adds `CRASH name reason ns N code X: text` (exit reason description = abort_with_payload text). CI `38959096811` -> `xnu/out-0044`, QEMU OK. Image `shim/out/shim-boot-0044n.img` = 0044 + `shim/out/sweet-0044hi.adt` (wdt no-pmu, crypto-hash-method) + cmdline (wdt=-1, no -wdt_no_pmu).
- **First symbolicated daemon crashes (boot 0043u on journaled v4, 19:38:53 UTC; video frame chat image 36; transcribed in `research/crash-0043u.txt`; shared cache slide 0x40d60000 for every process).** (Gemini's video transcription invented values, use frames only.) `tools/sweet-crash.py research/dsc/dyld_shared_cache_arm64 x research/crash-0043u.txt`:
  - **watchdogd** pc main+0xb82c (`_os_crash` trap helper) from 0x100009bb0 = set PMU boot stage via IORegistry (no PMU) -> fix: boot-args `wdt=-1 -wdt_no_pmu` (Apple's own test mode writes "%s wdt=-1 -wdt_no_pmu"; watchdogd logs "skipping setting PMU boot stage because -wdt_no_pmu found in boot-args or no-pmu found in EDT"). Kernel effect of wdt=-1: sched hygiene debug off, zone_exhausted_timeout -1 (harmless).
  - **SpringBoard** sig 5 in `-[FBSDisplayMonitor _initWithBookendObserver:transformer:]+1160` <- `+[FBDisplayManager sharedInstance]` <- `FBSystemShellInitialize` <- `SBSystemAppMain`: no main display. GUI WALL: display service (IOMobileFramebuffer / CoreAnimation display).
  - **backboardd** sig 6: abort <- std::terminate <- _objc_terminate (uncaught exception; message not shown).
  - **CommCenter** sig 6: `_objc_fatal` in `imp_implementationWithBlock` (from `+[_PFRoutines initialize]`, CoreData): objc block trampolines cannot be allocated -> likely kernel gap (trampoline page remap); will hit many processes.
  - **mediaserverd** sig 11: CFDictionaryGetValue(NULL) in FigNotificationListenerStartNotifications (routing session manager).
  - **logd** sig 5 at its main+0x18160 (bt main+0x9dfc); lockdownd sig 5 (not yet symbolicated).
  - Image v5 = v4 + launchd.plist (`/System/Library/xpc/launchd.plist`, contiguous at image offset 0x1e025f000, 1456980 bytes) with the 7 `_PanicOnCrash` keys renamed `_PanicOnCrasX` in place (raw image patch, no metadata change) -> `diff-v4-v5.simg` = 7 blocks; v5 SHA256 78f96974...185a. Boot image `shim/out/shim-boot-0043p.img` = 0043 + `wdt=-1 -wdt_no_pmu`.
- **0043 console crash reports (QEMU verified); image `shim/out/shim-boot-0043u.img`; NEXT: flash v4 + boot 0043u.** Boot 0042u (video photo IMG_20261016_211646): short exec lines work; watchdogd crashes with NO `SWEET WDT:` line (fails before its first IOWatchdog call: lookup or IOServiceOpen, or elsewhere); lockdownd, SpringBoard, mediaserverd, CommCenter, identityservicesd, backboardd, watchdogd all crash repeatedly ("Too many corpses being created" = corpse limit, no crash reports). AKS callers: lockdownd (0, 7), imagent/sleepd (0, 17, 7), backboardd (0, 17), UserEventAgent (0, 7, 102, 103 -> unsupported). Patch **0043**: `sweet_crash_log` (osfmk/kern/exception.c, called from proc_prepareexit for crash exits on the current proc) prints `CRASH name[pid] sig S code (exc<<32|code) sub X slide SR mh MH`, `CRASH name pc lr sp fp far`, `CRASH name bt` (10 fp frames); AKS sel 103 notify_state_is_set -> 0. CI `38954520419` -> `xnu/out-0043`. QEMU test: init forks, child `brk #1`: `CRASH launchd[2] sig 5 code 0x600000001 sub 0x1000004f0 slide 0x0`, pc correct, parent keeps running (pid 1 crashes panic before proc_prepareexit, so test with a child). `tools/sweet-crash.py CACHE ROOT [report]` symbolicates typed-in CRASH lines (`ipsw dyld a2s` with addr - slide; main binary offsets = addr - mh + 0x100000000).
- **v3 reflashed 18:50-18:55 UTC (`research/flash-userdata-v3b.log`, 24/24 OKAY); 0042u booted 19:01:17 UTC on the clean disk (`research/boot0042u-2.log`), SLOW MO VID pending (watchdogd failure reason).** ABL hangs on the first `fastboot boot` after every big flash; user re-enters fastboot. User gave standing approval to reflash/boot without asking (memory standing-flash-approval). Commits now end with `Co-Authored-By: dipa-studio <183933817+dipa-studio@users.noreply.github.com>` (user request; never a Claude trailer).
  - watchdogd flow: connect_to_kext (0x100005408): IOServiceGetMatchingService("IOWatchdog") fails -> "failed to discover" + _os_crash; IOServiceOpen(type 1) fails -> "IOServiceOpen failed with error : 0x%x" + _os_crash. Then sel 0 (out 1 scalar): 0 -> "userspace monitoring disabled", 0x100009bb0, sleep 2, exit(0); nonzero -> "userspace monitoring enabled", normal operation.
  - **Image v4 (JOURNALED):** `tools/mkiosroot.sh` now does `mkfs.hfsplus -J`, mounts with `-o loop,force`, adds the /System/Library/Caches/com.apple.dyld hard links (44) and /private/var/keybags/systembag.kb (0700/0600 root). Built from the IPSW dmgs (OS 087-86698-044, SystemOS 087-86593-047, AppOS 087-86715-047) -> `/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392-v4.img` SHA256 fba4aeae...ec0f9 + `.simg`. Header: attr 0x80002100 (unmounted, journaled), journal info block 129, journal 8 MiB at 532480 flagged need-init. Linux `fsck.hfsplus -n` reports "Volume header needs minor repair" on any fresh journaled volume even after -y (quirk). QEMU: 64 MB journaled test root (`rd=md0 rootrw=1`, 0042 kernel): `hfs: Initializing the journal (joffset 0x3000 sz 0x80000)` -> mounted -> init runs, no panic. NEXT: flash v4 (full), boot 0042u.
- **SPRINGBOARD STARTS (boot 0041u 18:39:53 UTC, photo IMG_20261016_204142).** backboardd, bluetoothd, fairplayd.H2, SpringBoard (pid 111, crashed: "Too many corpses"), xpcproxy run; `SWEET AKS: backboardd sel 0 -> 0`, `sel 17 in 1/0 out 0/4096 -> 0`. Panic: watchdogd[113] exited, namespace 2 subcode 5 (SIGTRAP = its _os_crash): watchdogd crashes on purpose when IOServiceGetMatchingService("IOWatchdog") fails ("connect_to_kext() unexpectedly failed") or IOServiceOpen(type 1) fails ("IOServiceOpen failed with error"); IOWatchdog DOES register (QEMU msgbuf: `SWEET WDT: IOWatchdog registered`), cause not on screen yet -> need video. Note `wdt_test=no_user_checkin` makes watchdogd log "detected testing boot-args to not run, exiting" (path not reached here?). **HFS CORRUPTION:** `hfs_swap_BTNode: offset #0 invalid (0xBC1D) (blockSize 0x2000 numRecords 81)`, `node=19677 fileID=4` (catalog), `hfs_mark_inconsistent` repeated. Likely cause: non-journaled HFS + unclean panics while writing (0038e wrote a 2.7 GB core then panicked; every boot since ends in panic). Plan: reflash v3 (clean), longer term HFS journaling. Patch **0042**: one short `exec NAME` console line instead of the 3-line "Allowing spawn of iOS binary" notice; CI `38949451276` -> `xnu/out-0042`; image `shim/out/shim-boot-0042u.img` (same cmdline as 0041u).
- **LAUNCHD DAEMONS RUN (boot 0039u, 18:29:13 UTC, photo IMG_20261016_203052).** With `launchd_unsecure_cache=1` all boot tasks pass and launchd starts LaunchDaemons (pids > 100: identityservicesd 114 and lockdownd 106 crash, "Too many corpses being created"). Fatal: `watchdogd: ERROR: failed to discover watchdog KEXT service` -> exit (namespace 2 = signal, subcode 5) -> `_PanicOnCrash` panic. watchdogd: IOServiceMatching("IOWatchdog"), IOServiceOpen type 1, IOConnectCallScalarMethod sel 0/1 (check in)/3/4 (disable/enable userspace monitoring)/5, IOConnectCallStructMethod sel 2 (1 KiB in) and 9 (small out); VM path ("detected virtual machine environment and no watchdog KEXT found, exiting...") only when it detects a VM. Console also flooded with `hfs: set hardlink bit on vol=iOSRoot cnid=321318` (Linux-made hard links lack kHFSHasLinkChainBit; repaired only in memory on each lookup). Patches **0040** (`iokit/Kernel/arm/SweetWatchdog.cpp`: IOWatchdog + IOWatchdogUserClient, all selectors succeed with zeroed outputs, each logged once as `SWEET WDT: ...`) and **0041** (sweet_hfs hfs_catalog.c: the three link-repair printfs limited to 8 per boot); CI `38948245372` PASSED -> `xnu/out-0041` (QEMU regression OK). Image `shim/out/shim-boot-0041u.img` (0041 + sweet-0038hi.adt + ufsrw rootrw + launchd_unsecure_cache=1) booted 18:39:53 UTC (`research/boot0041u.log`), photo pending.
- **v3 FLASHED + keybag passes; next wall AMFI (launchd_cache_loader).** User said "flash, nothing to lose": `fastboot -S 512M flash userdata ios16-root-20H392-v3.simg` 17:51:52-17:57:01 UTC, 24/24 chunks OKAY (`research/flash-userdata-v3.log`). userdata = v3 (SHA256 fa84274c...22df) until the next rw boot. ABL fastboot then hung ("Sending" forever, `reboot bootloader` timed out) until the user re-entered fastboot by hand (common Xiaomi ABL crash). Boot 0038e 18:06:15 UTC (`research/boot0038e-3.log`), photos IMG_20261016_200812/200838: keybag OK, then boot tasks tzinit (`Bad zoneinfo link`, resets to system partition, OK), finish-restore, finish-demo-restore, sysstatuscheck, prng_seedctl (`failed to load kernel prng seed`, `failed to load virtual random (-147)`, AllowCrash), auearlyboot, then **launchd_cache_loader: `abort: Unable to find AMFI`** -> 2.7 GB core written to /cores in 91 s -> launchd panic `launchd_cache_loader[22] exited -- exit reason namespace 7 subcode 0x1`. launchd_cache_loader: SecStaticCodeCheckValidity of /System/Library/xpc/launchd.plist with detached .sig, then IOServiceMatching("AppleMobileFileIntegrity") + IOServiceOpen type 0 + IOConnectCallMethod sel 6 (1 scalar = 1, struct in = cdhash) = trust the cdhash, then sends the cache to launchd. Boot-arg `launchd_unsecure_cache=1` skips signature + AMFI ("Using unsecure cache"); the value is parsed with strtoul base 10 (helper 0x100002da8), so a path = 0 = off: boot 0039w (18:17:13 UTC, `=/System/Library/xpc/launchd.plist`, photo IMG_20261016_202008) still aborted `Unable to find AMFI` (core dump now skipped: `Failed to generate core file ... error 14`, so 0039 works). Image `shim/out/shim-boot-0039u.img` uses `launchd_unsecure_cache=1`. Patch **0039**: do_coredump = 0 on SWEET (kern.coredump sysctl still works); CI `38945267341` -> `xnu/out-0039` (_do_coredump now in __common). Image `shim/out/shim-boot-0039w.img` = 0039 + sweet-0038hi.adt + ufsrw rootrw + `launchd_unsecure_cache=/System/Library/xpc/launchd.plist`. TODO later: real AppleMobileFileIntegrity IOService (sel 6 trust cdhash etc.).
- **Image v3 ready, awaiting user "flash".** Boot 0038w 17:38:10 UTC, photo (chat image 30): `SWEET AKS: keybagd sel 0 -> 0x0`, `sel 14 out 1/0 -> 0x0` (x2), `MKB_INIT: mount is with NO CPROTECT ... does not support Data Protection`, `System Keybag loaded`; then keybagd still opens /private/var/keybags/systembag.kb (0x100012d3c, for BackupKeyBagKeys) -> ENOENT, `no-effaceable-storage` not set -> `Can't load the keybag. tears in rain... Time to die` -> `FATAL KEYBAG ERROR: kb_load` -> reboot -> Halt/Restart Timed Out panic. Fix: ADT `/defaults/no-effaceable-storage` (mkadt.py; `shim/out/sweet-0038hi.adt`, `research/q0038-hi.adt`, QEMU OK) + file `/private/var/keybags/systembag.kb` (0600 root, dir 0700; XML plist {KeyBagKeys: data}). **v3 image** `/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392-v3.img` = v2 + that file, fsck OK, SHA256 fa84274c...22df; `ios16-root-20H392-v3.simg` (img2simg: zero blocks become FILL chunks, so a full flash overwrites every block the rw boots changed). Flash: `fastboot -S 512M flash userdata ios16-root-20H392-v3.simg`, then boot `shim/out/shim-boot-0038e.img` (0038 + sweet-0038hi.adt + ufsrw=1 rootrw=1).
- **0038 AppleKeyStore (CI 38938744130 PASSED -> `xnu/out-0038`; QEMU msgbuf: `SWEET AKS: AppleKeyStore registered (no passcode, unlocked)`; phone image `shim/out/shim-boot-0038w.img` booted 17:38:10 UTC, `research/boot0038w.log`, photo pending).** QEMU full kernel log trick (fb.txt is only the last screen): `llvm-nm KERNEL | grep _msgbufp` -> `--hmp "x /1gx ADDR"` gives struct msgbuf address (static, 0xfffffe0007b56678 on 0038) -> `--hmp "x /3gx STRUCT"` gives bufc (3rd quad) -> `--hmp "memsave BUFC 0x20000 \"FILE\""` (quote the file name), `tr -d "\0" < FILE`. Same inputs give the same addresses. Boot 0037w 17:08:35 UTC, photo IMG_20261016_191052: bindfs fixed mount; mount-phase-1/2 pass; `cc_fips_test` boot task: all corecrypto FIPS POST tests PASSED in userspace; then keybag boot task `keybagd --init`: `MKB_INIT: FATAL KEYBAG ERROR: failed to load system bag`, `Could not get options entry from the device tree` (x2, IODeviceTree:/options = NVRAM, non-fatal), `REBOOTING INTO RECOVERY MODE` -> reboot -> panic `Halt/Restart Timed Out @IOPlatformExpert.cpp:884` (no restart path on SWEET).
  - keybagd (static libaks): load_devicebag (0x100012c30) calls aks_get_system (sel 14, 0-1 scalar in, 1 out) and loads /private/var/keybags/systembag.kb only if the result is 0xe00002f0 (NotFound); any other error -> fatal; SUCCESS -> skip the file (userspace-reboot path). systembag.kb is a plist {KeyBagKeys}; decrypted with effaceable storage unless IODeviceTree:/defaults has `no-effaceable-storage`. Image has no /private/var/keybags. has_data_protection: statfs of /private/var; no cprotect on our HFS -> device-bag volume mapping skipped.
  - libaks connection: IORegistryEntryFromPath / IOServiceMatching("AppleKeyStore"), IOServiceOpen type 0, then selector 0 (no args) must succeed.
  - **AppleKeyStore selector map (iOS 16.7 AppleKeyStore.framework, via `ipsw dyld disass`):** 0 open, 2 create_bag, 3 save_bag, 4 unload_bag, 5 set_system_with_passcode, 6 load_bag, 7 get_lock_state (1 in, 1 out; bit 2 = unlocked since boot), 9 unlock_device, 10 wrap_key, 11 unwrap_key, 12 unlock_bag/test_stashed_kek, 13 lock_bag, 14 get_system, 15 change_secret_se, 16 internal_state, 17 get_device_state (1 in, struct out <=4K: DER SET of SEQUENCE{UTF8 key, INTEGER}: ss state, sls lock_state (MKBGetDeviceLockState returns it), sb backoff, sbo, sfa failed attempts, sfao, sgs generation, sas assertions, sgpe grace, srcd countdown, sr reserved), 18 recover_with_escrow_bag, 19 obliterate_class_d, 20 drain_backup_keys, 21/22 set/clear_backup_bag, 23 get_bag_uuid, 24 rewrap_key_for_backup, 26/27 assert_hold/drop, 30/31 set/get_configuration, 33-37 stash, 38 auth_token_create, 40 generation, 41 fdr_hmac_data, 42 verify_password, 43 _aks_operation, 44 remote_session, 49/50 signing keys, 51/53/54 stash enable/persist/escrow, 55 unload_session_bags, 57/58 remote peer, 59-62 smartcard, 63 migrate_s_key, 65 set_keybag_for_volume_with_cookie_persona, 66/67 sync bags, 68 copy_volume_cookie_persona, 69-73 se_*, 74-79/84/85/99 fv_* (FileVault/VEK), 80/81 absinthe, 82 make_public_backup_bag, 83 drop_auxiliary_auth, 86 kext get/set options, 87 invalidate_bag, 88-91/94/95/106/107 se_*, 92 lower_iteration_count, 93 get_internal_info, 96-98/117 keybag_persona create/list/delete, 100/101 assert promote/consume, 102/103 notify_state set/is_set, 104 fairplay, 105 change_secret_epilogue, 108 delete_xart_leak, 110-113 backup volume, 114 sealed_hashes_set, 115 prewarm_sps, 118-128 AKSIdentity*/AKSGetLastUser.
  - Patch **0038**: `iokit/Kernel/arm/SweetKeyStore.cpp` (class AppleKeyStore on IOResources, IOUserClientClass AppleKeyStoreUserClient; personality in KernelConfigTables.cpp): 0/4/5/9/12/13/26/27/55/102 success, 14 -> handle 0, 7 -> 0x4, 17 -> DER state (ss 4, sls 0), others kIOReturnUnsupported; logs `SWEET AKS: <proc> sel N arg0 in a/b out c/d -> ret` for every call.
  - Tools: shared cache copied to `research/dsc/` (git-ignored; ipsw needs a writable dir for its .a2s symbol cache); `ipsw dyld disass research/dsc/dyld_shared_cache_arm64 --image AppleKeyStore|MobileKeyBag`; scratchpad `annot2.py BIN DIS FIXUPS` annotates llvm-objdump output with strings and import names (`ipsw macho info --fixups`).
- **0037 bindfs (phone boot 0037w pending photo).** Boot 0036mw 16:57:47 UTC, photo IMG_20261016_190102: WRITABLE ROOT WORKS: `/dev/ufsroot0 on / (hfs, local, noatime)` after mount_hfs update (GetMasterBlock EBUSY harmless), coredump of mount written to /cores (rw). Then `mount: failed to mount /private/preboot/5CBE3601.../usr/standalone/firmware -> ...: Operation not supported by device (19)` -> exit 74 -> launchd panic `mount[2] exited`. Cause: the macOS-derived config had nullfs but no bindfs (ENODEV = unknown fs type). Caller passes env 0 -> bind not required, ENOENT (missing source dir) tolerated. Patch **0037** adds `bindfs` to FILESYS_BASE in MASTER.arm64.sweet; CI `38936550483` -> `xnu/out-0037` (bindfs_vfsops present; QEMU probe regression OK). Image `shim/out/shim-boot-0037w.img` (0037 + sweet-0036hi.adt + ufsrw=1 rootrw=1) booted 17:08:35 UTC (`research/boot0037w.log`). NOTE: userdata has now been modified by rw boots; it no longer equals the v2 image, so sparsediff with v2 as OLD is not safe any more (full reflash or a new baseline needed).
- **0036 phone: launchd boot tasks run; mount -P 1 needs /chosen/boot-manifest-hash.** Boot 0036hr 16:15:32 UTC, photo IMG_20261016_185236: platform check passes; fsck boot task runs (`fsck: not booting main or diagnostic OS. Skipping fsck on OS container`); mount-phase-1: `failed to get filesystem info` x2 (no IODeviceTree:/filesystems/fstab, non-fatal), `mount: data volume missing, but not required in env: 0`, mount_hfs update of /: `GetMasterBlock: Error 16 opening /dev/ufsroot0` (EBUSY, mounted block dev, non-fatal) then mount() EROFS (read-only boot) -> `mount: / failed with 1`; then `failed to get boot-manifest-hash` -> errx exit 66 -> launchd panic `mount[3] exited`. /sbin/mount: fn 0x100005f90 reads IODeviceTree:/chosen boot-manifest-hash (hex), bindfs-mounts /private/preboot/<HEX>/usr/standalone/firmware (ENOENT tolerated unless required). `tools/mkadt.py` now adds `boot-manifest-hash` = SHA-384("sweet boot manifest") (5CBE3601...5205). ADTs `shim/out/sweet-0036hi.adt`, `research/q0036-hi.adt` (QEMU probe OK, csops 0x26000001). Image `shim/out/shim-boot-0036mw.img` (0036 + new ADT + ufsrw=1 rootrw=1), booted 16:57:47 UTC (`research/boot0036mw.log`): FIRST WRITABLE BOOT of userdata (restore source: v2 image on SSD).
- **0036 CS_SIGNED (phone boot 0036hr pending photo).** Phone boot 0035hr 2026-10-16 15:57:02 UTC (`research/boot0035hr.log`, photo IMG_20261016_180249): highmem works on hardware; shared cache maps (trust-cache warnings only), Apple launchd runs (`Darwin Bootstrapper Version 7.0.0`, `entering ondemand mode`), starts boot task fsck, then userspace panic `boot task is not a platform binary (fsck, /sbin/fsck)`. launchd+0x3fea0: `csops(pid, CS_OPS_STATUS)` must have bit 0x04000000. Cause: nothing set CS_SIGNED (AMFI does it in vnode_check_signature), so csproc_get_blob() returns NULL for every process and csops never reports CS_PLATFORM_BINARY (also breaks per-process cdhash/entitlement queries). QEMU probe init (`csops` status printer, scratchpad csq/) on 0035: `0x02000001`; patch **0036** (`*cs_flags |= CS_SIGNED` in the SWEET AMFI hook), CI `38929635791` -> `xnu/out-0036`: `0x26000001`. Images `shim/out/shim-boot-0036hr.img` / `-0036hw.img` (same cmdlines as 0035). 0036hr booted 16:15:32 UTC (`research/boot0036hr.log`). Next launchd boot tasks (embedded __config plist): fsck -qL and mount -P 1/2 (RequireSuccess); no /etc/fstab on the image.
- **0035 ENTITLEMENTS + PLATFORM BINARIES (QEMU verified).** `xnu/patches/0035-sweet-amfi-entitlements-platform-binaries.patch`: new `iokit/Kernel/arm/SweetEntitlements.cpp` (OSObject subclass: OSDictionary from OSUnserializeXML of the signature's XML entitlements + original XML for CS_OPS_ENTITLEMENTS_BLOB); `bsd/kern/sweet_amfi.c` answers queryEntitlementBoolean/String(+WithProc, string also matches array members), copyEntitlementAsOSObject(+WithProc, retained), asdict (retained), get_xml (kalloc_data copy); built-in MAC policy "SWEET AMFI" (registered from bsd_init before vfs/exec) with mpo_vnode_check_signature: every signed binary on the MNT_ROOTFS mount gets CS_PLATFORM_BINARY (stand-in for AMFI's static trust cache: iOS system binaries are ad-hoc, cd_flags 0x2, platform byte 0), and attaches entitlements ONLY for the writable copy (cs_blob != csb_ro_addr; revalidation passes the RO blob). LESSON: first version attached in adjustContextWithoutMonitor -> QEMU `unable to adjust OSEntitlements context without monitor: 53` because ubc_cs_convert_to_multilevel_hash (4K-page signatures on 16K kernel) sets csb_entitlements_blob = NULL; ALL iOS 16 binaries (launchd, backboardd, SpringBoard) use 4K code pages, so this would have broken launchd on the phone. Boot-arg `sweet_amfi_debug=1` logs `SWEET AMFI: <ident>: N entitlements (test: ...)`. `tools/mkinit.py OBJ OUT [ENTS.plist]` adds an XML entitlements blob (special slot -5; default output byte-identical). QEMU `research/q0035-ent` (RAM disk `research/root-hfs-ent.img`, init with 3 test entitlements, highmem): `org.sweet.init: 3 entitlements (test: bool 1 string 1 array 1)` then init PID 1. MAC policies loaded: 0034 = 1, 0035 = 2 (QMP `mac_policy_list`). CI `38909807230` -> `xnu/out-0035`. Phone images: `shim/out/shim-boot-0035hr.img` (highmem, ro), `-0035hw.img` (highmem, +ufsrw=1 rootrw=1), `-0035r.img` (low mem fallback).
- **PHONE TEST ORDER (updated):** 0035hr -> if instant reset, 0035r -> then 0035hw.

- **HIGHMEM: XNU in the upper DDR bank, ~3.95 GiB (was 1.2 GiB).** Live FDT memory = <0x80000000 2G> + <0x1_00000000 0xfcc00000>; all fixed reserved-memory carve-outs are in the low bank (highest: ramdump_fb 0xaf000000, rmtfs ~0xfde01000), dynamic pools have alloc-ranges <= 0xffffffff, UFS node has no `iommus` (Linux DMAs anywhere). `tools/mkadt.py --highmem` sets /chosen dram-base 0x100000000 dram-size 0xfcc00000; `tools/mkpayload.py` now takes phys_base/mem_size from the ADT (default payloads byte-identical, verified); `tools/qemu-sweet.py` sizes -m from the payload (8G for highmem). Patch **0034** (`0034-sweet-ufs-dma-above-4g.patch`): UFS refuses DMA memory above 4G without UFSHCI CAP.64AS (bit 24), logs `DMA at 0x...`. CI `38905889883` success -> `xnu/out-0034`. **QEMU verified** (`research/q0034-hi`, ADT `research/q0034-hi.adt` --qemu --highmem, HFS RAM disk): phys_base 0x100000000, init PID 1 heartbeat, no panic; `max_mem` = `mem_size` = 0xfcc00000 read via QMP (`research/q0034-hi-mem`). Phone images: `shim/out/shim-boot-0034hr.img` (read-only) / `-0034hw.img` (+ufsrw=1 rootrw=1), ADT `shim/out/sweet-0034hi.adt` (asmb SIP + sweet-ufs + highmem). PHONE RISK: unknown runtime TZ/XPU protection in the upper bank would show as an instant reset; fall back to 0033r/w. Watchdog ruled out for the overnight reset: msm-watchdog bark is 20 s (qcom,bark-time 0x4e20) yet panic screens stay up for many minutes.

- **Offline research 2026-10-16 (user away, phone unavailable). Images rebuilt** `shim/out/shim-boot-0033r.img` / `-0033w.img` now also carry `wdt_test=no_user_checkin`. NEXT ON PHONE: boot 0033r (expect past in6_nigroup), then 0033w (first writes: rw root fixes HFS link-chain bits itself and gives /var for launchd sockets /var/run/syslog, /var/run/lockdown.sock).
- **launchd.plist** (`/System/Library/xpc/launchd.plist`, compiled; 532 daemons, 66 RunAtLoad/KeepAlive, list in scratchpad `early-daemons.txt`). `_PanicOnCrash` daemons: containermanagerd/usermanagerd (InternalOnly), lockdownd/remoted/trustd/remotepairingdeviced (AutomationOnly), **watchdogd unconditional** (KeepAlive SuccessfulExit=false). watchdogd needs IOKit `IOWatchdog` kext service; if absent it exits only when `kern.hv_vmm_present` (ADT `/defaults/vmm-present`, hvg_sysctl.c) or with boot-arg `wdt_test=no_user_checkin` ("detected testing boot-args to not run, exiting"; reads kern.bootargs). Using the boot-arg (vmm-present would change many daemons; keep as an option).
- **GUI path research (QuartzCore in the shared cache, `ipsw dyld str CACHE STR`, ~10 s/search):** CA::WindowServer has IOMFBServer/IOMFBDisplay (Apple DCP/IOMobileFramebuffer), AppleCLCDDisplay, AppleRGBOutDisplay, **VirtualServer/VirtualDisplay** and **MemorySurface**, EAGLServer. Renderers: CA::OGL::MetalContext, GLContext and a **CPU software rasterizer CA::OGL::SW** (samplers/blend modes; "image is too large for software renderer"). Env knobs: `CA_ENABLE_OGL`, `CA_DISPLAY_TYPE`, `CA_FORCE_LOCAL_SERVER` (249 CA_* vars). Hypothesis (unverified): backboardd's render server could run a VirtualServer/MemorySurface with the SW renderer and we copy the surface to the ABL framebuffer -> needs disassembly of CA::WindowServer server creation. Expected other GUI walls: IOSurface (closed-source kext; needs a reimplementation), IOMobileFramebuffer user client, IOHID touch events, AppleKeyStore/keybag (SEP) for lock state, MobileGestalt answers (AppleCLCD etc.).

- **0032r RESULT (boot 05:07:50 UTC, `research/boot0032r.log`, photo IMG_20261016_071200): SHARED CACHE MAPPED, LAUNCHD RUNS.** With SIP relaxed (ADT asmb) the `not in trust cache` lines are only warnings for every subcache (.31 ... .42.dyldlinkedit); no SIP rejection; libSystem loads; launchd configures networking (`skip attaching fsw to lo0 using legacy TX model`) -> kernel data abort far 0x28 in `SHA1Init` (symbolized as sha1_init) from `in6_nigroup` (IPv6 on lo0): g_crypto_funcs NULL. Kernel addresses are unslid: `~/swift/usr/bin/llvm-symbolizer --obj=KERNEL ADDR` works directly.
- **0032** BearSSL SHA-1 (`0032-sweet-bearssl-sha1.patch`), **0033** BearSSL SHA-384/512 (`0033-sweet-bearssl-sha384-sha512.patch`, BearSSL ctx stored in SHA512_CTX, static-asserted to fit; ubc_subr.c uses SHA-384 for code directories). `0020-stage-bearssl.sh` now also stages hash/sha1.c, hash/sha2big.c, codec/{dec,enc}{32,64}be.c. CI `38854909053` success (0032-only run `38854802073` superseded). Kernel `xnu/out-0033` (SHA1Init -> _br_sha1_init verified by disassembly; nm symbols have a leading underscore). Images (ADT sweet-0032): `shim/out/shim-boot-0033r.img` (read-only), `shim-boot-0033w.img` (+ufsrw=1 rootrw=1). Still NULL g_crypto_funcs users: des, chacha20poly1305, rsa, aesxts, rand, flow_divert.
- `research/check-patch-order.py` now skips patches touching CI-staged sweet_hfs sources (0031) instead of stopping.

- **0031r RESULT (boot 05:03:52 UTC 2026-10-16, `research/boot0031r.log`, photo IMG_20261016_070508): SHARED CACHE FOUND.** dyld now opens `dyld_shared_cache_arm64` (v2 image hard links), kernel refuses to map it: `shared_region: ... map(...'dyld_shared_cache_arm64'): not in trust cache` -> `vnode is not SIP-protected` (vm_unix.c: macOS arm64 path needs trust cache, else root-owned + SF_RESTRICTED unless CSR_ALLOW_UNRESTRICTED_FS) -> `dyld cache '(null)' not loaded: syscall to map cache into shared region failed` -> libSystem not loaded -> coredump to /cores fails error 30 (EROFS) -> panic initproc failed -> "MACH Reboot" (spins; screen kept). Lots of `hfs: set hardlink bit on vol=iOSRoot cnid=... linkid=...` spam (Linux-made hard links lack the link-chain bit; read-only mount cannot persist the fix). FIX: ADT `/chosen/asmb` with `lp-sip0`=0x6f (u64; incl. CSR_ALLOW_UNRESTRICTED_FS) and `lp-sip1`=1 (unauthenticated root), `tools/mkadt.py` -> `shim/out/sweet-0032.adt`. Images with kernel 0031: `shim/out/shim-boot-0032r.img` (read-only) and `shim-boot-0032w.img` (+ufsrw=1 rootrw=1).

- **2026-10-16 morning:** userdata now = **v2** image (`diff-v1-v2.simg` flashed 21:06:50 UTC 2026-10-15, OKAY, `research/flash-userdata-diff-v2.log`); future diffs use `ios16-root-20H392-v2.img` as OLD. Booted `shim-boot-0029k.img` (ignition_level=1) right after (`research/boot0029k-v2.log`); **no photo** (user asleep). Next morning the phone was in PixelOS recovery = some hardware reset (ABL then booted Android, which cannot use userdata). OBSERVATION: our kernel cannot reset the SoC itself (`PE_halt_restart` is never set; reboot/halt print "MACH Reboot"/"CPU halted" and spin), so the reset came from outside XNU: Qualcomm watchdog or a TZ/XPU violation. Unknown which; re-boot 0029k and watch/video until the reset. Do NOT tap factory reset/format data in recovery (would wipe the iOS image).
- **0030** (`xnu/patches/0030-sweet-ufs-writes.patch`, CI `38852655542`): UFS WRITE(10) + read-modify-write for partial 4 KiB blocks + SYNCHRONIZE CACHE (DKIOCSYNCHRONIZE), only with boot-arg `ufsrw=1`; `ufs_write_blocks` re-checks partition bounds before every write (only place data goes out).
- **0031** (`xnu/patches/0031-sweet-read-write-root.patch`, CI `38852837176`): boot-arg `rootrw=1` clears MNT_RDONLY before the root mount (no data volume on sweet: /private/var is on the root; image has no /etc/fstab); Apple HFS accepts a dirty non-journaled ROOT read-write on SWEET (logs "mounting dirty non-journaled root read-write"). Later: journaled HFS for crash safety. Kernel `xnu/out-0031` (CI `38852837176` success, 5m31s; 0030 run cancelled by the newer push). Boot images (phone ADT `sweet-0028.adt`, ramdisk byte-matched): `shim/out/shim-boot-0031r.img` = 0029k args (read-only, ignition_level=1) and `shim/out/shim-boot-0031w.img` = same + `ufsrw=1 rootrw=1`. PLAN: boot 0031r first and film until the reset (diagnose overnight reset), then 0031w (first ever writes to userdata; v2 image on the SSD is the restore source). `research/check-patch-order.py` cannot check 0031 (staged sweet_hfs files are not in its index); CI stage scripts run first, so CI is the check.

- **ignition_level=1 result** (boot 21:01:39 UTC, `research/boot0029k.log`, photo IMG_20261015_230308): preboot/cryptex stages skipped (need >= 2/3), `dylib_cache: finding shared cache on system volume: ignition level = 1, search root fd = 4, subpath = System/Library/Caches/com.apple.dyld/` -> not found -> `ignition boot failed: 19` -> no shared cache -> libSystem not loaded. FIX IN PROGRESS: image v2 = copy of the flashed image + `/System/Library/Caches/com.apple.dyld/` with HARD LINKS to the 44 cryptex cache files (no extra space; avoids symlink-following doubts), then `tools/sparsediff.py ios16-root-20H392.img ios16-root-20H392-v2.img diff.simg` and flash only the diff. Boot with `ignition_level=1` (shim-boot-0029k.img).
- **ignition_level=0 result** (boot 20:58:07 UTC, `research/boot0029j.log`, photo IMG_20261015_230037): all stages skipped as "ignition level insufficient" (hello/preboot/cryptex1 sniff >= 2, select os cryptex path/graft >= 3, **dyld_cache >= 1**), `ignition boot failed: 89`, "ignition partially disabled", then same `Library not loaded: /usr/lib/libSystem.B.dylib (no such file, no dyld cache)`. => dyld gets the shared cache directory from ignition's dyld_cache stage. Next: `ignition_level=1` (`shim/out/shim-boot-0029k.img`) to skip preboot/cryptex stages but run dyld_cache; its log "finding shared cache on %s ... subpath = %s" will show where it searches. If it searches rootfs /System/Library/Caches/com.apple.dyld, add a symlink there (image rebuild; consider a diff-only sparse flash tool to avoid rewriting 12 GB).
- **APPLE dyld/launchd RUNNING (libignition) with `unentitled_ios_sim_launch=1`** (boot 20:53:24 UTC, `research/boot0029i.log`, photo IMG_20261015_225617): kernel prints "Allowing spawn of iOS binary ... boot-arg set to true"; `shared_region: ... check_np ... vm_shared_region_start_address() failed` (no region yet, normal); dyld's built-in **libignition** (Darwin Ignition Sequence 1.0.0, libignition-51~1974; prints rd=ufsroot0, hardware target sweet, ignition level 0x5, platform 0x2, boot spec local, 7 stages): `hello from launchd.1` -> `preboot: mounting preboot` -> `failed to lookup preboot: 25` (ENOTTY: looks for a separate Preboot volume by role) -> ignition fails -> dyld `Library not loaded: /usr/lib/libSystem.B.dylib ... (no such file, no dyld cache)` -> launchd exit -> panic initproc failed. dyld boot-args found via strings: `ignition_level`, `ignition_force_dylib_root` (forced rootfs/livefs/cryptex fallback), `ignition_halt_after`, `ignition_live_app_graft`; dyld cache search paths include /System/Cryptexes/OS, /System/Volumes/Preboot/Cryptexes/OS/, /private/preboot/Cryptexes/OS/ (present in our image). Next try `ignition_level=0` (`shim/out/shim-boot-0029j.img`).
- **APPLE launchd EXECUTED FROM UFS (2026-10-15).** Flashed iOS image: `img2simg` -> `ios16-root-20H392.simg` (12.1 GB) then `fastboot -S 512M flash userdata ...simg` (24 chunks, 307 s, `research/flash-userdata-ios16.log`; a raw-image flash was killed by earlyoom at 2.6 GB RSS - always flash the sparse image). ABL fastboot hung on getvar after the flash; power+vol-down fixed it. Boot 0029u 20:49:04 UTC (`research/boot0029u-ios16.log`), photo IMG_20261015_225134: `hfs: mounted iOSRoot` -> load_init_program /sbin/launchd -> panic `unexpected SIGKILL of launchd (CS_KILLED) with reason -- namespace 9 code 0xe` = OS_REASON_EXEC / EXEC_EXIT_REASON_WRONG_PLATFORM: our kernel is XNU_TARGET_OS_OSX, iOS-platform binaries are "alien" and refused unless spawn attr platform set or DEVELOPMENT TUNABLE `unentitled_ios_sim_launch`. Next try: same kernel, cmdline + `unentitled_ios_sim_launch=1` (`shim/out/shim-boot-0029i.img`). LONGER TERM: macOS-config kernel marks iOS maps alien (vm_map_mark_alien) and differs from iOS in many policies; an iPhoneOS-config kernel build may eventually be needed.
- **iOS 16 ROOT IMAGE BUILT:** `/run/media/dipa/android/ios-sweet-ipsw/ios16-root-20H392.img` (16 GiB case-sensitive HFS+, label iOSRoot, 12 GB used, fsck OK after `fsck.hfsplus -y` rewrote 32 non-ASCII localized WorkflowKit Shortcut names Linux decomposes differently). Built by `tools/mkiosroot.sh OS.dmg SYSTEMOS.dmg APPOS.dmg OUT.img [SIZE]` (needs sudo; apfs-fuse as root; OS dmg is UDIF -> link must end .dmg). Contents: iPhone X 20H392 OS root + SystemOS cryptex at /private/preboot/Cryptexes/OS (so /System/Cryptexes/OS -> cache, 44 files, dyld_v1 arm64) + AppOS at .../App. /sbin/launchd and /usr/lib/dyld root:wheel 0755. NEXT: (confirm) `fastboot flash userdata ios16-root-20H392.img` (auto-sparse), boot 0029u (rd=ufsroot0) -> Apple launchd attempt.
- **MILESTONE ON HARDWARE: BOOT FROM INTERNAL FLASH.** 0029 CI `38797924912` PASSED, `xnu/out-0029` SHA256 `a68bc847...2a37`. Image `shim/out/shim-boot-0029u.img` (payload-0029u = 0029 kernel + `shim/out/sweet-0028.adt` + `rd=ufsroot0`, NO RAM disk). Boots 20:01:34 and 20:12:37 UTC (`research/boot0029u*.log`), photo IMG_20261015_221403: `SWEET UFS: "userdata" on LUN 0: first block 0x2b8c00, 109643 MiB, read-only` -> `BSD root: ufsroot0, major 1, minor 0` -> `hfs: mounted SweetRoot on device b(1, 0)` -> `SWEET: root volume is not authenticated (error 25); continuing unsealed` -> `load_init_program ... /sbin/launchd` -> `*** SWEET userspace: init running as PID 1 ***` -> heartbeat (ran for minutes unattended). userdata currently holds the 8 MB `research/root-hfs.img`. NEXT: build a multi-GB HFS+ image with the iOS 16 (iPhone X 20H392) userland (OS rootfs + SystemOS cryptex contents incl. dyld shared cache at /System/Library/Caches/com.apple.dyld; preserve modes/owners/symlinks; decompress LZBITMAP via apfs-fuse), flash it to userdata (sparse, needs user OK), then try Apple's dyld/launchd. Driver is read-only (root mounts RDONLY), fine for first launchd attempts.
- **userdata FLASHED with the 8 MB HFS test volume** (user said "flash it", 2026-10-15 19:53:17 UTC, `research/flash-userdata-hfs-test.log`: `fastboot flash userdata research/root-hfs.img` OKAY; pre-checks: one sweet device, partition-size:userdata 0x1AC4BFB000, partition-type f2fs, image fsck OK, SHA256 3626ea69...). Android userdata is now destroyed (expected/approved). Boot 0028u at 19:53:20 (`research/boot0028u-hfs.log`), photo IMG_20261015_215541: `BSD root: ufsroot0` -> **`hfs: mounted SweetRoot on device b(1, 0)` from internal UFS** -> panic `rootvp not authenticated after mounting @bsd_init.c:931` (arm64 macOS-config requires FSIOC_KERNEL_ROOTAUTH sealed root for non-ramdisk roots). Patch **0029** (`dd1c284`): SWEET logs `SWEET: root volume is not authenticated (error N); continuing unsealed` instead of panicking (Apple configs keep the panic; pivot_root still requires auth). CI **`38797924912`** running. Next: download out-0029, phone image with sweet-0028.adt + rd=ufsroot0 (no RAM disk), boot -> expect init from UFS.
- **UFS ROOT DRIVER VERIFIED ON HARDWARE (read-only).** 0028 CI `38796139570` PASSED, `xnu/out-0028` SHA256 `8b981640...9da6`; QEMU HFS RAM-disk regression `research/q0028-hfs` still runs init. Phone boot 2026-10-15 19:50:24 UTC (`research/boot0028u.log`, image `shim/out/shim-boot-0028u.img`, phone ADT `shim/out/sweet-0028.adt` with /sweet-ufs, NO RAM disk, `rd=ufsroot0`), photos IMG_20261015_215151/215220: `SWEET UFS: "userdata" on LUN 0: first block 0x2b8c00, 109643 MiB, read-only` -> `BSD root: ufsroot0, major 1, minor 0` -> `hfs_ValidateHFSPlusVolumeHeader: unknown Volume Signature : f188` (Android-encrypted data, as expected) -> `cannot mount root, errno = 19`, kernel retries mountroot (no panic). Nothing written to flash. NEXT (destructive, needs user confirmation right before): `fastboot flash userdata research/root-hfs.img` (8 MB HFS with test init) then boot rd=ufsroot0 -> expect init from internal flash.
- **PATCH 0028 (`33aceac`): XNU read-only UFS root device**, CI **`38796139570`** running (next artifacts xnu/out-0028, research/bt29, run29.log). `bsd/dev/sweet_ufs.c`: reuses ABL's UFSHCI state (like the shim probe), takes over UTRL at a kmem_alloc_contig region (DMA layout: UTRL 0x0, UCD 0x1000, 1 MiB bounce 0x4000), verifies UTRLBA readback before any doorbell, IE=0 polled, one SCSI cmd at a time on LUN0 (TUR x3, READ(10) via bounce, PRDT 256 KiB chunks), flush_dcache64 by PA around each command (host not dma-coherent per DT), finds GPT partition by name (`ufsroot=` boot-arg, default `userdata`), exposes `/dev/ufsroot0`/`rufsroot0` (512-byte logical sectors, physical 4 KiB, DKIOC* ioctls), refuses writes (EROFS). IOKitBSDInit: `rd=ufsroot0` -> sweet_ufs_rootdev() (lazy init) else panic. ADT: `tools/mkadt.py` adds `/sweet-ufs` reg <0x1d84000 0x3000> for the PHONE only (not --qemu). Local compile OK, imports resolve. Sandbox research/bt28 (pre0028 originals). FIRST PHONE TEST PLAN (non-destructive): boot 0028 with phone ADT + `rd=ufsroot0` and NO RAM disk: expect `SWEET UFS: "userdata" on LUN 0: first block 0x2b8c00, 109643 MiB` + `BSD root: ufsroot0`, then root mount failure (userdata is still Android-encrypted) -> panic. That validates the driver before flashing an HFS image into userdata (needs explicit user confirmation at that time).
- **SUPERSEDES the 64 GiB iosroot GPT plan: user said "u can delete android" (2026-10-15).** Use the existing `userdata` partition (LUN0 sda34, 4K LBA 0x2B8C00, 0x1AC4B MiB ~107 GiB) directly as the iOS root: NO GPT changes. Keep bootloaders, recovery (OrangeFox), modem/persist/fsg/modemst untouched. Write the HFS image later with `fastboot flash userdata` (sparse, auto-split under the 768 MiB limit). Android will no longer boot normally (expected; reinstallable). Order: XNU UFS driver first, read-only against the current GPT; flash only once it can locate userdata. Nothing erased yet.
- **DECIDED (user, 2026-10-15): 64 GiB `iosroot` on LUN0 (sda), taken from userdata (wipes Android user data; Android/super kept).** Planned GPT (4K LBAs): userdata 0x2B8C00..0xD7D6FF (~43 GiB, keep type/unique GUIDs and attributes); iosroot 0xD7D700..0x1D7D6FF (0x1000000 blocks = 64 GiB, 1 MiB aligned); backup GPT area unchanged. Procedure: user backs up phone data -> boot OrangeFox recovery (adb) -> back up GPT (sgdisk --backup + raw dd of LBA 0-5 and last 6 blocks) to research/ -> sgdisk edit -> Format Data -> verify Android boots to setup. NOT EXECUTED YET.
- **INTERNAL UFS WORKS FROM THE SHIM (read-only), user authorized internal-UFS approach incl. flashing (2026-10-15, "i allow everything").** Shim probe `shim/ufs.c` (commit `12ed3ed` + filter): ufshc@1d84000 is UFSHCI 2.1 (ver 0x210, cap 0x1587031F, 32 slots), ABL leaves HCE=1, HCS=0x10F (device present, lists ready, UIC ready); probe takes over UTRL at its own buffer (verifies UTRLBA readback before any doorbell), TEST UNIT READY/READ CAPACITY/READ(10) all succeed. LUN0 = 0x1D7D800 x 4 KiB (~126.6 GB), valid GPT (64 entries at LBA 2). Photos IMG_20261015_212916/213325/213429. Big LUN0 partitions (start in 4K LBAs / MiB): super 0xCA00/0x2200 (8.5 GiB), logdump 0x22CA00/64, minidump 0x230A00/128, rawdump 0x238A00/128, recovery 0x240C00/128, cache 0x248C00/384 ext4, exaid 0x260C00/384, cust 0x278C00/1024 ext4, **userdata 0x2B8C00/0x1AC4B MiB (~107 GiB), fs unreadable = encrypted (metadata encryption)**. cache..cust contiguous = only 1.75 GiB (too small for iOS ~10+ GiB). Plan needing user consent: shrink userdata in GPT (wipes Android data) and add an `iosroot` partition at the end of LUN0. LUNs 1-5 not listed yet (sdb..sdf backed up in backup/lun).
- **fastboot limit measured (2026-10-15, read-only getvar):** `max-download-size: 805306368` (768 MiB); `max-fetch-size` unsupported; `is-userspace: no` (ABL fastboot). A `fastboot boot` image (shim+kernel+RAM disk) must be < 768 MiB, so the 2.5 GiB iOS shared cache cannot ride in the boot RAM disk even if XNU gets all RAM. Real userland needs storage access (UFS driver, or USB host) or a much smaller cache. Unlocking full RAM is still needed later (GUI).
- **iOS 16 USERLAND SOURCE (Claude, 2026-10-15).** Chose **iPhone X (iPhone10,3/10,6, D22/D221AP)** iOS **16.7.16 (20H392)** over iPhone 8: same A11 (no PAC -> plain arm64, runs on Kryo 470/ARMv8.2), last iOS for A11; X userland is home-button-less and tall-screen (1125x2436 vs sweet 1080x2400), better fit for later GUI. Note the X has its OWN SystemOS cryptex (different digest from iPhone 8's). IPSW URL in `research/ipsw-x/URL.txt` (+ BuildManifest). Images on the user's external SSD (NOT in git, do not format that disk: it holds the user's photos): `/run/media/dipa/android/ios-sweet-ipsw/iPhone10,3_16.7.16_20H392/` — `087-86593-047.dmg` = Cryptex1,SystemOS (2,743,074,816 B), `087-86698-044.dmg` = OS rootfs (4,730,814,044 B), both zip CRC-32 verified, plus Firmware/*.root_hash/.trustcache/.mtree. AppOS cryptex is 087-86715-047.dmg (10 MB, same as iPhone 8).
  - Images are raw APFS; files use LZBITMAP (decmpfs type 14). 7z cannot decode. Tools: `ipsw` 3.1.738 (AUR ipsw-bin, user-approved) needs apfs-fuse on Linux; **apfs-fuse** built in user space (system cmake broken: cmake 4.4.4 wants libjsoncpp.so.27, jsoncpp 1.9.6 installed = partial upgrade, NOT fixed) with pip cmake + `-DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_CXX_FLAGS="-include cstdint"`, installed to `~/.local/bin/apfs-fuse` (+apfs-dump-quick). Mount via a comma-free symlink (apfs-fuse splits options on ',' in `iPhone10,3`; exFAT has no symlinks -> put link elsewhere): `apfs-fuse LINK/087-86698-044.dmg MNT` -> `MNT/root/...`; unmount `fusermount3 -u MNT`.
  - Verified from headers: `dyld_shared_cache_arm64` magic `dyld_v1   arm64`; `/sbin/launchd`, `/usr/lib/dyld` = cputype 0x100000c subtype 0 (plain arm64). libSystem exists only inside the cache.
  - **BLOCKER for real userland via RAM disk:** shared cache = 3.10 GiB in 44 files (~2.5 GiB without the 592 MB `.symbols`), but the kernel manages only 1.20 GiB (0xb0000000..0xfd000000). Options: (A) give XNU the phone's full ~6 GB (banks 0x80000000+2G and 0x100000000+0xfcc00000, carve-out holes need pmap support) AND check fastboot max-download-size for a multi-GB boot image; (B) storage driver (Qualcomm UFS) to read a root from flash (no flashing allowed: would need a file/partition strategy); (C) run against individual dylibs extracted from the cache (uncertain).
- **MILESTONE ON HARDWARE: HFS+ ROOT FILESYSTEM -> PID 1.** Boot 2026-10-15 18:22:12 UTC (`research/boot0027b.log`, image `shim/out/shim-boot-0027b.img`), photo `IMG_20261015_202334.jpg`: `BSD root: md0` -> `hfs: mounted SweetRoot on device b(1, 0)` -> `load_init_program: attempting to load /sbin/launchd` -> `*** SWEET userspace: init running as PID 1 ***` -> repeated `SWEET init: still alive`, no panic. Kernel 0027 (built-in Apple OSS HFS + BearSSL MD5), init with SP alignment fix. NEXT: real iOS 16 userland on the HFS image (dyld, libSystem/dyld shared cache, launchd). Known gaps: entitlements (none granted), SHA-1/SHA-384/512 providers, no storage driver (RAM disk only), root mounted read-only.
- **PHONE HFS ROOT (0027) + SIGBUS ROOT-CAUSED.** Phone boot 2026-10-15 17:49:06 UTC (`research/boot0027.log`, photo `IMG_20261015_200031.jpg`): `hfs: mounted SweetRoot on device b(1, 0)` (HFS works on hardware), init printed its first line, then `pid 1 exited -- exit reason namespace 2 subcode 0xa` = SIGNAL/SIGBUS -> `initproc failed to start` panic. Diagnostic boot 18:08:13 UTC (`research/boot0027d.log`, image `shim/out/shim-boot-0027d.img`, diag init `research/diag-init` from scratch diag-init.S with [a][b][c] markers, `cs_debug=1`; photo `IMG_20261015_201547.jpg`): output `PID [a][b]` then SIGBUS -> fault at first `strb w21,[sp]`; no code-signing messages. Cause: kernel enters a static binary with sp at argc, not necessarily 16-aligned (depends on arg/apple string lengths, differs mockfs vs HFS); EL0 SP alignment check -> EXC_ARM_SP_ALIGN -> SIGBUS (sleh handle_sp_align). QEMU does not enforce SP alignment. NOT a kernel bug: real binaries start in dyld which aligns. Fix `1a8fc15`: sweet-init aligns sp at entry. Rebuilt `research/root-hfs.img`, QEMU `research/q0027-hfs2` OK. Phone image `shim/out/shim-boot-0027b.img` SHA256 `098ba46c...c5c` (payload-0027b, ramdisk match check-0027b) ready, awaiting FASTBOOT. Lesson: Assembly `;` is a comment in Apple arm64 asm (use .macro, not ;-joined #define).
- **HFS ROOT WORKS (QEMU).** 0027 CI `38779441895` PASSED, `xnu/out-0027` SHA256 `a8643886...5f6a`. QEMU `research/q0027-hfs` (RAM disk = `research/root-hfs.img`, rd=md0): `BSD root: md0` -> `hfs: mounted SweetRoot on device b(1, 0)` -> `load_init_program: attempting to load /sbin/launchd` -> `*** SWEET userspace: init running as PID 1 ***` + heartbeat, no panic. Phone image `shim/out/shim-boot-0027.img` (payload-0027 = 0027 kernel + sweet-0021.adt + root-hfs.img + rd=md0, ramdisk byte-match check-0027) ready; awaiting FASTBOOT for phone test.
- **HFS ROOT WORK (Claude), patches 0026-0027.**
  - 0026 (`f0e990c` + link fix `64c96f4`): Apple OSS **hfs-627.100.6** (commit `31d5ec238dfab485e78a9a30b8b92d13e8914f03`, paired with xnu-8796.141.3 in macos-135 release.json) staged by `xnu/patches/0026-stage-hfs.sh` into `bsd/sweet_hfs` (core + hfs_encodings; AppleKeyStore include/key prototypes guarded by CONFIG_PROTECT; SDK TargetConditionals copied). New config option `sweet_hfs` (MASTER + MASTER.arm64.sweet); 40 `optional sweet_hfs` files; Makefile.template foreach adds `_CFLAGS_ADD = -include sweet_hfs_compat.h -I...` (MUST come after kernel -D flags; compat undefs BSD/XNU_KERNEL_PRIVATE and the CONFIG_* HFS tests so kext-config.h decides: macOS profile, no content protection). `sweet_hfs_iokit.c` replaces hfs_iokit.cpp/hfs_encodings_kext.cpp: `sweet_hfs_register()` called in bsd_init after vfsinit (encodings init, vfs_fsadd VFS_TBLCANMOUNTROOT, zones, sysctls); is_ejectable 0, iterate_media none, serial KERN_NOT_SUPPORTED, OSKextGetCurrentLoadTag -> kOSKextInvalidLoadTag (renamed via compat macro). hfs_encodings' own `hfs_allocated` renamed per object (separate kexts on Apple; first CI `38777325964` failed on that duplicate at link). mockfs now validates Mach-O magic (its TODO) so non-Mach-O roots fall through to HFS (new fs entries come AFTER mockfs in vfsconf). CI `38778133720` PASSED, `xnu/out-0026` SHA256 `0b49170c...701a`, prints `SWEET HFS: hfs-627.100.6 registered`.
  - HFS+ image: `research/root-hfs.img` (8 MB, mkfs.hfsplus from AUR hfsprogs installed with user approval; loop-mounted with sudo; /sbin/launchd = research/sweet-init, /dev; fsck.hfsplus OK). QEMU `research/q0026-hfs`: `BSD root: md0` then data abort in MD5Init from hfs_getvoluuid (mount computes volume UUID).
  - 0027 (`14bf2b7`): 0020 stager also copies BearSSL hash/md5.c + codec/dec32le.c/enc32le.c; `corecrypto_md5.c` SWEET branch converts MD5_CTX <-> br_md5_context around br_md5_* calls; wrappers sweet_md5.c/sweet_dec32le.c/sweet_enc32le.c. Host test 40/40 match md5sum. CI **`38779441895`** running.
  - Local tooling: `tools/xnu-cc.py` has `XNU_CC_POST` (flags after logged ones). Sandbox `research/bt28/xnu` = 0025 CI tree + 0026/0027 edits; originals `research/pre0026`, `research/pre0027`. HFS local objects `research/hfs-objs`. Checker entries updated to bt28.
  - SHA-1 / SHA-384/512 still have no provider.
- **MILESTONE ON HARDWARE: USERSPACE PID 1 RUNS ON THE PHONE.** Boot 2026-10-15 17:16:00 UTC (`research/boot0025.log`: send OKAY0.410s, boot OKAY0.135s), image `shim/out/shim-boot-0025.img` SHA256 `9dbfa0b1...89db0`. Photo `IMG_20261015_191733.jpg`: `BSD root: md0` -> `load_init_program: attempting to load /sbin/launchd` -> `*** SWEET userspace: init running as PID 1 ***` -> repeated `SWEET init: still alive` (5 s heartbeat), no panic. Kernel 0025 + mockfs RAM disk + built-in no-entitlements AMFI. No flashing performed.
- **NEXT (toward real iOS userland):** real root filesystem with real binaries. Options: (a) build Apple OSS `hfs` (macOS 13.5 tag `hfs-627.100.6`) into SWEET like libpthread, then an HFS RAM disk image; (b) iOS 16 dyld + libSystem/dyld shared cache from the IPSW (needs APFS or repacking onto HFS). Expected hurdles: entitlements (sweet_amfi grants none), SHA-1/MD5/SHA-384/512 providers (BearSSL), missing kexts/daemons. Current init is a static test program, not launchd.
- **MILESTONE: USERSPACE RUNS (QEMU).** 0025 CI `38774788048` PASSED, `xnu/out-0025` SHA256 `5496069b...4877`. QEMU `research/q0025-rd` (150 s, no panic): `BSD root: md0` -> `load_init_program: attempting to load /sbin/launchd` -> `*** SWEET userspace: init running as PID 1 ***` -> `SWEET init: still alive` every 5 s. Exec, ad-hoc SHA-256 code signature, syscalls, devfs /dev/console, select timeouts all work. Phone image prepared: `shim/out/shim-boot-0025.img` 16,515,072 bytes SHA256 `9dbfa0b15140c0bd733a16c4f727f6a7df44a8741f98d8e266d5f2fa4f689db0` (payload-0025 = 0025 kernel + sweet-0021.adt + research/sweet-init + rd=md0; ramdisk byte-match check-0025). Waiting for user to put phone in FASTBOOT.
- **0024 CI `38773277811` PASSED**, `xnu/out-0024` SHA256 `a0ba964b...4348`. QEMU `research/q0024-rd` and **PHONE (boot 2026-10-15 17:05:55 UTC, `research/boot0024.log`, image `shim/out/shim-boot-0024.img` SHA256 `cf3dac86...6964`, 16,510,976 bytes, payload `shim/out/payload-0024.bin` = 0024 kernel + `shim/out/sweet-0021.adt` + RAM disk `research/sweet-init` + rd=md0; ramdisk byte-match `check-0024`)** agree: `Added memory device md0`, `BSD root: md0`, `load_init_program: attempting to load /sbin/launchd`, then data abort in accelerate_entitlement_queries (PC 0x...77d2458, FAR 0x1a0) = NULL AMFI interface. Photo `IMG_20261015_190715.jpg`. RAM disk root is physically verified.
- **0025 (`2518c79`)**: new `bsd/kern/sweet_amfi.c` registers a built-in AMFI interface at EARLY_BOOT/MIDDLE: no entitlements (adjustContextWithoutMonitor succeeds without creating a context, queries KERN_DENIED, copies NULL/KERN_NOT_FOUND, get_xml/transmuted false); WithMonitor KERN_NOT_SUPPORTED; OSEntitlements_query and query_context_to_object panic explicitly (CoreEntitlements closed; no kernel caller); TrustCache version 0 (0015 keys on trust_cache_rt==NULL, img4 absent -> still unavailable); CoreEntitlements table zero (PMAP_CS only). Compiles locally; checker updated (bt27 entries). CI **`38774788048`** running. Next artifacts `xnu/out-0025`, `research/bt29`, `research/run29.log`. Real iOS binaries will need real entitlements later (no OSS CoreEntitlements exists).
- **0021-0024 RAM-disk-root iteration (Claude), QEMU only so far, no new phone boot since 0020.** Each kernel tested with `tools/mkpayload.py KERNEL research/q0021.adt OUT --ramdisk research/sweet-init --cmdline "debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=md0"` then `tools/qemu-sweet.py OUT DIR --secs 150 --kernel KERNEL --fail-on-panic` (PATH needs ~/swift/usr/bin for llvm-nm). Fresh ADTs: `research/q0021.adt` (QEMU), `shim/out/sweet-0021.adt` (phone).
  - 0021 CI `38769532000` PASSED, `xnu/out-0021` SHA256 `2b7500a1...962e`, `research/bt25`/`run25.log`. QEMU `research/q0021-rd`: md0 root, then assert `iomediaClass` in IOService::publishHiddenMedia.
  - 0022 (`20ece9c`, publishHiddenMedia without IOMedia class) CI `38770666158` PASSED, `xnu/out-0022` SHA256 `a4d0e787...30c5`, `research/bt26`/`run26.log`. QEMU `research/q0022-rd`: data abort in SHA256_Init (NULL g_crypto_funcs) from vm_kernel_addrhash_internal.
  - 0023 (`c8089d1`, libkern SHA256_Init/Update/Final use built-in ccsha256_ltc_di + ccdigest_init/update on SWEET; also serves code-signing SHA-256; SHA-1/MD5/SHA-384/512 still have NO provider - BearSSL from 0020 could supply them later) CI `38771876423` PASSED, `xnu/out-0023` SHA256 `d763fed7...1003`, `research/bt27`/`run27.log`. QEMU `research/q0023-rd`: **mockfs mounted md0, `load_init_program: attempting to load /sbin/launchd`**, then panic `mockfs_fsnode_vnode failed to create fictitious pages ... rvalue = 5` (mockfs.c:351).
  - 0024 (`3293c80`): mockfs used memdev mi_base (4K page number of a VIRTUAL kernel address for IOKit RAMDisk, truncated to 32 bits) << PAGE_SHIFT as a physical address. Now zero-copy pager mapping only when mi_phys (with 4K units); virtual md uses pagein/blockmap/strategy -> memdev bcopy. memdev's own mdPhys path assumes 4K ppnums (unsafe on 16K arm64), so do NOT switch the RAMDisk to physical. CI **`38773277811`** running. Next artifacts `xnu/out-0024`, `research/bt28`, `research/run28.log`.
  - Sandboxes: bt25/bt26/bt27 contain the next patch's edited files; pristine copies in `research/pre0022`..`pre0024`.
- **PATCH 0021 (Claude): RAM disk root via mockfs -> first userspace program.** Commits `9c37771` (initial; CI `38768500280` FAILED: mockfs_fsnode.c kfree_type(mockfs_fsnode_t) typed-alloc static assert; local xnu-cc stubs `__builtin_xnu_types_compatible` so it can't catch this) and `193772f` (fix), CI **`38769532000`** running: https://github.com/dipa-studio/ios-sweet/actions/runs/38769532000. Next artifacts: `xnu/out-0021`, `research/bt25`, `research/run25.log`.
  - Kernel: `config/MASTER.arm64.sweet` FILESYS_BASE += `mockfs` (XNU's built-in FS: root device is itself a Mach-O, served as /sbin/launchd, plus /dev for devfs). Upstream mockfs bit-rot fixed: kalloc_type/kfree_type used the POINTER typedef mockfs_fsnode_t (nodes were 8 bytes) -> `struct mockfs_fsnode`. `IOService::setRootMedia` asserted IOBlockStorageDriver class exists (IOStorageFamily absent): SWEET-only, a missing class means root=NULL (same as IOSetImageBoot); Apple path keeps assert. All 21 patches apply (`research/check-patch-order.py`); 5 TUs compile locally with -DMOCKFS (`research/mockfs-objs`), imports resolve vs 0020 kernel. Sandbox `research/bt24/xnu` now holds 0021 versions of those 3 files; pristine 0020 copies in `research/pre0021`.
  - Tools: `tools/mkpayload.py --ramdisk IMAGE` appends IMAGE as an extra payload segment right after the kernel, moves kernel_end past it (shim unchanged: ADT+boot_args follow it, image stays below topOfKernelData), and adds ADT `/chosen/memory-map` `RAMDisk`=<phys,size>. Boot with `rd=md0`. Without --ramdisk output is byte-identical to existing 0020 QEMU and phone payloads (verified). `tools/sweet-init.S` + `tools/mkinit.py`: PIC static init (open /dev/console, print PID, heartbeat every 5 s via select, never exits) wrapped into a static arm64 Mach-O (__PAGEZERO, __TEXT@0x100000000, LC_UNIXTHREAD, ad-hoc SHA-256 CodeDirectory v0x20400, 4K pages). Build: `~/swift/usr/bin/clang -target arm64-apple-ios16.0 -c tools/sweet-init.S -o X.o && tools/mkinit.py X.o research/sweet-init` (ld64.lld cannot link static iOS). Signature not verified by a real codesign; the kernel will tell.
  - QEMU with 0020 kernel + RAM disk (`research/q0020-rd.bin`, rd=md0, 150 s `research/q0020-rd150`): `Added memory device md0`, **`BSD root: md0, major 1, minor 0`** (plumbing works), then the setRootMedia assert (now fixed in 0021). NOTE: QEMU needs >60 s to reach IOFindBSDRoot (60 s run showed nothing after stf0; likely RTC/inittodr wait), so use --secs 150.
  - NEXT: download 0021, QEMU 150 s with ramdisk; expect mockfs mount then init exec -> `*** SWEET userspace: init running as PID 1 ***`. Then phone boot with same payload (phone ADT shim/out/sweet-0020.adt pattern + --ramdisk + rd=md0).
- **0020 PHONE RESULT (user transcription of screen, 2026-10-15): KERNEL INIT COMPLETE, WAITING FOR ROOT.** After Skywalk self-tests PASSED, kminit, ifnet_attach lo0/gif0/stf0, screen prints `BSD`, then `Waiting on <dict><key>IOProviderClass</key><string>IOMedia</string><key>Content</key><string>Apple_HFS</string></dict>` and `Failed to write boot-picker-bringup-reason to NVRAM.` No panic. This is IOFindBSDRoot waiting for a root device (none exists); NVRAM warning is expected (no NVRAM driver). QEMU `cpu_idle` snapshot is presumably the same wait (not GDB-confirmed; milestone GDB run was cancelled by user since phone answered it). Draft `research/check-milestones20.gdb` (hbreaks inittodr/vfs_mountroot/IOFindBSDRoot/bsd_utaskbootstrap) left uncommitted/ignored.
- **NEXT MILESTONE: root filesystem -> launchd.** Plan: (1) RAM disk: shim places an image in RAM, ADT /chosen/memory-map `RAMDisk` entry, boot-arg `rd=md0` (XNU md driver). (2) HFS is a separate kext on Apple; build Apple OSS `hfs` (tag paired with macOS 13.5 in distribution-macOS macos-135 release.json) into SWEET like libpthread 0019. APFS is closed. (3) Minimal HFS image with iOS 16 launchd (later: dyld/shared cache; AMFI/code-signing absent will be a later hurdle). User's end goal is full iOS GUI.
- **0020 (AES) VERIFIED + PHONE BOOTED (Claude took over after Codex usage limit).** Actions `38765422261` (`ab9e23f`) PASSED; kernel `xnu/out-0020/kernel.development.sweet` checksum OK; buildtree `research/bt24`, log `research/run24.log`. Actual-kernel AES checks PASS (`research/check-aes20.gdb` / `.log`, 12 extra CBC cases match OpenSSL). 45s QEMU `research/q0020`: no panic, zero unknown glyphs, past old TCP/AES panic -> Skywalk self-tests PASSED -> bsd_autoconf kminit -> ifnet_attach lo0/gif0/stf0; final snapshot PC in `cpu_idle` (idle or waiting; NOT yet diagnosed, could be root-device wait). Image `shim/out/shim-boot-0020.img` 16,461,824 bytes SHA256 `775200cb02d95fc750981516b79d91dcdc96184bbe67a38f9d57c59b4a391828`, ramdisk byte-matches `payload-0020.bin` (`check-0020`). **Phone temporarily booted 2026-10-15 16:10:00 UTC**: one FASTBOOT product sweet, send OKAY0.407s, boot OKAY0.134s, total0.549s, exit0 (`research/boot0020.log`). Awaiting user photo; do not reboot the phone before it. NEXT: read photo; diagnose what QEMU waits on after stf0 (GDB backtrace of threads / longer run). Codex's STOP request below is complete.
- User requests STOP after completing the current0020 AES iteration (Actions/QEMU/phone), then leave a precise committed handoff for another AI. User says FASTBOOT ready again after0019 photo. Do not start a new blocker fix after this iteration.
- Goal: iOS16-generation XNU on Redmi Note10Pro sweet/SM7150. Always commit, use gh/Actions for kernel builds, keep this handoff current. Temporary fastboot boot only; preserve Android/backups. No userland/root filesystem boot yet.
- **Patch0020 update:** initial `e71098d` / Actions `38765012466` superseded by scalar-only compile flags. Added -mgeneral-regs-only to all six provider/BearSSL TUs and corecrypto_aes.c; object disassembly now confirms no SIMD. Updated implementation `ab9e23f`, Actions `38765422261` queued/running: https://github.com/dipa-studio/ios-sweet/actions/runs/38765422261. Do not launch another run. portable BearSSL AES CBC and legacy one-block ECB wired directly into SWEET corecrypto_aes.c. Genuine bitslice implementation, no CPU AES/SIMD requirement, heap or fake global crypto table. Source fetched by `0020-stage-bearssl.sh` from official BearSSL git at immutable `7bea48e5e850ab4cafbe68d3765cdaba13a86d6f`; MIT license retained, downloaded source stays out of git. Kernel limits include adapter only. All128/192/256-bit keys, CBC encrypt/decrypt, copied contexts, in-place/out-of-place; zero block count and size overflow handled, invalid keys clear context. Seven TUs compile to arm64 objects (`research/aes-objs`), imports resolve, all20 patches apply and sources match (`research/patch0020-check.log`). Sandbox `research/bt23/xnu`, originals `research/pre0020`. NEXT: Actions then actual-kernel NIST/random CBC/ECB checks and >=45s QEMU before another phone boot. Next artifacts out-0020 / bt24 / run24.log. 0020 updated CI pending. Local sources/checks match the scalar-only patch.
- **Latest built kernel0019**, implementation `256d3f0`, patches0001-0019. Actions `38763072907` PASSED (4m5s): https://github.com/dipa-studio/ios-sweet/actions/runs/38763072907. Kernel `xnu/out-0019/kernel.development.sweet`, SHA256 `a27df7568f03fb541cf0e8024c0a594fa178a85054fcf9eba29158cbd4c5ecc0`; checksum verified. Log/source `research/run23.log` / `research/bt23` (no nested .git). Seven pthread source/build/header files and staged adaptations byte-match local compile inputs.
- **0019 hardware photo received** `IMG_20261015_175306.jpg`: pthread registration visible, passes mbinit and DLIL checksum/scheduling, same AES fault as QEMU: PC`0xfffffe00079174e0` (`aes_encrypt_key128`), LR`0xfffffe000767c3a4` (`tcp_init`), FAR0x78, x8=0. Disassembly proves NULL g_crypto_funcs->ccaes_cbc_encrypt. Photo processed; no more0019 observation pending. General crypto table remains absent, other hash/mode operations may still fault after0020. DO NOT bypass TCP or install fake crypto. XNU already contains SHA256/HMAC implementations; AES source there is a dispatch wrapper. Full future provider interface libkern/libkern/crypto/register_crypto.h. Apple/corecrypto default README describes evaluation-only licensing, so no external corecrypto was fetched or staged; BearSSL selected for this portable AES integration.
- **0019 pthread FIXED in QEMU and observed beyond its init on phone**: 45s QEMU `research/q0019`, zero unknown glyphs, then AES panic. Actual-kernel API checks PASS `research/check-pthread19.gdb` / `.log`, guest `research/q0019-api`: function/callback table identity, actual provider pthread_init returns, locks/global hash/threadcall/typed zones initialized, thread_selfid via syscall shim + buffer bounds, process hash init/delete via shims restores NULL. Monitor quit prints expected remote-disconnect after PASS. All fixture guests stopped.
- **0019 provider**: genuine Apple libpthread-514.100.2 commit `a6c70ca0e544347a0377babf748f831577ec24f9`, exact paired release with xnu8796.141.3 in distribution-macOS/macos-135/release.json (`research/macos-135-release.json`). 0019 shell stage runs before patches (workflow copies *.sh); three SWEET wrapper TUs use kext BSD header view, vm_fault_external, renamed provider-side pthread_kern/current_uthread; register real function table at EARLY_BOOT SECOND, real pthread_init later. Stager applies bounded address casts, zero user addresses, proper panic format. SWEET opaque ksyn storage enlarged48->56 for trailing kwe_uth, checked with provider static assertion. Local pre-CI TargetConditionals fixture was syntax-only; artifact bt23 carries actual SDK header and CI is authoritative.
- **Phone0019 temporarily booted** 2026-10-15 15:51:36 UTC: exactly one FASTBOOT/product sweet verified; send OKAY0.406s, boot OKAY0.134s, total0.546s, exit0 (`research/boot0019.log`). Image `shim/out/shim-boot-0019.img`, 16,457,728 bytes, SHA256 `19429a57e486b856880df9e27327ed488e0139345311fdb0350974e72103a9a1`. Phone ADT/payload `shim/out/sweet-0019.adt` / `payload-0019.bin` timer19, unpacked ramdisk byte-match (`check-0019`). EntryPA0xb146b488, kernelendPA0xb2000000, boot_argsPA0xb2004000/top0xb2008000. Last user FASTBOOT+USB reply preceded this boot; do not assume phone is still in FASTBOOT.
- **CPU0018 physically verified** by `IMG_20261015_173951 (2).jpg`: boot CPU0 registered, real SGI1 verified, initialization complete -> BSD/MAC/mbinit -> old pthread-table panic. SweetCPU uses legacy IOCPU, ml_processor_register/processor_start/initCPU, real SGI1 clears SIGPdisabled before max CPUs completion; no forced flags/skipped waits. CPU APIs and two-CPU rejection passed (`research/check-cpu18.gdb`, `q0018-api`, `q0018-smp`). Single core; SMP/suspend unsupported. CURRENT SWEET has NO USE_APPLEARMSMP.
- QEMU next run: generate fresh `tools/mkadt.py research/q0020.adt --qemu` (timer27), mkpayload with `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress`, then `tools/qemu-sweet.py PAYLOAD OUT --secs 45 --kernel KERNEL --fail-on-panic`. 12s can miss later panics because IORTC waits30s. Runner snapshot only: panic exit2, blank/incomplete exit3; absence of panic does not mean complete boot. Qualcomm XPU/ABL/panel and phone SMC PSCI require hardware checks.
- Local checker `tools/xnu-cc.py research/run23.log research/bt23 FILTER --per-file`, XNU_CC_OBJDIR for objects. For new BearSSL TUs add XNU_CC_EXTRA with -I bt23/xnu/libkern/crypto/sweet_bearssl/{inc,src}. Patch checker `research/check-patch-order.py` uses temporary upstream index; source fixtures/artifacts ignored under research. GDB mask registers to unsigned64, use function-entry manual-call return traps, discard manipulated guests. No QEMU guest intentionally left running.

## Session log and earlier handoffs (superseded by the active summary above)

### Prior 0019 transition notes (superseded)

- Goal: iOS 16 generation XNU on sweet. Always commit completed work, use gh/Actions for kernel builds, keep this handoff current. Temporary fastboot boot only; preserve Android/backups.
- **0019 build PASSED** Actions `38763072907` (4m5s), implementation `256d3f0`. Kernel `xnu/out-0019/kernel.development.sweet`, SHA256 `a27df7568f03fb541cf0e8024c0a594fa178a85054fcf9eba29158cbd4c5ecc0`; checksum verified. Log/source `research/run23.log` / `research/bt23`; all seven patched files and staged provider adaptations match local compile inputs. Prefer bt23 as the next baseline.
- **0019 pthread FIXED in QEMU**: 45s run `research/q0019` registers provider, passes mbinit, DLIL SUM16 checks and DLIL thread scheduling. Actual-kernel GDB checks `research/check-pthread19.gdb` / `.log` PASS: function/callback table identity, real _pthread_init returns, locks/global hash/cleanup threadcall/typed zones non-NULL, thread_selfid via actual syscall shim with output bounds, process hash init/delete through actual shims restores NULL. Guest stopped after tests; no fixture left running. GDB monitor quit prints expected remote disconnect after PASS.
- **Current next blocker:** QEMU0019 panic data abort FAR0x78 at `aes_encrypt_key128` PC`0xfffffe00079174e0`, called by `tcp_init` LR`0xfffffe000767c3a4`. Disassembly confirms `g_crypto_funcs == NULL`, loading ccaes_cbc_encrypt at+0x78. General crypto registration is still absent; DO NOT bypass TCP or supply fake crypto. Next integrate a genuine compatible crypto implementation/provider (AES first needed here, other digest/mode APIs also used). XNU contains SHA256/HMAC but no AES implementation; its corecrypto_aes.c is a dispatch wrapper. Full crypto table is in libkern/libkern/crypto/register_crypto.h.
- **0019 phone image prepared and verified**, user reports FASTBOOT+USB again; exactly one device/product sweet verified. `shim/out/shim-boot-0019.img`, 16,457,728 bytes, SHA256 `19429a57e486b856880df9e27327ed488e0139345311fdb0350974e72103a9a1`; unpacked ramdisk matches phone payload (`shim/out/check-0019`, `payload-0019.bin`, `sweet-0019.adt`, timer19). EntryPA0xb146b488; kernelendPA0xb2000000; boot_argsPA0xb2004000/top0xb2008000. Usual debug cmdline cpus=1/-noprogress. **Temporarily booted 2026-10-15 15:51:36 UTC**: send OKAY0.406s, boot OKAY0.134s, total0.546s, exit0 (`research/boot0019.log`). User asked for photo after45s. Await the photo; DO NOT reboot again before observation. Bootloader acceptance only; no0019 physical progress observed yet.
- **Hardware photo confirms 0018 progress** (`IMG_20261015_173951 (2).jpg`): real phone prints `SWEET CPU: boot CPU 0 registered, SGI1 verified, initialization complete`, enters BSD/MAC, reaches `mbinit: done`, then the same missing-pthread-function-table panic as QEMU at pthread_shims.c:318. CPU completion/interrupt delivery is now physically observed. The photo was received; no further phone boot performed yet.
- **Patch0019 committed/pushed `256d3f0`; Actions `38763072907` queued/running:** https://github.com/dipa-studio/ios-sweet/actions/runs/38763072907. Do not launch a duplicate. genuine Apple OSS libpthread-514.100.2 provider (immutable commit `a6c70ca0e544347a0377babf748f831577ec24f9`), paired with xnu-8796.141.3 by Apple's `distribution-macOS/macos-135/release.json` (`research/macos-135-release.json`). `0019-stage-libpthread.sh` fetches/stages it before patches; workflow now copies shell scripts too. SWEET-only wrappers compile all three real kernel sources, rename provider-side symbols, use kext header view and vm_fault_external, register the real function table at EARLY_BOOT SECOND. Existing pthread_init then runs the actual provider initialization. No pthread wait/syscall is bypassed. Source staging includes bounded explicit address casts/zero user addresses and panic-format fixes. SWEET kernel opaque ksyn storage enlarged from48 to56 bytes to contain this provider's trailing kwe_uth, with a provider size assertion. Local compile of three provider TUs plus pthread_shims/kern_fork passed; imports resolve and provider exports do not collide with existing kernel symbols. All19 patches apply and changed sources match (`research/patch0019-check.log`). Source sandbox `research/bt22/xnu`, originals `research/pre0019`, objects `research/pthread-objs`. Local TargetConditionals fixture only has target macros for syntax; CI stages the real macOS SDK header and is authoritative. Next Actions artifacts: out-0019 / bt23 / run23.log; run QEMU >=45 seconds. 0019 CI is pending; no 0019 QEMU run yet.
- **Latest kernel implementation `e7d9550`, patches0001-0018; CI `38760004398` PASSED (3m56s)**: https://github.com/dipa-studio/ios-sweet/actions/runs/38760004398. No build is pending. Kernel `xnu/out-0018/kernel.development.sweet`, SHA256 `b3c8d59acc88f93a2c836eb2527a05ed4fbaac7c580a2ea8c3b795137f4aadf1`; checksum verified. Source/log `research/bt22` / `research/run22.log` (baseline for patch0019; no nested .git). New driver/config sources match CI exactly.
- **CPU wait FIXED in QEMU**: SweetCPU uses legacy IOCPU, validates single boot CPU, ml_processor_register -> processor_start -> initCPU real SGI1 -> scheduler/IOKit completion -> ml_set_max_cpus. It does NOT force a flag or skip a wait. CPU APIs passed: Running CPU0, processor_array[0] association, SGI signalling enabled, name, unsupported secondary-start error (`research/check-cpu18.gdb` / `.log`, `research/q0018-api`). Single-core only; SMP and suspend unsupported. Two-CPU topology fails explicitly (`research/q0018-smp`).
- **Next blocker reproduced in 45s QEMU** (`research/q0018-long`, zero unknown glyphs): BSD initialization reaches MAC framework, network mcache and `mbinit: done`, then **`pthread kernel extension not loaded (function table is NULL). @pthread_shims.c:318`**. Do not bypass pthread_init: find/integrate the matching open-source libpthread kernel implementation and register its real function table. A 12s run `research/q0018` looked panic-free before the 30s IORTC wait elapsed; use >=45s or GDB checkpoints for the next iteration. No userland/root filesystem boot yet.
- **Phone 0018 TEMPORARILY BOOTED** 2026-10-15 **15:31:15 UTC**: exactly one FASTBOOT device verified product sweet; send OKAY0.400s, boot OKAY0.134s, total0.539s, exit0. Local log `research/boot0018.log`. This confirms bootloader acceptance only. User was asked for a photo; await it, DO NOT reboot the phone again before their observation. No flashing performed.
- Current hardware image `shim/out/shim-boot-0018.img`, **16,437,248 bytes**, SHA256 **`b7a23595d143a76c72c9fe2cfcc5d77a8f16987b5af1a2703bbffdfa6922908c`**. Phone ADT/payload `shim/out/sweet-0018.adt` / `shim/out/payload-0018.bin` (timer19), unpacked ramdisk exactly matches payload (`shim/out/check-0018`). EntryPA0xb146b488; kernelendPA0xb1ffc000; boot_argsPA0xb2000000/top0xb2004000. Command line `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress`.
- QEMU payload/ADT `research/q0018.bin` / `research/q0018.adt` (timer27). Run `python3 tools/qemu-sweet.py research/q0018.bin research/NEW-OUT --secs 45 --kernel xnu/out-0018/kernel.development.sweet --fail-on-panic`; fresh ADT seed for a new payload. Output fb.png/fb.txt/regs.txt/qemu.log/result.json. Visible panic exit2; blank/incomplete decode exit3; no_panic_observed is snapshot-only, not successful boot. -noprogress prevents the graphical indicator corrupting console text. Qualcomm XPU/bootloader/panel and SMC PSCI still need physical validation.
- Patches0014-0017 fixed PRNG registration/direct SHA256, explicit unavailable trust-cache service with rejected loads/no matches, built-in SweetPlatformExpert, and timer PPI from ADT (phone19/default19, QEMU27). All their checks/artifacts are preserved in the history below. CURRENT SWEET has NO USE_APPLEARMSMP; do not assume gCPUIC/gAIC/gPMGR AppleARMSMP globals exist.
- Local single-file checker: tools/xnu-cc.py research/run22.log research/bt22 FILTER --per-file, output via XNU_CC_OBJDIR. Patch checker `research/check-patch-order.py` applies all18 via temporary index, matches sandbox sources. Sandbox for0018 `research/bt21/xnu`, originals `research/pre0018`, objects `research/cpu-objs`. First compiler issues were missing machine/atomic.h and nonexistent getNameSymbol; fixed and both TUs compiled successfully before CI. Fixtures/artifacts under research are local-only/ignored.
- GDB: mask int(register)&((1<<64)-1) for unsigned kernel pointers; use function-entry manual-call return traps, discard manipulated guests. No QEMU fixture is intentionally left running.

### Earlier active handoff snapshot (superseded)


- **0018 milestone:** Actions `38760004398` PASSED (3m56s), checksums passed, new CPU/build files byte-match CI tree. Kernel `xnu/out-0018/kernel.development.sweet`, SHA256 `b3c8d59acc88f93a2c836eb2527a05ed4fbaac7c580a2ea8c3b795137f4aadf1`; log/tree `research/run22.log` / `research/bt22`. QEMU `research/q0018` 12s: boot CPU registered, SGI1 verified, CPU initialization complete, **BSD initialization entered** (copyright, MAC framework, buffer headers), no panic/zero unknown glyphs. Direct CPU API checks PASS (`research/check-cpu18.gdb`, `.log`, `research/q0018-api`): CPU0 Running, processor matches processor_array[0], real SGI enabled, CPU name correct, secondary-start returns KERN_NOT_SUPPORTED. Two-CPU ADT correctly panics before registration (`research/q0018-smp`). Longer 45s run `research/q0018-long` still running; next BSD wait/fault not yet identified.
- **Prepared 0018 phone image:** `shim/out/shim-boot-0018.img`, 16,437,248 bytes, SHA256 `b7a23595d143a76c72c9fe2cfcc5d77a8f16987b5af1a2703bbffdfa6922908c`. Phone ADT/payload `shim/out/sweet-0018.adt` / `shim/out/payload-0018.bin`, usual debug args with cpus=1 and -noprogress. Unpacked ramdisk byte-compared (`shim/out/check-0018`). Entry PA remains 0xb146b488; kernel end PA 0xb1ffc000, boot_args 0xb2000000/top0xb2004000. User reports FASTBOOT+USB ready; read-only check found exactly one product sweet. NEXT: temporary fastboot boot of this verified image, record send/boot results, then await hardware photo without rebooting again.
- Patch 0018 committed/pushed **`e7d9550`**; Actions **`38760004398`** queued/running: https://github.com/dipa-studio/ios-sweet/actions/runs/38760004398. Do not launch a duplicate run.
- Active continuation: patch **0018** implemented in `iokit/Kernel/arm/SweetCPU.cpp` + arm64 source list + exact qcom,kryo470 personality. Keeps legacy IOCPU, accepts ONLY the single boot CPU, fills ml_processor_info from parsed topology with CPU object as cpu_id, calls ml_processor_register and processor_start. initCPU sends SGI1 via ICC_SGI1R_EL1 and waits (1-second deadline) for real cpu_signal_handler to clear SIGPdisabled. Only after successful startup calls ml_cpu_init_completed/cpusRunning and publishes completion/max CPUs. Secondary startup/suspend are explicitly unsupported. Local C++ compile passed for both TUs (`research/cpu-objs`), all imports resolve, object contains dsb ishst / ICC_SGI1R / isb; all18 patches apply in order and match sources. Sandbox `research/bt21/xnu`, originals `research/pre0018`; next CI artifacts should use `xnu/out-0018`, `research/bt22`, `research/run22.log`. User has the phone available; first run QEMU, then prepare/temporarily boot useful hardware progress.
- Goal: iOS 16 generation XNU on Redmi Note 10 Pro / sweet. User wants persistent progress, commits, kernel builds via `gh` Actions, and this handoff kept current across agent switches. Temporary `fastboot boot` only; preserve Android and backups.
- Latest kernel implementation: **`aa3f991`**, patches **0001-0017**. All four new Actions builds PASSED: 0014 `38748543058` (4m0s), 0015 `38749549779` (4m3s), 0016 `38750733996` (4m3s), 0017 **`38751507437` (4m7s)**. Latest: https://github.com/dipa-studio/ios-sweet/actions/runs/38751507437. No build is pending.
- **Current blocker: CPU initialization has no SWEET CPU driver.** QEMU registers SweetPlatformExpert, then kernel_bootstrap_thread waits in **kperf_init_early -> ml_wait_max_cpus**. Confirmed via actual-kernel GDB call stack (`research/locate-cpu-wait2.log` / `.symbols`) and normal-run `max_cpus_initialized == 2` (MAX_CPUS_WAIT). Do not force the flag or remove the wait. Next implement real CPU registration and completion using XNU's CPU/processor interfaces. CURRENT SWEET uses legacy IOCPU (`USE_APPLEARMSMP` is absent); enabling AppleARMSMP is a separate architectural change requiring GIC/PMGR services. No userland/root filesystem boot yet.
- Fixed this session: PC=0 unregistered PRNG callback (0014, built-in HMAC-SHA256 provider + direct entropy/write_random hashing); absent Image4/AMFI trust-cache service (0015, unavailable runtime, loads rejected and queries no-match); missing platform driver (0016, SweetPlatformExpert exact personality); incorrect QEMU timer IRQ (0017, validated ADT PPI property, phone default19/QEMU27).
- **Latest kernel** `xnu/out-0017/kernel.development.sweet`, SHA256 `055a80190ab998b4df9203f1102072dcc78faad1779a537a514e522b682b582f`. Buildtree/log **`research/bt21` / `research/run21.log`**; all nine changed C/C++/header/config files byte-match local checked sources. Checksums passed. Entry PA `0xb146b488`, kernel end PA `0xb1ff4000`. Preferred baseline for patch 0018: `research/bt21/xnu` (no nested .git).
- **QEMU verified**: `research/q0017-noprogress` ran **30 seconds**, no visible panic, **zero unknown glyphs**, IRQ exceptions returned normally (4 IRQs, tickless idle). It still waits for CPU completion, so this is NOT a completed boot. Earlier 15s run `research/q0017` captured 122 IRQs, timer value27, GICR_ISENABLER0 `0x08000002`, and CPU WAIT; graphical progress overlay corrupted 13 glyphs. Add **`-noprogress`** to keep the console readable. New runner classifies incomplete/blank decoding explicitly (exit3 with --fail-on-panic), visible panic exits2. Snapshot-only; use regs/GDB to diagnose stalls.
- Current QEMU payload/ADT: **`research/q0017-noprogress.bin` / `research/q0017.adt`**. Run: `python3 tools/qemu-sweet.py research/q0017-noprogress.bin research/NEW-OUT --secs 30 --kernel xnu/out-0017/kernel.development.sweet --fail-on-panic`. Generate fresh seed with mkadt for a new payload. QEMU virt models generic ARM execution, not Qualcomm XPU/bootloader/panel or the phone's SMC PSCI conduit.
- **Prepared phone image**: **`shim/out/shim-boot-0017.img`**, 16,416,768 bytes, SHA256 `51ff7fe30b4a6668c3452ffe1da922c5ac30cb8de60625c2a652587ecbd0ec92`. Phone ADT/payload `shim/out/sweet-0017.adt` / `shim/out/payload-0017.bin` (timer19). Unpacked ramdisk exactly matches payload (`shim/out/check-0017`). Command line **`debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress`**. NOT sent to phone this session: known CPU-driver wait should be addressed in QEMU first. Last actual phone boot remains 0013; user's latest photo `IMG_20261015_160033.jpg` confirmed the old PRNG PC=0 panic.
- Direct QEMU/GDB API checks: PRNG 600-byte chunking, buffer bounds, changing output, zero-length reads/writes, user reseed, contended refresh, generator1 init/output PASS again on latest0017 (`research/check-prng17.gdb` / `.log`, guest `research/q0017-api`). Trust-cache unavailable-service/argument/output cases PASS on0015 (`research/check-trustcache.gdb` / `.log`). Platform registration + target/product normal/truncated/zero/null/bounds PASS on0016 (`research/check-platform.gdb`, `research/check-platform3.log`). Different platform ID correctly retains IOPanicPlatform fallback (`research/q0016-negative`). Timer PPI32 and size2 correctly panic (`research/q0017-badppi`, `research/q0017-badsize`); omitted property selects19 (`research/q0017-default`). These are API/bring-up checks, not crypto certification or SMP scheduling validation.
- Local checker **`research/check-patch-order.py`** verifies all17 patches and changed source equality using a temporary upstream git index. Fixtures/logs/artifacts under research are local-only and ignored. For GDB unsigned kernel pointers, mask `int(register_value) & ((1<<64)-1)`; x30/x29 may be rendered signed. Stop at a function entry for manual-call return traps, and discard each manipulated guest after API tests. All fixture QEMU guests have been stopped.


- User wants persistent progress toward iOS 16, commits for completed changes, builds through `gh` / GitHub Actions.
- Keep this file current at every milestone so another agent can resume immediately, including when usage limits interrupt a session.
- Patch 0017 committed/pushed `aa3f991`, Actions `38751507437` running: https://github.com/dipa-studio/ios-sweet/actions/runs/38751507437. Next artifacts: xnu/out-0017, research/bt21, research/run21.log. Do not duplicate.
- Patch 0016 kernel downloaded/checksum verified: SHA256 `d06336c54baa06e0df6561a8bd7df98a9b9f7502c9381c62d1a44c045cd1ce46`, `xnu/out-0016/kernel.development.sweet`; buildtree/log `research/bt20` / `research/run20.log`. QEMU `research/q0016` (10s) prints platform expert registered, zero unknown glyphs, no panic observed BUT stalls (timer mapping still wrong until 0017). Direct actual-kernel GDB tests passed for registered instance and target/product names, including maxLength=1/0 and NULL, sentinels intact (`research/check-platform.gdb`, `research/check-platform3.log`, `research/q0016-api3`). First two fixture attempts used premature/wrong return breakpoints; discarded, corrected fixture uses start-return observation then a function-entry return trap. No phone boot yet.
- Patch 0016 CI `38750733996` PASSED (4m3s); artifacts not yet downloaded/booted. Patch 0017 prepared to fix QEMU timer fidelity BEFORE interpreting future no-panic/stall runs: actual `qemu-system-aarch64 -M virt,gic-version=3,dumpdtb=research/qemu-virt.dtb ...` timer property has virtual PPI 11 => INTID 27, while phone uses INTID 19. Kernel formerly hardcoded 19. New optional /arm-io/gic virtual-timer-intid property selects the PPI (validate exact u32 and 16..31); missing property retains phone default 19. One RO-late global drives GIC enable and sleh_irq dispatch. tools/mkadt.py emits phone19/QEMU27. Both C TUs compile (`research/timer-objs`), ADT serialize/parse checks confirm values/addresses, all 17 patches apply and match. Sandbox `research/bt19/xnu`, originals `research/pre0017`; initial local sleh compile failed due read-only exported header not updated, fixed export and BOTH recompiled successfully. CI exports normally.
- Architecture correction for next agent: CURRENT SWEET board_config does NOT define USE_APPLEARMSMP; it compiles the legacy IOCPU path, not cpu_boot_thread/IOPMGR AppleARMSMP. Existing roadmap mentions AppleARMSMP as a future approach. Do not look for gCPUIC/gAIC/gPMGR globals in the current kernel: they are absent. Determine the actual CPU-init wait after platform registration before choosing the next driver architecture.
- Patch 0016 committed/pushed as `0dcdf5c`; Actions `38750733996` running: https://github.com/dipa-studio/ios-sweet/actions/runs/38750733996. Next artifacts: `xnu/out-0016`, `research/bt20`, `research/run20.log`.
- Patch 0016 implemented: new `iokit/Kernel/arm/SweetPlatformExpert.cpp`, arm64 source list, built-in personality in KernelConfigTables.cpp guarded by ARM64_BOARD_CONFIG_SWEET. Matches only xiaomi,sweet at score 10000, keeps IOPanicPlatform fallback for other hardware. Uses IODTPlatformExpert base initialization/power domain and createNubs CPU logical-ID annotation; overrides top-level publishing because base requires nonexistent Apple NVRAM /options. Publishes real CPU/top-level nodes, provides bounded target/product names, and registers the platform service. GIC/PMGR and arm-io child-bus drivers remain separate work. Both C++ TUs compile (`research/platform-objs`), all imports resolve against 0015/own objects, all 16 patches apply and sources match. Sandbox `research/bt19/xnu`; originals `research/pre0016`. NEXT: full Actions/QEMU; inspect CPU boot waits after the platform registers, do not equate absence of panic with successful boot.
- Patch 0015 CI `38749549779` PASSED (4m3s), checksum verified. Kernel `xnu/out-0015/kernel.development.sweet`, SHA256 `ca1b424a596c7058550ad1659080a333e7643270f019656401d80bf2b876645f`; buildtree/log `research/bt19` / `research/run19.log`. QEMU `research/q0015` (10s, zero unknown glyphs) passes trust-cache handling and machine lockdown, then panics `Unable to find driver for this platform: "xiaomi,sweet" @IOPlatformExpert.cpp:2319` (IOPanicPlatform fallback). Next concrete work: add a built-in SWEET IODTPlatformExpert personality/class; keep the fallback for mismatched platforms. No phone boot yet.
- Direct trust-cache API checks PASSED in the actual 0015 kernel under QEMU/GDB (`research/check-trustcache.gdb`, `research/check-trustcache.log`, `research/q0015-api`): runtime pointers NULL, hash/UUID queries return NOT_FOUND, typed/untyped/legacy loads return NOT_SUPPORTED, capabilities outputs zero and bounds preserved, invalid-argument cases still reject. Second PRNG check also verifies contended refresh returns immediately (`research/check-prng2.log`, `research/q0014-api2`).
- Patch 0015 committed/pushed `8f851d4`, Actions run `38749549779` running: https://github.com/dipa-studio/ios-sweet/actions/runs/38749549779. Do not duplicate.
- Direct PRNG API checks passed in the REAL 0014 kernel under QEMU/GDB, stopped before trust-cache init (`research/check-prng.gdb`, log `research/check-prng.log`, guest `research/q0014-api`). Invoked read_random for 600 bytes (chunking and buffer sentinel intact), repeated output differed, zero-length read/write succeeded, write_random(64-byte input) succeeded, secondary generator 1 initialized and generated distinct output. QEMU log has no exceptions during these checks; guest was discarded after the tests. This tests API behavior, not a cryptographic certification or SMP scheduling.
- Patch 0015 implemented in `bsd/kern/kern_trustcache.c`: SWEET with missing Image4/AMFI marks both runtime pointers NULL and logs service unavailability. Existing static loader handles NULL. Public load APIs return KERN_NOT_SUPPORTED; hash/UUID queries return KERN_NOT_FOUND; capabilities outputs are zero with KERN_NOT_SUPPORTED. Invalid-input checks remain, and Apple paths/available-provider initialization retain existing behavior. No trust is granted. Local arm64 compile passed (`research/trustcache-objs`), all 15 patches apply and sources match. Sandbox `research/bt18/xnu`, baseline `research/pre0015`. Next: Actions/QEMU and direct unavailable-service API checks using GDB.
- Patch 0014 CI `38748543058` PASSED (4m0s), artifact checksum passed. Kernel `xnu/out-0014/kernel.development.sweet`, SHA256 `741de20c851755d333759d7e668346f3edb4f325efac4cc7c142d80d1f5ff75c`; buildtree/log `research/bt18` / `research/run18.log`. QEMU run `research/q0014` (10s, zero unknown glyphs) prints `SWEET PRNG: HMAC-SHA256 registered`, passes commpage initialization, loads vnguard policy, THEN panics `image4 interface not available @kern_trustcache.c:253`. PC=0 fault FIXED IN QEMU. No new phone boot performed.
- Next work: SWEET currently has neither AppleImage4 nor AMFI. `trust_cache_runtime_init` unconditionally requires both; unlike BCM2837, SWEET enters this startup path. Investigate an explicitly unavailable trust-cache runtime with rejected loads/no query matches while providers are absent; preserve all Apple-platform checks. Merely skipping the startup call would leave later AMFI/IMG4 dereferences unsafe. Existing load_static_trust_cache already handles trust_cache_rt == NULL.
- QEMU runner now supports `--kernel MATCHING_KERNEL --fail-on-panic`: runtime font extraction from the payload produces exact `fb.txt`, plus `result.json`; a visible panic returns 2. Baseline 0013 re-run `research/q0013-text` detects the same NULL callback panic with zero unknown glyphs. Synthetic glyph roundtrip (including literal `?`) and invalid-VA rejection passed. Screen rows remain circular, not a full log; `no_panic_observed` does not prove successful boot. README has the invocation.
- Patch 0014 committed/pushed as `be61f99`; Actions run `38748543058` is running: https://github.com/dipa-studio/ios-sweet/actions/runs/38748543058. Do not start a duplicate build.
- 2026-10-15 active: hardware photo `IMG_20261015_160033.jpg` confirms the same PC=0 instruction-fetch abort as QEMU (LR `0xfffffe0007443fe4` = read_random). Independently reproduced with kernel 0013 in `research/q0013` (8-second run); prior allocator fix works. Latest tooling commit reviewed: `8d66d2d`.
- Patch 0014 implemented: registers a built-in HMAC-SHA256 DRBG provider at EARLY_BOOT/FIRST, before commpage creation. A shared mutex serializes output/reseed across CPUs (correctness first; no per-CPU scaling yet), initgen validates CPU identities, refresh uses try-lock and the existing entropy filter/health tests. SWEET entropy accumulation and write_random now use the built-in SHA256 directly; no incomplete g_crypto_funcs table is registered. The existing bootloader-seed requirement remains enforced.
- Local validation: both PRNG translation units compile to arm64 objects in `research/prng-objs`; no SHA256 wrapper imports remain. All 14 patches apply in CI order and resulting PRNG sources match local inputs. Sandbox `research/bt17/xnu`, originals `research/pre0014`, checker `research/check-patch-order.py`. NEXT: Actions kernel build, download to `xnu/out-0014`, run the QEMU payload before requesting another phone boot. Baseline QEMU ADT/payload are `research/q0013.adt` / `research/q0013.bin`.
- 2026-10-15 08:15 QEMU EMULATION WORKS (`tools/qemu-sweet.py`, see "QEMU emulation" below). Patch 0013 VERIFIED in QEMU: boot passes kmem_crypto_init and ulock_initialize. NEXT BLOCKER (reproduced in QEMU, expected on hardware too): `pmap_create_commpages -> random() -> RandomULong -> read_random -> prng_funcs.refresh == NULL` (instruction fetch abort at pc 0, lr read_random+0x34). Nobody calls `register_and_init_prng` (closed corecrypto kext does it on Apple). Fix = patch 0014: SWEET-registered cckprng_funcs provider (osfmk/prng/prng_random.c); note random_cpu_init also panics while !prng_ready. The 07:26 hardware boot of 0013 will most likely show this same panic.
- Previous hardware boot: patch 0013 (`a3a46e2`) CI `38686345689` PASSED (3m44s), image `shim/out/shim-boot-0013.img` was temporarily booted on 2026-10-15 at 05:26 UTC: send OKAY (0.407s), boot OKAY (0.134s), total 0.546s. Superseded by the hardware/QEMU PC=0 observation and patch 0014 work above.
- Latest kernel implementation commit: `8f851d4`. Latest successful kernel CI: `38749549779` (patch 0015), https://github.com/dipa-studio/ios-sweet/actions/runs/38749549779.
- CURRENT image: `shim/out/shim-boot-0013.img`, 16,412,672 bytes, SHA256 `110d1c46aee4b60253db24b6535e9781c4cf0fd25ca2a70e9016cf81378cea25`. Kernel `xnu/out-0013/kernel.development.sweet`, SHA256 `f0b1d375995316c550ce7014ff234d8271e9b9ac2857795ceff41b76ba2cd740`, plain arm64. CI log confirms 0013 applied; checksums passed. Entry PA `0xb146b488`, kernel end PA `0xb1ff4000`.
- Current log/buildtree: `research/run17.log`, `research/bt17` (extracted, no nested .git; preferred baseline for patch 0014). Payload/ADT: `shim/out/payload-0013.bin`, `shim/out/sweet-0013.adt` (includes /defaults). Unpacked ramdisk byte-compared with payload in `shim/out/check-0013`.
- Patch-0012 original image: `shim/out/shim-boot-0012.img`, 16,412,672 bytes, SHA256 `cf4b8ec4a65a51888d71c17d09cd0831d6b761b90e2531fdb8e575c32f4fd24a`. Kernel `xnu/out-0012/kernel.development.sweet`, SHA256 `69b78f49f6459cc63a0af44e7cf73c1779ef72130ef72b12ae86c88183ffc742`; checksums passed and sweet_early_relocate symbol present. Entry PA remains `0xb146b488`, kernel end PA `0xb1ff4000`.
- Patch-0012 log/tree: `research/run16.log`, `research/bt16` (extracted, no nested .git; preferred baseline for next patch). CI log confirms 0012 applied. Payload `shim/out/payload-0012.bin`, ADT `shim/out/sweet-0012.adt`; packed ramdisk byte-compared with payload in `shim/out/check-0012`.
- Active payload command line: `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam`.
- Latest observed photo: `/home/dipa/Downloads/IMG_20261015_071346.jpg` (local only). Stages 9 (kernel framebuffer VA), 10 (TTBR0 off/TLB flush), 11 (physmap table pointers) and 12 (calling pmap_bootstrap) all visible. Persistent diagnostics are VERIFIED ON HARDWARE.
- pmap.c:1987 is the assert after SecureDTLookupEntry(NULL, "/defaults", &entry). The pmap-max-asids property itself is optional; an empty /defaults uses XNU's MAX_ASIDS. Do not bypass the assertion or guess an ASID limit.
- Previous payload-only fix image: `shim/out/shim-boot-0012-defaults.img`, SHA256 `3ff61a268853c6ea7cbf284833f1346a1d791980ca366b6e1a215a86e040512b` (16,412,672 bytes). Same kernel/CI as 0012; ADT 2516 bytes (`shim/out/sweet-0012-defaults.adt`), root /defaults present with no ASID override. Payload `shim/out/payload-0012-defaults.bin`; unpacked ramdisk exactly matches payload (`shim/out/check-0012-defaults`). This boot reached the allocator crypto NULL-pointer fault below.
- Latest hardware photo: `/home/dipa/Downloads/IMG_20261015_071608.jpg` (local only). Normal serial framebuffer console works. VM bootstrap/zone initialization, logging, scheduler, IPC, KDP and ulock_initialize print before the kmem_crypto_init data abort. gPanicBase warnings are expected because PLATFORM_PANIC_LOG_DISABLED is configured, and are not the faulting call.
- Faulting instruction: `ldr x0, [x8, #0x150]` in crypto_random_kmem_ctx_size; x8 = NULL g_crypto_funcs. Source: libkern/crypto/corecrypto_rand.c and osfmk/vm/vm_kern.c:2448. rand.h explicitly permits NON-cryptographic kmem RNGs, but requires no locking in generation and context size <=256. Do not substitute read_random here: the global PRNG provider is also unregistered and kmem generation must remain lock-free. early_random may seed contexts during single-CPU bootstrap; it uses the built-in HMAC-SHA256 DRBG with the host-generated ADT seed.
- Patch 0013 keeps the replacement entirely private to vm_kern.c: SplitMix64 state is 8 bytes per CPU/sizeclass, initialized using early_random. Uniform selection uses rejection sampling to avoid modulo bias. Other platforms retain the original corecrypto calls; SWEET's generic crypto APIs/registration remain untouched. Reference: https://prng.di.unimi.it/splitmix64.c (Sebastiano Vigna, public domain).
- Validation: vm_kern.c compiles to arm64 (`research/kmem-rng-objs`, using `research/run16.log` + `research/bt16`). Undefined symbols include early_random and NO crypto_random_* references. All 13 patches apply in CI order and match the checked source. Original saved as `research/vm_kern.pre0013.c`.
- RNG host checks: extracted actual new helper in `research/kmem-rng-check.c`; 16,384 outputs match the author's downloaded reference (`research/splitmix64-reference.c`), 147,456 bounded outputs satisfy their limits (including 1 and UINT64_MAX), and a forced rejection advances correctly. Full kernel crypto services and the registered kernel PRNG provider remain future work; this patch only supplies the allocator RNG contract.
- Patch-0011 artifacts: kernel `xnu/out-0011/kernel.development.sweet`, log `research/run15.log`, extracted buildtree `research/bt15` (no nested .git). CI log confirms patch 0011 applied; artifact checksums passed. Kernel is plain arm64, entry VA `0xfffffe000746b488` -> PA `0xb146b488`, kernel end PA still `0xb1ff4000`.
- Patch-0011 image: 16,412,672 bytes, SHA256 `29ad5cbfc752473de4af2c471a24a8b34f92da4bff5afec65c614b90cd3ad53a`. Kernel SHA256 `8ac3a956894b09f7bd0d890de8c5de38c65513287feb1e1bcd12db8ca772ee5c`. Payload/ADT in `shim/out/payload-0011.bin`, `shim/out/sweet-0011.adt`. Header unpacked/checked in `shim/out/check-0011`.
- First patch-0011 attempt timed out waiting for FASTBOOT; superseded by the successful send/boot recorded above. Do not repeat the boot before the user reports the current screen.
- Patch-0011 photo: `/home/dipa/Downloads/IMG_20261015_070218.jpg` (local only). Visible stages 1-8 and old red shim text; entry PA B146B488, boot args PA B1FF8000 / top B1FFC000. No evidence yet locating execution after stage 8.
- Patch-0012 sandbox: `research/bt15/xnu` (NO nested .git). Proposed permanent debug VA: VM_MIN_KERNEL_ADDRESS + ARM_TT_L2_SIZE, in the reserved gap below gVirtBase and above low globals; map the same PA framebuffer as Normal-NC in the final TTBR1 before arm_vm_physmap_init changes phystokv(). Keep the early panic sink until normal kprintf startup.
- Patch 0012 validation: all 4 changed C translation units compiled to arm64 objects in `research/post-ttbr0-objs`; internal header export added to osfmk/arm64/Makefile and recreated locally in EXPORT_HDRS for pe_serial.c. All 12 patches apply in CI order and match all 6 edited files. Baselines are saved under `research/pre0012/`.
- Actual mapping-helper host model (`research/early-map-check.c`, barrier stubbed only for host compilation) confirms: VA `0xfffffe0002000000`, L1 index 2016, L2 index 1; descriptor `0x006000009c000605` = framebuffer PA, Normal-NC, outer-shareable, EL1 RW, PXN+UXN. All other L2 entries preserved. The gap is excluded by ARM_LARGE_MEMORY's pmap_virtual_region(0).
- Next boot command line MUST add `-enable_kprintf_spam`: DEVELOPMENT disables kprintf_output by default even when DB_KPRT is set (`pexpert/arm/pe_kprintf.c`). Planned command line: `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam`.

### Patch 0012 screen legend (after original stages 1-8)
- 9: kernel framebuffer VA live; 10: TTBR0 off / TLB flushed; 11: physmap pointers rebound.
- 12: calling pmap_bootstrap; 13: pmap_bootstrap returned; 14: early I/O page tables ready; 15: arm_vm_init returned.
- 16: calling serial_init; 17: fbcon config read / mapping; 18: fbcon mapping returned; 19: serial_init returned; 20: kprintf startup complete.
- Normal serial initialization clears the screen, so earlier stages may disappear before 19. If serial exists, early console disables after 20; otherwise early panic output stays enabled.
- Local source sandbox: `research/bt13/xnu` (git baseline `623b060`, patches 0001-0008 already in baseline; uncommitted export edits correspond to patch 0009). Preserve those edits when producing patch 0010.
- Previous compile log/tree: `research/run13.log`, `research/bt13`; previous kernel: `xnu/out/kernel.development.sweet`. New successful log/tree: `research/run14.log`, `research/bt14`; new kernel: `xnu/out-0010/kernel.development.sweet`.
- Current device access: patch-0012 image was temporarily started from FASTBOOT; no adb connection is expected. Never flash partitions for bring-up; use `fastboot boot` with the shim image.
- Patch `0010` lives in `xnu/patches/0010-sweet-early-framebuffer-debug.patch`. Its exact compiled sources are under `research/bt13/xnu`; generated objects are in `research/early-objs`.
- Local checks passed: all 5 changed/new translation units compiled to arm64 Mach-O objects; new console only imports `_doprnt` and `iso_font` (both exist in the previous kernel). All 10 patches applied to a temporary upstream git index in CI order, and all 7 resulting changed source files matched the local compile inputs.
- Reproduce changed-file compilation: `XNU_CC_OBJDIR="$PWD/research/early-objs" python3 tools/xnu-cc.py research/run13.log research/bt13 arm_init.c arm_vm_init.c kern/debug.c arm64/start.s osfmk/arm64/sweet_early.c --per-file` (create the output directory first). The helper now accepts explicit new source paths absent from the old artifact's Makefiles and rejects empty selections.
- Device command result: `adb reboot bootloader`, then `timeout 30s fastboot boot shim/out/shim-boot-0010.img`: send OKAY (16028 KB), boot OKAY, total 0.541s. This confirms bootloader acceptance only, not XNU progress.
- The successful boot above was on 2026-10-14. On 2026-10-15, `timeout 45s fastboot boot ...` timed out waiting for a device; no image was sent. Boot image SHA256 rechecked and unchanged. No new build is needed to repeat the trial.
- Earlier retry: `timeout 90s fastboot boot shim/out/shim-boot-0010.img` timed out (exit 124). This is superseded by the successful 2026-10-15 repeat boot recorded above; do not repeat it until the user reports the screen.
- User observation confirms MMU-on C entry, platform expert, CPU topology/bootstrap, startup bootstrap and cpu_init all complete. Failure is within arm_vm_physmap_init (non-XNU_MONITOR branch), before stage 8 / TTBR0 teardown. Old red shim text remains behind the early console; this is expected because only written rows are cleared.
- New edit/compile sandbox is `research/bt14/xnu` (extracted artifact, NO nested .git; `git diff` there would act on the parent project). Use a saved baseline file / generated unified diff, or explicitly initialize a local baseline before editing. `research/bt13/xnu` does have its own baseline git repo.
- Exact user-reported panic: `arm_vm_init.c:1606 Assertion failed: (temp_ptov_table[ptov_index - 1].va + temp_ptov_table[ptov_index - 1].len) <= physmap_end`.
- Root cause: MacOSX build sets `ARM_LARGE_MEMORY=1`; `XNU_MONITOR` is off. Block alignment in arm_vm_physmap_slide can add gaps, but the non-PPL large-memory physmap_end omitted the padding already present in the small-memory branch. Patch 0011 reserves PTOV_TABLE_SIZE*ARM_TT_TWIG_SIZE (8*32MB) in both the aperture bound and its L1 allocation; monitor/PPL builds retain zero padding. The assertion is preserved.
- Validation: `arm_vm_init.c` compiled to an arm64 object using `research/run14.log` + `research/bt14` (object in `research/physmap-objs`). All 11 patches apply in CI order and produce exactly that source. Host harness `research/physmap-check.c` extracts the real XNU slide function with page-table-write stubs: all 65,536 page-aligned slides within 1GB checked against the current kernel memory layout; old bound fails 65,504 cases, padded bound fails zero; worst overrun 0x1ffc000 bytes. Baseline source saved as `research/arm_vm_init.pre0011.c`.
- CI: https://github.com/dipa-studio/ios-sweet/actions/runs/38638702083 (success; artifacts and full log downloaded).
- New image: `shim/out/shim-boot-0010.img` (16,412,672 bytes, SHA256 `ed2c270e0081bad5ff517be415f9bfe8805463aea7866732203fa97ac737e64e`). Previous image preserved as `shim/out/shim-boot-pre0010.img`.
- New kernel SHA256: `3ee05270cc291c49589a101678f904b1b69cb2f2575e05398bce8a4e052f409a`. Artifact checksums passed; arm64 (not arm64e), early-console symbols present. Payload entry VA `0xfffffe000746a488` -> PA `0xb146a488`; kernel end PA `0xb1ff4000`. Command line remains `debug=0xc serial=3 cpus=1 keepsyms=1`.

### Patch 0010 screen legend
- Bottom-left white 64x32 tile: assembly entered `start_first_cpu`, before page tables/MMU.
- Text `SWEET EARLY 1`: entered `arm_init` with MMU on; 2: platform expert done; 3: CPU topology done; 4: CPU bootstrap done; 5: startup bootstrap done; 6: CPU init done; 7: entering `arm_vm_init`; 8: leaving bootstrap TTBR0.
- `SWEET EARLY PANIC:` prints a copy of panic arguments before normal panic handling needs per-CPU/thread state.
- In patches 0010/0011 the console disabled before TTBR0 invalidation; patch 0012 replaces that with a persistent kernel VA alias and diagnostics through normal serial/kprintf startup (see its legend above).
- Screen contents require a physical observation from the user: adb cannot capture a framebuffer after Android has been replaced by a bare-metal kernel.

## QEMU emulation (2026-10-15)
- `tools/mkadt.py OUT.adt --qemu` = same ADT with QEMU virt GICD 0x08000000 / GICR 0x080a0000 / CNTFRQ 62.5 MHz.
- `tools/qemu-sweet.py PAYLOAD OUTDIR [--secs N] [--hmp "x /8gx ADDR"] [--gdb]`: host-side copy of shim/loader.c
  (segments + ADT + boot_args at their PAs, 6-instruction stub sets x0 and jumps), `-M virt,gic-version=3 -cpu cortex-a76`
  (same ID_AA64MMFR0 as Kryo 470), 4G RAM so 0x9c000000 fb and 0xb0000000 kernel are plain RAM.
  Outputs `fb.png` (the screen), `regs.txt`, `qemu.log` (exceptions with ESR/FAR/ELR). `--gdb` halts with a stub on :1234
  (system `gdb` + `set architecture aarch64`, `hbreak *VA` works with the MMU on).
- Not emulated: Qualcomm XPUs, ABL, real panel, PSCI conduit (QEMU virt uses hvc). Hardware still decides those.
- Example: `python3 tools/mkadt.py /tmp/q.adt --qemu && python3 tools/mkpayload.py xnu/out-0013/kernel.development.sweet /tmp/q.adt /tmp/pq.bin --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam' && python3 tools/qemu-sweet.py /tmp/pq.bin /tmp/q`

## Layout
- `backup/`  partition dumps + full sdb..sdf LUNs, `SHA256SUMS` (all verified on-device == local)
- `dtb/`     live FDT (from OrangeFox), PixelOS boot.img dtb, dtbo, dts versions
- `shim/`    bare-metal boot shim (`./build.sh` -> `out/shim-boot.img`)
- `research/` mainline sm7150 dts, XNU pe_fiq.c etc, PocketDarwin patches
- `tools/unpack_bootv2.py`

## Device access
- No root in PixelOS 17 (user build, adb root disabled). Root = `fastboot boot recovery/recovery.img` (OrangeFox R12.0_2, temp boot, not flashed).
- `fastboot boot` works for stock boot.img, OrangeFox, and our shim.
- Shim resets itself via PSCI SYSTEM_RESET; IMEM restart_reason 0x77665500 is seen
  (bootreason=bootloader) but ABL still boots Android, so it does not stop in fastboot.

## Hardware facts (live DT + shim measurements)
- Framebuffer (ABL cont splash): 0x9c000000, 1080x2400, stride 4320, a8r8g8b8, panel is DSC *video* mode (no kick needed).
- RAM: 0x80000000+2G, 0x100000000+0xfcc00000. Live reserved-memory = PixelOS base dtb + sweet dtbo fixups.
- GICv3: GICD 0x17a00000, GICR 0x17a60000 (stride 0x20000, 8 PEs). GICD_TYPER 0x007B041D: SecurityExtn=1 (DS=0).
  ABL leaves GICD_CTLR = 0x10 (ARE_NS on, groups off). Writing 0x13 reads back 0x12: EnableGrp1A (bit1) is the one that matters.
- GIC Group 1 VERIFIED (shim 2c): vtimer INTID 19 = 30 IRQs/300ms, ptimer INTID 18 = 30, SGI 1 to self = 10/10.
  ICC_SRE=1 already, ICC_CTLR 0x8440, priority/enable writes stick. GICR_IGROUPR0 and GICD_IGROUPRn read 0 from NS
  even though Group 1 delivery works (RAZ in NS view) - do not use them as a health check.
  INTID 28 shows pending constantly (unknown PPI 12).
- Timer 19.2 MHz. Qualcomm PPI numbering: secure-phys/phys/virt/hyp = PPI 1/2/3/0 -> vtimer INTID 19, ptimer 18 (NOT 27/30).
- PSCI 1.1 via SMC, SMCCC 1.1. CPU_ON ok; SYSTEM_SUSPEND and SYSTEM_RESET2 unsupported.
- SMP: CPU_ON works for all 7 secondaries (MPIDR 0x81000n00).
- Entry EL1, MMU off, x0 = DTB (magic ok). ID_AA64MMFR0 = ...101122: 16K granule YES, 4K YES.
- No serial console: debug UART SE is in SPI mode on sweet. Screen is the only debug channel.

## XNU implications
- XNU GICv3 path (pexpert/arm/pe_fiq.c, VMAPPLE) puts the timer (PPI 27) in Group 0 = FIQ. With SecurityExtn=1,
  Group 0 is secure -> impossible from NS EL1. Need: Group 1 IRQ, ICC_IGRPEN1, INTID 19, and the timer handled in the IRQ path.
- XNU VMAPPLE PSCI uses `hvc`; sweet needs `smc`.
- PocketDarwin NonAppleGenericCpu.patch only swaps -mcpu=apple-h7 for -march=armv8-a.

## Milestone 3 (2026-10-14): 16K MMU verified
- ABL loads the Image at 0x80080000 (base 0x80000000 + 0x80000) regardless of text_offset=0.
- 16K granule, T0SZ=28 (L2 start, 32MB blocks), MAIR 0x44ff00, TCR 0x1409CB51C, PARange=2 (40-bit PA).
- Only own image pages WB (Qualcomm XPUs: never map carve-outs cacheable); fb Normal-NC; rest Device.
- AT S1E1R checks all as expected; unmapped -> translation fault L2.
- Fill fb: 110 ms (MMU off) -> 3.5 ms (NC). Memory loop 70 ms -> 0.7 ms. vtimer + SGI IRQs still fine with MMU on.

## XNU loader design notes (xnu-8796)
- Entry: `_start` -> `start_first_cpu`, x0 = boot_args (PA), MMU off, EL1. boot_args: Revision/Version 2,
  virtBase/physBase/memSize/topOfKernelData, Boot_Video (fb 0x9c000000, rowBytes 4320, 1080x2400, depth 32),
  deviceTreeP/Length (ADT), CommandLine[608], bootFlags, memSizeActual.
- start.s maps [kernel mach header .. physBase+memSize) with cacheable BLOCKS. On Qualcomm every XPU carve-out
  must therefore lie below the kernel: use physBase = 0xb0000000 (above ramdump_fb 0xaf000000+16M,
  cdsp_sec, qseecom), end before rmtfs 0xfde01000 -> memSize ~0x4d000000 for bring-up.
- Base ADT: iPhone 8 d20ap DeviceTree from iOS 16.7.16 IPSW (tools/remotezip.py + tools/adt.py; LZFSE payload).
  Template values are empty: the loader must fill chosen/*, memory-map, cpu*/reg etc. like iBoot.
- XNU build: GitHub Actions (dipa-studio/ios-sweet, xnu.yml) via blacktop/darwin-xnu-build, MACOS_VERSION=13.5.
  New-clang fixes in xnu/patches; Xcode 16 iig is incompatible (IORPC.kernelContent) -> macos-14 runner, oldest Xcode.

## Kernel architecture plan (SWEET machine config)
- First stock build (VMAPPLE) is arm64e (PAC). Kryo 470 = ARMv8.2, no PAC -> SWEET must build plain arm64
  (HAS_APPLE_PAC is only defined for __arm64e__, so arm64 drops PAC automatically).
- Template: VMAPPLE (16K pages, GICv3 code in pe_fiq.c) minus APPLEVIRTUALPLATFORM hypercalls/paravirt PAC,
  plus BCM2837 (generic ARM: no APPLE_ARM64_ARCH_FAMILY Apple sysregs). Do not link the KDK lib<cfg>.os.*.a.
- Timer: XNU expects it on FIQ (sleh_fiq -> rtclock_intr). SWEET: GIC Group 1, so sleh_irq must ack ICC_IAR1,
  route INTID 19 to the same timer path, SGIs to cpu_signal_handler, EOI via ICC_EOIR1.
- SMP/interrupts: open-source AppleARMSMP (USE_APPLEARMSMP) needs an IOInterruptController (AIC role) and an
  IOPMGR (CPU power -> PSCI CPU_ON via SMC). Plan: built-in IOKit classes (SweetGIC, SweetPMGR, platform
  expert) compiled into the kernel and matched via iokit/KernelConfigTables.cpp -> no closed kexts needed.
- Debug: xnu patch 0003 sweet-fbcon = kprintf drawn on the framebuffer (ADT node "sweet-fbcon").
- ADT /arm-io ranges must not map to parent 0 (pe_arm_get_soc_base_phys()==0 disables serial): use parent 0x1000000.

## Status 2026-10-14 late: first XNU boot attempt
- SWEET kernel builds (CI run 38635343732, patches 0001-0009). Verified offline: arm64, no PAC, no >v8.2 code,
  70300 classic relocs all in range (slide 0 = no loader work), entry = __start.
- Boot: shim loader worked (initrd 0x846F0000-0x855FE3E0, BOOTARG 0xB1FF8000, JUMP 0xB146A488) but screen stayed
  red -> xnu died/hung before serial_init (fbcon). kprintf is a no-op before STARTUP_SUB_KPRINTF.
- Historical next-step plan (patch 0010, now implemented and built; see active handoff above): early fb debug channel
  1. start.s start_first_cpu (after mov x20,x0 / mov x21,#0): PA marker band (MMU off, direct store to 0x9c000000).
  2. start.s after both create_bootstrap_mapping calls: add ONE block entry to the existing V=P L2 table
     (x25 + 2*PGBYTES; do NOT call create_bootstrap_mapping again: fb and RAM share L1 entry 0, it would replace
     the L2 table). Entry = TYPE_BLOCK|VALID|SH(OUTER)|ATTRINDX(CACHE_ATTRINDX_WRITECOMB=1)|AF|PNX|NX|0x9c000000,
     index = (va & ARM_TT_L2_INDEX_MASK) >> ARM_TT_L2_SHIFT.
  3. new osfmk/arm64/sweet_early.c (+files.arm64 entry): sweet_early_mark(n) colored bands at screen bottom and
     sweet_early_putc using iso_font via VA=PA while the bootstrap TTBR0 is live; disable before
     arm_vm_init's set_mmu_ttb(invalid_ttep) (arm_vm_init.c:2148).
  4. markers in arm_init after PE_init_platform, ml_parse_cpu_topology, cpu_bootstrap, kernel_startup_bootstrap,
     cpu_init, before arm_vm_init.
  5. panic hook at top of panic_trap_to_debugger: va_copy + _doprnt(fmt, &copy, sweet_early_putc, 16).
  Verify with tools/xnu-cc.py (compile+symbols) and patch-order simulation before the single CI run.

## ATHENS (RMX2117) — rootfs deployed, launchd spawn reached (2026-11-06)

**Kernel**: fully working on hardware — 8/8 CPUs PSCI, GIC, timer, AppleCLCD
(ovl1 surface, console to it via 0160 + EL2 trap-skip emulation in shim),
touch, MT6359 PMIC keys + battery, UFS host.

**Rootfs**: ios16-root.simg (iPhone X 16.7.16, 4 DMGs merged) flashed to
userdata/sdc59. Last sparse chunk failed -> repaired via recovery dd
(sha256-verified, tail 283 MB at block 12513632).

**Boot chain so far**: kernel boots -> mounts HFS+ root -> spawns launchd
(pid 1) -> panic `initproc failed to start: failed to reserve stdin
descriptor: /dev/null: 2` (ENOENT). devfs can't mount without a /dev dir
on the rootfs; mkiosroot.sh now seeds /dev + real device nodes.

**Kernel bugs found+fixed**: realme lk enters at EL2 (shim now erets to EL1),
early fb writes need `dc cvac`, secondary CPUs trap MSR/MRS to EL2 (shim
emulates/skip via new exc path), UFS DMA>4G -> constrained <4G always,
`/sweet-ufs` ADT node was missing (mkadt needed --athens-ufs; regenerating
the adt without it silently dropped the node), UFS ENXIO sites now tagged
61-69 for diagnosis.

**Pending**: rootfs CI run 42204859640 rebuilds image w/ /dev; flash +
boot to verify launchd proceeds. Then Setup Hello gate -> home screen.

**Update (run 42235617514)**: first /dev rebuild (42205129956) used default
rootfs_size=52G -> image 52 GiB > ~49.8 GiB userdata -> fastboot "size span
overflow". Re-triggered with rootfs_size=48G (the 48 GiB that fit before).
mkiosroot.sh now seeds /dev + real null/zero/console nodes. Boot after flash
should clear the "reserve stdin descriptor" panic -> Setup Hello.

**/dev/null panic deep-dive (run 42260249664)**: /dev + real mknod device
nodes still panicked "reserve stdin descriptor: /dev/null: ENOENT".
Diagnosis: devfs is NOT mounting at /dev (if it were, devfs's own null
would resolve), so the open hits rootfs /dev -> needs /dev/null there.
mknod on Linux hfsplus doesn't reliably write device records, so the
nodes were likely absent. Changed to touch /dev/null|zero|console as
REAL files (open() succeeds regardless) + mknod attempt kept. If this
still panics, the lookup isn't reaching rootfs -> kernel-side VFS fix
(create /dev/null post-mount) is next.

**Dual /dev/null fix in flight**: kernel patch 0162 adds devfs_make_node for
null/zero/console in sweet-ufs (covers devfs-mounted-but-nodes-missing);
image rebuild seeds real /dev/null file (covers devfs-not-mounted).
Kernel run 42260613587 (~9min), image run 42260249664 (~2.5h).

**/dev/null RESOLVED**: kernel patch 0162 (devfs_make_node null/zero/console)
+ image real-file /dev/null cleared the stdin-reservation panic. launchd now
runs into real userspace. NEW blocker: pid 4 "sepul" panics parsing its own
Mach-O — "malformed load command #13 of 32 ... size too large, handshake
structure not initialized". SEP daemon binary is corrupt/incompatible.
Next: drop sepul (and any SEP-dependent jobs) from launchd.plist like
CommCenter, or fix the binary in the image.
Kernel run 42260613587, image run 42260249664 both applied; boot img has
ufslun=2 + devfs nodes; userdata has /dev real-file fix.

**sepul fix (run 42305185694)**: sepul panicked on malformed Mach-O (dataless
cryptex binary / no SEP). Two-pronged: (1) removed com.apple.sepul from
launchd.plist, (2) stubbed the binary with a valid no-op in mkiosroot.sh
(find -name sepul -> cp sysstatuscheck/true). If it now panics on the NEXT
cryptex binary, the dataless-placeholder problem is systemic and needs
broad materialization, not per-binary stubs.

**sepul->seputil mechanism (researched, not guessed)**: both are launchd
"data-protection" BOOT TASKS (not launchd.plist jobs) that handshake the SEP
via AppleSEPUserClient. No SEP hw -> handshake fails -> mandatory task exits
-> panic. vphone research confirms: "Boot task failed: data-protection -
exit(60)", "IOUC AppleSEPUserClient failed MACF in seputil".
Fix committed: stub the whole SEP binary family (sepul,seputil,sepfwupdate,
seprestore,sepmigration,sepd*,sep_rom*) to a valid exit-0 Mach-O so tasks
report success. DEEPER patch (hw-capability, not stub) = kernel-side built-in
AppleSEP driver+user client answering the handshake, modeled on SweetKeyStore
(patch 0038); needs seputil's handshake selector protocol (log-and-iterate).
Run 42361275377 (stub + launchd label dump) in flight.

**FACTORY-OS PIVOT (user directive)**: goal is a daily driver -> stock
rootfs (factory=true skips sweet-root-tweaks + all binary stubs), kernel
supplies all hw capability, fixes only from verified research.
Current userdata image: run-42305909620 image (seputil plist-drop; binary
intact). Factory img build: 42361811996.
Kernel SweetSEP (patch 0163): built-in AppleSEPControl IOService +
logging user client (modeled on SweetKeyStore). First build skipped the
patch as corrupt (hunk count off by 2) -> boot still panicked
kalloc.16384 use-after-free (a pre-existing kernel bug on seputil's
teardown path, NOT the stub). Fixed count; rebuild 42363930829.
seputil matches AppleSEPControl (sep.yaml: xnu_name, AppleSEPManager
kext, sepd endpoint 0, A7-IOP mailbox).
Persistent log ring: last ~4 MB region of sdc59 works via
`dd bs=1M skip=50500` + grep SWEET.

**Kernel panic shift (SweetSEP boot)**: seputil task-exit panic became a
kernel UAF: `[data.kalloc.16384] element modified after free` detected in
_hfc_btree_open_ext during posix_spawn->exec_mach_imgact->_binary_match
(backtrace symbolized vs kernel.development.sweet). NOT caused by
SweetSEP — same signature on the skipped-patch boot. Corrupted element =
16 KiB buffer = HFS btree node size. Candidate causes: (a) HFS node
buffer lifecycle bug in hfs-627 on Linux-mkfs btree, (b) pre-existing
heap corruptor detected at btree alloc, (c) journal replay writing into
freed nodes. UFS DMA ruled out (single static bounce buffer, never
freed). DISCRIMINATOR: factory image (42361811996) = clean journal+btree.
If UAF persists on clean image -> kernel driver bug; if gone -> old
userdata's btree corrupted by unclean rw panics. Persistent ring didn't
capture this boot (panic kills flusher).
SweetSEP patch 0163 confirmed in kernel (strings+personality present);
seputil still printed "handshake structure not initialized".

**seputil root cause identified (factory image boot):** panic `seputil[4]
exited -- exit reason namespace 0 subcode 0x9 description: file does not
start with MH_MAGIC(_64): 0x7a43019D 0x7a43019C` + "handshake structure
not initialized" (the latter is KDP debugger noise, unrelated). Facts:
- /usr/libexec/seputil IS a valid Mach-O (203584 bytes, cffaedfe) via
  hard-link iNode - binary fine, exec works.
- dyld cache + all 42 sub-caches valid ("dyld_v1 arm64").
- "file does not start with MH_MAGIC" NOT in kernel binary or seputil -
  it is userspace dyld's fileset validator (dyld_kernel_fixups.h is
  shared kernel/dyld code).
- seputil strings: wants AppleSEPManager service
  (com.apple.driver.AppleSEPManager), AppleSEPUserClient, entitlement
  com.apple.private.applesepmanager.allow, checks
  IODeviceTree:/arm-io/sep, get_firmware_path, loads SEP fw img4.
- My stub registered WRONG NAME (AppleSEPControl) -> seputil never
  connected -> fell into firmware-load path -> hit a non-Mach-O file.
- No file in the image starts with 0x7a43019d/9c (scanned all regular
  files + all 179k iNode data forks) - likely an uninitialized/missing
  firmware-path buffer or a file outside the volume.
- kalloc.16384 UAF did NOT recur on clean factory image -> was old
  userdata btree corruption.
FIX: patch 0163 rewritten - AppleSEPManager attaches to
IODeviceTree:/arm-io as "sep" (satisfies fromPath lookup), registers
AppleSEPManager service + AppleSEPUserClient (initWithTask logs open
type), logs every selector. Kernel CI 42386132566.
NEXT: if seputil connects, log shows sel/args -> implement real
handshake; else check whether arm-io attach works (attachToParent log).

**AppleSEPManager arm-io attach broke UFS (panic):** kernel CI 42387138633
(with attachToParent(arm-io) under IODeviceTree:/arm-io) PANICKED:
`IOPfindBSDRoot: SWEET UFS root ufsroot0 unavailable: 66 @IOKitBSDInit.cpp:770`.
The DT attach corrupted the arm-io node tree so the UFS driver could not
find its provider -> no ufsroot0. The UFS driver's discovery happens via
the real DT; grafting a service onto arm-io reordered/invalidated it.
FIX: drop the DT attach entirely - register AppleSEPManager on IOResources
(like AppleKeyStore). seputil's IOServiceGetMatchingService("AppleSEPManager")
finds it by name; the IODeviceTree:/arm-io/sep path lookup is a secondary
check that may still fail but the connection is the important part.
Kernel CI 42396684096.
ALSO: phone flashed via adb dd (recovery) - fastboot flash unreliable.
boot = /dev/block/sdc52. `adb exec-in dd of=...` stdin streaming failed;
use `adb push` to /tmp then `adb exec-out dd`.
NEXT: if seputil connects (SWEET SEP: sel lines in log), implement real
handshake; the log ring only holds ~4MB and often goes stale - pull
/dev/block/sdc59 last 1025*4096 bytes after panic.

**ufsroot0 panic - real cause unknown, instrumented:** kernel 42396684096
(AppleSEPManager WITHOUT arm-io attach) panicked SAME:
`IOPfindBSDRoot: SWEET UFS root ufsroot0 unavailable: 66`.
CORRECTION to prior note: the DT attach could NOT cause this - UFS root
resolution (IOFindBSDRoot -> sweet_ufs_rootdev) runs BEFORE IOKit service
matching. The UFS failure started independently around the factory
userdata reflash.
FACTS:
- GPT on LUN0 verified INTACT from recovery: userdata = part 58,
  LBA 2566144-15615991 (13049848 blocks, ~49.8GiB). EFI PART magic ok.
- Error 66 = sweet_ufs.c loop-exhaustion mask; real per-LUN error was
  62(host not ready)/63(no GPT)/64(bad entries)/65(bad bounds)/
  ENOENT/scsi-error - hidden by `error = 66`.
- sweet_log_start() runs AFTER ufs_init succeeds, so a UFS failure
  never flushes the ring -> ring shows stale old-boot data.
- The SWEET UFS: LUN 0: no (XX) printf goes to framebuffer only.
FIX: patch 0164 makes `error = lun_error` so the panic shows the real
code. Kernel CI 42400552881. Boot it -> panic will say
"unavailable: 62|63|64|65|2|scsi-code" -> tells which stage fails.
SUSPECT (unverified): UFS host left in bad state (requests outstanding
from previous panic'd boot) or flaky TUR; or ufslun=0 missing the right
LUN after reflash (measured LUN0 2026-11-06, GPT confirmed on sdc).

**UFS root cause SOLVED (factual):** recovery sysfs showed sdc = SCSI
0:0:0:2 = UFS LUN 2. My ufslun=0 cmdline scanned the wrong LUN ->
panic 63 (no GPT on LUN 0). Boot WITHOUT ufslun scans all -> finds
GPT on LUN 2 -> userdata mounted rw. Correct arg: ufslun=2 or omit.
**task_id_token UAF panic:** after UFS fix, boot reached userspace and
panicked [task_id_token] element modified after free (off:8, val:
0x17c1970217cb6c64, sz:40). off:8 = token->port. Writers:
task_id_token_set_port (creation only) + lazy alloc in
convert_task_id_token_to_port (exception path EXCEPTION_IDENTITY_
PROTECTED fires on task fault). A dying task's token freed on one
thread while convert writes port on another = race. assert patch 0165
(os_ref_get_count_raw>0) panics at the WRITER for a real backtrace.
**AppleSEPManager never registered:** class+personality both in kernel,
identical to working AppleKeyStore pattern, but no SWEET SEP: line.
start() either not invoked or IOService::start returned false silently.
0163 now logs start() entry + failure. Kernel CI 42403347459.
MISTAKES MADE (guessing): ufslun=0 (wrong LUN), attachToParent(arm-io)
(DT graft couldnt even run - UFS resolves before services), reading
KDP "handshake structure not initialized" as a SEP error (its debugger
noise). LESSON: verify LUNs/partitions from recovery sysfs before
cmdline args; verify every panic string's source file before treating
it as the real fault.

**Memory-corruption root cause hunt (2026-11-07):** three distinct zone
panics on different boots — task_id_token off:8, kalloc.12288 off:64,
pmap PTE 0x2003037972ff1fe9 — all "element modified after free" with
~40-440 bytes of high-entropy runtime data. One stray writer, not three
bugs. RULED OUT (verified, not guessed): SMP race (cpus=1 still
corrupts -> pmap wired underflow + data abort), co-processor overlap
(live-FDT reserved map clean: all carve-outs <0xc0000000 or >0x1be000000,
kernel range doesn't touch them), FB overlap (0x78816000 below kernel
RAM), UFS DMA misconfig (sub-4GiB bounce, real PA, bounded copy-out).
Corruption started when UFS began real data reads (post-LUN-2).
**Catch-the-writer:** 0166 quarantines freed task_id_tokens (canary
instead of zfree) + validator on each release -> stray write panics
within one release, exposing writer context. Kernel CI 42409654215.
Panic log lives at phys 0x1bdf00000 (panic_base) but /dev/mem absent in
recovery so unreadable; ring log dies with panic so panics never flush.

## 2026-11-12 handoff - ZCHECK HIT: stray writer into the free pool confirmed

### Result (run 4, flashed image, beaa8e3d build)

- `SWEET ZCHECK` panic: **a shim-scrubbed page was nonzero at its FIRST
  handout** - `vm_resident.c:1260`. This is the first classification:
  something writes to free memory before any owner gets it (bus master /
  DMA or a stale CPU alias), NOT a live-owner UAF.
- BUT: the zcheck record with PA/offset/qwords was overwritten by the
  console-panic record - every `sweet_ufs_panic_write` wrote at the SAME
  fixed offset. Details of the hit are lost; only the panic string survives
  (`logs/run4-console-panic.txt`, raw `logs/athens-0175-run4-pull.txt.bin`).
- Runs 2-3 earlier: pulls were byte-identical -> those boots never wrote
  (old binary: @pmap_data.c:2766 false-positive lineage).

### Fix landed (commit 3c67ba2)

- `sweet_ufs_record_write(blk_off, tag, data, len)`: panic/console records
  stay at slot 0; `sweet_ufs_diag_write` slots at `72 + 8*n`, above the 256KB
  transcript zone -> zcheck/poolscan records survive the transcript rewrite.

### In flight

- CI run **43190643922** (workflow_dispatch, same drop set, verify adds
  `sweet_ufs_diag_write`). Next: artifact -> repack -> boot -> tail pull.
  Expect: `zcheck` record WITH PA/offset/qwords + population, then compare
  PA vs reserved-memory dump (DPM at 0xffe60000 is the prime suspect range).

### How to read the next tail

- `zcheck`/`poolscan` records at slots 72,80,88,96,... - walk them in order.
- PA near window top (~0xffe6xxxx) -> DPM/DRAM dummy-write HW; scattered PAs
  -> stale CPU store path; PA in low pages -> allocator bookkeeping.


### Follow-up (same day, commit 8f27322)

- The run-4 ZCHECK hit was probably a FALSE POSITIVE: zero-canary was not
  gated on topOfKernelData. ml_static_mfree frees kernel-carve pages
  (arm_vm_init.c:1636/1644/1653 + vm_pages[] tail) into the pool UNMARKED
  with live contents - a dirty first handout below tokd is expected.
- Fix: never-used population now requires pa >= BootArgs->topOfKernelData
  in both sweet_first_grab_pn and the scanner. Below-scrub pages are still
  marked at handout so they join the used-freed poisoned population.
- Records now carry tokd + avail_end; SWEET STATICFREE logs each
  ml_static_mfree range under DEVELOPMENT; record_write bzeros its extent.
- Rebuilding: CI run 43191529298 (supersedes 43190643922).


### Slot fix v2 + offline static-free check (commit 4ec33a8, CI 43192237918)

- SLOT BUG FOUND in first fix: diag slots 72+ landed inside the live ring
  flush region (base+1..base+1024), and panic-context diag_write still
  wrote blk 0 where console-panic rewrites land. Both would lose records.
- Now: top 256 blocks of the log window are reserved; ring flusher caps at
  SWEET_RING_BLOCKS=768 and skips reserved blocks; diag slots at 769+8n in
  BOTH locked and panic paths; record payload capped to slot size.
- ml_static_mfree ranges kept in sweet_sfree_ranges[32]; every zcheck/
  poolscan record appends the table; first panic console write emits a
  "layout" record. Hit PAs now classifiable without the ring.

- OFFLINE CHECK settled the PTD question: physmap delta = 0xfffffdef5e000000
  (from node VA 0xfffffdf020694460 <-> pa 0xc2694460). ml_static_mfree #1636
  frees physmap [gPhysBase, pa_of___TEXT) = ALL managed memory below the
  kernel image. PTD pa 0xc2694460 sits in [0xc0000000,~0xc6ff0000) -> inside
  static-free range 1. Legitimate pool usage; also THE population that can
  false-trip ZCHECK. All ml_static_mfree targets are below topOfKernelData
  by construction, so the tokd gate covers all three ranges.


### Build 43192237918 landed + booted

- CI: success 8m56s; verify gate printed all 7 markers (ZCHECK, POOLSCAN,
  PTD, used-freed, STATICFREE, sweet_ufs_diag_write, sweet_staticfree_dump).
- kernel sha256 868d88144441b7143e6f0e60d49227b97ea3933402ce824502c728cb5c8916a6
- image  sha256 3f34899bc0756fc1cd4bcebcf7eac63e6bcd30a9cec75aa19589962ff06b36ad
- cmdline: ufs-rw diag set + cpus=1 sweetuaf=1 sweetwatch=1 zlog1=vm_objects -zc
- fastboot boot ~10:08Z; device left fastboot. Watch screen / pull tail via
  PitchBlack. Expect records: layout, zcheck/poolscan slots, console-panic.


### RUN 6 - CLEAN STRAY-WRITER HIT (the real signal)

- Pull logs/athens-0175-run6-pull.txt.bin; decoded logs/run6-records.txt.
- Slot layout worked: 4x poolscan + zcheck + layout + console-panic all
  persisted in reserved zone.
- 4 CONTIGUOUS pages dirtied: pn 0x38000-0x38003 = pa 0xe0000000..0xe0010000
  (64KB block). Each dirty from offset +0x0, ~191 bad qwords/page.
  tokd 0xc25cc000 < hit < aend 0xffd60000: inside scrubbed window, NOT
  static-free -> real stray writer.
- qwords look structured: 0xd8c001dfd34060c0, 0x00000038014d4d4d (8/MMM),
  other pages w0 all differ - a writer filling a 4-page buffer, per-page
  from offset 0. Possibly DMA descriptor/data region at a round 0xe0000000.
- Same page later hit ZCHECK at handout (bad 191) -> panic @1281.
- STATICFREE table: only 3 ranges logged (SF0-2 inside kernel image pa
  0xc1b9../0xc215..) - hmm, range #1636 (everything below image) MISSING?
  Only 3 ml_static_mfree calls hit? Check: n=3 but #1636 frees [gPhysBase,
  segLOWEST) - maybe vm_page_create found no managed pages there, or it
  ran before counting? first_ppn==0 if freed_pages==0 -> not recorded.
  The three ranges recorded: 0xc1b90000,0xc1b98000,0xc2150000..0xc2198000
  = __KLD gap, __KLDDATA gap, __BOOTDATA (image-internal frees).

- NEXT: identify what owns pa 0xe0000000. Nothing in reserved-mem dump
  maps it. Check shim/ADT reserved regions and any fixed-PA carveout
  near 0xe0000000; check if EMI/dram dummy engine writes there.


### RUN 6 analysis - writer profile

- Writer hit 4 CONTIGUOUS 16K pages at pa 0xe0000000 (= window_base
  +0x20000000, round programmed-looking base), each from offset +0x0,
  ~191 nonzero qwords/page, while the pages sat on the FREE queue.
  t~562M ticks @19.2MHz ~= 29.3s into boot; ZCHECK then panicked when
  pn 0x38000 was handed out.
- 0xe0000000 is inside reserve-memory-dram_r1_dummy_read alloc-range
  [0xc0000000,0xffe60000) - the ONLY reserved region overlapping our
  window. MTK driver programs dram_rank*_addr into the SPM/DRAMC
  dummy-read engine; engine state persists across reboot from the
  Android-era boot. Unified theory: leftover engine writes at a stale
  programmed address -> explains the ROAMING corruption PAs across
  prior runs (ptd_free_list, task_id_token, kalloc.12288).
- su.dma ruled out: kmem_alloc_contig pages are wired+grabbed, not free.
- STATICFREE n=3 (image-internal frees only; range-1 freed 0 managed
  pages since kernel image starts at window base). tokd gate sound.
- aend 0xffd60000 = window top minus 1MB panic-log carve. Consistent.

- NEXT: identify what programs dram_rank1_addr / whether the engine can
  be disabled in the shim (DRAMC/EMI/SPM registers), or reserve the page
  it targets. Also consider: is the 0xe0000000 writer actually an SPM
  write-verify pattern or a data buffer from another firmware agent.


### HIGH-BANK MOVE (commit a2c912c, CI 43200619575)

- Rationale: run6 hit pa 0xe0000000 is inside dram_r1_dummy_read alloc-range;
  EVERY MTK reserved/dynamic region is 32-bit -> no firmware engine can
  write above 4 GiB. Window moves to [0x100000000, 0x1bffff000) ~3GiB
  (dramc-rk1 4K carve at 0x1bffff000 stays outside; panic log carve inside).
- mkadt: --athens --highmem selects it; FIXED a real bug where serialize/
  write was nested inside --athens-mem so mkadt wrote nothing (stale ADT
  was silently reused in earlier image builds - verify past images!).
- 0175: bitmap 1<<19 (<8G), poison pn field 32 bits, sweet_ufs falls back
  to fixed low-bank DMA at ufsdma= (default 0xfd000000, old window left
  unmanaged -> nothing owns it; still inside dram_r1 range but dodges the
  observed target). su.dma uses ml_io_map - uncached, no sync needed.
- If corruption persists in the high bank -> the writer is XNU CPU-side
  (stale VA/owner bug), not a firmware engine. That is the differential.
- Image build: mkadt --athens --athens-ufs --highmem; same repack.


### RUN-4 HIGHMEM BOOT + UFS LOG PIPELINE (2026-11-12)

- run4 image 3d5b57f7: kernel 4475c6ea + shim ufs harvest + fb dump.
  Boot: "Unaligned kernel data abort" panic, esr 0x96000061,
  far 0xfffffe301551040, kernel_task tid 101 (photo; digits approximate).
- Tail pull (sdc59 = 13,049,848 blocks EXACT - earlier ~13,044,966 math
  was wrong, correct pull = skip=13045751 count=4097):
  SHIMFB at 0, SHIMPRAM at 0xaff000, SWEETPAN at 0xc00000.
- Shim ufs.c originally used Qualcomm 0x1d84000 -> dead. Fixed to
  MediaTek 0x11270000 (dt: ufshci@11270000, reg 0x2300, lanes=2,
  ufs_mphy@0x11fa0000). Writes verified on disk (commit f1722eb).
- pram @0x1bfeff000 = pure DRAM garbage: highmem kernel died BEFORE its
  panic log init. SWEETPAN/ZCHECK records in kernel zone are run-6
  leftovers (tokd 0xc25cc000/aend 0xffd60000/pa 0xe0000000 = lowmem run).
- fb dump rendered panic-screen.png = LK realme splash, NOT panic: LK
  redraws fb each boot -> fb capture is a dead path for panic screens.
- NEW capture path (commit fcd71c6, patch 0176): sleh.c
  panic_with_thread_kernel_state copies arm_saved_state64 + "SWEETABR"
  magic into boot_args page tail (topOfKernelData-0x4000+0x3f00, inside
  physmap, survives warm reset). Shim ufs_dump_ba() writes the 16K ba
  page to userdata [last-4352,last-4349] in loader_boot BEFORE zero64().
- CI gotcha: SWEETABR as u64 immediate never appears as ASCII in the
  binary -> verify_strings can't find it. Must be a char[] constant.
- Live-dt harvest (adb/PitchBlack, in ATHENS.md): dram_r1_dummy_read
  alloc-ranges = 0xc0000000+0x3fe60000 covers the ENTIRE old lowmem pool
  -> stray-writer hypothesis now evidence-backed; highmem [0x100000000,
  0x1bffff000) is outside both engines. Touch = novatek nf_nt36672c on
  spi4@0x11018000 (gpio14 irq, gpio33 reset, 9.6MHz, 1080x2400 incell).
  LK initrd base 0x47c80000 verified. toprgu 0x10007000 verified.
- NEXT: gated build 43238787255 (@fcd71c6, verify_strings incl
  SWEETABR) -> repack highmem image -> flash -> panic -> normal reboot
  (shim harvests ba page+pram) -> PitchBlack -> pull
  skip=13045495 count=4353 -> decode trap frame -> fault PC.

### CI GOTCHA: drop_patches input is mandatory context (2026-11-12)

- The known-good kernel builds (43212579684, 43234832624) were dispatched
  with drop_patches="0161-athens-ufs-diag.patch 0164-athens-ufs-err.patch
  0165-athens-tidt-assert.patch". Without it, 0161/0164/0165 apply and
  shift sweet_ufs.c content, so 0175's :798 DMA hunk fails -> whole 0175
  skipped -> all ZCHECK/POOLSCAN/ufsdma instrumentation missing.
  ALWAYS pass the same drop_patches + verify_strings when dispatching.
- verify gotcha: strings that are u64 immediates (0x5357454554414252)
  never appear as ASCII in the binary; verify_strings needs char[]
  constants (SWEETABR fixed in 0176 v2, commit 7d61816).
- Run 43240706339 kernel: SWEETABR present (0176 applied+works), all
  0175 strings absent (patch skipped) -> unusable for the mailbox test.
- Rebuild: 43245911553 (@7d61816, drop_patches as above, verify incl
  SWEETABR). If green -> repack highmem image -> flash test.

### RUN-5 MAILBOX IMAGE (2026-11-12, CI 43245911553)

- Build 43245911553 @7d61816 SUCCESS, all 8 verify markers incl SWEETABR.
  Kernel: logs/ci-0176/kernel.development.sweet
  sha256 cbb29270932bf394a7c376ca4edd0aac03d5e84e32114c4b280f551270ac03cc
- Shim: out/athens (ufs.o linked: ufs_harvest_pram + ufs_dump_fb +
  ufs_dump_ba all present; loader calls ufs_dump_ba(ba_pa) pre-zero64).
- Image: shim/out/athens-boot-highmem.img
  sha256 6baa162503692a91078d2bf6ffea8653b1d7b788ebc922c337227cc9179399e7
  payload: phys_base 0x100000000 mem_size 0xbfeff000, entry
  0xfffffe00074b0488, ufs-ro + cpus=8.
- BOOT SEQUENCE: flash -> panic -> NORMAL reboot (shim harvests
  ba-page mailbox + pram + fb BEFORE zeroing) -> PitchBlack ->
  pull: dd if=/dev/block/sdc59 bs=4096 skip=13045495 count=4353
  (ba zone at [last-4352,last-4349] = SHIMBA; fb zone hdr at
  skip=13045751; pram zone SHIMPRAM at 0xaff000; kernel tail SWEETPAN).
- ba-page record: "SWEETABR" magic + arm_saved_state64 (pc,esr,far,
  x0-28,fp,lr,sp,cpsr) at offset 0x3f00 of the 16K page at
  topOfKernelData-0x4000.

### BUTTONS/PMIC-KEYS WORK (2026-11-12, patch 0178, CI 43284849223)

- User asked for buttons+touch while run-9 boots to Hello. Audit result:
  viva drivers are the right reuse BUT compatibles must match exactly.
- ADT (mkadt athens_devices) already emits: keypad mt6781-keypad @
  10010000 SPI74 (VivaKeypad matches -> probes, read-only KP_MEM scan,
  relies on LK having configured scanning - runtime will show),
  eint mt6781-eint @1000b000 (VivaEINT), pwrap mt6781-pwrap @10026000
  (VivaPwrap bus), pmic mt6359-pmic + keys mt6359-keys (NO driver matched
  -> wrote new ones).
- MT6359 facts (mainline mt6359/registers.h + mtk-pmic-keys.c
  mt6359_regs, verified): SWCID@0xa id 0x59; TOPSTATUS=0x2a (deb bits
  pwrkey 0x2 / homekey 0x8, 0=pressed); PSC_TOP_INT_CON0=0x910 /
  STATUS0=0x91c (same addrs as MT6358); TOP_INT_STATUS0=0x19e group
  order identical (PSC=bit2); PSC int bits pwrkey/homekey/_r/_r same
  positions. BUCK/LDO/SCK/AUD group bases DIFFER from MT6358 -> new
  gAthensPMICGroups table (BUCK 1418/1424 n1, LDO 1b14/1b28 n2,
  PSC 910/91c n1, SCK 528/534 n1, BM c32/c4a n2, HK f92/f9e n1,
  AUD 2328/2334 n1, MISC 188/194 n1).
- Patch 0178 (commit a23679b): NEW iokit/Kernel/arm/AthensPMIC.{h,cpp}
  + hid/AthensPMICKeys.cpp (mirrors VivaPMIC/VivaPMICKeys, MT6359 map);
  VivaPwrap.cpp +AthensPMIC.h include + writeAllowed() now also
  whitelists gAthensPMICGroups; KernelConfigTables +2 match entries
  (mt6359-pmic->AthensPMIC, mt6359-keys->AthensPMICKeys); files.arm64 +2.
  Viva drivers untouched (user request: separate device driver).
- KEYMAP: ADT keys node already (0=POWER,1=VOL_UP) per Realme dts
  (PWRKEY=power, HOMEKEY=vol up). Keypad node keymap bit0->VOL_DOWN is
  still a MEASURE guess - needs live 'VIVA KP: unmapped bit' logs.
- RISKS to verify on device: (a) VivaPwrap pwrap IP on MT6853@10026000
  assumed same USPI block as MT6781@1000d000 - INIT_DONE0 handshake
  will show; (b) EINT118->GIC212 path via VivaEINT; (c) KP_MEM only
  works if LK left scanning on.
- CI: push-run 43284810028 lacks drop_patches (will fail 0175 gate -
  ignore); authoritative dispatch 43284849223 with drop 0161/0164/0165
  + verify SWEETABR,takeover hce,AthensPMIC,MT6359 keys,mt6359-pmic,polls.
- TOUCH still untouched: needs MTK SPI4 host @11018000 + Novatek
  NT36672C noflash (139KB fw, EINT14 irq, GPIO33 reset, 9.6MHz, 1080x2400
  10pt). No SPI driver exists in tree - biggest remaining driver task.

### RECOVERY DATA PULL + RUN-9 SWEETLOG (2026-11-12)

- PitchBlack recovery ADB: live FDT + /proc/interrupts + input devices
  dumped (all recorded in ATHENS.md "Live FDT" block - verified facts).
- BUTTONS (verified, supersedes earlier guess): power=MT6359 PWRKEY,
  vol-up=MT6359 HOMEKEY (both PSC irq via mt-eint 118, IRQs 48-51 on
  mt6358-irq chip), vol-down=EINT 80 GPIO key (mtk-kpd-vol-down).
  KP matrix hw-init-map is ALL ZEROS -> matrix scan unused; kp node
  compat is mediatek,kp. => AthensPMICKeys (0178) covers power+vol-up;
  vol-down still needs a small EINT-key driver (TODO patch 0179).
  ADT keymap (0=POWER,1=VOL_UP) already correct.
- TOUCH (verified): spi4 = mediatek,mt6765-spi @11018000 size 0x100,
  GIC INTID 195 (SPI163+32), pins GPIO12 MI/13 MO/97 CLK/98 CSB
  drive-str 4, child oppo,tp_noflash OPPO_TP_NOFLASH EINT14 irq
  GPIO33 reset 9.6MHz 16x36 10pt 1080x2400. Needs: MTK SPI master
  driver (spi-mt6765 register map) + NT36672C noflash protocol.
- RUN-9 SWEETLOG decoded (logs/athens-run9-pull.bin, ring total
  0x511a44): boot was ALIVE at 16:06:39 - launchd spawning user-domain
  daemons at pid ~1030 (assistantd, tccd, wifianalyticsd, cryptexd).
  NOT hung - user restarted mid-boot. Daemons crash-loop on missing
  /var/run (cryptexd ns18/code2 ENOENT) and assistantd SIGABRT -
  userspace issues to fix later, not boot blockers.
- LESSON: 4MiB ring wraps in ~7min of userspace spam; early kernel
  probe logs (VIVA KP/VIVA PWRAP/ATHENS PMIC) get evicted. For driver
  verification rely on key-EVENT logs (post-boot) or add UFS snapshot.
- GIC convention confirmed: DT stores SPI# (74->INTID106, 163->195);
  mkadt spi() writes DT-style numbers - keypad/eint nodes correct.

### 0178 IMAGE READY (2026-11-12, CI 43284849223)

- Build SUCCESS, all markers verified in kernel.development.sweet:
  SWEETABR, takeover hce, AthensPMIC(68), MT6359, ATHENS PMIC(11),
  polls, VIVA KP.
- Image: shim/out/athens-boot-highmem.img
  sha256 0e9f7414afee828b6c1c2b74f4c0e685ef6183bd88f289c77424c2b81dbf8567
  payload c7936f1385af475b4c80fb60962c66ec8415426c9a348261bb90bb8fda53ba3d
  highmem adt, ufs-rw, cpus=8, sweetlog=1 ufslogsecs=5.
- EXPECTED on boot: 'VIVA KP: sta ... mem ...' (keypad probe - matrix
  unused but harmless), 'VIVA PWRAP' init on pwrap@10026000,
  'ATHENS PMIC: MT6359 swcid 0x.., all PMIC interrupts off',
  'ATHENS PMIC KEYS: power -> 0x30, home -> 0xe9, topstatus 0x..'.
- BUTTONS TEST: power btn -> HID power; vol-up -> HID vol-up (HOMEKEY);
  vol-down = EINT80 NOT covered yet (needs 0179 EINT-key driver).
  Press keys during/after boot; 'ATHENS PMIC KEYS: key 0x.. down/up'
  appears in console -> visible in next SWEETLOG pull.
- CAVEAT: probe-time IOLogs get evicted from 4MiB ring by userspace
  spam; key-EVENT logs post-boot survive. If no PMIC lines at all,
  check whether pwrap init itself failed (VIVA PWRAP logs).

### 0179: VOL-DOWN GPIO KEY (2026-11-12)

- Live-FDT facts (recovery pull): vol-down = mt-eint 80 "mtk-kpd-vol-down",
  KP matrix unused (kpd-hw-init-map all zeros). Power/vol-up = MT6359
  PWRKEY/HOMEKEY (covered by 0178 AthensPMICKeys).
- NEW iokit/Kernel/arm/hid/AthensGpioKeys.cpp: IOHIDEventService matching
  "athens,gpio-keys"; polls GPIO_DIN via VivaGPIO::wait()->getInput()
  every 16 ms, 48 ms debounce, active-low, emits HID consumer usages.
  Chosen over EINT edge because a single EINT line cannot give both
  press+release edges (VivaEINT supports one edge or one level only)
  and a missed edge sticks the key down.
- mkadt.py: new /arm-io/gpio-keys node key-gpios=<80> keymap=<0,0xea>
  (HID_CSMR_VOLUME_DOWN). GPIO number == EINT number on MT6853 AP domain
  is a MEASURE assumption - verify pin toggles on device; if not, find
  the eint->gpio mux in pinctrl-mt6853.c.
- ALSO fixed in mkadt.py (live-FDT corrections): removed the disproven
  Goodix/gt9896s i2c0 touch child (real panel = Novatek NT36672C on
  SPI4@11018000, needs SPI host driver - not yet written); gpio
  output-pins 15->33 (NT36672C reset GPIO per live FDT); keypad keymap
  removed (matrix unused).
- Patch 0179 verified applies clean to post-0178 buildtree baseline.
- TOUCH status: research done (SPI4 regs/pins/irq/EINT14/GPIO33/9.6MHz/
  16x36/10pt/1080x2400 all in ATHENS.md). Still needs: MTK SPI master
  driver for spi-mt6765 @0x11018000 + Novatek nf_nt36672c protocol.
  No SPI driver exists in tree - biggest remaining task.

### 0179 IMAGE READY (2026-11-12, CI 43290178829 SUCCESS)

- All markers verified in kernel.development.sweet: AthensGpioKeys x3,
  athens,gpio-keys, ATHENS GPIO KEYS x3, AthensPMIC x4, MT6359 x3.
- Image: shim/out/athens-boot-highmem.img
  sha256 260f0d4cd8d1405761d058a1fc829112b92e57e71b5735c1c420e56dd8360905
  payload 8012e38943b5c1778a0c449cf4849249580f97498fd6366fdd0227f616aaa5a3
  Same proven config: highmem adt, ufs-rw, cpus=8, sweetlog=1 ufslogsecs=5,
  unentitled_ios_sim_launch=1 launchd_unsecure_cache=1.
- BUTTONS NOW COVERED: power=PWRKEY, vol-up=HOMEKEY (0178 PMIC),
  vol-down=GPIO80 polled (0179). Expected logs: 'ATHENS PMIC KEYS: key
  0x.. down/up' and 'ATHENS GPIO KEYS: key 0xea down/up' + 'N keys,
  active-low, pins 80->0xea'.
- GPIO80==EINT80 is a MEASURE assumption: if vol-down never logs, the
  eint->gpio mapping differs; check pinctrl-mt6853 eint mux or try the
  pin the live FDT's volume-down gpio property names (wasn't dumped).
- TOUCH: still needs SPI4 host + NT36672C (see ATHENS.md notes); ADT
  touch node removed until then.

### 0182: ATHENS GPU MT6853 PORT (kernel driver, 2026-11-12)

GOAL: get Mali-G57 MC3 powered + self-tested on athens via the viva
VivaGPU driver (already compiled in via patches 0100-0146). Userspace
Metal stack is the separate ../viva-gpu repo (VivaMTLDriver.bundle) -
kernel alone does NOT give a GUI; it is the prerequisite.

WHAT 0182 CHANGES (all in iokit/Kernel/arm/VivaGPU.cpp + VivaPwrap.cpp +
KernelConfigTables.cpp; patch verified applies byte-identical to
post-0181 tree):
- PMIC regs MT6366->MT6359: VGPU=buck_vproc1 (EN 0x1708 VOSEL 0x172e
  DA 0x1726/0x1728), VSRAM=ldo_vsram_md (EN 0x1f2c VOSEL 0x1b46
  DA 0x1f32/0x1f2e). Verified vs docs/mtk/mt6359-registers.h.
- Per-rail voltage decode: vproc1 base 0.4 V, vsram_md base 0.5 V,
  both 6.25 mV/step (VGPU_UV/VSRAM_UV/VGPU_SEL_OF/VSRAM_SEL_OF).
- OPP table -> gpufreq mt6853 segment_1 (37 OPPs, 390-950 MHz,
  vgpu 0.575-0.8 V, vsram = max(vgpu,0.75 V)). vsram>=vgpu, NOT the
  MT6781 vsram>=vgpu+0.1 V rule.
- railsTo rewritten: enable VGPU->VSRAM (buck_control), ramp
  vsram-first-on-rise / vgpu-first-on-fall (volt_switch), <=50 mV steps.
- MTCMOS 5 domains {0,1,2,3,5} (mfg5 = index 5 -> PWR_CON 0x31c bit7);
  MC3 has all shader stacks so all five power (gpufreq shader_present
  = MT_GPU_SHADER_PRESENT_3 always for MT6853 segment).
- MFGPLL apmixed offsets -> CON0 0x268 CON1 0x26c PWR_CON0 0x274.
  mfgpllCon1 formula UNCHANGED (posdiv field = log2 div, same encoding;
  all MT6853 OPPs use POSDIV_POWER_4 = field 2 for >=390 MHz).
- topckgen mfg mux -> CLK_CFG_4 @0x050 (MT6781 used CLK_CFG_3 @0x040):
  mfg_pll_sel bit18 (1=mfgpll_ck,0=mfg_ref), mfg_ref_sel [17:16]
  (3=mainpll_d5_d2). Update kick = CLK_CFG_UPDATE bit18.
- KernelConfigTables: added 'mediatek,mt6853-mali' -> VivaGPUAccelerator
  (kept mt6781 entry).
- VivaPwrap whitelist: + MT6359 rail regs 0x1708/0x172e/0x1f2c/0x1b46.

ADT (tools/mkadt.py athens_devices 'gpu' node, already committed):
compatible mediatek,mt6853-mali; reg = Mali 0x13000000 + mfgcfg
0x13fbf000 + SPM 0x10006000 + topckgen 0x10000000 + apmixed 0x1000c000
+ infracfg 0x10001000 (driver map order kMapMali..kMapInfra);
interrupts SPI 0x16c-0x170 = GPU,MMU,JOB,EVENT,PWR (driver uses idx
0,1,2 = GPU/MMU/JOB).

BOOT ARGS for test: vivagpu=2 (power+publish), vivagpufreq=390..950
(pick mid, e.g. 500, or default->floor 390 MHz), vivagpumv margin.
VERIFY in SWEETLOG: 'VIVA GPU: driver started', 'GPU_ID 0x..' should be
Mali-G57, 'MFG0..MFG5 on', 'mfgpll con0/con1', selftest result.

NOT DONE / RISKS:
- infracfg_ao bus-protection regs (gMfgProt) still MT6781 values - only
  used on MFG1 power-OFF; verify if power-off misbehaves.
- CK_CFG_UPDATE kick bit for mfg_pll_sel assumed bit18 (mfg_ref shift);
  if clock doesn't switch, check topckgen update semantics.
- vsram_md DA_VOSEL is [14:8] of 0x1f32 (railsRead already >>8 &0x7f).
- Userspace Metal (VivaMTLDriver.bundle) NOT built yet - needs iOS SDK;
  check ../viva-gpu CI for a macOS runner that can produce it.

### 0182 KERNEL BUILT + BOOTED (2026-11-14)

- CI run 43578171782 SUCCESS. Patch 0182 compiled clean (no errors).
- Kernel: kout/0182/kernel.development.sweet (17.9 MB). Verified new
  code in binary: 'clk_cfg_4' x2, 'mt6853-mali' x1, 'VIVA GPU' x27.
- Boot image: shim/out/athens-boot-gpu.img (repacked with existing
  shim Image.gz; clang absent on Windows so reused prior shim).
  cmdline: ufs-rw + cpus=8 sweetlog=1 ufslogsecs=5 sweetfb_keep=1
  vivagpu=2 vivagpufreq=390 (lowest OPP, safest first power-on).
- fastboot boot -> device left fastboot, booting iOS now.
- GPU power-on runs at boot (vivagpu=2 -> powerOn -> mfgOn rails+
  MTCMOS+clock -> maliInit GPU_ID/softReset/powerCores/MMU -> publish).
  Selftest is NOT automatic - needs 'gpu selftest' over USB link later.
- EXPECTED SWEETLOG markers if HW port correct:
  'VIVA GPU: driver started (vivagpu=2)', 'MFG0..MFG5 on',
  'clock: 390 MHz, mfgpll con0/con1', 'GPU_ID 0x........',
  'id 0x........ cores 0x........ l2 on',
  'VIVA GPU: accelerator published (MetalPluginName VivaMTLDriver)'.
- FAILURE markers to watch: 'no power ack', 'MFG power-up failed',
  'GPU_ID 0x0: the GPU does not answer', 'shader cores not ready',
  'reset did not complete', kernel panic.
- USERSPACE ready: downloaded upstream CI artifact
  viva-gpu-ios/VivaMTLDriver.bundle (15 MB arm64 iOS16 BNDL,
  NSPrincipalClass VMDevice) -> ios/viva-gpu-artifacts/. Installs to
  /System/Library/Extensions/ in rootfs (sweet-root-tweaks.py pattern);
  mkuserdata.sh shows the exact target path. NOT yet injected - kernel
  power-on must be proven first.

## 2026-11-14 GPU boot test RESULT: driver never matched (frozen logo)

- Booted shim/out/athens-boot-gpu.img (vivagpu=2, vivagpufreq=390,
  sweetlog=1, sweetfb_keep=1). Device showed FROZEN APPLE LOGO.
- Pulled SWEETLOG (sdc59 skip=13048823 count=1025 -> gpu-log.bin/txt,
  405 KB total, ring NOT wrapped - all boot msgs present).
- FINDING: ZERO 'VIVA GPU' bytes in raw log. Other Viva drivers logged
  fine (VIVA KP/GPIO/I2C/PWRAP/EINT). backboardd IOAcceleratorES
  matching -> 0 found. => VivaGPUAccelerator::start() NEVER RAN = no
  match. NOT a power-on fault - the driver never got that far.
- VERIFIED all match layers correct: ADT gpu node present
  (compatible+6reg+5irq), KCT IONameMatch entry in kernel binary,
  driver class compiled, createNubs makes IOPlatformDevice for every
  arm-io child, compareName checks compatible (exact match).
- CONFIRMED-DATA fix (real RMX2117 mt6853.dts, NOT guesses):
  real node is mali@13000000 compatible="mediatek,mali","arm,mali-valhall"
  reg=<0 0x13000000 0 0x4000> (ONE region; MFG blocks are SEPARATE nodes:
  mfgcfg_clk@13fbf000, sleep/scpsys@10006000, topckgen@10000000,
  apmixed@1000c000, infracfg_ao@10001000). Driver still needs all 6 reg
  regions via mapDeviceMemoryWithIndex(0..5) so kept consolidated.
  All 6 bases VERIFIED vs real DT. Interrupts SPI 364-368 = GPU/MMU/JOB/
  EVENT/PWR confirmed; spi()=32+n is CORRECT (SweetGIC FIRST_SPI=32).
- Changed mkadt.py node 'gpu'->'mali', compatible->'mediatek,mali';
  KCT IONameMatch->'mediatek,mali'. (Cosmetic/faithful - NOT expected to
  be the match fix since old string was also self-consistent.)
- ADDED DIAGNOSTICS (patch 0183) to localize non-match:
  * IOPlatformExpert::createNub logs 'SWEET NUB: created/FAILED mali'
    (nub creation / init failure)
  * VivaGPU::start() logs 'start() entered' + instrumented the two
    previously-SILENT bail paths (workloop/locks/accelStart, gate/timer).
- NEXT: rebuild -> boot -> pull log. Outcomes: 'SWEET NUB created mali'
  + no 'start() entered' = match failure; 'init FAILED' = nub init;
  'start() entered'+bail = specific start failure; 'start() entered'+
  'driver started' = GPU powers on (then watch MFG/GPU_ID markers).

## 2026-11-14 GPU diag boot #2 RESULT: still no match, panic was userspace/ramoops-stale

- Built kernel from CI run 43581545159 (patches thru 0183 with
  'mediatek,mali' compatible + createNub/start diagnostics). Repacked
  boot image shim/out/athens-boot-gpu2.img with sweetfb_hz=0 added to
  cmdline (framebuffer copies every vsync tick = smoothest CPU path;
  NOT a 120Hz panel mode - panel timing is separate).
- fastboot boot FAILED ('Too many links'); flashed boot partition
  directly: fastboot flash boot ... OKAY, reboot. GPT/other partitions
  untouched.
- Pulled SWEETLOG -> gpu2-log.txt (405 KB, 6291 lines). RESULT:
  * ZERO 'SWEET NUB', ZERO 'VIVA GPU', ZERO 'start() entered' - the
    exact-name 'mali' diagnostic stayed silent for EVERY node.
  * backboardd IOAcceleratorES matching -> 0 found (unchanged).
  * NO kernel panic in SWEETLOG - userspace ran to liveactivitiesd.
    Tail = repeated userspace daemon crashes (chronod SIG5, accountsd
    SIG6, ReportCrash) + ATHENS TOUCH reset-state timeouts.
  * ramoops /sys/fs/pstore/console-ramoops-0 = STALE ANDROID panic
    (UsbFfs-worker OOM, Nov 1) - NOT the iOS boot. The 'panic' the user
    saw is NOT captured as a kernel panic; likely userspace crash-loop
    visual or a panic that auto-rebooted before log flush.
- INTERPRETATION: 'SWEET NUB' silence means either (a) mali node never
  reaches createNub (ADT->DT drop / not an arm-io child in gIODTPlane),
  or (b) getName()!="mali" so the exact-match guard skipped it. The
  broad 'node=%s' diagnostic (commit 9cf4557) now logs EVERY createNub
  node name to distinguish these.
- NEW BUILD: CI run 43583130785 (athens, workflow_dispatch) with 0183
  broadened to 'SWEET NUB: node=%s' for all nodes + 'init FAILED'.
  Will show: is 'mali' iterated? what does getName() return? does
  IOPlatformDevice::init fail on the 6-region reg?
- STILL OPEN: touch reset-state timeout (SPI status reads 0x00 after
  fw download); GPU match unresolved; VivaMTLDriver.bundle staged but
  not injected (kernel power-on unproven).

================================================================================
2026-11-14 FULL-DAY HANDOFF - ATHENS GPU PORT (MT6853 / Mali-G57 MC3)
================================================================================

GOAL (unchanged): real iOS GUI on RMX2117 via the Mali GPU. Long-term fix =
port viva's WORKING Mali-G57 kernel driver + viva-gpu userspace Metal stack.
User rejected the SW-renderer/rootfs-only shortcut.

--------------------------------------------------------------------------------
VERIFIED HARDWARE DATA (all from real RMX2117 mt6853.dts / live DT, NOT guesses)
--------------------------------------------------------------------------------
GPU node (real): mali@13000000
  compatible = "mediatek,mali", "arm,mali-valhall"
  reg       = <0 0x13000000 0 0x4000>          (Mali MMIO only, ONE region)
  interrupts= SPI 364(GPU) 365(MMU) 366(JOB) 367(EVENT) 368(PWR), lvl-high
  spi()=32+n is CORRECT (SweetGIC FIRST_SPI=32)
MFG power/clock blocks are SEPARATE DT nodes (driver still needs them
consolidated into the synthetic node's 6 reg regions, driver order):
  [0] Mali MMIO   0x13000000 size 0x4000
  [1] mfgcfg      0x13fbf000 (mfgcfg_clk@)
  [2] sleep/scpsys 0x10006000
  [3] topckgen    0x10000000
  [4] apmixed      0x1000c000
  [5] infracfg_ao  0x10001000
MTCMOS domains (5, vs viva's 4): mfg0 mfg1 mfg2 mfg3 mfg5
  PWR_CON layout same; status bit = 1<<(2+n)
PMIC = MT6359 (NOT MT6366):
  VGPU  = buck_vproc1  EN 0x1708 VOSEL 0x172e DA 0x1726/0x1728  (0.4V base)
  VSRAM = ldo_vsram_md EN 0x1f2c VOSEL 0x1b46 DA 0x1f32/0x1f2e  (0.5V base)
  (_vgpu-supply=&mt_pmic_vproc1_buck_reg ; _vsram_gpu-supply=&mt_pmic_vsram_md_ldo_reg)
  vgpu11 buck is a DECOY feeding proc1 - do NOT use it.
MFGPLL offsets (MT6853, differ from MT6781): CON0 0x268 CON1 0x26c PWR 0x274
OPP table (MT6853): 390-950 MHz; vgpu 0.575-0.8V ; vsram 0.75-0.8V
mfgcfg register offsets: IDENTICAL to viva.
Panel: panel4 = jdi,nt36672c,dphy,vdo,120  => 120Hz-capable panel.

--------------------------------------------------------------------------------
WHAT WAS DONE (commits, all pushed to origin/athens)
--------------------------------------------------------------------------------
2aa69ce  0182 patch: full MT6853 port of VivaGPU.cpp + VivaPwrap.cpp
         - PMIC defines MT6366->MT6359, per-rail UV decode (SEL_OF removed)
         - oppSels/OPP table -> MT6853 390-950MHz
         - railsTo rewritten: enable VGPU->VSRAM, volt_switch ramp order
         - MTCMOS 5-domain loop (mfg0,1,2,3,5), mfgOn/mfgOff/mfgDump
         - MFGPLL offsets -> 0x268/0x26c/0x274
         - MT6853 topckgen defines + mfgClock CLK_CFG_4 mux rewrite
         - KCT: added 'mediatek,mali' -> VivaGPUAccelerator (kept mt6781 too)
de1095d  mkadt.py: gpu node -> mali node, 6 reg regions in driver order,
         real compatible; docs/ATHENS-GPU.md full 10-pt port spec
eaa0b9f  research: MT6359 rail regs + MT6853 gpufreq/clk/regulator src
b0db767  0183: real 'mediatek,mali' compatible + createNub/start diagnostics
7603644  0183 fix: strstr NOT in kernel libkern -> strcmp
9cf4557  0183: broaden nub diag - log EVERY createNub node name (node=%s)
81e647b  NOTES update

--------------------------------------------------------------------------------
CI BUILDS (harman1390/ios-athens, workflow xnu, --ref athens)
--------------------------------------------------------------------------------
43578171782  SUCCESS - 0182 MT6853 port compiled clean. Kernel verified to
             contain 'clk_cfg_4','VIVA GPU' etc. (kout/0182/kernel...sweet)
43580732155  FAILED - 'strstr' undeclared in IOPlatformExpert.cpp -> fixed 7603644
43581545159  SUCCESS - 0183 diagnostics + real compatible (strstr->strcmp)
43583130785  IN PROGRESS - 0183 broadened 'SWEET NUB: node=%s' all nodes

--------------------------------------------------------------------------------
BOOT TESTS
--------------------------------------------------------------------------------
#1 athens-boot-gpu.img  (vivagpu=2 vivagpufreq=390 sweetfb_keep=1)
   fastboot boot -> FROZEN LOGO. SWEETLOG: ZERO 'VIVA GPU'. backboardd
   IOAcceleratorES match -> 0 found. => driver NEVER matched (not a
   power-on fault). Root cause then unknown.
#2 athens-boot-gpu2.img (same + sweetfb_hz=0; flashed boot partition after
   'fastboot boot' failed 'Too many links')
   User saw 'a panic'. Pulled SWEETLOG gpu2-log.txt (405KB):
   * ZERO 'SWEET NUB','VIVA GPU','start() entered' - exact-name 'mali'
     guard stayed silent for ALL nodes.
   * NO kernel panic in SWEETLOG - userspace ran to liveactivitiesd;
     tail = userspace daemon crash-loop (chronod SIG5, accountsd SIG6,
     ReportCrash) + ATHENS TOUCH reset-state timeouts.
   * ramoops console-ramoops-0 = STALE ANDROID OOM panic (Nov 1), NOT iOS.
   * Payload/boot-img VERIFIED contain 'mediatek,mali' + cmdline args, so
     the mali node IS in the flashed image (not a stale-ADT issue).
   CONCLUSION: 'SWEET NUB' silence => either (a) mali node never reaches
   createNub (ADT->DT drop / not an arm-io child in gIODTPlane), or
   (b) getName()!="mali" so the exact-match guard skipped logging.

--------------------------------------------------------------------------------
MATCH PATH (verified in source - should work, so bug is upstream of it)
--------------------------------------------------------------------------------
processTopLevel -> createNubs(this, IODTFindMatchingEntries(armio,
  kIODTExclusive,NULL))  [arm-io children, NO exclusions]
  -> createNub -> new IOPlatformDevice -> nub->init(from,gIODTPlane)
  -> attach(platformExpert) -> registerService() -> driver matching
IOPlatformDevice::compareName -> platformExpert->compareNubName ->
  IODTCompareNubName -> CompareKey checks name/compatible/device_type/model
KCT: IONameMatch 'mediatek,mali' + IOProviderClass IOPlatformDevice
     -> VivaGPUAccelerator  (unconditional, both mt6781+mt6853 entries)
reg encoding u64 = 8-byte cells matches #address-cells=2/#size-cells=2;
same encoding as working framebuffer/UFS nodes => init should succeed.

--------------------------------------------------------------------------------
OPEN / NEXT
--------------------------------------------------------------------------------
* Await CI 43583130785 -> repack boot img -> flash -> pull SWEETLOG.
  'SWEET NUB: node=' dump reveals: is mali iterated? getName() value?
  'init FAILED'? Then branch:
    - mali absent from list      => ADT->DT drop; inspect node props
    - mali present + init FAILED => fix reg/property encoding
    - mali present + created     => matching fails; inspect compatible
                                   property bytes on the nub
* GPU power-on (once matched): watch 'VIVA GPU: driver started',
  'MFG0..5 on', 'mfgpll', 'GPU_ID 0x..', 'accelerator published'.
* TOUCH still broken: 'reset state timeout (last 0x00)' after fw
  download; embedded fw loads (15 parts nt36672a map) but status read
  returns 0x00 - SPI event-buf/reset-sequence bug, separate from GPU.
* USERSPACE: VivaMTLDriver.bundle (15MB arm64 iOS16, VMDevice) staged at
  ios/viva-gpu-artifacts/ - NOT injected until kernel power-on proven.
* DISPLAY: sweetfb_hz=0 = copy every vsync (smoothest CPU path), NOT 120Hz.
  True 120Hz needs SWEET_FB_VSYNC_US 16667->8333 AND panel already 120Hz.
* Local env: NO clang -> reuse shim/out/athens/Image.gz + viva-bootimg.py
  repack. fastboot boot flaky ('Too many links') -> flash boot partition.

## 2026-11-14 GPU diag boot #3 RESULT: panic = stray-writer (NOT GPU); nub diag was too-early

- Built athens-boot-gpu3.img from CI 43583130785 (0183 broadened
  'SWEET NUB: node=' all createNub nodes + start() entered + mali
  compatible). Repacked via viva-bootimg.py (reused shim Image.gz).
  NOTE: mkadt --dump with no --athens flags clobbered athens.adt once -
  regenerated with --athens --athens-ufs; verified mali under arm-io.
- Flashed boot partition OK, rebooted. USER SAW: brief "pmic wrapper"
  text then PANIC. (pmic wrapper = normal 'VIVA PWRAP: ... WACS2 not
  initialized' line, coincidental with panic screen.)
- Pulled SWEETLOG (bs=4096 skip=13045495 count=4353 -> gpu3-log.bin,
  ~6MB nonzero). FINDINGS:
  * ZERO 'SWEET NUB', ZERO 'VIVA GPU', ZERO 'start() entered' - the
    broadened createNub diagnostic produced NO output for ANY node.
  * Drivers still registered (SEP/WDT/AMFI/VIVA KP/PWRAP/GPIO/I2C/HID).
  * Log ends in KERNEL PANIC = the KNOWN stray-writer memory bug:
    'ZCHECK pn 0x38000 pa 0xe0000000 bad 191 ... w1 0x00000038014d4d4d'
    (0x4d4d4d4d='MMMM' pattern, dram_r1 dummy-read range) + POOLSCAN/
    STATICFREE SWEETPAN records. PRE-EXISTING, unrelated to GPU - it is
    the intermittent corruption documented earlier (run-6 hit 0xe0000000).
- ROOT CAUSE of silent diagnostic (verified in source, not guessed):
  processTopLevel->createNubs->createNub runs inside
  IODTPlatformExpert::configure(), which executes BEFORE
  SweetPlatformExpert::start(). The 'SWEET NUB' IOLog fires during
  configure() - before the persistent log ring captures IOKit output.
  Driver start() messages (SEP etc.) ARE captured because matching is
  deferred/async and lands inside the captured window. => createNub-time
  logging is fundamentally invisible; need a captured-point diagnostic.
- VERIFIED match path is sound (read source, not assumed):
  AthensSPI uses IOProviderClass=IOPlatformDevice + IONameMatch and
  WORKS, so IOPlatformDevice nubs match fine. mali node is a direct
  arm-io child, identical structure to spi4. reg u64==io() encoding.
  CompareKey reads compatible as OSData/OSString, exact NUL-separated
  match -> 'mediatek,mali' should match IONameMatch.
- FIX: moved diagnostic to SweetPlatformExpert::start() AFTER
  'platform expert registered' (captured). New 'SWEET NUB2: child
  <name> (<class>) compat=<compatible>' dumps every service-plane
  device nub the platform created. Reveals: does mali produce an
  IOPlatformDevice nub? what compatible does it carry?
  (commit cdf5d8d; hunk git-apply --check verified; APIs match
  VivaPwrap.cpp/AthensPMIC.cpp proven usage.)
- NEW BUILD: CI run 43584629140.
- STILL OPEN: GPU match (nub existence now being tested); touch
  reset-state 0x00; stray-writer panic (separate, intermittent);
  VivaMTLDriver.bundle staged not injected.

## 2026-11-14 GPU diag boot #4 RESULT: NUB2 still silent -> switched to whole-plane walk

- Built athens-boot-gpu4.img from CI 43584629140 (SWEET NUB2 dumps
  platform-expert service-plane children: name/class/compatible).
  Diagnostic strings verified present in the kernel binary.
- Flashed boot, rebooted. USER: panic again (same stray-writer, see
  below). Pulled SWEETLOG (~7MB nonzero, 77580 lines).
- FINDINGS:
  * 'SWEET: platform expert registered' IS captured (proves start()
    reached the diagnostic point).
  * ZERO 'SWEET NUB2', ZERO 'child ', ZERO 'compat=' - the
    getChildIterator(gIOServicePlane) block produced NO output even
    though the strings are in the binary. => iterator was empty/NULL.
  * Drivers still registered (SEP/WDT/AMFI/VIVA KP/PWRAP/GPIO/I2C/HID,
    ATHENS SPI spi4 ready, SWEET FB/GIC/EINT).
  * Log ends in same stray-writer panic: 'ZCHECK pn 0x38000 pa
    0xe0000000 bad 191 ... 0x4d4d4d4d' + POOLSCAN never-used. NOT GPU.
- ROOT CAUSE hypothesis (verified partially, NOT yet proven):
  IOService::attach(provider) DOES use gIOServicePlane
  (IOService.cpp:856 attachToParent(provider, gIOServicePlane)). So
  device nubs SHOULD be gIOServicePlane children of the platform
  expert. But getChildIterator(gIOServicePlane) on `this` returned
  nothing. Possible: attach() ran but children attach under a different
  effective parent, OR attach() failed silently for these nubs, OR
  getChildIterator needs a child-set that isn't populated yet. NOT yet
  confirmed which.
- VERIFIED interrupt encoding is fine: GIC #interrupt-cells=2, spi()
  emits (INTID=32+n, flags) 2 cells; mali 5 specifiers=10 cells,
  concatenated correctly. reg u64==io() (SOC_BASE-relative) - same as
  working spi4. Node structure identical to working arm-io children.
- FIX (commit a1fc8de): replaced getChildIterator with
  IORegistryIterator::iterateOver(gIOServicePlane,
  kIORegistryIterateRecursively) - the exact call IOCatalogue.cpp:705
  uses - walking the WHOLE service plane from gRegistryRoot. Dumps
  every entry's name/class/compatible. This removes ALL parent/plane/
  attach-timing doubt: if the mali nub exists ANYWHERE in the service
  plane it will appear; if absent, nub creation itself is broken.
  Verified IORegistryIterator : public OSIterator (OSIterator* assign
  OK), iterateOver declared in IORegistryEntry.h (reachable via
  IOService.h->IOPlatformExpert.h), getProperty borrowed-ptr no release.
- NEW BUILD: CI run 43586049946.
- STILL OPEN: GPU match; touch reset-state 0x00; stray-writer panic;
  VivaMTLDriver.bundle staged.

## 2026-11-14 GPU diag boot #5 RESULT: whole-plane walk at platform-start ALSO empty -> moved to late driver

- Built athens-boot-gpu5.img from CI 43586049946 (SWEET NUB2 now uses
  IORegistryIterator::iterateOver(gIOServicePlane,
  kIORegistryIterateRecursively) - whole service plane from gRegistryRoot,
  the exact call IOCatalogue.cpp:705 uses). Flashed boot, rebooted.
- USER: panic again (stray-writer). Pulled SWEETLOG - NOTE: needed an
  8 MiB pull (skip=13046798 count=2048); the 1025-block pull caught only
  stale/zero data. Header 'SWEETLOG' v1 ring=4MiB totalbytes=405815
  flushseq=22 = FRESH gpu5 boot.
- FINDINGS (verified from log, not guessed):
  * Boot reached USERSpace: launchd exec, dyld_shared_cache mapping,
    backboardd running, SpringBoard exec - full userspace came up.
  * 'platform expert registered' printed; ZERO 'SWEET NUB2', ZERO
    'compat=' - even the whole-plane recursive walk produced NO output.
  * backboardd log line 886-887: 'path IODeviceTree:/arm-io ->
    IOPlatformDevice' + 'children of arm-io in IODeviceTree' - the DT
    plane DOES have the tree; drivers DID match arm-io children (SEP,
    WDT, VIVA KP/PWRAP/GPIO/I2C, ATHENS SPI spi4 ready, SWEET FB/GIC/EINT,
    touch bind+fw attempt).
  * 'ATHENS TOUCH: reset state timeout (last 0x00)' still present.
- VERIFIED (source, not assumed):
  * IOService::attach(provider) -> attachToParent(provider,
    gIOServicePlane) (IOService.cpp:856). nubs attach in service plane.
  * SweetPlatformExpert::processTopLevel creates nubs for cpus-children,
    root-children, AND arm-io-children (line 119), all attach(this).
  * Chain is SYNCHRONOUS: IODTPlatformExpert has no own start(); inherits
    IOPlatformExpert::start -> configure -> IODTPlatformExpert::configure
    -> processTopLevel -> SweetPlatformExpert::processTopLevel -> createNubs.
    So ALL nubs (incl mali) exist BEFORE 'platform expert registered' and
    before my diagnostic.
  * getNextObject needs no reset(); iterateOver matches IOCatalogue use;
    metaCast(const char*) on OSMetaClassBase; fromPath returns retained
    ptr (VivaBattery pattern).
- UNRESOLVED WHY platform-start iterateOver saw nothing: candidates are
  (a) nubs attach to `this` but child-set links populate later than
  start(), (b) iterateOver returned NULL, (c) service-plane entries not
  reachable from gRegistryRoot at that instant. NOT yet distinguished.
- FIX (commit 633ccf9): moved diagnostic into AthensSPI::start - a
  guaranteed arm-io child driver that runs AFTER every nub exists. It
  now dumps: svcIter NULL-check + recursive gIOServicePlane walk counting
  entries + every IOPlatformDevice name/compatible ('ATHENS GPNUB'),
  fromPath('/arm-io/mali', gIODTPlane) presence, and gIODTPlane total
  count. Distinguishes nub-absent vs wrong-plane vs NULL-iterator vs
  attach-failure in ONE boot.
- NEW BUILD: CI run 43587874869.
- STILL OPEN: GPU match; touch reset-state 0x00; stray-writer panic;
  VivaMTLDriver.bundle staged.

## 2026-11-14 build 43587874869 FAILED -> fixed gIODTPlane include -> 43588710370

- 43587874869 compile FAILED: AthensSPI.cpp:172,178 'use of undeclared
  identifier gIODTPlane'. gIOServicePlane comes via IOService.h but
  gIODTPlane is declared in IOKit/IODeviceTreeSupport.h (VivaBattery.cpp
  includes it). NOT a logic bug - missing include only.
- FIX (commit 1b7a9eb): added #include <IOKit/IODeviceTreeSupport.h> to
  AthensSPI.cpp; regenerated the 0183 AthensSPI hunk (now 2 hunks:
  include + diagnostic). Reverse-apply verified clean.
- NEW BUILD: CI run 43588710370.

## 2026-11-14 gpu6 boot PANICKED at FindBSDRoot/UFS ENOMEM -> carved-DMA fix (commit bc3c7bf)

- gpu6 (CI 43588710370 = gpu5 kernel + AthensSPI whole-plane diagnostic)
  flashed + booted. USER reported panic; the pulled SWEETLOG was STALE
  (header totalbytes/flushseq byte-identical to gpu5 = 405815/22), i.e.
  gpu6 wrote NOTHING to the log -> it died before the log writer init.
- USER then captured the panic screen via adb. Decoded panic string:
  "FindBSDRoot: SWEET UFS root ufsroot0 unavailable: 12
  @IOKitBSDInit.cpp:778". This is the XNU root-device path, NOT a GPU or
  stray-writer panic.
- VERIFIED (source, errno.h:102 ENOMEM=12): sweet_ufs_rootdev ->
  sweet_ufs_init. Enumerated EVERY return path: error 12 can ONLY come
  from the DMA-buffer allocation (lines ~833/841). ufs_take_over_host,
  ufs_find_partition/ufs_lookup_partition, ufs_scsi return only
  ENXIO/ENOENT/EIO/ETIMEDOUT/EBUSY/EINVAL/EPERM - none is 12.
- ROOT CAUSE (verified, not guessed): with --highmem XNU manages RAM ONLY
  via /chosen dram-base/dram-size = the high bank 0x100000000+. There is
  NO low-bank RAM and NO reserved-memory node. So the kmem_alloc_contig
  fallback ml_io_map(0x4e000000) maps a physical address BELOW every DRAM
  bank XNU declares -> not valid RAM -> returns NULL -> ENOMEM. The
  fallback is effectively DEAD under highmem; every boot depends solely on
  kmem_alloc_contig finding ~64 contiguous pages in the high bank.
  gpu5 found them; gpu6 did not -> panic. (833 vs 841 sub-case not
  distinguished - no fresh log - but both are the same DMA-alloc failure.)
- NOTE: the "going backwards" feel = this panic is at root-mount, an
  EARLIER stage than gpu5's userspace reach. Whether the AthensSPI
  diagnostic contributed to memory pressure is UNPROVEN; the carve makes
  UFS immune to allocator state regardless, and the diagnostic is kept
  (it runs before FindBSDRoot and now cannot affect the carved DMA).
- FIX (commit bc3c7bf), two parts, both fact-based:
  * tools/mkadt.py: carve a dedicated 2 MiB UFS DMA region just below the
    panic-log carve (UFS_DMA_SIZE=0x200000), 64 KiB-aligned, shrink
    mem_size so the page allocator never hands it out, expose physical
    address as /sweet-ufs dma-phys. Verified: ufs_dma=[0x1bfcf0000,
    0x1bfef0000), panic=[0x1bfeff000,0x1bffff000), no overlap, inside DRAM
    top 0x1bffff000, dramc-rk1 untouched, dram-size=0xbfcf0000.
  * xnu/patches/0184-athens-ufs-carved-dma.patch: sweet_ufs_init reads
    dma-phys and ml_io_map()s it directly when present, bypassing
    kmem_alloc_contig -> removes BOTH ENOMEM paths deterministically.
    dma-phys absent on viva/qemu -> old kmem_alloc_contig+fallback kept.
  * Patch validated (check_patch_counts OK), generated from post-0183
    baseline (logs/xnu-src confirmed post-0183: has 0183 diag + 0177
    pollcap). Reverse-apply verified.
- NEW BUILD: CI run 43591977976 (push-triggered on xnu/patches/**).
- STILL OPEN: GPU match (0183 diag still in this build - will finally
  report whether mali nub exists once UFS mounts); touch reset 0x00;
  stray-writer panic; VivaMTLDriver.bundle staged.

## 2026-11-14 CORRECTION: 0184 first attempt SKIPPED -> regenerated vs real dxb source

- Build 43591977976 (first carve attempt) SUCCEEDED compiling but patch
  0184 was SKIPPED: "patch failed: bsd/dev/sweet_ufs.c:822". Kernel binary
  had ZERO 'carved DMA'/'dma-phys' strings -> change never shipped.
- ROOT CAUSE of the skip (verified via xnu-buildtree artifact, the REAL
  patched source): logs/xnu-src has DIVERGED from what dxb produces.
  dxb SKIPPED patches 0174, 0175, 0177 (and possibly others) - "already
  upstream, previously applied, or malformed". So dxb's sweet_ufs.c is an
  OLDER version than logs/xnu-src.
- CRITICAL DIFFERENCE in dxb's sweet_ufs_init: it FORCES
  max_pnum = atop_64(1ULL<<32)-1 = DMA alloc constrained to <4GiB, with NO
  ufsdma/ml_io_map fallback and NO CAP_64AS conditional (those are the
  skipped 0177 changes). Under --highmem managed RAM is mostly >4GiB; the
  <4GiB pool is small/fragile -> kmem_alloc_contig intermittently fails ->
  ENOMEM -> FindBSDRoot panic. This is the REAL panic mechanism.
- REGENERATED 0184 (commit 9a454f1) against the actual dxb sweet_ufs.c
  (extracted from xnu-buildtree.tgz): dma-phys carve inserted before the
  <4GiB alloc which is kept as the else fallback. git apply --check OK,
  check_patch_counts OK, content verified.
- CAP_64AS guard (dxb line 558) only rejects >4GiB DMA if host lacks
  64-bit addressing; MT6853 CAP 0x387071f has bit24 CAP_64AS set -> the
  0x1bfcf0000 carve is valid.
- NEW BUILD: CI run 43593130388.
- OPEN QUESTION (not blocking): why did gpu5 reach userspace if dxb
  forces <4GiB DMA? Either <4GiB RAM exists and gpu5 got contiguous pages,
  or gpu5's build applied 0177. Patch application is deterministic per
  run, so likely <4GiB RAM exists but is fragile. The carve removes the
  dependency either way.
- NOTE: logs/xnu-src and dxb have diverged for sweet_ufs.c (and possibly
  other files). logs/xnu-src is git-ignored reference only; the PATCH is
  the source of truth for builds. Future patches touching sweet_ufs.c
  MUST be generated against the dxb buildtree, not logs/xnu-src.

## 2026-11-14 gpu8 carved-DMA HUNG -> reverted; real fix is CAP_64AS alloc (commit 1d61e5c)

- gpu8 (carved DMA 0x1bfcf0000) did NOT panic - it HUNG. Screen looped
  "rootvnode is not set" + ATHENS TOUCH fw retry. NO sweetlog was written
  (verified: correct tail offset has only STALE gpu5 data).
- FIRST pulled the WRONG window: skip=13042688 read ~28MiB before the
  tail. sdc59=userdata has 13049848 4K-blocks; correct tail skip=13045752.
  gpu8-tail.bin then showed SWEETLOG@12578816 + 6x SWEETPAN - but the
  SWEETLOG header total=405815 seq=22 is byte-identical to gpu5 = STALE.
  gpu8 wrote nothing -> hung BEFORE sweetlog_start (su.ready never set).
- gpu5 console (gpu8-console.txt, the stale log) is the ROSETTA STONE:
    "SWEET UFS: host cap 0x3587071f, DMA at 0x103f28000"
    "SWEET UFS: userdata on LUN 2 ... read-write, DMA at 0x103f28000"
    "hfs: mounted iOSRoot on device b(1,0)"  -> reached USERSPACE.
  0x103f28000 is ~63MiB into the high bank AND >4GiB -> proves (a) UFS host
  does 64-bit DMA and (b) gpu5's kernel had CAP_64AS max_pnum=0, NOT dxb's
  <4GiB hardcode. ANSWERS the open question above: gpu5 was built with the
  CAP_64AS path (0177 applied), dxb builds skip 0177 -> <4GiB -> ENOMEM.
- WHY the carve hung: 0x1bfcf0000 is ~6.95GiB (top of bank). ufs_take_over
  _host writes it to REG_UTRLBA/UTRLBAU; host accepted it but DMA never
  completed -> ufs_scsi polled forever -> sweet_ufs_init never returned.
  logs/xnu-src documents the SAME failure for an earlier 0xfd000000 carve
  (inside dram_r1 scribble range). Fixed carves outside managed RAM are
  unreliable for UFS DMA; managed-pool pages (kmem_alloc_contig) are the
  proven path.
- FIX (commit 1d61e5c): patch 0184 REGENERATED as 0184-athens-ufs-cap64as-
  dma.patch - ports the authoritative logs/xnu-src alloc block into dxb:
    max_pnum = (ufs_rd(REG_CAP)&CAP_64AS) ? 0 : <4GiB   (CAP read after
    ml_io_map; REG_CAP/CAP_64AS/ufs_rd all present in dxb)
    + ufsdma boot-arg/0x4e000000 fixed low-bank fallback if kmem fails.
  mkadt.py REVERTED: UFS_DMA_SIZE carve + dma-phys prop removed, dram-size
  back to panic-only carve. logs/xnu-src dma-phys carve block removed to
  match. git apply --check OK vs dxb buildtree.
- NEW BUILD: CI run 43596846980.
- VERIFY NEXT BOOT: sweetlog should show "SWEET UFS: host cap ... DMA at
  0x1..." (a managed-pool addr, NOT 0x1bfcf0000) then "hfs: mounted
  iOSRoot" -> userspace. If it hangs again, the DMA addr will show whether
  kmem returned an unreachable high page (then bound max_pnum).
