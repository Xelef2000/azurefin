# System Update and Bazaar

This testing branch packages Universal Blue's `uupd` without forking its
update engine. Bazaar replaces GNOME Software as the application store.
The development branch adds the System Update interface described below. It is
not yet included in the tested `v0.0.9-alpha` image.

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

## Scheduling safeguards (not enabled yet)

The prepared systemd drop-ins use Bluefin's six-hour schedule with ten minutes
of jitter, AC-power and live-session conditions, upstream uupd hardware checks,
and the same firmware lock/preflight as manual updates. They never use `--apply`.
`uupd.timer` remains masked and its system module disabled until hardware tests
pass. Existing Homebrew timers remain unchanged for now; disable those overlapping
timers when scheduled uupd is enabled, not before. Distrobox updates remain off.

Channel promotion verifies both release signatures and then checks the candidate's
firmware-bundle and loader-ABI labels against `surface/update-contract.json`.
The build rejects a firmware manifest that differs from this contract. Images
without labels (including v0.0.9-alpha) cannot pass the new promotion/preflight
gate; a new signed candidate is required to test this workflow. Do not change
the existing channel's contract casually: different required firmware needs a
provisioning/channel transition plan. Registry/channel publication and the
release workflow remain trusted parts of this design; this is not protection
against a malicious authorized publisher.

## Before enabling full System Update

### Persistent firmware setup

This branch routes `azurefin-setup-firmware` to the persistent store helper.
`azurefin-setup-firmware-store` remains an alias for the same implementation.
The legacy private-image code remains available internally to the older updater;
it is no longer the default firmware setup entry point.

On an installed system with no pending update or rollback:

```sh
# Reuse the verified firmware in an existing private deployment:
sudo azurefin-setup-firmware --from-installed
# Or extract directly into a staging directory, without rebuilding the OS:
sudo azurefin-setup-firmware --download
```

`--msi PATH` supports offline extraction, and `--bluetooth-address MAC` remains
optional. Setup verifies the image's policy, the separate ext4 boot mount,
available boot space and all copied firmware. It keeps versioned bundles for
rollback and opts into the existing early-boot loader only after verification.
It neither switches the OS image nor enables updates or reboots. Download and
extraction workspaces are retained under `/var/lib/azurefin` for diagnosis.

Hardware setup using `--from-installed` and a subsequent clean candidate boot
passed on 2026-10-28: all 11 firmware hashes verified, the loader exposed
`/run/azurefin-firmware`, battery reporting and Wi-Fi worked, and no system units
failed. The clean candidate contained no Microsoft-extracted firmware fallback.
This local OCI test was unsigned; it does not validate signed OTA updates.
Download and MSI extraction through the new default entry point still need
end-to-end hardware tests. The upstream update schedule remains disabled.

The fresh test installation's read-only firmware preflight also passed, with
1.25 GiB available on `/boot`. Its container policy still has the default
`insecureAcceptAnything` rule and no Azurefin registry override. Native signature
enforcement must be installed and tested on this installation before switching
to signed registry updates; earlier tests on a previous installation do not
establish its current trust configuration. Both `uupd.timer` and
`bootc-fetch-apply-updates.timer` remain masked.

The branch now includes a Bluefin-style native container policy for future
images: Azurefin's repository requires its dedicated OTA key and exact repository
identity, while other development containers remain usable. Isolated native
signature tests passed locally and on the Surface without changing its host
policy. A rebuilt image and signed registry-to-bootc tests are still required.

### Update enablement gates

- Verify the prepared Flatpak preinstallation on a fresh install, including
  delayed connectivity after offline firmware provisioning and user removal.
  Automatic installation passed; verify the app-store-free live session after
  rebuilding with GNOME Software removed.
- Test download and offline MSI setup through the new persistent-store default
  on a fresh installation, including failures and insufficient extraction space.
- Ensure normal updates enforce Azurefin's native signature policy and preserve
  firmware across updates and rollback. Gate firmware-policy changes against
  available local bundles before enabling unattended OS updates.
- Test manual `uupd` OS staging on the signed testing channel, then reboot with
  the user's approval for LUKS unlock.
- Adopt Bluefin's scheduling/AC-power policy; disable overlapping Homebrew,
  rpm-ostree, GNOME Software and bootc automatic updaters.
- Replace the preview launcher with System Update only when OS updates work.

## Upstream provenance

- [Universal Blue uupd](https://github.com/ublue-os/uupd/tree/v1.5.0), packaged by
  [ublue-os/packages](https://github.com/ublue-os/packages/tree/main/packages/uupd).
  The preview pins `uupd-1.5.0-1.fc44.aarch64` from that COPR.
- [Bluefin shared configuration](https://github.com/projectbluefin/common):
  `system_files/shared/etc/uupd/config.json`, the `uupd` systemd units, and
  `system_files/bluefin/usr/share/flatpak/preinstall.d/bazaar.preinstall`.
- [Bluefin administration guide](https://docs.projectbluefin.io/administration/).

Azurefin's temporary differences are intentional: the system module and timer
are disabled, Flatpak preinstallation uses a delayed retry timer for firmware-free
offline boots (and skips the live session).
No Microsoft firmware, device identifiers or credentials belong
in this integration.

## Validation (2026-10-28)

The signed v0.0.9-alpha base was staged with native container-policy enforcement,
booted, rolled back to the previous local candidate, and returned successfully.
All 11 firmware files verified, Wi-Fi and battery reporting worked, and no
system services failed. Promotion to `:testing` and the subsequent channel-based
boot also passed. Automatic update timers remained masked throughout. The USB
Ethernet adapter needed one replug after a reboot; that issue is deferred.

These tests do not yet validate the newly added System Update launcher,
compatibility-label gate or scheduled service. Local validation covers 164
Surface tests plus six promotion-orchestration tests, including rejection before
publication when firmware metadata is missing or incompatible.

An isolated installation on the ARM64 Surface (Flatpak 1.18.4) reproduced a
silent skip when the preinstall definition specified `CollectionID`: a newly
added Flathub remote did not have that ID in its local configuration. The
definition now matches Bluefin's unrestricted preinstall definition.

With the corrected definition and retry behavior, the hardware test passed:

- Offline attempt, then automatic retry and successful Bazaar installation.
- A subsequent periodic preinstall completed without reinstalling the app.
- Removing Bazaar was respected by the next preinstall run.

The test used an isolated user installation, redirected Flatpak configuration
and data directories, temporary user systemd units, a 20-second retry interval,
and a deliberately unreachable proxy to simulate network failure. The normal
user's apps and network settings were not modified. This validates Flatpak and
timer behavior, not a complete fresh-install/system-service test or a new ISO.
Automatic OS updates remain disabled.
