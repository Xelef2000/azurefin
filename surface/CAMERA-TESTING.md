# On-demand camera test image

Promotions and creation of new releases require explicit user permission.
Approval to commit and push these testing branches does not authorize either.

This candidate keeps the v0.0.31-alpha image configuration and changes two
package inputs:

- `kernel-azurefin-7.4~rc1-2.0.2.fc44.aarch64`, built in
  [COPR build 11284730](https://copr.fedorainfracloud.org/coprs/build/11284730).
  It adds v4l2loopback 0.15.3, built against and signed by the same kernel.
- `azurefin-camera-0.1-2.fc44.aarch64`, built in
  [COPR build 11284735](https://copr.fedorainfracloud.org/coprs/build/11284735).
  It contains private libcamera 0.7.2 libraries with ported OV02C10 tuning,
  a GStreamer plugin and v4l2-relayd 0.2.0 under `/usr/lib/azurefin-camera`.

Both builds succeeded. The kernel RPM signature and payload digest were
verified; its loopback module has matching vermagic and the same signing key
as the packaged sensor module. Hardware loading still requires booting it.

The image does not install `azurefin-camera-integration`, enable the service,
load loopback automatically, or change device access and desktop routing.
No claim of improved image quality or negligible full-service idle power is
made until the following hardware checks pass.

## Checks after a signed test-image boot

Keep a known-good deployment pinned and arrange access to the encrypted boot
prompt before rebooting. Verify `uname -r` is
`7.4.0-rc1-azurefin.2.0.2.fc44` and the existing camera still works.

1. Check video42 is unused. Load the temporary device:
   `sudo modprobe v4l2loopback devices=1 video_nr=42 card_label='Surface Camera' exclusive_caps=1 max_buffers=4`.
   Loading must succeed under the existing integrity lockdown.
2. Run `camera/test-loopback.py` from the matching `azurefin-packages` source
   branch as the desktop user. It checks device enumeration without sensor
   activation, three start/stop cycles, a killed consumer, and a 60-second idle
   window with unchanged camera active-time counters and negligible relay CPU.
   It discards frames and cleans up its processes. This harness is prepared
   and syntax checked, but has not yet run on hardware.
3. Compare image quality under fixed lighting and test browser/PipeWire
   capture, simultaneous consumers, reopen, crashes and suspend/resume.
   PipeWire must release the virtual stream after its final client exits.
4. Compare repeated idle battery windows with relay stopped and resident,
   unchanged brightness and workload. Also check CPU, wakeups and runtime-PM
   active-time counters. Keep `sustain_framerate=0` and `timeout=0`.
5. Stop all test consumers and relay processes, then
   `sudo modprobe -r v4l2loopback` to remove the temporary device.

Only after acceptance should a subsequent image install the integration RPM
and enable `azurefin-camera.service`. That package reserves the physical
camera for the service and presents the processed virtual camera to desktop
applications. Repeat the checks with the actual service and access rules.

## Evidence collected before this image

The private processing stack delivered frames, survived repeated starts and
stops, and released sensor/CAMSS/CCI after a killed capture process. Reopening
after normal system suspend also delivered 60 frames and returned all three
devices to runtime suspend. This does not test an active relay across suspend.

A retained stopped input pipeline used about 0.000304 CPU seconds in 60 seconds.
Three-minute battery samples averaged 7.369 W before capture and 7.510 W after;
the ranges overlapped widely. Neither test included the full relay, so these
results do not establish its idle overhead. The old kernel rejected the
unsigned prototype loopback module; lockdown was left intact.
