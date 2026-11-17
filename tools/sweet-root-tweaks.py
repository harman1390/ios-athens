#!/usr/bin/env python3
"""Apply the SWEET bring-up changes to an iOS root made by tools/mkiosroot.sh.

  sudo sweet-root-tweaks.py MOUNTED_ROOT

MOUNTED_ROOT is the HFS+ image mounted read-write (Linux: run
`fsck.hfsplus -fy` on the image, then `mount -t hfsplus -o loop,force`).
Run as root (it writes root/mobile owned files). Idempotent. This is what
turned the plain mkiosroot.sh output into the images that reach the home
screen (image versions v8-v14 in NOTES.md):

  launchd.plist   _PanicOnCrash -> _PanicOnCrasX (a crashing daemon must not
                  panic the system); CommCenter jobs removed (no baseband: it
                  crash-loops and Setup blocks on its CoreTelephony XPC)
  containers      /private/var/containers/{Bundle,Data/System,Shared/SystemGroup,Temp}
                  (on iOS they live on the data volume)
  migration       LastSystemVersion so DataMigration does not run for an hour
                  on every boot
  audio           VirtualAudio HAL plug-in disabled (mediaserverd crash)
  MediaToolbox    StartRecorderServer=false (camera filter prewarm calls a
                  NULL OpenGL function without a GPU -> mediaserverd crash loop)
  SpringBoard     BKNoWatchdogs (one slow CPU path, no scene-create watchdog
                  kills), no cloud-configuration UI
  Setup           skipped: SetupDone, SetupFinishedAllSteps, SetupVersion 11,
                  mini-buddy flags off
  activation      mobileactivationd data ark seeded; the actual Activated state
                  comes from its Hactivation branch, selected by the /chosen
                  security-status properties in tools/mkadt.py
"""
import glob, os, plistlib, shutil, sys

BUILD, VERSION = '20H392', '16.7.16'
MOBILE = 501


