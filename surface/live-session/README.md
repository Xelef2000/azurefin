# Alpha 3 live desktop — validation notes

The combined live desktop, installer, and post-install firmware setup have been
tested on the Surface. The user approved publication of the exact audited
October 26 candidate as v0.0.3-alpha.

This directory contains the local live-desktop and combined-installer prototype.
Automatic ISO composition is not wired to it yet. Prebuilt tested releases use
the `<!-- azurefin:prebuilt-tested-iso -->` release-note marker to prevent the
legacy workflows from replacing the tested media. The combined ISO uses a separate
clean installation payload; live-session settings are not installed onto disk.

## Local validation

Run `python3 -m unittest discover -s surface -p 'test_live_user.py'`.
These tests use temporary files and mocked account/service commands, not host
accounts. They do not demonstrate that GNOME boots successfully.

The disposable container account test accepts Podman's `fuse.fuse-overlayfs`
and simulates a native overlay for the setup script. It checks the actual
filesystem type and Podman marker first and rejects ordinary disk filesystems.
This test does not validate live-root safety or RAM backing: those require the
unit and boot tests. Production `setup.py` remains unchanged and rejects FUSE
roots; no container-test exception is enabled in the live-boot service.

Container checks (network disabled, read-only test mount, no host devices):

```sh
bash surface/live-session/30-test-container.sh localhost/azurefin:postinstall-bootstrap --emulated
bash surface/live-session/30-test-container.sh localhost/azurefin-iso-builder:postinstall-x86 --accounts-only
```

Local results, 2026-10-13:

- Six unit tests passed; ShellCheck passed.
- Fedora 44 ARM64 Azurefin container: real account/home creation, empty password,
  sudo policy validation, GDM configuration, offline SSH masks and effective
  GNOME lock-screen settings passed.
- Fedora 42 native x86_64 test container: actual `liveuser` → `sudo -n id -u`
  elevation passed. This corroborates the configuration, not ARM64 PAM login.
- ARM64 setuid sudo execution under user emulation failed without diagnostics;
  the subsequent full-system ARM64 VM successfully executed passwordless sudo.
- The test substitutes the kernel command line and applies SSH masks offline;
  it does not boot systemd or GDM. Production setup stops/masks SSH before
  unlocking the account. The GDM drop-in requires successful setup; the unit
  asserts the live command-line flag instead of silently skipping setup.

The overlay/tmpfs guard is only an initial check. An overlay can also have a
persistent backing store. Before media integration we must verify the actual
live root uses a RAM-backed writable layer and does not persist changes.

## Required tests before alpha 3

- [x] Refuse account creation without the live kernel flag.
- [x] Refuse account creation on a regular installed root filesystem.
- [x] Do not unlock an existing account.
- [x] Generate liveuser-only passwordless sudo and GNOME autologin configuration.
- [x] Validate real account creation and sudo configuration in disposable containers.
- [x] Validate ARM64 sudo, GDM autologin and running systemd service ordering in a full-system VM.
- [x] Wire the service into a non-persistent VM live root; make GDM require successful setup.
- [x] Validate the live-user setup with SELinux enforcing in an ARM64 VM.
- [x] Package the live root into UEFI-bootable ISO media and boot it in an ARM64 VM.
- [x] Boot GNOME as liveuser without a password on the Surface (user confirmed).
- [ ] Confirm SSH is off and screen lock does not strand the passwordless user.
- [ ] Confirm reboot discards files and settings; internal disks stay untouched.
- [x] VM restart discards a session marker; autologin and sudo pass on both boots.
- [x] Add Anaconda launcher with a separate clean installation payload.
- [x] Verify installation and FDE in the VM; no live account or passwordless policy in installed OS.
- [x] Verify installation on the Surface and post-install firmware setup after reboot (user confirmed).
- [ ] Integrate a reproducible live-media build without VM-only validation services.
- [x] Audit tested r3 live media against the firmware/personal-data policy (2026-10-17).
- [ ] Repeat the full artifact audit on the final release candidate after build integration.

Firmware preparation is post-install only; temporary live-session firmware setup
is not a release requirement. Audit combined live media with
`sudo bash surface/51-audit-release-iso.sh IMAGE.iso NEW_AUDIT_DIRECTORY live`.
The default audit mode remains the older Anaconda-only layout.

