# Universal Blue updater and Bazaar preview

This testing branch packages Universal Blue's `uupd` without forking its
update engine. GNOME Software remains installed while Bazaar is evaluated.
This is not yet the final System Update interface.

## Try Bazaar

After connecting to the internet (install Surface firmware first if using
built-in Wi-Fi), run as your desktop user:

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

- Test Bazaar launch, browsing, installation and removal on ARM64.
- Add Bluefin-style Flatpak preinstallation, with Flathub configured, and test
  delayed connectivity after offline firmware provisioning. Keep GNOME Software
  until that works on fresh installs and in the live session.
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
  Remove GNOME Software only after its replacement passes the above checks.

## Upstream provenance

- [Universal Blue uupd](https://github.com/ublue-os/uupd/tree/v1.5.0), packaged by
  [ublue-os/packages](https://github.com/ublue-os/packages/tree/main/packages/uupd).
  The preview pins `uupd-1.5.0-1.fc44.aarch64` from that COPR.
- [Bluefin shared configuration](https://github.com/projectbluefin/common):
  `system_files/shared/etc/uupd/config.json`, the `uupd` systemd units, and
  `system_files/bluefin/usr/share/flatpak/preinstall.d/bazaar.preinstall`.
- [Bluefin administration guide](https://docs.projectbluefin.io/administration/).

Azurefin's temporary differences are intentional: the system module and timer
are disabled, Bazaar is installed explicitly for testing, and GNOME Software
is retained. No Microsoft firmware, device identifiers or credentials belong
in this integration.
