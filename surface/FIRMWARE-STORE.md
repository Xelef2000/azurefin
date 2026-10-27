# Firmware store integration status

This is an opt-in development path, not yet a replacement for
`azurefin-setup-firmware` or the tested private-image updater.

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
The release-recipe wiring is covered by source-level regression tests, but a
fresh release-base build and complete layer/initramfs audit are still required.

Before enabling normal public-image updates:

- Add supported installation/migration, including boot mount validation,
  provisioning locks, persistent local boot-device selection and space checks.
- Check required bundles before staging and define recovery for missing or
  corrupt firmware. Currently the initramfs logs failure and creates
  `/run/azurefin-firmware.failed`; it does not provide a complete recovery UI.
- Verify signed registry-to-bootc staging, reboot and rollback, including a
  changed kernel and changed firmware policy.
- Install and test native signature enforcement as a separate migration step.
- Evaluate desktop and automatic updates only after these gates pass.

Automatic updates remain masked. Existing post-install provisioning still
creates a private firmware-enabled image; this integration does not silently
change that workflow or modify existing deployments.

Tests: from `surface/`, run `python3 -m unittest test_firmware_bundle
test_firmware_store_probe test_firmware_loader test_firmware_store_build`
(as one command).
