# Current limitations

Azurefin is an experimental, alpha-stage project. Known limitations as of the
current testing image:

For version-specific status, workarounds and deferred work, see the
[known-issues list](known-issues.md).

- **Updates on older ISOs.** Scheduled updates are enabled in the
  `v0.0.12-alpha` testing image; older release ISOs do not acquire the new
  defaults until updated. Do not switch to an image that lacks the loader or
  requires an unprovisioned firmware bundle. See
  [update requirements and validation](../surface/UBLUE-UPDATES.md).
- **Firmware setup is not an OS updater.** It uses the currently installed
  image's firmware policy.
- **Firmware-free first boot** — especially encrypted-root unlock — still needs
  hardware validation before release.
- **Suspend and wake.** Suspend battery drain and intermittent device
  initialization still need work. Use the power button to wake from deep sleep;
  waking with ordinary keyboard keys is not supported.
- **Camera.** Capture works, but colour and flicker tuning remain incomplete.
- **Speakers.** Output uses conservative gain limits; full thermal protection is
  not validated. Keep the supplied audio profiles and kernel limits.
- **Secure Boot** is not supported by the current unsigned kernel.
- **15-inch model** is not validated. Only the 13-inch model has been tested.