The complete audit of `azurefin-alpha3-live-installer-local-r3.iso` passed on
2026-10-17: media checksum, ISO files, all 76 installation-payload OCI layers
(including deleted content), live filesystem, boot and module initramfs, and
EFI files. No policy-prohibited Microsoft firmware or personal configuration
was detected. Fedora redistributable firmware remains allowed. Both GRUB copies
matched the expected single live entry. Read-only audit mounts were cleaned up.
The local evidence is `images/alpha3-live-audit-20261017-r2.log` in the mss7
workspace. This result applies to r3, not to any subsequently rebuilt ISO.

Broad local regression checks (2026-10-17): 82 surface tests and 5 release-audit
tests passed. The payload-preparation tests require the firmware tools sources:

```sh
AZUREFIN_FIRMWARE_TOOLS=/path/to/azurefin-packages/firmware/SOURCES \
  PYTHONPATH=surface /usr/bin/python3 -m unittest discover -s surface -p 'test_*.py'
/usr/bin/python3 -m unittest discover -s scripts -p 'test_*.py'
```

## Full-system ARM64 VM test

### Consolidated candidate build

`Containerfile.live` combines the live account, desktop launcher, and Anaconda
configuration without the VM-only validation service. It requires an explicit
firmware-free installer base image ID or digest; it does not inherit the
prototype images. The clean installed OS payload remains separate.

```sh
podman build --pull=never --network=none \
  --build-arg BASE_IMAGE=IMMUTABLE_INSTALLER_IMAGE_ID \
  -f surface/live-session/Containerfile.live \
  -t localhost/azurefin:alpha3-live-combined .
podman unshare bash surface/live-session/40-export-vm.sh \
  /absolute/path/to/new-artifacts localhost/azurefin:alpha3-live-combined
bash surface/live-session/60-compose-local-iso.sh SOURCE_INSTALLER.iso \
  /absolute/path/to/new-artifacts NEW_LOCAL.iso installer
```

These commands remain local-only. A successful build is not a boot test: rerun
the ISO audit, live desktop, and installation tests before release integration.

Local consolidated build passed on 2026-10-17 with installer base
`f0fdb09e511e9a27be1a0f6addefa567b54fc2b8f180f687074d1c82a1513c4f`.
Result: `213c726efa84af47826dcefb52333efe7b57ab5f2232664a050d1918f623e975`.
The final build had no initramfs attribute-copy warnings. Disposable ARM64
container checks passed for account creation, home ownership, empty password,
sudo policy, GDM configuration, SSH masks and lock-screen settings. The pristine
image has no liveuser account or VM diagnostic service/script; live setup and
GDM are enabled. These emulated checks do not test PAM login or graphical boot.
All 83 surface unit tests and ShellCheck passed after consolidation.

The resulting local ISO `azurefin-alpha3-live-combined-20261018.iso` has SHA256
`1ae2a736b0f3489d28111b47ba4e28d89ac6203cc213ee626e1fe9dc34ae9d98`.
Its complete artifact audit passed on 2026-10-18, including all 76 installation
OCI layers, live root, initramfs and EFI content (saved log:
`images/alpha3-combined-audit-20261018.log` in the mss7 workspace).
The ARM64 VM booted the unmodified ISO into GNOME as liveuser with SELinux
enforcing. Serial login and sudo were passwordless, both SSH units were
runtime-masked, the writable overlay was RAM-backed, and no services failed.
The idle display woke on Shift without a password prompt. Screenshots and
serial evidence are in `images/alpha3-combined-vm-20261018/`.
Launching the desktop installer's command as liveuser also reached Anaconda's
graphical language-selection screen (`installer.png`); no installation was
started during this smoke test.
Installation/FDE and Surface tests still need repeating on this consolidated ISO.

