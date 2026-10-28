# System Update and Bazaar

Azurefin uses Universal Blue's packaged `uupd`, without forking its update
engine. Bazaar replaces GNOME Software for Flatpak applications; bootc handles
signed OS downloads and deployments.

The next image enables scheduled updates. The service configuration has been
tested and enabled on the development Surface; published images through
`v0.0.11-alpha` still default to disabled scheduled updates.

## Bazaar on fresh installations

The image schedules Bazaar setup shortly after boot. It configures Flathub
and runs the upstream `flatpak preinstall` command. Downloads happen on the
installed system, not during image construction. If the machine is offline,
setup retries every 15 minutes without blocking boot or firmware preparation.
The check repeats even after a successful exit: Flatpak can return success
after skipping an unreachable remote. Already-preinstalled apps are skipped,
and user removal is respected by Flatpak's preinstall mechanism.

The automatic setup is skipped in the nonpersistent live session to avoid
downloading runtimes that would disappear at reboot. GNOME Software is removed
from the image, so the live session has no preinstalled app store. You can
install Bazaar manually in either environment with the commands below.

To retry immediately after connecting, run:

```sh
sudo systemctl restart azurefin-flatpak-preinstall.service
```

Check progress with `journalctl -u azurefin-flatpak-preinstall.service`.
Automatic system-wide Bazaar installation passed the fresh-install hardware
test. A rebuilt clean candidate also booted with GNOME Software absent and
Bazaar still installed.

## Try Bazaar manually

After connecting to the internet, run as your desktop user:

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub io.github.kolunmi.Bazaar
```

Open **Bazaar** from the application menu. It installs Flatpak applications;
it does not update the operating system. Its initial download includes a
GNOME runtime. Offline firmware installation does not require Bazaar.

## Manual system updates

Open **System Update**, or run `ujust update` (`ujust upgrade` is an alias).
Following Bluefin's manual recipe, this calls upstream `bootc upgrade`, then
updates system/user Flatpaks and Homebrew packages owned by the desktop user.
It requests sudo authentication for OS staging and never reboots automatically.

Azurefin adds a preflight under the firmware setup lock. It requires an installed
system following the signed `:testing` channel, no pending deployment/rollback or
development overlay, a verified firmware store, at least 768 MiB free on `/boot`
and 10 GiB on `/var`, and matching target firmware contract metadata. It never
deletes pinned deployments to recover space. After staging an OS update, reboot
before running another update. Bazaar can still update apps independently.

This is not a replacement update engine: bootc still performs downloads,
signature enforcement and deployment. The target-metadata check is an early
compatibility check, not a substitute for signature verification.

## Scheduled updates

`uupd.timer` runs at midnight, 06:00, noon and 18:00 with up to ten minutes
of random delay. Its persistent timer can catch up after downtime. The service
requires AC power and upstream hardware checks. The configured thresholds are
20% minimum battery, 50% maximum CPU, 90% maximum memory and 700000 bytes for
network activity. A skipped run can be retried at the next scheduled time.

OS, Flatpak and Homebrew updates are enabled; Distrobox updates remain disabled.
Separate Homebrew update timers are disabled to avoid duplicate scheduling;
initial Homebrew setup remains enabled. The independent bootc auto-apply service
and timer remain masked. Neither update entry point uses `--apply` or reboots
automatically.

Both the timer and service exclude live sessions. Manual OS updates also reject
live sessions in the preflight. Complete persistent firmware setup and reboot
before updating. A failed preflight stops the combined run before updating OS
or apps; Bazaar remains available independently.

Inspect the schedule and results:

```sh
systemctl list-timers uupd.timer
journalctl -u uupd.service
```

Pause scheduled updates with `sudo systemctl disable --now uupd.timer`.
Re-enable them with `sudo systemctl enable --now uupd.timer`. This does not
cancel a running update. Older installations with a masked timer or locally
modified `/etc/uupd/config.json` may retain those overrides across image
updates; enabling the timer alone does not enable its OS module.

Channel promotion verifies both release signatures and checks firmware-bundle
and loader-ABI labels against `surface/update-contract.json`. Builds reject a
firmware manifest that differs from that contract. Changing required firmware
needs an explicit provisioning/channel transition plan. The authorized image
publisher and channel publication remain trusted parts of this design.

## Persistent firmware

### Fresh-install update source

The next installer retains `ostreecontainer` with the local OCI payload, then
runs `bootc switch --mutate-in-place --transport registry
--enforce-container-sigpolicy ghcr.io/xelef2000/azurefin:testing` in its chrooted
Anaconda `%post` hook. This changes only the deployment's future update origin:
no registry access, replacement deployment or reboot is needed. A failed hook
fails the installation. Both installer configurations are tested against the
channel in `surface/update-contract.json` to prevent drift.

This uses bootc 1.17.1's installer-specific
[in-place switch implementation](https://github.com/bootc-dev/bootc/blob/v1.17.1/crates/lib/src/deploy.rs#L1423),
not a manual origin-file editor. It configures signature enforcement for future
registry pulls; it does not retroactively authenticate the offline installation
payload, which remains covered by the media audit and checksum verification.
Firmware preflight still prevents updates before provisioning is complete.

A disposable ARM64 container with networking disabled confirmed that bootc
1.17.1 writes `ostree-image-signed:docker://ghcr.io/xelef2000/azurefin:testing`.
This used a synthetic deployment directory, not the Surface's disk. Full
Anaconda installation, first-boot origin verification and offline firmware
setup still need testing on rebuilt media. Do not run this installer-only
command manually on an existing multi-deployment installation.