def load(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def save(path, data, uid, gid, mode, fmt=plistlib.FMT_BINARY):
    with open(path, 'wb') as f:
        plistlib.dump(data, f, fmt=fmt)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def merge_pref(root, name, values):
    """Merge keys into /var/mobile/Library/Preferences/NAME.plist (mobile, 0600)."""
    path = os.path.join(root, 'private/var/mobile/Library/Preferences', name + '.plist')
    data = load(path) if os.path.exists(path) else {}
    data.update(values)
    save(path, data, MOBILE, MOBILE, 0o600)
    print('pref', name, sorted(values))


def launchd(root):
    path = os.path.join(root, 'System/Library/xpc/launchd.plist')
    st = os.stat(path)
    plist = load(path)
    jobs = plist['LaunchDaemons']
    renamed = 0
    for job in jobs.values():
        if '_PanicOnCrash' in job:
            job['_PanicOnCrasX'] = job.pop('_PanicOnCrash')
            renamed += 1
    # daemons that cannot run on this port (no baseband, no SEP) and crash hard
    # enough to panic boot; drop them like CommCenter.
    drop_labels = {
        'com.apple.CommCenter',
        'com.apple.sepul',
        'com.apple.seputil',
    }
    removed = [k for k, j in jobs.items() if j.get('Label') in drop_labels]
    for k in removed:
        del jobs[k]
    # dump every job label so we can see the real names of SEP/security tasks
    # without needing the plist extracted from the device image.
    for k in sorted(jobs):
        j = jobs[k]
        print('launchd job:', j.get('Label'), '|', k,
              '| MandatoryService' if isinstance(j, dict) and j.get('MandatoryService') else '')
    save(path, plist, st.st_uid, st.st_gid, st.st_mode & 0o7777)
    print(f'launchd.plist: {renamed} _PanicOnCrash renamed, {len(removed)} jobs removed')


def containers(root):
    base = os.path.join(root, 'private/var/containers')
    for sub, uid in (('Bundle', 33), ('Data/System', 0), ('Shared/SystemGroup', 0), ('Temp', 0)):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            os.makedirs(d)
            os.chown(d, uid, uid)
            os.chmod(d, 0o755)
            print('mkdir', d)


def find_container(root, kind, identifier):
    for meta in glob.glob(os.path.join(root, 'private/var/containers', kind, '*',
                                       '.com.apple.mobile_container_manager.metadata.plist')):
        if load(meta).get('MCMMetadataIdentifier') == identifier:
            return os.path.dirname(meta)
    return None


def vardirs(root):
    """Runtime dirs that live on the data volume on real iOS. Our single
    HFS root has no separate data volume, so without these every service
    whose plist sets WorkingDirectory to /tmp, /var/run, /var/mobile/
    Library/Caches etc. fails to initialize (ENOENT -> launchd exit 78
    respawn storm; seen on athens run-10)."""
    for rel, uid, gid, mode in (
            ('private/var/tmp', 0, 0, 0o1777),
            ('private/var/run', 0, 0, 0o755),
            ('private/var/empty', 0, 0, 0o555),
            ('private/var/select', 0, 0, 0o755),
            ('private/var/root', 0, 0, 0o700),
            ('private/var/audit', 0, 0, 0o755),
            ('private/var/networkd', 0, 0, 0o755),
            ('private/var/preferences', 0, 0, 0o755),
            ('private/var/vm', 0, 0, 0o755),
            ('private/var/wireless', 0, 0, 0o755),
            ('private/var/logs', 272, 272, 0o755),
            ('private/var/MobileSoftwareUpdate', 0, 0, 0o755),
            ('private/var/Managed Preferences', 0, 0, 0o755),
            ('private/var/MobileDevice', 0, 0, 0o755),
            ('private/var/lockdownd', 0, 0, 0o755),
            ('private/var/log/com.apple.xpc.launchd', 0, 0, 0o755),
            # data-volume dirs the daemon crash storm needs (gpu19 diag:
            # NSTemporaryDirectory -> /var/folders/.../T and keychain ->
            # /Library/Keychains -> /private/var/Keychains both EIO when the
            # parent is absent). folders/Keychains were missing entirely.
            ('private/var/folders', 0, 0, 0o755),
            ('private/var/Keychains', 0, 0, 0o755),
            ('private/var/db/diagnostics', 272, 272, 0o751),
            ('private/var/db/uuidtext', 272, 272, 0o755),
            ('private/var/db/diagnostics/timesync', 272, 272, 0o755),
            ('private/var/MobileActivation', 0, 0, 0o755),
            ('private/var/itunesstored', 0, 0, 0o755),
            ('private/var/MobileGestalt', 0, 0, 0o755),
            ('private/var/backups', 0, 0, 0o755),
            ('private/var/local', 0, 0, 0o755),
            ('private/var/lib', 0, 0, 0o755),
            ('private/var/mobile/Library/Caches', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/Cookies', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/Logs', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/WebKit', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/SyncedPreferences', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/Favorites', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/mad', MOBILE, MOBILE, 0o755),
            ('private/var/mobile/Library/Keychains', MOBILE, MOBILE, 0o755)):
        d = os.path.join(root, rel)
        if not os.path.isdir(d):
            os.makedirs(d)
            os.chown(d, uid, gid)
            os.chmod(d, mode)
            print('vardir', rel)
        elif mode & 0o1000 and os.stat(d).st_mode & 0o7777 != mode:
            os.chmod(d, mode)
            print('vardir mode', rel, oct(mode))


def mobileactivationd_patch(root):
    """Stop mobileactivationd crash-looping on activation-data migration.

    main() runs the com.apple.MobileActivationMigrator migration once,
    synchronously, before it brings up its NSXPC listener. On this port the
    sydro migration cannot complete (keychain / data-volume state the single
    HFS root does not have), so the failure branch logs "Migration failed."
    and hits __os_crash -> brk #0x1. The daemon respawned ~460x/boot and
    SpringBoard's synchronous activation XPC (getActivationState) never got
    an answer -> Apple logo.

    Two sites reach the crash thunk, both guarded by `tbz w19,#0,<crash>`:
      * sync path   0x100050470 -> loc_100050668 -> 0x1001bf35c
      * async block 0x100050718 -> loc_100050730 -> 0x1001bf6a0
    NOP-ing the tbz makes migration failure fall through to the same
    success tail as migration success (the error object is simply retained
    and ignored), so the listener comes up either way. Verified these are
    the ONLY two BL call sites to the two MigrationFailed thunks in the
    20H392 build (xref scan of __text). Idempotent: only writes when the
    expected tbz encoding is present."""
    path = os.path.join(root, 'usr/libexec/mobileactivationd')
    NOP = b'\x1f\x20\x03\xd5'
    sites = {0x50470: b'\xd3\x0f\x00\x36',   # tbz w19,#0 -> MigrationFailed-main
             0x50718: b'\xd3\x00\x00\x36'}   # tbz w19,#0 -> MigrationFailed-block
    try:
        with open(path, 'r+b') as f:
            data = f.read()
            if data[:4] != b'\xcf\xfa\xed\xfe':
                print('mobileactivationd: not a Mach-O, skipped')
                return
            patched = False
            for off, expect in sites.items():
                cur = data[off:off + 4]
                if cur == NOP:
                    continue                      # already patched
                if cur != expect:
                    print('mobileactivationd: unexpected bytes at %#x (%s), skipped'
                          % (off, cur.hex()))
                    return
                f.seek(off)
                f.write(NOP)
                patched = True
            if patched:
                print('mobileactivationd: migration-fail crash branches NOP-ed')
    except FileNotFoundError:
        print('mobileactivationd: not present, skipped')


def installd_dirs(root):
    """MCM codesign-mapping DB home. containermanagerd opens its SQLite DB
    under /private/var/installd/Library/Caches/com.apple.containermanagerd
    (ContainerManagerCommon MCMSQLiteDB openDBWithURL). On the single HFS
    root that whole /private/var/installd tree is absent (it lives on the
    data volume on real iOS), so openDBWithURL fails -> MCM's
    fixAndRetryIfPermissionsError can't repair a missing dir -> SIGTRAP
    crash-loop. backboardd then blocks forever on the container-path XPC
    (symbolicated r0203 SMP: backboardd->_container_system_path_for_identifier
    ->containermanagerd; SpringBoard->_BKSDisplayServicesStart->backboardd).
    Create the tree root:wheel 0755 unconditionally so wrong perms on an
    existing dir are repaired too. containermanagerd is a root LaunchDaemon."""
    base = os.path.join(root, 'private/var/installd')
    for rel in ('', 'Library', 'Library/Caches',
                'Library/Caches/com.apple.containermanagerd'):
        d = os.path.join(base, rel) if rel else base
        os.makedirs(d, exist_ok=True)
        os.chown(d, 0, 0)
        os.chmod(d, 0o755)
        print('installd dir', os.path.relpath(d, root))


def tcc_dirs(root):
    """TCC database homes. tccd (com.apple.tccd, UserName=mobile) opens its
    sqlite TCC.db under ~/Library/Application Support/com.apple.TCC and the
    binary carries an "aborting..."/db_queue assert when it cannot set up the
    DB (seen on athens r0203c: tccd crash-looped 440x, which left profiled's
    TCCAccessSetOverride unanswered -> migration hang -> SpringBoard
    waitForMigration stall -> Apple logo). On the single HFS root the whole
    mobile "Application Support" tree is absent (data-volume-only on real
    iOS), exactly like /private/var/installd was. Create the parents and the
    com.apple.TCC leaf for both the mobile user and the system /Library TCC
    store, unconditionally so wrong perms get repaired. tccd runs as mobile
    (uid 501); the /Library store is root-owned."""
    for rel, uid, gid in (
            ('Library/Application Support/com.apple.TCC', 0, 0),
            ('private/var/mobile/Library/Application Support', MOBILE, MOBILE),
            ('private/var/mobile/Library/Application Support/com.apple.TCC',
             MOBILE, MOBILE)):
        d = os.path.join(root, rel)
        os.makedirs(d, exist_ok=True)
        os.chown(d, uid, gid)
        os.chmod(d, 0o755)
        print('tccdir', rel)


def activation(root):
    c = find_container(root, 'Data/System', 'com.apple.mobileactivationd')
    if c is None:
        print('warning: no mobileactivationd system container in the image; skipped data ark')
        return
    d = os.path.join(c, 'Library/internal')
    os.makedirs(d, exist_ok=True)
    os.chown(d, MOBILE, MOBILE)
    os.chmod(d, 0o755)
    save(os.path.join(d, 'data_ark.plist'), {
        '-ActivationState': 'Activated', '-BrickState': False,
        '-BuildVersion': BUILD, '-ProductVersion': VERSION,
        '-DataMigrationCompleted': True, '-PreSydroDataMigrationCompleted': True,
    }, MOBILE, MOBILE, 0o600)
    print('data ark', d)


def audio(root):
    src = os.path.join(root, 'Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin')
    dst_dir = os.path.join(root, 'Library/Audio/Plug-Ins/HAL.disabled')
    if os.path.exists(src):
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst_dir)
        print('VirtualAudio.plugin disabled')
    for conf in glob.glob(os.path.join(root, 'System/Library/Frameworks/MediaToolbox.framework/*/SubServerConfiguration.plist')):
        st = os.stat(conf)
        data = load(conf)
        data['StartRecorderServer'] = False
        save(conf, data, st.st_uid, st.st_gid, st.st_mode & 0o7777, plistlib.FMT_XML)
        print('StartRecorderServer off', os.path.relpath(conf, root))


