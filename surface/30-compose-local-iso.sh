#!/usr/bin/env bash
# Root-only local composition helper. Receives a Podman installer archive on
# stdin (or a builder archive for a retry), then composes an ISO.
# Never writes to a host block device.
set -euo pipefail

if [[ ${GITHUB_ACTIONS:-false} == true ]]; then
    echo "Firmware-inclusive ISO builds are local-only." >&2
    exit 1
fi
if [[ $EUID != 0 || $# -lt 3 || $# -gt 4 ]]; then
    echo "Usage (as root): $0 OUTPUT_DIR CONFIG_TOML EXPECTED_INSTALLER_ID [BUILDER_ID] < image.tar" >&2
    exit 1
fi
output_dir=$(realpath -m -- "$1")
config=$(realpath -e -- "$2")
expected_id=$3
[[ $expected_id =~ ^[a-f0-9]{64}$ ]] || exit 1
[[ -f $config && ! -e $output_dir ]] || {
    echo "Config must exist and output directory must be new." >&2
    exit 1
}

payload=${ROMULUS_PAYLOAD_REF:-localhost/azurefin:romulus-testing}
installer=${ROMULUS_INSTALLER_REF:-localhost/azurefin-installer:romulus-testing}
# Pinned locally tested builder; do not silently change its CLI or defaults.
builder=${4:-3042e19695ac2bd40442defba2acd8f69b9079eddd531733d3ed0f817c133a73}
[[ $builder =~ ^[a-f0-9]{64}$ ]] || exit 1
podman load
podman image exists "$payload"
if [[ -n ${ROMULUS_EXPECTED_PAYLOAD_ID:-} ]]; then
    [[ $ROMULUS_EXPECTED_PAYLOAD_ID =~ ^[a-f0-9]{64}$ ]]
    [[ $(podman image inspect --format '{{.Id}}' "$payload") == "$ROMULUS_EXPECTED_PAYLOAD_ID" ]] || {
        echo "Payload does not match the expected image ID." >&2
        exit 1
    }
fi
podman image exists "$builder"
[[ $(podman image inspect --format '{{.Id}}' "$installer") == "$expected_id" ]] || {
    echo "Imported installer does not match the expected image ID." >&2
    exit 1
}
mkdir -- "$output_dir"
available_kib=$(df --output=avail -k "$output_dir" | tail -n 1 | tr -d ' ')
if (( available_kib < 30 * 1024 * 1024 )); then
    echo "Less than 30 GiB free; refusing to start ISO composition." >&2
    exit 1
fi
podman run --rm --privileged --pull=never --security-opt label=disable \
    --network=host \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    -v "$config:/config.toml:ro" \
    -v "$output_dir:/output" \
    "$builder" build --type bootc-installer --target-arch aarch64 \
    --rootfs=xfs --output /output --installer-payload-ref "$payload" "$installer"

echo "Base ISO composed. Surface DTB/GRUB patching and inspection are still required."