Encrypted-install retest started on 2026-10-18 in the existing combined VM,
using only its new 64 GiB `/dev/vda`. Automatic partitioning and encryption
were selected through the graphical installer. Both passphrase fields were
verified as `azurefin-test-only-qemu-2026` (disposable VM only). Anaconda began
creating LUKS on `/dev/vda3`. Its anaconda/program/storage logs are streamed to
the host `serial.log`; the VM remains supervised by
`azurefin-alpha3-combined-vm-20261018.service`. Completion and installed boot
are not yet verified. Do not inspect the qcow2 through another writer while
this VM is running.

October 26 follow-up: the retained serial log confirms installation finished
on October 18 at 10:38:04 UTC. With no QEMU writer running, read-only inspection
unlocked LUKS, verified the composefs fstab correction, and found no liveuser in
the deployed `/etc/passwd` and no files in `/etc/sudoers.d`.

The installed-boot test uses a copy-on-write overlay in
`images/alpha3-combined-installed-boot-20261026/`, preserving the original disk.
Only the Surface `devicetree` line was removed from the overlay's BLS entry so
QEMU could use its own firmware-provided hardware description. No ISO or network
was attached. The test passphrase unlocked the encrypted root, the system
switched into the installed deployment, GDM started, and GNOME Initial Setup's
Welcome/language-selection window appeared (`screen.png`). No failed-unit
messages were found in the boot log. This passes installation and encrypted
first boot for the consolidated ISO in QEMU; completing account creation and
repeating the test on Surface hardware remain separate checks.

### October 26 provisioning-support correction

The user confirmed the consolidated ISO installed on the Surface, but firmware
setup still logged the old `/root`, syslog and build-cache warnings. SSH inspection
confirmed that the installed `/var/lib/azurefin/installer/support` contained the
old recipe. The local composer had replaced the live filesystem while retaining
the old ISO's entire `/azurefin` bundle. The earlier content audit checked for
prohibited firmware/personal files, not whether provisioning code was current.

Installer-mode composition now replaces `/azurefin/support` with the current
build scripts, provisioning Containerfile and helper scripts, retaining only
the exact firmware tools from the original audited payload. It extracts the
finished ISO's support directory and compares code byte-for-byte with the
checkout. The full ISO audit repeats that check. Missing, changed, symlinked or
extra build files fail validation; the old October 18 ISO fails this new gate.

The corrected local ISO is `azurefin-alpha3-live-combined-20261026.iso`, SHA256
`3523db0e2e966fc2a3104758218b28ba0de52ceb8536f2b18aea79f18605dcea`.
Its media checksum and extracted-support comparison pass. The full content
audit subsequently passed on October 26, including the source/support match,
all 76 installation OCI layers, live root, initramfs and EFI files. Evidence:
`images/alpha3-combined-audit-20261026.log` in mss7. Reflashing and end-to-end
hardware revalidation remain pending. No image has been published.

Native validation on the Surface used the support bundle extracted from this
exact corrected ISO, not a separately patched context. The isolated build
completed successfully (76 seconds), verified the firmware and initramfs, and
passed 13 bootc lint checks with one skip and no warnings. The `/root` and
syslog errors did not recur. Private validation image:
`b9edb1e744faabd9e3ca140970f409364f744ab2c628f0b51c30834d22ac277c`.
No deployment was staged and no reboot was performed. Evidence is saved in
`images/alpha3-iso-support-native-validation-20261026.log` in mss7. All 89
surface tests and ShellCheck passed. The separate bootc OCI-lookup diagnostic
is not addressed by this provisioning fix; no deployment errors are filtered.

### Original diagnostic prototype

```sh
podman build --pull=never --network=none -f surface/live-session/Containerfile.vm -t localhost/azurefin:alpha3-live-vm .
podman build --pull=never --network=none -f surface/live-session/Containerfile.enforcing -t localhost/azurefin:alpha3-live-enforcing .
podman unshare bash surface/live-session/40-export-vm.sh /absolute/path/to/new-vm-directory
bash surface/live-session/50-run-vm.sh /absolute/path/to/new-vm-directory
```

The export destination must not exist. This creates a local SquashFS root plus
kernel/initrd, not a flashable ISO. The VM has no network or host disks attached.
Its writable overlay is in RAM. The current test requires SELinux enforcing.
The first successful VM tests below used SELinux disabled; do not confuse those
with the later enforcing test.

