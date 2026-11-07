# Azurefin

**A Fedora Atomic desktop for the Microsoft Surface Laptop 7 13-inch**
(Romulus13, Snapdragon X Elite).

[![Build](https://github.com/Xelef2000/azurefin/actions/workflows/build.yml/badge.svg)](https://github.com/Xelef2000/azurefin/actions/workflows/build.yml)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Platform](https://img.shields.io/badge/platform-ARM64%20Snapdragon%20X%20Elite-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

Azurefin pairs a GNOME desktop with a Surface-tuned kernel and userspace so the
Surface Laptop 7 boots, installs, and updates like an ordinary immutable Fedora
system. It is built on [Fedora Silverblue](https://fedoraproject.org/atomic-desktops/silverblue/),
[bootc](https://github.com/bootc-dev/bootc), and
[Universal Blue / Bluefin](https://github.com/ublue-os/bluefin).

> ⚠️ **Experimental, alpha-stage, community project** — not affiliated with
> Fedora or Microsoft. Only the 13-inch model is tested. Back up your data
> before installing, and read the [current limitations](docs/known-issues.md).

## Highlights

- **Surface hardware support** — keyboard, touchpad and touchscreen (including
  during encrypted boot), Wi-Fi, USB, Bluetooth, conservative speaker profiles,
  and experimental camera support.
- **Surface-tuned kernel** — Linux 7.4-rc1 with Azurefin's fixes and an opt-in,
  read-only module for factory Bluetooth-address discovery.
- **Graphical install with full-disk encryption** via Anaconda, and a live
  GNOME session you can try before installing.
- **Verified Surface firmware** stored on `/boot`, independent of the immutable
  OS image — downloaded from Microsoft or extracted from an MSI you provide.
- **Signed, scheduled system updates** through Universal Blue's updater, with a
  manual `ujust update` workflow that stages the OS, Flatpaks, and Homebrew.
- **Layered tooling** — Homebrew for development tools, Bazaar as the app store,
  and an opt-in multi-user Nix store (testing).

## Quick start

1. Download the latest [release ISO](https://github.com/Xelef2000/azurefin/releases)
   and verify it with `sha256sum -c ISO-SHA256SUM`.
2. Grab Microsoft's ARM64 Surface driver MSI (file only — don't run it).
3. Disable Secure Boot, connect the charger, and boot the USB media.
4. Run **Install Azurefin** from the live desktop, then reboot into the
   installed system on the internal SSD.
5. On the installed system (not the live session), complete firmware setup:

   ```sh
   sudo azurefin-setup-firmware --download   # or --msi /path/to/driver.msi
   ```

See the **[full installation guide](docs/installation.md)** for prerequisites,
offline setup, Bluetooth configuration, and updates.

## Documentation

All guides live in **[`docs/`](docs/)**:

- [Installation guide](docs/installation.md)
- [Current limitations](docs/limitations.md)
- [Known issues and remaining work](docs/known-issues.md)
- [Updates](surface/UBLUE-UPDATES.md)
- [Build & release guide](surface/RELEASING.md) · [Contributing](CONTRIBUTING.md)

## Components

- [azurefin-linux](https://github.com/Xelef2000/azurefin-linux) — kernel RPM.
- [azurefin-packages](https://github.com/Xelef2000/azurefin-packages) — touch
  input, hardware integration, and firmware extraction tools.

## Credits

Hardware support draws on [nix1e](https://github.com/orvitpng/nix1e),
[ELLX-Kernel](https://github.com/ProgrammerIn-wonderland/ELLX-Kernel),
[linux-surface](https://github.com/linux-surface),
[Alex Lentz's iptsd fork](https://github.com/alex-lentz/iptsd), and
[Bryce Hoehn's Surface Laptop 7 work](https://github.com/bryce-hoehn/linux-surface-laptop-7).
Firmware tooling uses Qualcomm's
[qca-swiss-army-knife](https://github.com/qca/qca-swiss-army-knife).
Microsoft provides the Surface driver MSI. Azurefin-specific calibration,
integration, and fixes are maintained in the repositories above.

## License

Apache 2.0 — see [LICENSE](LICENSE).