### Provisioning

`azurefin-setup-firmware` provisions the independent firmware store on the
separate ext4 `/boot` filesystem. Use `--download` for online setup or
`--msi PATH` for offline extraction; `--bluetooth-address MAC` is optional.
Verified versioned bundles remain across OS updates and rollback. Setup neither
switches images nor reboots. See the [installation guide](../README.md).

## Known updater limitation

The pinned `uupd-1.5.0-1.fc44.aarch64` package does not honor `--dry-run` in its
OS updater. **Do not use `uupd --dry-run` with the system module enabled:** it
can stage a real update. Normal updates do not depend on dry-run support.
The regression was reproduced safely using a fake bootc executable, and the
[upstream fix](https://github.com/ublue-os/uupd/pull/207) has been merged.
Adopt the official fixed package after it is available and validated;
Azurefin does not ship a temporary fork. Neither shipped update entry point
passes `--dry-run`.

## Hardware validation (2026-10-28)

- Signed staging, boot, rollback and return passed with the persistent firmware
  store; all 11 firmware hashes verified and Wi-Fi remained functional.
- `v0.0.11-alpha` booted with native signature enforcement. Its preflight passed,
  including the deployed terminal-output parsing fix. Approved removal of
  obsolete test deployments recovered boot space without lowering the threshold.
- `ujust update` completed successfully with the channel already current.
- The real upstream OS module ran `bootc upgrade` successfully against the
  current channel. A forced check exercised that command even without a newer
  image; it did not bypass signature, firmware or hardware checks, or stage a
  deployment.
- The scheduled service completed with OS, Homebrew and Flatpak modules enabled.
  AC conditions, lock contention, hardware checks and calendar parsing were
  checked. The timer is enabled on the development Surface.
- Bazaar offline retry, successful installation and respect for user removal
  passed. Automatic system-wide setup also passed on a fresh installation.

Still to validate: a new image built with these scheduling defaults, an actual
new-version deployment initiated by the scheduled service, and physical
battery-only/suspend-resume scheduling. The service test above was invoked
explicitly, not by waiting for a calendar event. This configuration change
does not itself publish an image.

## Upstream provenance

- [Universal Blue uupd](https://github.com/ublue-os/uupd/tree/v1.5.0), packaged by
  [ublue-os/packages](https://github.com/ublue-os/packages/tree/main/packages/uupd).
- [Bluefin shared configuration](https://github.com/projectbluefin/common):
  the uupd configuration, systemd units, manual recipe and Bazaar definition.
- [Bluefin administration guide](https://docs.projectbluefin.io/administration/).

Azurefin adds Surface firmware compatibility/space checks and delayed Flatpak
setup for offline installations. Microsoft-extracted firmware, device identifiers
and credentials are not included in public images.