Results are written to `serial.log`: `AZUREFIN_VM_ACCOUNT_PASS` confirms actual
ARM64 sudo and the RAM overlay, while `AZUREFIN_VM_DESKTOP_PASS` confirms a
graphical logind session for liveuser. Neither substitutes for visual inspection
or a Surface hardware test. The monitor socket is local to the artifact folder.
The VM remains running until explicitly stopped.

The exporter uses the image's own SELinux file-context policy to generate
SquashFS xattrs without changing host file labels. It excludes `sysroot/ostree`:
that unused backing store has hardlinks to `/usr` and would otherwise overwrite
executable labels with the backing-store path labels. Labels on systemd and
sudo have also been checked directly in the resulting filesystem with guestfish.
Systemd loads policy at the real-root transition; the experimental dracut
pre-pivot SELinux hook was reverted after it failed in the unlabelled initramfs.

## Local ISO test

```sh
bash surface/live-session/60-compose-local-iso.sh SOURCE_INSTALLER.iso /absolute/path/to/vm-directory NEW_LOCAL.iso
bash surface/live-session/70-run-iso-vm.sh NEW_LOCAL.iso /absolute/path/to/new-uefi-vm-directory
```

This preserves the existing installer ISO's EFI/GPT boot layout, but replaces
its installer root with the live root and removes the installable OS payload.
There is one Try Azurefin menu entry. It is a desktop test, not yet an installer.
The ARM64 UEFI VM boots it as a read-only USB disk with no network/host disks.
Only the explicit `AzurefinVM` SMBIOS marker skips the Surface DTB; hardware
booting still supplies the 13-inch Surface DTB and display preloads.

### First VM boot results

The full-system ARM64 QEMU test reached GDM autologin and a Wayland session for
`liveuser`. The screen capture subsequently showed GNOME's desktop/top bar.
The in-VM account check passed: real ARM64 `sudo -n`, SSH masks, and a tmpfs-backed
overlay. This used the Surface kernel and firmware-free local installer base.
It is not yet a Surface hardware or SELinux-enforcing result.

An initial zstd SquashFS test failed because this kernel only supports zlib/xz
SquashFS decompression. The test exporter now uses gzip. The inherited
`bootloader-update.service` failed in the diskless VM; it must be disabled in
the final live-only layer. Do not carry that change into the installed payload.

Artifacts are under `mss7/images/alpha3-live-vm-20261013-gzip`, including
`first-boot.log` and `desktop2.png`.

A QEMU reset then passed both checks again: the marker written to `/var/tmp`
during the first boot was absent, sudo worked, and liveuser again acquired a
Wayland session. `serial.log` contains both sets of pass markers. The VM was
stopped after testing. No host disks were attached and nothing was flashed.

### Enforcing VM results

`alpha3-live-selinux-20261013-r5/serial.log` records all three pass markers:
SELinux enforcing, the account/sudo/SSH/RAM-overlay checks, and a Wayland
liveuser session. No AVC denials appeared in this boot log. The VM was stopped
after the test. This fixes the export labels rather than adding policy allow
rules or disabling enforcement.

Current scope is only local live-user tests. Anaconda integration, flashing and
publication are not performed by these tests.

### UEFI ISO results

The local `azurefin-alpha3-live-local-r2.iso` booted through ARM64 UEFI and GRUB
as a read-only virtual USB disk. All three checks passed with SELinux enforcing;
the screen capture shows the GNOME overview and welcome dialog. No AVC denials
appeared in the serial log. The VM was stopped after inspection.

The ISO is 3,520,987,136 bytes (3.28 GiB). SHA-256:
`47a679e91a9b385529a325f903dd62a77676f35d46a5052d4240dc5ec6b0ab36`.
Logs and `desktop.png` are in `mss7/images/alpha3-live-uefi-r2-20261013`.
This revision includes the matching GRUB `smbios.mod`, needed to distinguish
the VM from Surface hardware before supplying the device tree.

This is a local desktop-only test ISO, not the combined alpha 3 installer.
Surface boot testing and Anaconda integration remain outstanding. No release
or publication was performed.

## Combined live/installer prototype

