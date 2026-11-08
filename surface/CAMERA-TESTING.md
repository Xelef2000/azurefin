# On-demand camera image integration

Promotions and creation of new releases require explicit user permission.
Approval to commit and push these testing branches does not authorize either.

## Current signed-image status (2026-11-08)

The signed `v0.0.34-alpha` image is published to the testing channel and has
booted successfully on the Surface. GitHub release publication and source
integration into `main` remain separate manual release tasks; the user will
initiate them. No new installer ISO has been validated.

### Changes

- Install the published private libcamera softISP runtime and integration RPMs
  at `0.1-100.0.0.3.0.fc44.aarch64` and enable `azurefin-camera.service`.
- Expose the processed **Surface Camera** through the desktop camera path,
  reserving the physical camera for the service. Applications need no private
  libcamera patch of their own.
- Capture on demand and release sensor/CAMSS/CCI when the final client exits.
- Preserve the virtual output during input-only pause, supplying black frames
  while physical capture is paused and restoring live input afterward.
- Include the OS changes through v0.0.33-alpha, including the Bazaar environment
  fix. Retain the tested signed camera kernel and other package pins.

### Release and hardware evidence

[Image build](https://github.com/Xelef2000/azurefin/actions/runs/42487349025)
and [testing promotion](https://github.com/Xelef2000/azurefin/actions/runs/42488147288)
passed. Audits covered all 95 base layers and 107 installer-container layers.
Keyless image signatures and the base native OTA signature passed verification.

Base digest: `sha256:388bccc0dec3dfaa39ba87bfb273588365dd58a536e993d8b1dda802ede7fa21`.
Installer-container digest: `sha256:121688e77db5d5d8462be0003e84bbe88d4b6bb027e2176868e475d6f07739e5`.

The Surface booted the exact base digest from the registry `testing` origin
with `containerPolicy` signature enforcement. Camera startup was automatic,
with PID 1600 and zero restarts. Package verification reported timestamp-only
differences; verification excluding timestamps passed. No system units failed.
Firmware and signed-channel update preflight passed.

The input-only pause harness passed capture, black-frame output during pause,
client reopen while paused, same-client live recovery, and resume without a
client. The final idle check measured zero CPU ticks over five seconds and
confirmed hardware runtime suspend. This harness does not suspend the system.
The user confirmed a reasonable live GNOME Camera preview on the signed image.
After closing Camera, all three hardware components returned to runtime suspend
with the same service PID and zero restarts.

Earlier local-image tests covered Firefox and Brave preview/reopen; the
published-package local image also passed GNOME Camera and Brave checks. These
browser results should not be described as fresh tests on the signed image.
Evidence is retained in the package worktree under
`work/image-integration/signed-v34-*`, `release-v0.0.34-alpha/` and
`promotion-v0.0.34-alpha/`.

### Camera limitations

- Measured throughput is about 18.8 fps, also observed with raw Bayer capture.
- Loopback buffer warnings remain unresolved.
- Two direct V4L2 consumers may encounter EBUSY; shared PipeWire consumers passed.
- Broader lighting coverage and long-term camera testing remain limited.

The separately reported system suspend/wake issue is unrelated to this camera
project. It is not a camera regression or a camera-release blocker. Earlier
successful GNOME Camera and Brave sleep-cycle tests remain recorded below;
they do not claim to resolve that separate system issue.

## Historical published-package local candidate (2026-11-08)

Package release `azurefin-packages v0.0.3-alpha` is published; all four COPR
builds succeeded. Camera build [11287468](https://copr.fedorainfracloud.org/coprs/build/11287468)
produced runtime and integration RPMs at `0.1-100.0.0.3.0.fc44.aarch64`.
Both RPMs passed signature/digest verification against the project's COPR key.
The runtime retains the private-library dependency fix and integration helpers.

The main `Containerfile.romulus` recipe now installs these two exact camera
packages from `xelef2000/azurefin-romulus` and enables the service. Other package
pins are unchanged. The camera kernel remains `7.4~rc1-2.0.2.fc44` from its
signed camera side repository. OS changes through `v0.0.33-alpha`, including the
Bazaar environment fix and refreshed documentation, are incorporated.
Published-package hardware results are recorded below. The user separately
authorized signed OS release `v0.0.34-alpha` and testing-channel promotion after
build, audit and signature verification. Deployment remains a separate step.

A full native ARM build uses `Containerfile.romulus --target base-image`, local
tag `localhost/azurefin:camera-published-rpms` and development version label
`v0.0.33-alpha+camera.test`. This label is not a new OS release. The older local
same-NVR overlay below remains a historical test fixture, not the published
package build path.

The full native build completed as image ID
`f7e45d300dc81921824ce04b5ac5e2258bb7a754b360b3e3824a83c6171ecb4d`.
Bootc lint passed 14 checks, skipped one and reported no warnings. Initramfs
and firmware-free checks passed. The installed camera RPMs passed integrity
checks, camera and Bazaar environment services are enabled, and the firmware
manifest matches the existing Surface store. ShellCheck, shell syntax,
Justfile parsing and 13 update/firmware-store regression tests passed. A
validation command initially looked for the Bazaar unit under the user-service
directory; correcting it to the packaged system-service path passed.
Build/validation evidence is in the package worktree's `work/image-integration/`
(`published-image-build.log`, `published-image-validation.log`). The image was imported into root Podman storage for a trial and its image ID
was verified. Firmware preflight still passes with 793 MiB free on `/boot`
and 294 GiB on `/var`. The user subsequently approved staging and reboot. Booted OSTree checksum:
`335c79d64e83bffcb472bee724715d6c5ba31f46083dc9b81f90b03bc96b7196`;
manifest digest:
`e77f904e5b438b9cc2b8e4792a856ddf9cc429702473747f1c22c13b72dc66e5`.
Boot ID: `f81dfad6-4a88-491f-a78d-32ec9c53a7b0`. Both published camera RPMs
are installed at the pinned version. The service started automatically (PID
1603, zero restarts), desktop discovery exposes Surface Camera, and all three
hardware components are runtime-suspended before capture. Earlier deployments
remain pinned. The published-package input-pause harness passed capture, pause/reopen,
same-process recovery and hardware-idle checks without system sleep. GNOME
Camera preview was confirmed live with reasonable colours/exposure by the
user. Closing Camera returned all three components to runtime suspend, with
PID 1603 unchanged and zero restarts. The user confirmed live Brave B2 video and successful Stop/Start recovery
with the published packages. After the final Stop, all three camera components
returned to runtime suspend, with PID 1603 unchanged and zero restarts. B2
reported 4032 frames and 4031 changing frames over its final 215-second capture.
The temporary browser server was stopped and numerical telemetry saved under
`work/image-integration/published-*` in the package worktree. These checks pass
published-package boot/startup, GNOME Camera preview, Brave preview/reopen and
hardware release; Firefox's visual/reopen pass was on the earlier local-package
image. At this stage the Surface still used the local development image and
the signed-channel updater was blocked. The signed deployment and update
preflight recorded above supersede that temporary state.

## Historical local integration candidate (2026-11-08)

`Containerfile.camera-integration` layers the tested camera packages onto the
firmware-free v0.0.32-alpha OS image, pinned by digest. It installs the runtime
and integration RPMs, validates their service/device configuration and enables
`azurefin-camera.service`. On boot, the integration package loads the signed
loopback module, reserves the physical camera for the service and exposes the
processed **Surface Camera** feed through the normal desktop camera path.
The input-only sleep handler preserves the virtual output while pausing physical
capture. The service remains resident but releases capture hardware when idle.

This was a separate, local-only build path. At that stage the release
Containerfile, COPR package pins and workflows remained unchanged. The local RPMs retain the
old `0.1-2` version despite containing newer code, so **version alone cannot
identify this candidate**. `surface/camera/SHA256SUMS` pins the exact tested
binaries; the build explicitly reinstalls an existing runtime of the same NVR.
Do not substitute the older COPR build 11284735. A later published package must
receive a new release number and new image pins after approval.

From the image repository, with the tested RPMs in an external directory:

```bash
podman build --arch arm64 \
  --build-context camera-rpms=/absolute/path/to/tested-rpms \
  -f Containerfile.camera-integration \
  -t localhost/azurefin:camera-integration-local .
```

The directory must contain the two aarch64 RPM filenames in
`surface/camera/SHA256SUMS`. The build checks hashes, the exact tested kernel,
udev rules, systemd units, the sleep dependency and service enablement, then
runs `bootc container lint`. It neither pushes the image nor deploys it.
Microsoft-extracted firmware is not included; any later deployment must use
the established firmware-preserving image/provisioning procedure.

### Local image build result

The local build completed on 2026-11-08 as
`localhost/azurefin:camera-integration-local`, image ID
`cf8d9abe116ee5d579a6740695735bc53277a2803cc0c5b5ccfc4463d464bff9`.
The final bootc lint passed 14 checks, skipped one and reported no warnings.
ShellCheck, shell syntax and Justfile parsing passed. A negative checksum check
rejected the older same-version RPMs. The initial direct context mount was
blocked by local permissions; copying RPMs into the temporary context stage
resolved it. Build-state cleanup uses the existing image cleanup script.
The image has not been pushed, deployed or booted.

### Prepared Surface trial (before staging)

The local image was exported, transferred and imported into the Surface's root
Podman store on 2026-11-08. Its image ID matches the local build above. The
archive SHA256 is
`de0d82588925efef62eabe642ccb48f2edbb8b927d14f34397bc77cf0266cd83`.
Native validation passed RPM integrity, service enablement, sleep dependency,
relay pause support and bootc lint (14 passed, one skipped, no warnings).
The firmware-store preflight verified all 11 files; kernel, initramfs, device
tree, firmware policy and firmware manifest hashes match the booted image.

No deployment has been staged and no reboot has been requested. Before a trial
boot, pin the currently booted deployment and recheck firmware/space/status
under `/var/lib/azurefin/firmware-store.lock`. Stage the imported image using
`bootc switch --transport containers-storage localhost/azurefin:camera-integration-local`
without `--apply`, inspect the staged deployment and boot arguments, then reboot
only with the user ready to unlock the encrypted system. Retain existing pinned
deployments and firmware bundles. The current signed registry reference is
`ghcr.io/xelef2000/azurefin@sha256:9cfe17bd3c3a31df7a4eac29364b12e79fc4035dff17e5dac97fe441602c862f`.
Restore the signed registry update source after the local trial; the imported
image is a development artifact, not a published update channel. It inherits
the base's version label, so identify it by image ID and camera package hashes.

### First integrated boot (2026-11-08)

After explicit readiness confirmation, the previous deployment was pinned and
this local candidate was staged and booted. Booted OSTree checksum:
`37871f4b116995b46deec8d455553a5a817542fe17ad09acafb30c2e3b586c69`;
image manifest digest:
`e758e8b082b67e23f9af80b626975defde19bf8482f2c1e5b8c3e41ad058951a`.
Firmware-store and encrypted-root kernel arguments were preserved. Boot ID:
`6508a57d-4732-4ae9-b7c7-02c8f9402410`.

The actual installed service started automatically (PID 1562, zero restarts).
WirePlumber exposed only Surface Camera, with desktop-user access; all three
camera components were runtime-suspended before capture. No failed system units
were reported. The installed-service input-pause harness passed live/black/live,
reopening while paused, hardware-idle transitions and same-process assertions.
The final five-second idle sample used zero CPU ticks. No system suspend ran.
The user confirmed a live GNOME Camera preview with reasonable colours/exposure.
Closing it returned all three components to runtime suspend. A subsequent reopen
activated capture and closing again returned hardware to idle, with PID 1562
and zero restarts preserved. The user also confirmed a live, reasonable-looking installed-image Firefox F2
preview and successful Stop/Start recovery in the same window. Its local page
has no automatic stop. After the user stopped Firefox, all three hardware
components were suspended, with the same relay PID and zero restarts. The user confirmed Brave B1 also has a good live preview on the installed
image and confirmed successful Stop/Start recovery. After Brave was stopped, all three camera components returned to runtime
suspend. The installed relay remained active as designed, with PID 1562 and
zero restarts throughout the GNOME Camera, Firefox and Brave checks. The
temporary browser test server was stopped and its metadata logs saved. The final check found `uupd.service` failed because its preflight requires
the signed testing channel and refuses this local containers-storage trial.
The update policy was left intact. This establishes first-boot discovery,
visual quality, application reopen and hardware release for the integrated
image; it does not establish long-term stability or system suspend reliability.
Evidence is in the package worktree's `work/image-integration/booted-*` logs.
No release or promotion was made. The system currently tracks the local trial
image; restoring the signed registry source remains a separate follow-up.

### Evidence and remaining acceptance

- A native ARM build and clean Fedora 44 container installation passed for both
  packages, with the matching signed kernel. Private library/plugin resolution
  passed. RPM dependencies no longer incorrectly require system libcamera 0.7.
- Extracted-payload tests passed capture/release, killed-consumer recovery,
  repeated input pause, and idle runtime-PM checks. The idle battery comparison
  found no measurable increase within noise, not proof of zero energy use.
- GNOME Camera and Brave each passed a real sleep cycle with the same relay
  process and recovered live preview. Firefox passed three clearly labelled
  input-only pause cycles visually and numerically; real Firefox sleep remains
  untested, and an earlier blank-preview report remains unexplained.
- A subsequent lid suspend, after camera trial cleanup, required a reboot.
  The screen stayed black and power-button wake did not respond. Logs stop at
  deep-suspend entry; no crash dump was saved. The user identifies this as a
  separate system issue unrelated to the camera project; investigation is out
  of scope and this is not a camera-release blocker.
- About 18.8 fps and loopback buffer warnings remain unresolved. Shared PipeWire
  clients worked; two direct V4L2 clients may fail with EBUSY.

The next hardware phase is booted-image acceptance: service startup at boot,
access/discovery in GNOME Camera, Firefox and Brave, capture/release/reopen,
idle hardware and power, and rollback. Do not treat container validation as
booted-image acceptance. Further suspend tests require the user to be available
and must not be inferred from approval to prepare this image.

Detailed dated evidence is maintained in the camera package repository's
`camera/README.md`. Release, promotion, and deployment remain separate actions.

## Historical runtime-only image

The following records the older runtime-only candidate, before the local
integration work and subsequent hardware tests above.

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
