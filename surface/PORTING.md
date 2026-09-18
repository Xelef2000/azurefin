# Romulus migration status — 2026-09-18

Target: Surface Laptop 7 **13-inch, 16 GB**, Fedora 44 aarch64.
This is a staging port; do not replace the working pmOS installation yet.
No Surface SSH access, reboot, disk write or on-device change was made.

## Build split

- azurefin-linux: kernel-azurefin, existing xelef2000/azurefin-kernel COPR.
- azurefin-packages: IPTSD, Romulus integration, firmware extraction tools.
- azurefin: Containerfile.romulus assembles those packages separately from the
  old ELLX/source-build path. Existing local changes remain intact.

The new Containerfile currently uses Fedora Silverblue 44, matching the existing
project's Fedora base while updating it from 42. It is not yet a complete Bluefin
userspace integration. Select and pin a verified ARM64 Bluefin base in a separate
step; do not silently substitute CentOS packages for Fedora 44 RPMs.

## Checklist

- [x] Import the 24 pmOS 7.2-r14 kernel patches and config with provenance.
- [x] Build the initial kernel source RPM; checksum of upstream archive matches pmOS.
- [x] Apply all 24 patches to the exact source. RPM preparation needs the same
  context fuzz allowance as Alpine. Local full preparation is blocked by missing
  lld; build dependencies are declared for COPR.
- [x] Preserve machine-driver PA/digital gain limits with source assertions.
- [x] Package the separately retained IPTSD r4 driver-handoff fix and calibration.
- [x] Port the child-only stop/unbind/rebind suspend hook; do not restart in place.
- [x] Package input udev rules and Bluetooth provisioning without a device MAC.
- [x] Translate early display/input module list into generic dracut configuration.
- [x] Provide local-only verified MSI extraction and board-data alias helper.
- [x] Keep internal audio disabled during bring-up; retain UCM as reference files.
- [x] Build integration and firmware-tools noarch RPMs locally.
- [ ] Configure COPR API access locally (not in Git or chat).
- [ ] Create the three custom-package COPRs; kernel COPR already exists.
- [ ] Build kernel and IPTSD binaries in Fedora 44 aarch64; resolve build failures.
- [x] User approved committing/pushing testing branches and creating the package repository.
- [ ] Assemble the experimental image and run bootc container lint.
- [ ] Verify every required driver and firmware file in the generated initramfs.
- [ ] Wire and verify Romulus13 DTB selection through the actual installer/bootloader.
- [ ] Carry over early EFI display selection and encrypted-unlock behavior.
- [ ] Verify kernel arguments (initially retain clk_ignore_unused/pd_ignore_unused);
  never reuse pmOS root UUIDs or boot-device identifiers.
- [ ] Validate Secure Boot policy/signing separately; do not claim signed support.
- [ ] Test only on external storage first: unlock, display, Wi-Fi, input, USB,
  charging, Bluetooth, suspend/resume, SELinux AVCs and idle/sleep battery draw.
- [ ] Validate Fedora UCM routing and gain limits before enabling speaker playback.
- [ ] Review firmware redistribution permission before any public image push.

## Local image assembly, after COPR builds pass

Use Podman on a native ARM64 machine or with explicitly configured emulation:

    podman build --platform linux/arm64 -f Containerfile.romulus \
      --secret=id=surface-msi,src=/path/to/SurfaceLaptop7_ARM_Win11_26100_26.053.36539.0.msi \
      -t localhost/azurefin:romulus-testing .

The MSI is not committed or uploaded to COPR. Extracted firmware DOES remain
in the resulting image; using a secret mount does not make that image suitable
for redistribution. This new path is not connected to the automatic push workflow.

The extraction helper retains its temporary directory for local diagnosis.
The Containerfile runs it with a temporary /tmp mount, so MSI extraction debris
does not enter the final image layer.

## References

- COPR policy: https://docs.copr.fedorainfracloud.org/user_documentation.html
- bootc initramfs contract:
  https://github.com/bootc-dev/bootc/blob/main/docs/src/initramfs.md
- pmOS baseline: pmaports 1ff232fcf1659952054ac0384dfc0e0b83041aa6.
- IPTSD startup fix: pmaports e585b65b372075f5895733ceb39104e25087b92b.
