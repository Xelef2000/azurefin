# Azurefin

Experimental Fedora Silverblue / bootc for the **Surface Laptop 7 13-inch
(Romulus13, Snapdragon X Elite)**. This is not an official Fedora or Microsoft
image. The 15-inch model is not validated.

## What Makes this Raptor Different?

- A versioned [Azurefin kernel](https://github.com/Xelef2000/azurefin-linux) and
  [Surface packages](https://github.com/Xelef2000/azurefin-packages), built in COPR.
- Surface touch input, encrypted-boot display/input support, conservative speaker
  settings, camera support, and per-device Bluetooth configuration.
- Fedora's redistributable firmware is included. **Microsoft-extracted Surface
  firmware and personal data must not be included in public artifacts.**
- The installer prepares a private firmware-complete system locally, using
  either USB Ethernet or an offline Microsoft MSI. No Wi-Fi setup is required.
- Homebrew integration with writable user tooling outside the immutable OS.
- The legacy CPU-parking and restart-only input hooks are not used in the
  current Romulus build path.

*Last updated: 2026-10-07*

## Installation status

The graphical installer, internal-SSD installation and full-disk encryption
have been tested on the 13-inch device. Offline MSI and Ethernet-download
provisioning succeeded; the live installer without Microsoft-extracted firmware
also passed a hardware installation test.

The tested media is currently a **locally prepared USB SSD**, not a generic
download-and-flash release. Its workspace setup is still device-specific.
Do not copy the entire test SSD for distribution: it contains private downloads
and locally provisioned images.

See [release policy and audit](surface/RELEASE-AUDIT.md),
[build/release details](surface/RELEASING.md), and
[development history](surface/PORTING.md). Tagged-release workflow changes are
being prepared; this README is not a claim that release artifacts are already
available.

## Installing with prepared USB media

Back up the target computer first. Keep the charger connected.

1. Use the prepared Azurefin USB SSD and select its Microsoft-firmware-free
   installer entry in UEFI. Disable Secure Boot for this unsigned custom kernel.
   If the internal OS starts instead, check UEFI boot order: installing another
   OS can move USB storage below its entry.
2. Have either:
   - a working USB Ethernet connection for the Microsoft download, or
   - the MSI named in the trusted firmware policy, on a USB drive's top level
     or in a `firmware/` directory.
   Do not rely on built-in Wi-Fi before firmware preparation.
3. For offline installation using the same SSD, copy the MSI **after preparing
   the media** to `firmware/` on its writable `AZUREFIN_WORK` partition.
   This partition is ext4; copying directly from Windows is not supported.
   Keep another copy of the original MSI. Do not place it in the EFI partition.
4. In the preparation console, choose download or offline input. The installer
   validates the MSI and extracted files against the reviewed policy. You may
   enter the device's Windows **Bluetooth public MAC**, or leave it blank.
   It is stored only in the installed system, not the published base.
5. Wait for preparation to complete and graphical Anaconda to appear.
   Preparation runs before partitioning and needs **at least 30 GiB free**
   disk-backed workspace. Each attempt retains logs and build data; allow
   substantial extra room when repeating tests.
6. Select the internal NVMe as the installation target. Check model and size
   carefully. Do not select the installer/workspace or MSI-source disk.
   Reclaiming partitions erases their contents. Enable encryption if wanted
   and retain the passphrase securely.
7. Finish installation, shut down, remove the installer and boot the internal
   SSD. Unlock encryption and complete account setup.

On preparation failure, do not proceed with an unfinalized payload. Diagnostics
are in `/tmp/azurefin-preparation.log` and the workspace's `launcher.log` /
per-run directories. Do not delete an active preparation or installation.

## Bluetooth after installation

If you skipped the optional address prompt:

```sh
sudo azurefin-extract-firmware --bluetooth-address YOUR:FACTORY:ADDRESS
```

Replace the placeholder with the actual six-byte colon-separated Bluetooth
public address from Windows, not the Wi-Fi MAC. Configuration takes effect on
the next boot; the command does not reboot or disconnect peripherals itself.
Never add a personal address to the source tree or public image.

## Updates and limitations

The provisioned system contains locally extracted firmware. Automatic image
updates are intentionally disabled in this prototype so an update cannot
replace it with an unfinalized public base. **Do not run bootc switch to a
`*-base` tag**, and do not install that base directly onto a disk.

Secure Boot is not validated. Suspend/battery behavior, camera image quality
and complete speaker protection still need work. Preserve the tested speaker
gain limits; do not substitute unrestricted audio profiles.

## Building and releasing

The supported clean path is `Containerfile.romulus --target packages`, not the
legacy top-level Containerfile. Build the live environment with
`Containerfile.installer`, `INSTALLER_FIRMWARE=none`, and an immutable clean
base image ID. Microsoft firmware finalization is a separate local step.

Published numeric GitHub releases (`vMAJOR.MINOR.PATCH`) trigger the component
workflows when those workflows are present in the tagged commit:

- `azurefin-linux`: source audit and kernel submission to COPR.
- `azurefin-packages`: source audit and iptsd, Romulus configuration and
  firmware-extractor submissions to COPR. The extractor RPM contains tools and
  policy, not extracted firmware.
- `azurefin`: audit-gated ARM64 base and live-installer OCI image builds.

Wait for successful COPR binary builds, then pin their exact versions in
`surface/build/packages.env` before releasing the image. A green submission
workflow is not proof that COPR finished successfully. Plain tag pushes and
draft releases do not trigger these workflows.

Generic ISO publication remains blocked until the workspace setup and final
ISO audit are integrated. No firmware-inclusive image may be published.
Details and local finalization commands are in
[RELEASING.md](surface/RELEASING.md).

## Credits

Built on Fedora Silverblue, bootc, Universal Blue / Bluefin tooling,
linux-surface and iptsd, Qualcomm upstream support, and the Surface Laptop 7
community's kernel work. Microsoft supplies the Windows update MSI downloaded
by the user during private firmware preparation.
