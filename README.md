# azurefin

A custom [bootc](https://containers.github.io/bootc/) / [rpm-ostree](https://coreos.github.io/rpm-ostree/) image for the **Microsoft Surface Laptop 7 (ARM, Snapdragon X Elite / X1E80100)**, built on top of [Fedora Silverblue](https://fedoraproject.org/silverblue/).

The image bakes everything the hardware needs directly into the container — kernel, firmware, touchscreen driver, and power management — so the resulting system is fully immutable and self-updating via `bootc`.

---

## Why no pre-built ISO?

Two reasons pre-built images are not published right now:

1. **Firmware redistribution.** The image bakes in firmware extracted from Microsoft's official Surface Windows update package at build time. Redistributing that firmware as part of a downloadable image would violate Microsoft's terms. You need to build the image yourself, which downloads the firmware directly from Microsoft during the build.

2. **Cross-architecture ISO limitation.** [bootc-image-builder](https://github.com/osbuild/bootc-image-builder) cannot yet produce installer ISOs for a target architecture different from the build host. Building an `aarch64` ISO currently requires either a native ARM64 machine or a full `qemu-system-aarch64` environment. QCOW2 and RAW disk images have the same constraint for full builds.

If you have access to native ARM64 hardware (another device, a cloud instance), you can build and install from there. See [Installation](#installation) below.

---

## What's included

| Component | What it does |
|---|---|
| [ELLX Kernel](https://github.com/ProgrammerIn-wonderland/ELLX-Kernel) (`7.0-sl7` branch) | Upstream Linux with Surface Laptop 7 patches merged, built for `aarch64` |
| Microsoft Surface firmware | DSP, GPU, battery manager, and modem blobs extracted at build time from the official Windows update MSI |
| [ath12k board-2.bin fix](https://git.codelinaro.org/clo/ath-firmware/ath12k-firmware) | Patched WiFi board data file adding the SL7 subsystem device ID so the WCN7850 adapter is recognised |
| [iptsd](https://github.com/alex-lentz/iptsd) | Touchscreen / stylus daemon (alex-lentz fork with SL7 support) |
| [cpu-parking module](https://github.com/scuggo/x1e-nixos) | Kernel module that parks the efficiency cores on the Snapdragon X Elite, reducing idle heat |
| Display resume fix | Sleep hook that force-switches VTs on resume to wake the display |
| Trackpad resume fix | Sleep hook that restarts `iptsd` after suspend/resume |
| EC reboot utility | `ec-reboot` command — resets the embedded controller to unfreeze a stuck keyboard or trackpad |

---

## Building

### Prerequisites

Install on your build host (Fedora recommended):

```bash
sudo dnf5 install podman just
```

For building the image from an x86_64 host (cross-compilation is handled automatically inside the build):

```bash
# The kernel build script detects the host arch and installs the cross-compiler
# automatically — no manual setup needed.
just build
```

This produces a `linux/arm64` OCI container image tagged `localhost/azurefin:stable`.

The build takes roughly **20–40 minutes** on a modern x86_64 machine, most of which is kernel compilation via the `aarch64-linux-gnu-` cross-toolchain.

### Build a disk image (QCOW2 or RAW)

Requires a native `aarch64` host, or an `aarch64` QEMU VM (see below):

```bash
just build-qcow2   # QCOW2 for QEMU/testing
just build-raw     # RAW disk image for dd-to-disk installs
```

### Build an ISO installer

Requires a native `aarch64` host:

```bash
just build-iso
```

> **Why not on x86\_64?** `bootc-image-builder` explicitly refuses to build ISOs for a different architecture than the host. See [Why no pre-built ISO?](#why-no-pre-built-iso) above.

---

## Installation

### Option A — `bootc install` from a live environment (recommended)

Boot the Surface Laptop 7 with any ARM64 Fedora live image, then run:

```bash
# Install directly from the container image
sudo bootc install to-disk --target-imgref <registry>/azurefin:stable /dev/nvme0n1
```

Replace `<registry>/azurefin:stable` with wherever you've pushed your built image (e.g. `ghcr.io/yourname/azurefin:stable`), or with `localhost/azurefin:stable` if the live environment has the image available locally.

### Option B — Switch from an existing Fedora Atomic install

If you already have Fedora Silverblue or Bluefin running on the device:

```bash
sudo bootc switch <registry>/azurefin:stable
sudo systemctl reboot
```

### Option C — Build on a native aarch64 host

Clone this repo on any ARM64 Linux machine (another SL7, a Raspberry Pi 5, an AWS Graviton instance, etc.) and run:

```bash
just build-iso    # produces output/bootiso/install.iso
```

Then write the ISO to a USB drive and boot the Surface from it.

---

## ujust commands

After installation, these commands are available in a terminal:

| Command | Description |
|---|---|
| `ujust rebuild-initramfs` | Regenerate the initramfs (rarely needed) |
| `ujust ec-reboot` | Reset the embedded controller — fixes a stuck keyboard or trackpad |

---

## Project structure

```
build/
  10-build.sh        — copies custom files, installs base packages
  12-firmware.sh     — downloads and installs Surface firmware at build time
  15-kernel.sh       — builds and installs the ELLX kernel + cpu-parking module
  18-cpu-parking.sh  — no-op (module is built inside 15-kernel.sh)
  20-iptsd.sh        — builds iptsd from source

custom/
  etc/               — /etc overrides (GRUB config, module autoload)
  lib/               — systemd sleep hooks (display and trackpad resume fixes)
  usr/
    libexec/ec_reboot.py   — EC reset implementation
    local/bin/ec-reboot    — wrapper script
    src/cpu-parking/       — cpu_parking kernel module source
  ujust/             — ujust command definitions
  flatpaks/          — Flatpaks installed on first boot
  brew/              — Homebrew Brewfiles

iso/
  iso.toml           — bootc-image-builder ISO configuration
  disk.toml          — bootc-image-builder disk image configuration
```

---

## Credits

This project stands on the work of many upstream projects:

- **[Fedora Silverblue](https://fedoraproject.org/silverblue/)** — base image (multi-arch, arm64 + amd64)
- **[Universal Blue](https://universal-blue.org/)** and **[Bluefin](https://projectbluefin.io/)** — build system architecture inspiration and the finpilot template this repo started from
- **[ProgrammerIn-wonderland / ELLX-Kernel](https://github.com/ProgrammerIn-wonderland/ELLX-Kernel)** — the `7.0-sl7` kernel branch with Surface Laptop 7 patches
- **[Microsoft](https://www.microsoft.com/en-us/surface)** — Surface Laptop 7 firmware, downloaded directly from the official Windows update package at build time
- **[Qualcomm / ath12k-firmware](https://git.codelinaro.org/clo/ath-firmware/ath12k-firmware)** — upstream WCN7850 `board-2.bin` used as the base for the WiFi board data fix
- **[qca-swiss-army-knife](https://github.com/qca/qca-swiss-army-knife)** — `ath12k-bdencoder` tool used to patch `board-2.bin`
- **[alex-lentz / iptsd](https://github.com/alex-lentz/iptsd)** — touchscreen daemon fork with SL7 support (itself based on [linux-surface/iptsd](https://github.com/linux-surface/iptsd))
- **[linux-surface](https://github.com/linux-surface)** — Surface Linux project, source of many hardware workarounds and fixes
- **[scuggo / x1e-nixos](https://github.com/scuggo/x1e-nixos)** — source of the `cpu_parking` kernel module for Snapdragon X Elite
- **[bootc](https://github.com/containers/bootc)** — the image-based update system the whole thing is built on
- **[bootc-image-builder](https://github.com/osbuild/bootc-image-builder)** — converts the OCI container image into installable disk images and ISOs

---

## Community

- [Universal Blue Discord](https://discord.gg/WEu6BdFEtp)
- [linux-surface Matrix / GitHub](https://github.com/linux-surface/linux-surface)
- [bootc discussions](https://github.com/containers/bootc/discussions)
