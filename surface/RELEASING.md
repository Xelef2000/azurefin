# Azurefin tagged releases

## Manual live-ISO candidate CI

`Build audited live ISO candidate` (`build-live-iso.yml`) automates the local
combined GNOME desktop and Anaconda composition path. It is manual-only and
uploads short-lived Actions artifacts, never GitHub release assets or
SourceForge downloads. Use it for trials before publishing a release; the release
workflow uses the same live composer and input-signature checks.
The first complete CI-built candidate passed Surface installation and post-install
firmware testing on October 31; see the [validation record](live-session/README.md#october-31-public-runner-candidate-validation).
Publication remains separate and has not been enabled for this candidate workflow.

Manual dispatch defaults to `capacity_only=true`: a lightweight job on the
public `ubuntu-24.04-arm` runner reports CPU, RAM, filesystems, available bytes
and installed tools, without pulling images or composing an ISO. Its report is
retained as an Actions artifact for seven days. Measure actual capacity before
attempting the full pipeline. The 2026-10-29 probe measured 4 CPUs, 15 GiB RAM
and 114,281,193,472 available bytes (about 106 GiB) on a public ARM64 runner.
This is an observation, not a guaranteed capacity. Set `capacity_only=false`
for a full candidate build. The probe does not delete preinstalled software.

Supply an existing audited image tag, such as `v0.0.14-alpha`. The workflow
resolves immutable base and installer digests, verifies their keyless release
signatures plus the base's native OTA signature, and checks both source labels
against the tag. The selected workflow revision supplies the live composition
code; both input and composer revisions are recorded in `BUILD-INFO.txt`.

The default is the public `ubuntu-24.04-arm` runner. An optional
`AZUREFIN_ISO_RUNNER` JSON label list overrides it. The candidate needs
privileged nested Podman/loop mounts and checks for at least 100 GiB free before
pulling inputs (80 GiB afterward). These are trial admission thresholds, not a
measured peak-space guarantee. Run 41087723797 completed in about 62 minutes
with 82 GiB free at the end; peak usage was not measured. Disk-usage diagnostics
are retained even if composition fails.
Do not use a runner with unrelated workloads or credentials. No signing or
SourceForge upload secret is needed.

To reduce peak space, each audited OCI export or superseded ISO is removed
after its last successful consumer. Seed composition output, extracted seed
audit files and live SquashFS inputs are also discarded when no longer needed.
Cleanup accepts only named intermediates beneath a marked, newly created build
workspace, rejects symlinks and mounted paths, and never prunes shared container
storage. Audit logs and the final ISO remain; failed stages retain their
intermediates for diagnosis. Every original audit still runs before cleanup,
including the unchanged final live-ISO content audit.

The composer creates a fresh EFI seed from the audited OCI inputs instead of
depending on an old local ISO. It builds the live desktop without network
access, audits all its layers, tests the temporary live account in a disposable
container, exports SELinux-labelled SquashFS, and composes the single-entry
live ISO with a separate clean installation payload. The final audit inspects
the actual live filesystem, EFI, initramfs and bundled payload. Passing these
checks is not a hardware boot result. Compression and boot configuration remain
the tested local settings for this first candidate.

Download the `live-iso-candidate-RUN_ID` Actions artifact and extract it into an
empty directory. With only that candidate's parts present:

```sh
sha256sum -c SHA256SUMS
cat azurefin-live-*.iso.part-* > "$(awk '{print $2}' ISO-SHA256SUM)"
sha256sum -c ISO-SHA256SUM
```

Artifacts expire after seven days; metadata and logs after fourteen. Verify the
full checksum before flashing. Test the live desktop, offline OS installation,
firmware provisioning and signed update origin before proposing publication.

## Published v0.0.14-alpha: public-runner live installer

The [v0.0.14-alpha release](https://github.com/Xelef2000/azurefin/releases/tag/v0.0.14-alpha)
publishes the exact Surface-tested candidate from run 41087723797, renamed to
`azurefin-v0.0.14-alpha-aarch64.iso` without changing its contents. It is
7,109,738,496 bytes with SHA-256
`219b1613eed649481e175cd5732f8659987c256ab974ac3094a96017520454eb`.
The SourceForge upload passed checksum comparison, its public download returned
the expected size, and GitHub contains only the link and `ISO-SHA256SUM`.
The prebuilt marker prevented both automatic rebuild stages. The old
v0.0.13-alpha ISO was subsequently removed from SourceForge; its small metadata
files and historical GitHub release remain. Old download links are retired.

## Historical v0.0.13-alpha: signed-update live installer

The media release was published from the exact Surface-tested ISO, without
rebuilding it: 7,109,869,568 bytes, SHA-256
`5d31aa9f991f2bd65328293c0ffeb73baee2dd31944b35b65238f1a64c6930a4`.
It installs the audited `v0.0.12-alpha` OS and adds the offline signed-channel
hook from source commit `296a9bde66f554db4fb19b8a8286a058952b8f30`.
The media version and installed OS version therefore intentionally differ.

Pinned build inputs:

- Base: `ghcr.io/xelef2000/azurefin@sha256:646374cde6bf71fbdf4db0304df9fa42bfca063fbc96347b9078fcd0ab0d9545`.
- Installer: `ghcr.io/xelef2000/azurefin@sha256:1c4dae14b137035365f8d49929b70a1208ae25714afb91de620a0db0a215e05f`.

The final media audit passed, including all 92 payload layers, live filesystem,
initramfs and EFI contents. Fedora redistributable firmware is included;
Microsoft-extracted firmware and prohibited personal data are excluded.
Flash read-back matched the full ISO. On 2026-10-29 the user confirmed OS
installation with networking disconnected, followed by online firmware setup.
SSH verification confirmed the signed registry origin, all 11 firmware files,
connected Wi-Fi, successful update preflight and enabled scheduling, with no
failed system services. Subsequent OTA from v0.0.12-alpha to v0.0.14-alpha and
reboot passed on that fresh installation, with all 11 firmware files verified.
Offline MSI setup was not repeated. No new FDE-specific result was recorded.

Publication must use the prebuilt marker described below to avoid an automatic
rebuild, and attach only the full SourceForge ISO link and `ISO-SHA256SUM`.
The SourceForge upload was compared with the local files using a checksum-based
rsync dry run; no differences were reported. The public download returned the
expected size and checksum file. GitHub retains only the link and checksum
attachment. The older v0.0.3-alpha SourceForge files were removed after
verification; its historical GitHub release remains.

## Alpha 3: hardware-tested live ISO

`v0.0.3-alpha` publishes the exact October 26 live ISO tested on the Surface:
6,975,782,912 bytes, SHA-256
`835cfe7626ad22c54cd81936579e3e24a4b8496a45e03e879d805ea4facd5043`.
It boots a temporary passwordless GNOME account and launches Anaconda from the
desktop, while installing a separate clean OS payload. The full artifact audit,
VM desktop/installer launch, Surface installation, and post-install firmware
deployment passed. bootc 1.17.1 removes the spurious OCI transport error.
Firmware preparation can still emit a nonfatal root-cache tmpfiles warning.

This release is marked `<!-- azurefin:prebuilt-tested-iso -->` in its GitHub
notes. Both image-build and ISO-build workflows honor this marker, including
manual ISO dispatches, so a later build cannot replace
the tested artifact. Keep the marker when editing the release notes. Automatic
live ISO composition applies to unmarked releases. Public release assets are the SourceForge ISO link
and `ISO-SHA256SUM`. Retire older downloads only after verifying the replacement.

## Microsoft-firmware-free live installer (experimental)

Offline and Ethernet provisioning/installation, followed by installation from
the Microsoft-firmware-free live environment, were reported successful on
hardware on 2026-10-07. Fedora's redistributable firmware is allowed in releases;
Microsoft-extracted Surface firmware and personal configuration are not.
See RELEASE-AUDIT.md for the tested image IDs, checks, and shared metadata.

Build `Containerfile.installer` with `INSTALLER_FIRMWARE=none` and `BASE_IMAGE`
set to the verified clean assembly base's immutable image ID. Never derive it
from a locally provisioned image: removing files does not remove ancestor
layers. This variant retains Fedora's redistributable firmware, generates a
live-only initramfs, and checks it for Microsoft paths and per-device data.
The installed payload now gets a separate firmware-free, OSTree-capable
bootstrap initramfs. Installation and online post-install provisioning were
reported successful on 2026-10-13. FDE unlock remains an explicit test gate;
the earlier live-environment tests do not validate it in this new flow.

The ISO workflow audits the composed initrd, SquashFS, EFI filesystem and
bundled OCI payload as well as image ancestry. Do not assume built-in Wi-Fi
works before provisioning; use USB Ethernet or an offline MSI.

The image release workflow publishes audited clean base and
Microsoft-firmware-free live-installer OCI images.
Firmware provisioning is an explicit local operation, using either a supplied
MSI or the packaged CLI's checksum-pinned downloader. No download runs during
RPM installation or automatically on first boot. The release workflow builds
both OCI inputs. A separate `release-iso.yml` workflow composes the public ISO
after that workflow succeeds; neither workflow builds a locally finalized payload.

## ISO release workflow

`Build audited ARM64 live ISO` runs after successful image publication for a
published release (including prereleases). Tag-only OTA builds do not trigger it.
It can also be started manually with an existing `release_tag`, including
`v0.0.1-alpha`, once the workflow has been merged into the default branch.
It resolves both image references to immutable digests, verifies their keyless
release signatures and the base's native OTA signature before pulling, and checks
ARM64 architecture and source revision against the release commit. It invokes
the same `65-compose-release-live-iso.sh` used by the manual candidate workflow:
temporary passwordless GNOME live session, desktop Anaconda launcher, and a
separate clean OS payload. The ISO-builder source is independently
pinned by ARM64 digest in `surface/50-compose-release-iso.sh`. Both the upstream
builder and patched builder must report ARM64 before composition. The Containerfile
retains its separate x86 default for the existing local cross-build helper.

Use a native ARM64 runner with **at least 100 GiB free before pulling images**.
The standard runner may not have sufficient disk space. Set the repository
variable `AZUREFIN_ISO_RUNNER` to a JSON label list for a suitable dedicated
runner, e.g. `["self-hosted","Linux","ARM64","azurefin-iso"]`. A privileged
Fedora container is required for nested Podman/osbuild and loopback mounts.
Do not use a runner carrying unrelated credentials or workloads. Disk-space
checks fail explicitly; the workflow does not erase runner directories.

The ISO includes a clean, bootable bootstrap OCI and trusted firmware preparation
tools. Anaconda installs it directly with interactive disk selection, then copies
the clean OCI and tools into `/var/lib/azurefin/installer` on the target. No extra
workspace partition is used. After account setup, the user explicitly runs
`azurefin-setup-firmware --download` or `--msi PATH`, optionally adding
`--bluetooth-address MAC`. Preparation uses at least 30 GiB of free internal disk
space for extraction and provisions a verified, versioned firmware bundle on
the separate ext4 `/boot`. It configures the early-boot loader without rebuilding
or switching the OS image, and never reboots automatically. The retained OCI is
not required by this setup path. The installer now configures the signed registry
origin through bootc's offline, in-place Anaconda hook; scheduled updates still
require a provisioned firmware store. Automated builds run content and container
checks, not physical hardware tests; their build information explicitly records
hardware testing as not yet run. Changes to the installation path should first
be tried through the manual candidate workflow, including offline installation
and first-boot origin checks. No Microsoft-extracted firmware or per-device
address is embedded in public artifacts.

The final ISO removes the composer's unused `/container` payload copy. Its sole
boot entry selects our Kickstart, which uses `/azurefin/base-oci` for both
installation and the retained offline setup seed. The final audit requires the
retained payload and rejects a duplicate `/container` directory.

Final checks inspect the ISO filesystem, the live SquashFS (and any embedded
root filesystem), its initramfs archives, the EFI filesystem, and every bundled
OCI layer. These are technical content checks, not a comprehensive license or
security review. A successful compose/audit is not a hardware boot test.

GitHub limits each release asset to less than 2 GiB, so the workflow attaches
ordered ISO chunks, chunk and whole-ISO SHA-256 checksums, build provenance and
an audit log as temporary transport assets. After successful SourceForge
publication, the release retains only the full-ISO link and `ISO-SHA256SUM`.
It refuses to overwrite existing assets. Firmware-inclusive local ISO helpers
remain local-only.

When `SOURCEFORGE_PROJECT` is configured, successful composition calls the
SourceForge publisher automatically. Set `SOURCEFORGE_USERNAME` and the dedicated
`SOURCEFORGE_SSH_KEY` secret as described below. Metadata and failure diagnostics
are retained as Actions artifacts for fourteen days. A failed build or audit
cannot reach the upload step; a failed mirror verification retains the temporary
GitHub assets for diagnosis. No automatic deletion of older releases is performed.

## Order of operations

### SourceForge full-ISO mirror

`Publish complete ISO to SourceForge` runs after ISO publication when the
repository variable `SOURCEFORGE_PROJECT` is configured. It can also be run
manually with an existing release tag, without rebuilding the ISO.
Set `SOURCEFORGE_USERNAME` and `SOURCEFORGE_PROJECT`, and store a dedicated
Ed25519 private key in the `SOURCEFORGE_SSH_KEY` Actions secret. Add only its
public key to the SourceForge account with release-upload permission.

The publisher downloads the public GitHub release assets, requires the final
audit success marker, and verifies chunk and whole-ISO SHA-256 checksums.
This verifies the previously audited artifact; it does not rerun the filesystem
audit or turn the checksum into a signature. It refuses ISOs at or above
10,000,000,000 bytes, conservatively respecting SourceForge's 10 GB limit.
The SSH host key is pinned in `surface/sourceforge_known_hosts`, verified against
SourceForge's published fingerprint documentation.

Only the assembled ISO, its checksum, build information and audit log are
uploaded to `/home/frs/project/PROJECT/TAG/`. Existing release directories cause
a failure rather than an overwrite. If a transfer fails partway, inspect that
directory before arranging recovery; do not blindly rerun or delete releases.
The upload is followed by a read-only, checksum-based rsync comparison.
Mirrors may take time to make new files available. Finalization checks that the
full download responds and the mirrored checksum matches GitHub, then replaces
the release notes with the ISO link and verification instructions and deletes
only the known temporary assets. Unknown assets cause a refusal. The checksum
remains attached; build provenance and audit logs remain on SourceForge. Existing
prebuilt-release markers are preserved, without marking untested automated
builds as hardware-tested.
If upload succeeded but finalization failed, rerun the publisher manually with
`finalize_only=true`. This does not rebuild or re-upload the ISO. Keep only a
reasonable number of large releases on
SourceForge and consult its storage policy before expanding retention.

### Component release sequence

1. Publish a vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-alpha GitHub release in azurefin-linux and/or
   azurefin-packages. Their release workflows submit ARM64 builds to COPR.
2. Wait for successful COPR binary builds, not merely green submission workflows.
3. Update surface/build/packages.env to the exact published RPM NEVRAs.
4. Commit that lock file and publish an Azurefin GitHub release, e.g. v0.1.0.
   The tagged commit must contain .github/workflows/release-romulus.yml.

Draft releases and plain tag pushes do not start builds. Published prereleases
do. Tag the reviewed primary-branch commit after the release changes have
passed CI and been merged. Workflows must be present at the release tag.

Alpha tags map to RPM release `100.MAJOR.MINOR.PATCH.0`; stable tags use
`100.MAJOR.MINOR.PATCH.1`. The release is stored in the source RPM's spec so
COPR rebuilds retain it. Check the resulting binary metadata, not only the
source RPM filename, before updating the image lock file.

## Image output

The native ARM64 job publishes:

    ghcr.io/xelef2000/azurefin:v0.1.0-base
    ghcr.io/xelef2000/azurefin:v0.1.0-installer

It uses the built-in GITHUB_TOKEN with packages:write; no COPR credentials
are required in the image repository. Package repositories are public COPRs.
There is no automatic stable/latest tag or deployment to a running machine.
The job retains the installed-RPM manifest, audit reports and pushed OCI
digests as artifacts. Both images must pass before either is published.

**The new base is a firmware-free bootstrap system, pending hardware validation.**
The workflow selects `base-image`, including the Romulus initramfs with OSTree
support and explicit device tree selection. It rejects Microsoft firmware and
machine-specific Bluetooth configuration. No MSI is mounted or extracted during
this build. Use `--target local-image` only for private firmware-inclusive builds.

## Local finalization

The base includes the following CLI operations:

```sh
azurefin-extract-firmware --help
azurefin-extract-firmware --download /path/to/writable-image-root
azurefin-extract-firmware /path/to/SurfaceLaptop7.msi /path/to/writable-image-root
sudo azurefin-extract-firmware --bluetooth-address YOUR:FACTORY:ADDRESS
```

Use a real six-byte colon-separated Bluetooth address from Windows (not the
literal placeholder). `--root /path/to/image-root` can configure a private
installation tree instead of the current host. Existing address files are
backed up. The address takes effect through the packaged service on next boot;
the CLI does not disconnect Bluetooth peripherals or reboot the machine.

Firmware destinations must already contain Fedora's WCN7850 board data.
The CLI requires a writable image tree: it does not make immutable `/usr`
writable, rebuild the running deployment, or modify its boot files. Extraction
alone is not deployment. Download/extraction work directories are retained for
inspection and should be removed when no longer needed. Firmware-inclusive
images still require local initramfs/DTB finalization before booting.

Check out the matching release tag and finalize using the published digest:

    podman build --platform linux/arm64 -f Containerfile.romulus-local \
      --build-arg RELEASE_BASE=ghcr.io/xelef2000/azurefin@sha256:REPLACE_WITH_RELEASE_DIGEST \
      --secret=id=surface-msi,src=/path/to/SurfaceLaptop7_ARM_Win11_26100_26.053.36539.0.msi \
      -t localhost/azurefin:romulus-testing .

The resulting local image contains extracted Microsoft firmware. Do not upload
it until redistribution rights are established. Secret mounting keeps the MSI
input out of layers, but does not remove extracted firmware from the output.

Alternatively, replace the `--secret` option with
`--build-arg FIRMWARE_SOURCE=download`. The local build then calls the packaged
CLI to download and verify the pinned MSI into temporary storage before
extraction. This is opt-in, requires network access, and still produces a
private firmware-inclusive image. It is never enabled in the public base stage.

Bootloader/DTB selection, encrypted boot and physical hardware validation are
still tracked in PORTING.md. Successful image assembly alone is not boot validation.

## Legacy experimental installer-time preparation

The following describes the older alpha/prototype flow, not the new release
installer. It is retained as historical test documentation. The new installer
uses the same preparation backend only after installing the bootstrap system.

The tested live installer can omit Microsoft firmware. Its target
payload is finalized separately from the firmware-free base, before
Anaconda is allowed to change any disks. Do not use `%pre-install` for downloading:
that hook runs after partitioning and filesystem creation. Bluetooth address
configuration is optional in the preparation prompt or after account setup.

The preparation backend is available and has passed a full local OCI import,
download, build, initramfs validation and export test. It never selects, mounts,
formats, or partitions disks.
Run it explicitly with an OCI-layout directory, its independently trusted image
config ID, and an existing writable ext4/XFS/Btrfs workspace:

```sh
bash surface/28-prepare-installer-payload.sh /path/to/base-oci \
  EXPECTED_64_HEX_IMAGE_ID /path/to/workspace
# Offline alternative: append the path to the pinned MSI.
bash surface/28-prepare-installer-payload.sh /path/to/base-oci \
  EXPECTED_64_HEX_IMAGE_ID /path/to/workspace /path/to/SurfaceLaptop7_ARM_Win11_26100_26.053.36539.0.msi
```

The helper creates a new private `azurefin-provision.*` directory, imports the
base into isolated Podman storage, checks its image ID, downloads and verifies
the MSI, builds the initramfs/DTB configuration, runs bootc lint, and exports a
firmware-complete OCI directory. Only a successful export gets a `READY` file.
The base, build cache, export and logs are retained. Nothing is published.
The host needs Podman and native ARM64 execution or registered ARM64 emulation.

At least 30 GiB free disk-backed workspace is required; RAM-backed live storage
is refused to avoid exhausting the 16 GB Surface. A dedicated partition on the
external installer SSD is a candidate, not something this helper creates.
The installer must exclude that workspace disk from installation targets.
The opt-in prototype `installer-provision.ks` runs a fatal-on-error `%pre`
script before partitioning. It mounts the explicitly UUID-pinned USB workspace
and runs `installer_prepare.py` on VT8, separate from Anaconda's tmux console.
This offers either a download after connecting USB Ethernet, or a downloaded MSI
on a USB drive. There is no Wi-Fi setup. USB source partitions are mounted
read-only with `nosuid,nodev,noexec`; put the MSI in the drive's top-level folder
or a `firmware` subdirectory. The same installer SSD can be used: after flashing,
mount its **AZUREFIN_WORK** partition on Linux and copy the MSI to `firmware/`.
No second USB drive is required. This partition is ext4, so native Windows
copying is not currently supported. Do not put the MSI inside the ISO or small
EFI partition; use the writable workspace. Reflashing/repartitioning may erase
it, so keep the original download elsewhere.
The pinned SHA-512 is checked before importing container data and again during
extraction. Offline builds mount the MSI as a secret with networking disabled.
After preparation succeeds it emits a Kickstart include with
the finalized OCI source, excludes the whole workspace disk using `ignoredisk`,
and also excludes the MSI source disk, then returns to graphical Anaconda.
The Bluetooth MAC is not embedded. Console messages and exceptions are mirrored
to the Anaconda pre-script log and persistent `launcher.log` on the workspace.

`installer_provision_grub.py` appends a test entry without changing the original
entries or default. The local prototype uses an explicitly UUID-pinned ext4
workspace, later enlarged to 100 GiB for repeat tests. This remains
hardware-specific test configuration, not a generic release installer.
Preserve the old boot entry as a fallback. Ethernet/USB selection, the live
Podman runtime, and installation have passed hardware tests. Failed preparations retain
their disk usage and logs; do not repeatedly retry without reviewing free space.
Do not point Anaconda at the unfinalized base.
# Updating the installer firmware policy

Online preparation uses Podman's `--network=host` to share the installer's
Ethernet connection. The live environment cannot currently set up netavark's
nftables bridge/NAT rules; the default build network fails before the first
RUN command. Offline MSI preparation still uses `--network=none`. Host
networking applies only to this trusted local image build, not installed-system
firewall configuration.

The preparation console optionally accepts the device's Windows Bluetooth
public address (not its Wi-Fi address). Blank input skips configuration;
invalid input is rejected and prompted again. The generated Kickstart applies
the validated address using the CLI in the installed system's `%post`, without
embedding a device-specific address into the prepared OCI payload.

Each preparation run retains its storage and logs. A successful offline run
can leave too little free space for a second online run in the 40 GiB test
workspace. The helper requires 30 GiB free and reports this before importing
or downloading anything. Reclaim completed run data only after installation
is finished, or provide a larger workspace; do not delete an active payload.

The authoritative manifest is `azurefin-packages/firmware/SOURCES/firmware-policy.json`.
Keep the copies in this repository's `surface/firmware-policy.json` and
`azurefin-linux/SOURCES/firmware-policy.json` synchronized for release auditing.
It contains the MSI filename, Microsoft HTTPS URL, SHA-512 and the source,
destination and SHA-256 of each extracted firmware file. See that repository's
`firmware/POLICY.md` for the review and verification procedure.

Stage `azurefin-extract-firmware`, `firmware-policy.py` and
`firmware-policy.json` together under `AZUREFIN_WORK/support/firmware-tools/`.
For host-side helper tests, set `AZUREFIN_FIRMWARE_TOOLS` to that source directory.
The installer reads this policy, verifies offline input before the large import,
then snapshots the tools and policy into its private build context. This
prototype deliberately overrides the older base's extractor; its RPM database
still reports the base package version. No firmware is present in these support
files. A policy is trusted configuration: never automatically import one from an
arbitrary MSI USB. Retest extraction and hardware after changing releases.