Build `Containerfile.installer` locally and export it with `40-export-vm.sh`,
passing `localhost/azurefin:alpha3-live-installer` as the second argument.
Pass `installer` as the fourth argument of `60-compose-local-iso.sh` to retain
the source ISO's separate `/azurefin` installation payload. The default mode
continues to create a desktop-only test ISO.

The live desktop has an **Install Azurefin** application. It launches Anaconda
with `--liveinst` and the existing interactive installation defaults. No disk
is selected or formatted automatically. The clean OCI payload is installed,
not a copy of the running desktop. Firmware setup remains a post-install step.
Installation/FDE testing is still pending; this is not release media.
The existing installed-image recipe and publishing workflows are unchanged.

The first combined ISO booted in the ARM64 UEFI VM with the three live-session
checks passing. Launcher testing found a missing `findmnt -T` and Anaconda's
session-bus requirements: preserve the GNOME bus address and provide the
verified live-user UID via `PKEXEC_UID` for its existing screensaver helper.
With those launch corrections, Anaconda displayed its graphical language
selection inside the live GNOME session. Evidence is in
`mss7/images/alpha3-installer-uefi-20261013/serial.log` and `installer2.png`.
No target disk was attached and no installation was started. The first
`azurefin-alpha3-live-installer-local.iso` lacks those corrections and must not
be used for hardware testing; use a rebuilt revision after validation.

The corrected `azurefin-alpha3-live-installer-local-r2.iso` was composed and
passed its media checksum check (6,967,328,768 bytes; SHA-256
`bead442646929d8ef27ff05de0c6992683fbaa1cccb070ecb0b92e503b383e68`).
It incorporates the launch corrections tested in the first VM; a fresh boot
and complete installation test of this exact artifact remain pending.
`installer3.png` shows the unobscured Anaconda language-selection window.
The VM was stopped. Nothing was flashed, committed, pushed or published.

### Installation VM test

Pass `install` as the third argument of `70-run-iso-vm.sh` to create a fresh
64 GiB `install.qcow2` inside the new VM directory. This never accepts an
existing target disk. QMP and serial sockets are local to that directory;
the VM still has no network or host disks attached.

Testing the exact `local-r2.iso` with this disk passed the three live checks.
Its embedded clean payload (`153fb77f805272a7038a7430dae7f514fb8ffd3e56514bd8ba1353140136a5c7`)
also passed the 76-layer firmware/personal-data audit. The initial installer
startup waits on optional Kdump and Subscription modules which deliberately
exit without registering on DBus. The bus permits a 600,000 ms activation
timeout. `90-azurefin-live.conf` excludes only these unused optional modules
from future live builds; it does not change the installed payload.
Installation and encrypted-boot results are not yet confirmed.

The exact-ISO test eventually reached the graphical installer after the
10-minute optional-service activation timeout. Its packaged launcher worked
without runtime edits. Using only the disposable `/dev/vda`, automatic
partitioning with encryption created a 600 MiB EFI partition, 2 GiB `/boot`,
and a 61.4 GiB LUKS container with Btrfs inside. The test-only passphrase is
`azurefin-test-only-qemu-2026` (never use this for a real installation).
Anaconda began deploying `/run/install/repo/azurefin/base-oci` with bootc.
The VM is retained in `mss7/images/alpha3-fde-vm-20261013`, with
`install.qcow2`, firmware `vars.raw`, `serial.log`, QMP and serial sockets.
Do not open the qcow2 concurrently with a writer while QEMU is running.
The next checks are completed deployment, installed-account isolation,
and UEFI/LUKS boot without the ISO. None of those is marked passed yet.

On October 14, the VM was no longer running. Read-only inspection unlocked
the test LUKS container and found an OSTree deployment, but no deployed
`/etc/fstab`, an empty EFI partition, and a BLS entry without root/encryption
arguments. Installation therefore did not finish; this is not a successful
FDE boot test. No host OOM kill was found in the checked termination window.
Keep the original virtual disk for diagnosis. Repeat the test with the
optional-module startup fix and retain installer logs outside guest RAM.

