# Controlled GMU sleep experiment

Build from the immutable signed v0.0.37-alpha base image. Replace only
kernel-azurefin 2.0.3 with 2.0.4 from the isolated sleep-gmu-sync COPR
repository. Fail if any other RPM changes. Rebuild the initramfs and DTB
using the matching kernel, retain firmware audits and OTA signing.

Kernel source: https://github.com/Xelef2000/azurefin-linux/pull/13
Kernel build: https://copr.fedorainfracloud.org/coprs/build/11297684

The QCE-only baseline measured about 1.02 W during a 2h23m40s suspend,
with DDR sleep restored but GCC/GPUCC unsynchronized and no AOSD/CXSD.
The candidate adds GMU component binding and downstream lifecycle fixes;
it is experimental and has not yet been tested on hardware.

Do not dispatch the image build until the kernel build and RPM signature
checks pass. Publish a versioned, signed candidate only. Preserve v37 and
v34 rollback deployments, coordinate reboot for encrypted-root unlock,
then check GMU/GCC/GPUCC state, graphics, peripherals and short/long suspend.
Keep firmware, cmdline, wake and PCIe policy unchanged for comparison.

The release workflow override is specific to this experimental branch.
Restore the normal Containerfile before production release work. This branch
does not promote the testing channel or generate a release ISO.
