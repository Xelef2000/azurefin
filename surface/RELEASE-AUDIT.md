# Release content policy

Fedora's redistributable firmware is allowed. Microsoft MSI archives,
Microsoft-extracted Surface firmware, and personal configuration are not.
The term “firmware-free” in older scripts means **Microsoft-extracted-firmware-free**,
not absence of Fedora's linux-firmware packages.

## Tested artifacts, 2026-10-07

- Base image ID: `c43d62be7510e7da5c5eda06caca74cb26f6df188ec570aff445a3d555e279ba`.
- Installer image ID: `920aa2fbf85329c96d8ccb9369fe7f5870c558eeee3a9b7fcce34aeb5f23d009`.
- The content audit passed across all 69 base layers and all 81 installer
  layers, including files hidden or deleted by later layers.
- The installer was reported to boot and install successfully on Romulus13.
  Earlier offline-MSI and Ethernet-download provisioning tests also succeeded.

This result applies to those images, not arbitrary future builds or the whole
external test SSD. That SSD contains private MSI downloads and provisioned
payloads; never publish a clone of it.

## Shared metadata exception

Five tiny JSON files in the MSI are byte-identical to files shipped by Fedora:
`adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn`, and `cdspr.jsn`.
Their SHA-256 values and installed bytes match the RPM file records for
`qcom-firmware-20260916-1.fc44.noarch`, below
`/usr/lib/firmware/qcom/x1e80100/LENOVO/21N1/`.
The RPM identifies Fedora as vendor and records signing key
`dbfcf71c6d9f90a6`. Verification showed timestamp differences, not digest
differences. These shared metadata hashes are explicitly recorded as
`fedora_shared_metadata` in the policy. The Microsoft destination directory
remains forbidden even for these files.

The authoritative policy is in
`azurefin-packages/firmware/SOURCES/firmware-policy.json`. Keep its audit copies
at `azurefin/surface/firmware-policy.json` and
`azurefin-linux/SOURCES/firmware-policy.json` identical. Review provenance
before adding any shared metadata exception; never exempt device firmware
merely to make a build pass.

## Release gates and limitations

`scripts/audit-release.py` checks OCI descriptor digests, every layer's file
paths and known extracted-file hashes, and rejects known private image labels.
It also rejects MSI filenames, Bluetooth address configuration, SSH keys,
NetworkManager connection profiles, COPR credential files and signing keys.
Package builds audit their staged sources; RPM checks reject installed firmware
directories, and the kernel requires an empty CONFIG_EXTRA_FIRMWARE.

This is a targeted technical check, not a license opinion or a universal
secret detector. Nested archives (including initramfs and SquashFS) need their
own unpacked-content audit before publishing an ISO. Existing initramfs
build checks also reject Microsoft paths in the live installer.
Do not publish ISO artifacts until that final artifact gate is integrated.
The prototype workspace layout must also be generalized before an unattended
release compose can replace the locally prepared installer.

The legacy top-level Containerfile and all locally provisioned images remain
private build paths. Automatic publication must use only the audited clean
packages stage and an installer derived from that stage.