def firmware(root):
    """Install the NT36672C touch firmware the kernel driver loads.

    AthensNT36672C opens fw-path /usr/share/firmware/touch/nt36672c_jdi.bin
    (tools/mkadt.py) on the mounted root. Source blob lives in the repo at
    firmware/touch/; copy it root-owned into the image. Missing source is a
    warning, not fatal - rootfs builds without the blob still work."""
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           os.pardir, 'firmware', 'touch')
    dst_dir = os.path.join(root, 'usr/share/firmware/touch')
    for name in os.listdir(src_dir) if os.path.isdir(src_dir) else []:
        if not name.endswith('.bin'):
            continue
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, name)
        shutil.copyfile(os.path.join(src_dir, name), dst)
        os.chown(dst, 0, 0)
        os.chmod(dst, 0o644)
        print('firmware', os.path.relpath(dst, root))


def main():
    if len(sys.argv) != 2 or not os.path.isdir(os.path.join(sys.argv[1], 'System/Library/xpc')):
        sys.exit(__doc__)
    root = sys.argv[1]
    launchd(root)
    containers(root)
    vardirs(root)
    installd_dirs(root)
    tcc_dirs(root)
    activation(root)
    mobileactivationd_patch(root)
    audio(root)
    firmware(root)
    merge_pref(root, 'com.apple.migration', {
        'LastSystemVersion': BUILD,
        'DMUserDataDisposition': {'SyntheticDidUpgrade': False, 'buildVersion': BUILD}})
    merge_pref(root, 'com.apple.springboard', {
        'BKNoWatchdogs': True,
        'FBLaunchWatchdogExceptions': {'com.apple.purplebuddy': 100.0},
        'MCForceShowCloudConfigurationUI': False})
    merge_pref(root, 'com.apple.purplebuddy', {
        'SetupDone': True, 'SetupFinishedAllSteps': True, 'SetupVersion': 11,
        'daemonizeNeedsToRun': False})
    merge_pref(root, 'com.apple.purplebuddy.notbackedup', {
        k: False for k in ('ShouldRunDiagnosticsMiniBuddy', 'ShouldRunHSA2MiniBuddy',
                           'ShouldRunKeychainSyncMiniBuddy', 'ShouldRunMesaMiniBuddy',
                           'ShouldRunPaymentMiniBuddy', 'ShouldRunStandardMiniBuddy',
                           'SilentICDPUpgrade')})
    merge_pref(root, 'com.apple.managedconfiguration.notbackedup', {
        'LockdownActivationIndicatesCloudConfigurationAvailable': False})


if __name__ == '__main__':
    main()
