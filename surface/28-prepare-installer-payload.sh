#!/usr/bin/env bash
# Explicit local firmware image build, usable before or after OS installation.
# Does not mount or partition disks, stage a deployment, or reboot.
# Keep all intermediate state for diagnosis; never publish the resulting image.
set -euo pipefail
if [[ $# -lt 3 || $# -gt 4 || ${GITHUB_ACTIONS:-false} == true ]]; then
    echo 'Usage: bash 28-prepare-installer-payload.sh BASE_OCI EXPECTED_IMAGE_ID WORK_PARENT [LOCAL_MSI]' >&2
    exit 2
fi
source_oci=$(realpath -e -- "$1")
expected=${2#sha256:}
parent=$(realpath -e -- "$3")
context=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tools=${AZUREFIN_FIRMWARE_TOOLS:-$context/firmware-tools}
policy="$tools/firmware-policy.json"
python3 "$tools/firmware-policy.py" "$policy" metadata >/dev/null
[[ $expected =~ ^[a-f0-9]{64}$ && -f $source_oci/index.json &&
   -f $source_oci/oci-layout && -d $parent && -w $parent ]] || {
    echo 'Expected an OCI directory, pinned image ID, and writable workspace parent.' >&2
    exit 2
}
# Unpacking a 7+ GB image, temporary build state and OCI export must not exhaust
# the 16 GB Surface's live environment. Only explicitly selected native disks.
case $(findmnt -n -o FSTYPE -T "$parent") in
    ext4|xfs|btrfs) ;;
    *) echo 'Workspace must be disk-backed ext4, XFS or Btrfs, not live RAM storage.' >&2; exit 1 ;;
esac
available=$(df --output=avail -k "$parent" | tail -n 1 | tr -d ' ')
if [[ ! $available =~ ^[0-9]+$ ]] || (( available < 30 * 1024 * 1024 )); then
    echo 'At least 30 GiB free workspace is required for a new preparation run.' >&2
    echo "Workspace: $parent; available KiB: $available" >&2
    echo 'Earlier preparation runs are retained, including their container storage.' >&2
    echo 'After finishing the previous installation, reclaim its run workspace or use a larger workspace before retrying.' >&2
    echo 'Nothing has been downloaded or installed by this attempt.' >&2
    exit 1
fi
command -v podman >/dev/null
msi=
if [[ $# == 4 ]]; then
    msi=$(realpath -e -- "$4")
    [[ -f $msi && -r $msi && $parent != *,* ]]
    # Reject the wrong package before importing gigabytes of container data.
    python3 "$tools/firmware-policy.py" "$policy" verify-msi "$msi" || {
        echo 'MSI checksum mismatch: use the release specified in firmware-policy.json' >&2
        exit 1
    }
fi
umask 077
work=$(mktemp -d "$parent/azurefin-provision.XXXXXXXX")
echo "Preparation workspace: $work"
exec > >(tee "$work/prepare.log") 2>&1
trap 'echo "Preparation failed; retained workspace: $work" >&2' ERR
mkdir "$work/tmp"
# Snapshot the reviewed tools and manifest together. The same policy used for
# preflight is passed to extraction, including when the base has older tools.
mkdir -p "$work/context/firmware-tools"
cp -a -- "$context/build" "$context/Containerfile.provision" "$context/installer_fix_fstab.py" "$work/context/"
for file in azurefin-extract-firmware firmware-policy.py firmware-policy.json; do
    cp -- "$tools/$file" "$work/context/firmware-tools/$file"
done
export TMPDIR="$work/tmp"
# The installer has working Ethernet but may lack nftables support for
# netavark's bridge/NAT setup. Use its existing network for the trusted build.
firmware_args=(--build-arg FIRMWARE_SOURCE=download --network=host)
if [[ -n $msi ]]; then
    cp -- "$msi" "$work/firmware.msi"
    firmware_args=(--build-arg FIRMWARE_SOURCE=msi --network=none
        "--secret=id=surface-msi,src=$work/firmware.msi")
fi
# Dedicated store: never reuse or change the host's container images.
podman_cmd=(podman --root "$work/storage" --runroot "$work/run"
    --storage-driver overlay)
echo 'Importing and unpacking the local base image (several GB); firmware download has not started yet.'
"${podman_cmd[@]}" pull --platform linux/arm64 "oci:$source_oci"
actual=$("${podman_cmd[@]}" image inspect --format '{{.Id}}' "$expected")
[[ ${actual#sha256:} == "$expected" ]] || {
    echo 'Base image ID did not match; refusing to run it.' >&2
    exit 1
}
echo 'Base import verified. Starting firmware preparation and initramfs build.'
"${podman_cmd[@]}" build --platform linux/arm64 --pull=never \
    "${firmware_args[@]}" \
    --build-arg "RELEASE_BASE=$expected" --iidfile "$work/final-image-id" \
    -f "$work/context/Containerfile.provision" "$work/context"
final=$(<"$work/final-image-id")
[[ ${final#sha256:} =~ ^[a-f0-9]{64}$ ]]
"${podman_cmd[@]}" save --format oci-dir --output "$work/container.pending" "$final"
test -s "$work/container.pending/index.json"
test -s "$work/container.pending/oci-layout"
mv -- "$work/container.pending" "$work/container"
printf '%s\n' "$expected" > "$work/base-image-id"
printf '%s\n' "$work/container" > "$work/READY"
echo "PAYLOAD_READY: $work/container"
echo 'Preparation only: no deployment was staged and no disks were partitioned.'
