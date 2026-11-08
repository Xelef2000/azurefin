# Known issues and remaining work

Last reviewed: **2026-11-07**, against the hardware-tested **v0.0.31-alpha**
testing-channel image on a Surface Laptop 7 **13-inch, 16 GB**. An older ISO
may contain different fixes. This list distinguishes reported problems from
features that have not been validated; it is not a promise of support on all
Snapdragon X Elite devices.

## Open hardware issues

| Area | Status and impact | Current guidance |
| --- | --- | --- |
| Idle/light-use power | Open: matching Windows battery life remains a goal, not an achieved result. | Compare controlled measurements at the same brightness and refresh rate; no battery-life guarantee. |
| Suspend power | Open: excessive sleep drain has been reported. Long-duration suspend still needs validation after kernel changes. | Shut down for long periods when preserving charge matters. |
| Keyboard wake | Deferred: ordinary keys do not reliably wake deep sleep. | Use the power button. Lid wake has worked in tests but is not a universal guarantee. |
| Clock / UEFI RTC | Currently fails to write rtc clock offsets back to the uefi| Network time can correct the running system; persistent RTC handling needs further work. |
| Camera quality | The integration candidate improves processing; GNOME Camera, Firefox and Brave previews/reopen passed on a local image. Published-package boot, GNOME Camera and Brave checks also passed; broader lighting tests remain pending; about 18.8 fps and buffer warnings are unresolved. | Treat camera support as experimental; see [camera validation](../surface/CAMERA-TESTING.md). |
| Speaker protection | Conservative gain limits are retained; complete thermal protection is not validated. | Keep the supplied profiles and kernel limits. Do not bypass protection or raise hardware gains for testing. |

## Support and validation gaps

- **Secure Boot:** not supported by the current kernel setup; disable it for
  installation and boot.
- **Other hardware:** the 15-inch model and higher-memory configurations are
  not validated. General X1 Elite support does not establish device-specific
  regulator, firmware, suspend or audio correctness.
- **Bluetooth factory address:** automatic read-only discovery was validated
  on the 7.2 baseline. The module is retained in 7.4, but a fresh discovery test
  on that kernel remains outstanding. Manual address entry remains supported.
- **Nix runtime maintenance:** OS updates preserve an initialized store but do
  not automatically upgrade its Nix runtime or garbage-collect it. An uncertain
  interrupted initialization retains data and requires guided repair.
- **Nix desktop integration:** Home Manager users should enable
  `targets.genericLinux.enable = true` and log out/in for GNOME launchers.
  No legacy Nixpkgs channel is configured by default. See the
  [Nix guide](../surface/nix/USER-GUIDE.md).
- **Boot partition space:** old pinned deployments can fill `/boot` and block
  safe updates. Review retained deployments rather than bypassing the space
  check or deleting boot files manually.

## Fixed or currently passing — watch for regressions

- **7.4-rc1 speaker resume:** the initial regression was followed by successful
  speaker-after-suspend tests with `kernel-azurefin-7.4~rc1-2.0.1.fc44.aarch64`.
  This exact RPM is used by v0.0.31-alpha. Long-term reliability is not proven.
- **Touchpad/touchscreen:** working in the recent hardware tests. Earlier
  pointer loss and gesture problems should not be treated as confirmed current
  failures; report recurrences with the exact kernel and suspend history.
- **Nix persistence:** initialization, sandboxed builds, reboot and image-update
  persistence passed on the Surface with SELinux enforcing.
- **Firmware persistence:** firmware-store checks passed across the tested
  image updates. Firmware installation is separate from OS updating.

## Reporting a problem

Use the [Azurefin issue tracker](https://github.com/Xelef2000/azurefin/issues).
Include your model, OS version, `uname -r`, whether it followed a fresh boot or
suspend, and reproducible steps. For audio, do not increase gain or run loud
test tones to reproduce a failure. Review logs for personal information before
uploading; never attach encryption passwords, private keys or extracted firmware.

See also [installation limitations](limitations.md) and
[update requirements](../surface/UBLUE-UPDATES.md).
