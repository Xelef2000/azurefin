#!/usr/bin/env bash
# Native ARM64 candidate composer. Never publishes or accesses physical disks.
set -Eeuo pipefail
[[ $EUID == 0 && $# == 4 && $(uname -m) == aarch64 ]]
base=$1 installer=$2 output=$(realpath -m "$3") revision=$4
[[ $base =~ @sha256:[a-f0-9]{64}$ && $installer =~ @sha256:[a-f0-9]{64}$ ]]
[[ $revision =~ ^[a-f0-9]{40}$ && ! -e $output ]]
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
command -v mksquashfs >/dev/null
mkdir "$output"
printf 'azurefin-iso-workspace-v1\n' > "$output/.azurefin-iso-workspace"
available=$(df --output=avail -k "$output" | tail -n 1 | tr -d ' ')
(( available >= 80 * 1024 * 1024 )) || {
    echo 'Live ISO composition requires 80 GiB free after input pulls.' >&2
    exit 1
}
# Build the EFI layout and separate clean payload from released, audited inputs.
# No previously downloaded ISO or locally provisioned image is used as a seed.
bash "$repo/surface/50-compose-release-iso.sh" "$base" "$installer" "$output/seed" "$revision"
df -h "$output"
podman build --platform linux/arm64 --pull=never --network=none \
    --build-arg "BASE_IMAGE=$installer" --iidfile "$output/live-image-id" \
    -f "$repo/surface/live-session/Containerfile.live" "$repo"
live=$(<"$output/live-image-id")
[[ $(podman image inspect --format '{{.Architecture}}' "$live") == arm64 ]]
podman save --format oci-dir -o "$output/live-oci" "$live"
python3 "$repo/scripts/audit-release.py" oci "$output/live-oci" "$repo/surface/firmware-policy.json"
python3 "$repo/surface/iso_workspace.py" "$output" live-oci
bash "$repo/surface/live-session/30-test-container.sh" "$live"
# Rootful Podman already exposes the container's real ownership to the exporter.
bash "$repo/surface/live-session/40-export-vm.sh" "$output/live-artifacts" "$live"
# The local helper remains guarded against accidental direct CI use. This
# reviewed wrapper supplies audited inputs and requires the final audit below.
GITHUB_ACTIONS=false bash "$repo/surface/live-session/60-compose-local-iso.sh" \
    "$output/seed/azurefin-aarch64.iso" "$output/live-artifacts" \
    "$output/azurefin-aarch64.iso" installer
python3 "$repo/surface/iso_workspace.py" "$output" seed live-artifacts
df -h "$output"
bash "$repo/surface/51-audit-release-iso.sh" "$output/azurefin-aarch64.iso" "$output/final-audit" live
echo LIVE_ISO_CANDIDATE_AUDIT_PASSED
