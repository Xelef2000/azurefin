# Azurefin

Azurefin is an experimental Fedora Silverblue / bootc system for the
**Microsoft Surface Laptop 7 13-inch (Romulus13, Snapdragon X Elite)**.
It combines a GNOME desktop with Surface-specific kernel and userspace support.
It is an independent community project, not an official Fedora or Microsoft product.

## What Makes this Raptor Different?

- Surface keyboard, touchpad and touchscreen support, including input during
  encrypted boot.
- Wi-Fi, USB, Bluetooth configuration, conservative speaker profiles and
  experimental camera support.
- Full-disk encryption through the graphical Anaconda installer.
- Homebrew integration for development tools outside the immutable system.
- Surface firmware downloaded from Microsoft after installation, or extracted
  from an MSI you provide. Public images include Fedora's redistributable
  firmware but not Microsoft-extracted Surface firmware.

*Last updated: 2026-10-10*

The post-install firmware flow below is under development and has not yet been
validated on hardware. Existing alpha release media still uses the older
pre-install preparation flow.

## Before you install

The 13-inch model has been tested. The 15-inch model is not validated.
The release ISO workflow is experimental and still needs end-to-end hardware
validation. Only use ISO assets when they are present on the release; creating
a release tag alone does not mean the ISO has finished building. See the
[build and release guide](surface/RELEASING.md) if you want to build or contribute.

You will need:

- A backup of any data on the installation target.
- The charger connected and Secure Boot disabled for the custom kernel.
- Azurefin installation media and at least 30 GiB free on the installed system
  for the one-time firmware setup. No separate workspace drive is needed.
- Either a USB Ethernet connection or the supported Microsoft Surface Laptop 7
  ARM64 driver MSI. Built-in Wi-Fi is not available before firmware preparation.

### Downloading a release ISO

Open the [GitHub release](https://github.com/Xelef2000/azurefin/releases)
and follow its SourceForge link to download the complete `.iso`. Download
the attached `ISO-SHA256SUM` from the same release and verify it in your
download directory:

```sh
sha256sum -c ISO-SHA256SUM
```

No reassembly is needed. Write the complete ISO using your preferred image
writer. Double-check the destination: writing the image erases that drive.

Download the ARM64 driver MSI from Microsoft's
[Surface Laptop 7th Edition download page](https://www.microsoft.com/en-us/download/details.aspx?id=106120).
Download the file only—do not run the Windows installer. The updated firmware
policy supports both:

- `SurfaceLaptop7_ARM_Win11_26100_26.091.9400.0.msi` (default for downloads).
- `SurfaceLaptop7_ARM_Win11_26100_26.053.36539.0.msi` (existing offline copies;
  Microsoft no longer serves this version).

Both MSI checksums and all extracted firmware checksums are pinned in
[the firmware policy](surface/firmware-policy.json). Other versions are rejected.
Use installation media built with the updated firmware tools and policy;
older media only accepts the older MSI. Renaming a file does not bypass checks.

For offline setup, keep the supported MSI on a USB drive. After installation,
remove the installer drive and connect the MSI drive instead.

## Installation

1. Boot the prepared USB media through UEFI. If the internal OS starts instead,
   check that USB storage precedes it in the boot order.
2. Graphical Anaconda opens without firmware download or a workspace prompt.
3. Select the internal NVMe drive, checking its model and size. Do not select
   the installer or the drive carrying the MSI. Reclaiming partitions erases
   their contents. Enable encryption if desired and keep the passphrase safe.
4. Complete installation, shut down, remove the installation media, and boot
   the internal SSD. Unlock encryption and finish account setup.
5. Install Surface firmware as described below, then reboot.

## Install Surface firmware

Built-in Wi-Fi and other firmware-dependent hardware will not work yet.
Connect USB Ethernet, then run:

```sh
sudo azurefin-setup-firmware --download
```

Or use your downloaded MSI without a network connection:

```sh
sudo azurefin-setup-firmware --msi /path/to/SurfaceLaptop7_ARM_Win11.msi
```

Use the actual path to a supported MSI. Both methods verify the MSI and extracted
firmware against the packaged policy. Optionally append
`--bluetooth-address AA:BB:CC:DD:EE:FF`, using your device's **Bluetooth public
address from Windows**, not its Wi-Fi MAC.

The tool builds a private local OS image and stages it for the next boot; it
does not write into immutable `/usr` or reboot automatically. Reboot when it
reports success. The installer retains its clean base locally, so offline setup
does not need a registry download. Preparation logs and intermediate files stay
under `/var/lib/azurefin/provisioning`; failed builds do not stage a new OS.
Keep this directory after setup: the staged deployment uses its OCI image.
Repeated attempts need additional space.

## Bluetooth configuration

If you skipped the address during installation, run:

```sh
sudo azurefin-extract-firmware --bluetooth-address AA:BB:CC:DD:EE:FF
```

Replace the example with your device's actual Bluetooth public address from
Windows, then reboot.

## Current limitations

- Automatic OS image updates are not yet supported for locally provisioned
  installations. Do not switch a firmware-provisioned system back to the public
  firmware-free bootstrap image; it would lose Surface firmware support.
- The new firmware-free first boot, especially encrypted-root unlock, still
  needs hardware validation before release.
- Suspend battery drain and intermittent device initialization still need work.
- Camera capture works, but colour and flicker tuning remain incomplete.
- Speaker output uses conservative gain limits; full thermal protection is not
  validated. Keep the supplied audio profiles and kernel limits.
- Secure Boot is not supported by the current unsigned kernel.

## Components and contributing

- [azurefin-linux](https://github.com/Xelef2000/azurefin-linux): kernel RPM.
- [azurefin-packages](https://github.com/Xelef2000/azurefin-packages): touch input,
  hardware integration and firmware extraction tools.
- [Build and release guide](surface/RELEASING.md).
- [Release content policy](surface/RELEASE-AUDIT.md).

## Credits and upstream sources

Azurefin builds on [Fedora Silverblue](https://fedoraproject.org/atomic-desktops/silverblue/),
[bootc](https://github.com/bootc-dev/bootc),
[bootc-image-builder](https://github.com/osbuild/bootc-image-builder),
and [Universal Blue / Bluefin](https://github.com/ublue-os/bluefin).

Hardware support draws on [nix1e](https://github.com/orvitpng/nix1e),
[ELLX-Kernel](https://github.com/ProgrammerIn-wonderland/ELLX-Kernel),
[linux-surface](https://github.com/linux-surface),
[Alex Lentz's iptsd fork](https://github.com/alex-lentz/iptsd),
and [Bryce Hoehn's Surface Laptop 7 work](https://github.com/bryce-hoehn/linux-surface-laptop-7).
Firmware tooling uses Qualcomm's
[qca-swiss-army-knife](https://github.com/qca/qca-swiss-army-knife).
Microsoft provides the Surface driver MSI. Azurefin-specific calibration,
integration and fixes are maintained in these repositories.
