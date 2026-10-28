# Firmware store integration status

This testing branch uses the persistent store for `azurefin-setup-firmware`.
Older releases may still use private-image provisioning. Automatic OS updates
remain disabled pending signed staging and rollback validation.

The release base includes a generic dracut module and a deterministic manifest
of approved firmware hashes. It does not include Microsoft-extracted firmware,
a machine UUID, or a Bluetooth address. The manifest is generated from the
image's firmware policy before the initramfs is built.

When a locally configured `azurefin.boot_uuid=` argument is present, the loader
discovers that ext4 boot filesystem before udev coldplug and mounts it read-only
without journal replay. It looks for `/azurefin/firmware/<manifest-sha256>`,
copies bounded regular files into RAM, verifies their hashes, then exposes the
verified directory through the kernel firmware search path. The runtime copy
survives switch-root. Without the argument, the loader does nothing; this is
required for firmware-free installer boots.

`firmware_bundle.py` is a low-level provisioning helper, not an end-user setup
command. Its caller must validate the boot mount and root-owned parent paths
and serialize writes. It publishes complete bundles atomically and preserves
older versions for rollback. Do not remove an old bundle just because a newer
image uses a different manifest.

## Validation and remaining gates

The generic loader has passed local hardware boot, rollback and return tests.
The release-recipe wiring is covered by source-level regression tests. A fresh
local ARM64 release-base build passed bootc lint (14 checks, one skipped),
the complete 85-layer audit and unpacked initramfs audit. Its loader and
manifest matched the reviewed sources. This is not yet a signed candidate or
a hardware test of that fresh image.

Before enabling normal public-image updates:

- Validate fresh-install download and offline MSI setup. The setup helper now
  validates the boot mount, serializes provisioning, preserves local boot-device
  selection and checks boot and extraction space.
- Check required bundles before staging and define recovery for missing or
  corrupt firmware. Currently the initramfs logs failure and creates
  `/run/azurefin-firmware.failed`; it does not provide a complete recovery UI.
- Verify signed registry-to-bootc staging, reboot and rollback, including a
  changed kernel and changed firmware policy.
- Install and test native signature enforcement as a separate migration step.
- Evaluate desktop and automatic updates only after these gates pass.

On 2026-10-28, provisioning from the installed firmware and booting a clean
candidate passed: all 11 files verified, battery reporting and Wi-Fi worked,
and no system services failed. The candidate had no Microsoft firmware fallback
and GNOME Software was absent. This was a local unsigned OCI test, not signed
OTA validation. The working private deployment remains pinned for recovery.

Tests: from `surface/`, run `python3 -m unittest test_firmware_bundle
test_firmware_store_probe test_firmware_loader test_firmware_store_build`
(as one command).

### Read-only migration diagnostic

`sudo python3 surface/firmware_preflight.py` (from a checkout) checks the booted
image's policy and manifest, a separate writable ext4 `/boot`, the matching
local boot UUID argument, root-owned store directories, all required firmware
hashes and a conservative 512 MiB free-space floor. It prints JSON and returns
nonzero on failure; it never deletes, provisions, stages or reboots anything.
It is installed at `/usr/libexec/azurefin/firmware_preflight.py`. Its eight
unit tests run with `python3 -m unittest test_firmware_preflight` from `surface/`.

A pass is not evidence of signature enforcement or compatibility with a future
image. Target-image policy checks, sizing for the actual deployment, locking
and recovery must still be integrated before enabling unattended updates.
