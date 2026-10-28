# Universal Blue updater and Bazaar preview

This testing branch packages Universal Blue's `uupd` without forking its
update engine. Bazaar replaces GNOME Software as the application store.
This is not yet the final System Update interface.

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
test. The image change removing GNOME Software still needs a rebuilt-image test.

## Try Bazaar manually

After connecting to the internet, run as your desktop user:

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub io.github.kolunmi.Bazaar
```

Open **Bazaar** from the application menu. It installs Flatpak applications;
it does not update the operating system. Its initial download includes a
GNOME runtime. Offline firmware installation does not require Bazaar.

The preview image adds **Application Updates (Preview)** for manual Flatpak
and Homebrew updates using upstream `uupd`. It does not reboot, update the OS,
or enable an automatic update timer. Distrobox updates are disabled, matching
Bluefin's configuration. Existing Homebrew timers are unchanged in this preview;
they must be consolidated before enabling scheduled `uupd` updates.

## Before enabling full System Update

### Persistent firmware candidate

The next test image includes `azurefin-setup-firmware-store`. This is an
explicit test path; `azurefin-setup-firmware` still uses the previous private
image workflow until the new path passes its hardware gates.

On an installed system with no pending update or rollback:

```sh
# Reuse the verified firmware in an existing private deployment:
sudo azurefin-setup-firmware-store --from-installed
# Or extract directly into a staging directory, without rebuilding the OS:
sudo azurefin-setup-firmware-store --download
```

`--msi PATH` supports offline extraction, and `--bluetooth-address MAC` remains
optional. Setup verifies the image's policy, the separate ext4 boot mount,
available boot space and all copied firmware. It keeps versioned bundles for
rollback and opts into the existing early-boot loader only after verification.
It neither switches the OS image nor enables updates or reboots. Download and
extraction workspaces are retained under `/var/lib/azurefin` for diagnosis.

Next gates: test setup on hardware, boot a clean candidate without GNOME
Software using that store, then verify signed standard updates and rollback.
Only after those pass should this replace the default setup command and the
upstream update schedule be enabled.

### Update enablement gates

- Verify the prepared Flatpak preinstallation on a fresh install, including
  delayed connectivity after offline firmware provisioning and user removal.
  Automatic installation passed; verify the app-store-free live session after
  rebuilding with GNOME Software removed.
- Make the tested versioned `/boot` firmware store the fresh-install default.
  The current setup tool still creates a private firmware-inclusive image.
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
All 145 local Surface tests pass. Automatic OS updates remain disabled.
