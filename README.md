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
- Surface firmware downloaded from Microsoft during installation, or extracted
  from an MSI you provide. Public images include Fedora's redistributable
  firmware but not Microsoft-extracted Surface firmware.

*Last updated: 2026-10-09*

## Before you install

The 13-inch model has been tested. The 15-inch model is not validated.
A general-purpose downloadable installer is **not yet available**; installation
currently requires prepared development media. See the
[build and release guide](surface/RELEASING.md) if you want to build or contribute.

You will need:

- A backup of any data on the installation target.
- The charger connected and Secure Boot disabled for the custom kernel.
- Prepared Azurefin installation media with at least 30 GiB free workspace.
- Either a USB Ethernet connection or the supported Microsoft Surface Laptop 7
  ARM64 driver MSI. Built-in Wi-Fi is not available before firmware preparation.

For offline installation, use the MSI filename specified in
[the firmware policy](surface/firmware-policy.json). Copy it to the top level
or a `firmware/` directory on a USB drive. With prepared media that includes
an `AZUREFIN_WORK` partition, you can put it in that partition's `firmware/`
directory instead. That partition is ext4 and normally needs Linux to write it.

## Installation

1. Boot the prepared USB media through UEFI. If the internal OS starts instead,
   check that USB storage precedes it in the boot order.
2. Choose offline firmware extraction or download over USB Ethernet.
   The installer verifies the MSI and extracted files before continuing.
3. Optionally enter the device's **Bluetooth public address from Windows**.
   This is not the Wi-Fi MAC address; leave it blank if you do not have it.
4. Wait for firmware preparation to finish and graphical Anaconda to open.
5. Select the internal NVMe drive, checking its model and size. Do not select
   the installer or the drive carrying the MSI. Reclaiming partitions erases
   their contents. Enable encryption if desired and keep the passphrase safe.
6. Complete installation, shut down, remove the installation media, and boot
   the internal SSD. Unlock encryption and finish account setup.

If firmware preparation fails, its log is at
`/tmp/azurefin-preparation.log`. Repeated attempts use additional workspace;
check available space before retrying.

## Bluetooth configuration

If you skipped the address during installation, run:

```sh
sudo azurefin-extract-firmware --bluetooth-address AA:BB:CC:DD:EE:FF
```

Replace the example with your device's actual Bluetooth public address from
Windows, then reboot.

## Current limitations

- Automatic OS image updates are not yet supported for locally provisioned
  installations. Public `*-base` images are build inputs, not ready-to-boot
  systems: do not switch an installed system to them.
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