The rebuilt `azurefin-alpha3-live-installer-local-r3.iso` includes that fix
and passes its embedded media checksum. SHA-256:
`ca02d17f2f75d3a8bf4c604fc67102ab3ac8274ae5ad55a39e03d45acaaa73ba`.
All 11 local unit tests pass. A new disposable installation test lives in
`mss7/images/alpha3-fde-vm-20261014`, supervised by the user service
`azurefin-alpha3-fde-test-20261014` so the VM's exit status is recorded
independently of the launching terminal. Results are recorded below.

October 15 follow-up: the October 14 serial log records Anaconda's
`The installation has finished.` at 07:52:47 UTC, after successful bootupctl
installation and LUKS/root kernel-argument configuration. Read-only inspection
confirms the composefs fstab correction ran, `/etc/passwd` has no liveuser,
and `/etc/sudoers.d` is empty.

First-boot testing uses `mss7/images/alpha3-installed-boot-20261015/boot.qcow2`,
a copy-on-write overlay preserving the original installed disk. No ISO or
network is attached. The unmodified Surface device-tree boot entry did not
produce a kernel console in QEMU. Removing only its `devicetree` line in the
test overlay allowed the firmware-provided QEMU hardware description to be
used. This is a VM accommodation, not a change to the Surface image.
The installed initramfs prompted for LUKS, accepted the test passphrase,
mounted the encrypted root, switched into the installed OS, and started GDM.
GNOME Initial Setup's graphical Welcome/language-selection window subsequently
appeared, confirming that the encrypted installation reaches first-user setup
without the ISO. Evidence is `first-user-setup.png` and `serial-qemu-dtb.log`
in the boot-test directory. Account creation and physical Surface installation
testing remain open. Nothing was published.

Surface follow-up: the user confirmed installation and successful firmware
provisioning after reboot. SSH inspection on October 16 found the expected
private OCI deployment booted and no failed systemd units.

Build-warning cleanup: create the empty `/var/roothome` target before dracut
copies bootc's `/root` symlink. An isolated reproduction failed without that
directory and succeeded with it. Remove only rebuildable DNF/ldconfig caches
and the DNF build log before linting; the local test image passes 13 bootc lint
checks with one skipped and no warnings. A temporary dracut configuration
disables only build-time syslog output, retaining console diagnostics and not
altering installed-system logging.
The October 17 rebuild completed as local image
`47de9e4c001013da685266a0810f54c7b574d67e1ce39ba8aab1b842ddba1b37`:
initramfs and Microsoft-firmware-free checks passed; bootc lint reported
13 passed, one skipped, and no warnings. Neither the `/root` nor syslog
diagnostic appeared. This validates the bootstrap path; rebuilding the
firmware-inclusive provisioning image with these changes remains separate.

