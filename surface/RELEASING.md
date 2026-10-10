# Azurefin tagged releases

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
The installed FDE image must still use the normal provisioning path.

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

`Build audited ARM64 installer ISO` runs after successful image publication.
It can also be started manually with an existing `release_tag`, including
`v0.0.1-alpha`, once the workflow has been merged into the default branch.
It resolves both image references to immutable digests and checks their source
revision against the release commit. The ISO-builder source is independently
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

The ISO includes a clean base OCI and trusted firmware preparation tools.
At boot it asks for exactly one existing, unmounted USB partition labeled
`AZUREFIN_WORK`, using ext4, XFS or Btrfs, with at least 30 GiB free. It never
formats or creates this workspace. No machine-specific UUID, drive size,
firmware binary or Bluetooth address is embedded. Firmware preparation must
succeed before Anaconda receives an installation source.

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
Mirrors may take time to make new files available. Finalization checks that the
full download responds and the mirrored checksum matches GitHub, then replaces
the release notes with the ISO link and verification instructions and deletes
only the known temporary assets. Unknown assets cause a refusal. The checksum
remains attached; build provenance and audit logs remain on SourceForge.
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

**This is a firmware-free assembly base, not an installable system image.**
It has the packaged kernel but no finalized Romulus initramfs. The workflow
selects only the packages stage, which rejects the Microsoft firmware directory
and a machine-specific Bluetooth address file. The default Containerfile target
is now the same firmware-free base; use `--target local-image` for firmware builds.
It never mounts an MSI or runs the firmware-extraction step.

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

## Experimental installer-time preparation

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
