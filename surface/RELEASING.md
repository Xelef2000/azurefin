# Azurefin tagged releases

ISO and installer-image builds are temporarily disabled in this repository.
Firmware provisioning remains a build-time extraction step; there is no
first-boot or installation-time downloader. The release workflow below builds
only an OCI base, never an ISO.

## Order of operations

1. Publish a numeric vMAJOR.MINOR.PATCH GitHub release in azurefin-linux and/or
   azurefin-packages. Their release workflows submit ARM64 builds to COPR.
2. Wait for successful COPR binary builds, not merely green submission workflows.
3. Update surface/build/packages.env to the exact published RPM NEVRAs.
4. Commit that lock file and publish an Azurefin GitHub release, e.g. v0.1.0.
   The tagged commit must contain .github/workflows/release-romulus.yml.

Draft releases and plain tag pushes do not start builds. Published prereleases
do. Workflows must be present at the release tag; initially target the testing
branch rather than main. No release or tag has been created automatically.

## Image output

The native ARM64 job publishes:

    ghcr.io/xelef2000/azurefin:v0.1.0-base

It uses the built-in GITHUB_TOKEN with packages:write; no COPR credentials
are required in the image repository. Package repositories are public COPRs.
There is no automatic stable/latest tag or deployment to a running machine.
The job retains the installed-RPM manifest and pushed OCI digest as artifacts.

**This is a firmware-free assembly base, not an installable system image.**
It has the packaged kernel but no finalized Romulus initramfs. The workflow
selects only the packages stage and refuses a known Microsoft DSP firmware path.
It never mounts an MSI or runs the firmware-extraction step.

## Local finalization

Check out the matching release tag and finalize using the published digest:

    podman build --platform linux/arm64 -f Containerfile.romulus-local \
      --build-arg RELEASE_BASE=ghcr.io/xelef2000/azurefin@sha256:REPLACE_WITH_RELEASE_DIGEST \
      --secret=id=surface-msi,src=/path/to/SurfaceLaptop7_ARM_Win11_26100_26.053.36539.0.msi \
      -t localhost/azurefin:romulus-testing .

The resulting local image contains extracted Microsoft firmware. Do not upload
it until redistribution rights are established. Secret mounting keeps the MSI
input out of layers, but does not remove extracted firmware from the output.

Bootloader/DTB selection, encrypted boot and physical hardware validation are
still tracked in PORTING.md. Successful image assembly alone is not boot validation.
