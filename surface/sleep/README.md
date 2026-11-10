# Attended suspend diagnostic image

The v38 GMU candidate failed its second suspend. This branch builds an
attended diagnostic image from the immutable v37 base, replacing only the
kernel with 2.0.5. The kernel retains v38 code and adds PM_DEBUG and
PM_ADVANCED_DEBUG; it is not a new power fix. The package-inventory assertion,
firmware audits and signing pipeline remain enabled.

Wait for the isolated sleep-gmu-debug COPR build and signature checks before
publishing a fresh versioned candidate. Preserve v37 and v34. Coordinate boot
and attended freezer/devices tests; restore pm_test=none after each invocation.
Do not run unattended battery trials or promote this diagnostic image.

This experimental release workflow override must be removed before normal
production release work. No GitHub release or ISO is part of this experiment.