The OCI lookup diagnostic originates in bootc 1.16.10's
`image_exists_in_unified_storage` calling `podman image exists` with a transport
reference. Podman's libimage rejects non-storage transports for this lookup;
bootc treats the unsuccessful status as false, not a deployment failure.
See [bootc lookup](https://github.com/bootc-dev/bootc/blob/v1.16.10/crates/lib/src/deploy.rs),
[exit-status handling](https://github.com/bootc-dev/bootc/blob/v1.16.10/crates/lib/src/podstorage.rs),
and [Podman libimage](https://github.com/containers/common/blob/a5ccdae846b629b5ceaefa6ffd5c6511409c3487/libimage/runtime.go).
Do not blanket-filter stderr or ignore the final `bootc switch` exit status.

October 26: upstream fixed this lookup in
[bootc PR #2410](https://github.com/bootc-dev/bootc/pull/2410), included in
1.16.11. The package recipe now requires `bootc >= 1.16.11`; Fedora 44's
aarch64 repositories offer 1.17.1. Rebuild the clean OS payload as well as
the live image and installer before retesting: refreshing installer support
files alone cannot update bootc in the installed system. Existing installations
running 1.16.10 retain the diagnostic until booted into an updated deployment.

October 17 firmware-inclusive validation also passed on the Surface using a
separate build context at `/var/tmp/azurefin-firmware-validation.d08QBvYC` and
the existing isolated provisioning container cache. The reviewed scripts
downloaded and verified the MSI, extracted firmware, rebuilt and verified the
initramfs, and passed 13 bootc lint checks (one skipped, no warnings). Neither
the `/root` nor syslog diagnostic appeared. The resulting private image is
`df1eaea36a2a5eb85658eef7edf1706954f6f342a14a8ed0baaf942cb342f4c4`.
Logs are in the Surface journal for `azurefin-firmware-validation-20261017`.
This was build validation only: no `bootc switch`, reboot, SSD flash, or
publication was performed. The temporary sleep inhibitor ended with the build.

### October 26 bootc-fixed rebuild

The clean base rebuilt with Fedora bootc 1.17.1 and passed 14 bootc container
checks (one skipped), the bootstrap initramfs checks, and the Microsoft-firmware
exclusion checks. Local image IDs:

- Base: `e7511c40ebd670275907bd03089cf8caf41b84a21ea2e7e535c4a61bd29c954a`
- Installer: `8f6638c97ba9628b12d3b2dd63b2f49bea30a5ab9517c091b90846933166738b`
- Live: `f346d0517b866c1b5fb1539d160395a8d94f89c645bfa68f8a500e6c5569a607`

The ISO must embed the new base OCI and its matching image ID, not only the
new live filesystem. The local exporter now also exports the kernel's Romulus13
device tree; composition replaces the old ISO's DTB and the final audit checks
it against the live kernel's copy. The regression suite passes 90 tests.
The final ISO audit passed (`FINAL_ISO_CONTENT_AUDIT_PASSED`). The isolated
ARM64 VM booted into the passwordless live GNOME Wayland session, reported
bootc 1.17.1 with no failed system units, and opened the graphical Anaconda
language-selection screen. Screenshots and serial output are retained in
`images/alpha3-bootc-fixed-vm-20261026` in the local test workspace. A fresh
installation and firmware-provisioning run on the Surface remain to be tested;
no publication or physical disk writes have been performed.

Local ISO composition completed as `azurefin-alpha3-live-bootc-fixed-20261026.iso`
(6,975,782,912 bytes), SHA-256
`835cfe7626ad22c54cd81936579e3e24a4b8496a45e03e879d805ea4facd5043`.
The ISO checksum and extracted support/source comparison passed. Composition
now handles a source live ISO whose Anaconda-only files were already removed;
the current composer uses an exact-path xorriso find/remove operation, which
also succeeds when those files are absent. This replaces the earlier existence
probe, whose `-return_with WARNING 1` used an invalid xorriso exit code.

### October 31 public-runner candidate validation

[Actions run 41087723797](https://github.com/Xelef2000/azurefin/actions/runs/41087723797)
built and audited the live ISO successfully on the public ARM64 runner using
composer commit `816b34b55782e38ecbf37d7805c51d70cb02460c` and the signed
`v0.0.14-alpha` inputs. The live job took approximately 62 minutes; consolidating
the live container changes into one layer reduced that build stage to about
12 minutes. Final disk diagnostics showed 82 GiB free (not a peak-use measure).

Candidate: `azurefin-live-v0.0.14-alpha-41087723797-aarch64.iso`
(7,109,738,496 bytes), SHA-256
`219b1613eed649481e175cd5732f8659987c256ab974ac3094a96017520454eb`.
Input signature verification, container firmware-policy audits, live-account
tests, and the final ISO content and matching kernel/DTB audits passed. Fedora's
redistributable firmware is permitted; Microsoft-extracted firmware is excluded
from the distributed candidate.

After a verified flash, the Surface Laptop 7 13-inch completed installation and
post-install firmware provisioning. Inspection of the installed system confirmed:

- The booted base digest matched the candidate input:
  `sha256:bb16069b7bf7cee046f0176ff82178d724656ac3fd23dbe06f5df8306ba52094`.
- All 11 provisioned firmware files passed verification and the runtime loader
  exited successfully.
- Wi-Fi and Ethernet were connected, no systemd units were failed, and
  `uupd.timer` was enabled and active.
- No `liveuser` account remained in the installed system.
- The tester confirmed working sound.

The journal still contained driver and audio diagnostics; this is not a claim
of an error-free journal. Suspend, battery life, and a fresh OTA cycle were not
retested as part of this candidate check. The build-time `BUILD-INFO.txt` still
says hardware testing was pending; this follow-up records the subsequent test.
The candidate has not been published as a release.
