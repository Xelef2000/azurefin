# Controlled QCE sleep candidate

Use `Containerfile.sleep-qce` for the hardware experiment. It derives from the
immutable v35 base (same package inventory as the Surface's booted v34), upgrades
only kernel-azurefin from 2.0.2 to 2.0.3, and regenerates the matching bootstrap
initramfs and device tree. A build-time inventory comparison fails if any other
RPM changes. Normal firmware checks, all-layer auditing, lint and signing remain
in the manual image workflow.

The first candidate, v36, passed audits/signatures but rebuilt against newer
Fedora packages, including BlueZ. Do not use v36 for the controlled comparison.
The replacement tag-only candidate is v37. Neither is promoted to testing and
neither has a GitHub release or automatic ISO build.

The workflow Containerfile override is specific to this experimental branch.
Before proposing normal release integration, restore Containerfile.romulus in
the workflow and retain only the verified kernel pin/repository changes and
validation documentation.

Kernel diagnosis and checklist:
https://github.com/Xelef2000/azurefin-linux/blob/testing/sleep-qce-sync/SLEEP-QCE-TESTING.md
