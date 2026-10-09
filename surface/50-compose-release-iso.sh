#!/usr/bin/env bash
# Native ARM64, clean CI inputs only. Never accesses physical block devices.
set -Eeuo pipefail
status=0
trap 'status=$?; printf "ISO composition failed at %s:%s (exit %s): %s\n" "${BASH_SOURCE[0]}" "$LINENO" "$status" "$BASH_COMMAND" >&2; exit "$status"' ERR
[[ $EUID == 0 && $# == 4 && $(uname -m) == aarch64 ]]
base=$1 installer=$2 output=$(realpath -m "$3") revision=$4
[[ $base =~ @sha256:[a-f0-9]{64}$ && $installer =~ @sha256:[a-f0-9]{64}$ ]]
[[ $revision =~ ^[a-f0-9]{40}$ && ! -e $output ]]
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
bash "$repo/surface/52-check-iso-tools.sh"
mkdir "$output"
available=$(df --output=avail -k "$output" | tail -n 1 | tr -d ' ')
(( available >= 90 * 1024 * 1024 )) || {
    echo 'ISO composition needs at least 90 GiB free. Configure AZUREFIN_ISO_RUNNER for a larger ARM64 runner.' >&2
    exit 1
}
for image in "$base" "$installer"; do
    # Resolution step already pulled these immutable inputs while authenticated.
    # Do not require registry credentials during privileged composition.
    podman image exists "$image"
    [[ $(podman inspect --format '{{ index .Labels "org.opencontainers.image.revision" }}' "$image") == "$revision" ]]
done
bundle="$output/bundle"
mkdir -p "$bundle/support/firmware-tools"
podman save --format oci-dir -o "$bundle/base-oci" "$base"
podman save --format oci-dir -o "$output/installer-oci" "$installer"
python3 "$repo/scripts/audit-release.py" oci "$bundle/base-oci" "$repo/surface/firmware-policy.json"
python3 "$repo/scripts/audit-release.py" oci "$output/installer-oci" "$repo/surface/firmware-policy.json"
podman inspect --format '{{.Id}}' "$base" | sed 's/^sha256://' > "$bundle/base-image-id"
cp -a "$repo/surface/build" "$bundle/support/"
for name in 28-prepare-installer-payload.sh Containerfile.provision installer_fix_fstab.py installer_prepare.py release_workspace.py; do
    cp "$repo/surface/$name" "$bundle/support/"
done
# Extract tooling from the exact released RPM image, not a neighboring checkout.
container=$(podman create "$base")
trap 'podman rm "$container" >/dev/null' EXIT
podman cp "$container:/usr/bin/azurefin-extract-firmware" "$bundle/support/firmware-tools/"
podman cp "$container:/usr/libexec/azurefin/firmware-policy.py" "$bundle/support/firmware-tools/"
podman cp "$container:/usr/share/azurefin/firmware-policy.json" "$bundle/support/firmware-tools/"
podman cp "$container:/usr/lib/modules" "$output/modules"
python3 "$repo/scripts/audit-release.py" tree "$bundle" "$repo/surface/firmware-policy.json"
builder_base=quay.io/centos-bootc/bootc-image-builder@sha256:a4779fc2307a7c2e82fda09e5c7712871fdb2dfae8a587f61d1dab32e7c4edc8
podman pull --platform linux/arm64 "$builder_base"
[[ $(podman inspect --format '{{.Architecture}}' "$builder_base") == arm64 ]] || {
    echo 'ISO builder must be native ARM64; refusing emulated composition.' >&2
    exit 1
}
podman build --platform linux/arm64 --pull=never --build-arg "BUILDER_BASE=$builder_base" \
    -f "$repo/surface/Containerfile.iso-builder" -t localhost/azurefin-iso-builder "$repo"
[[ $(podman inspect --format '{{.Architecture}}' localhost/azurefin-iso-builder) == arm64 ]]
mkdir "$output/compose"
podman run --rm --privileged --security-opt label=disable --network=host \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    -v "$repo/iso/iso.toml:/config.toml:ro" -v "$output/compose:/output" \
    localhost/azurefin-iso-builder build --type bootc-installer --target-arch aarch64 \
    --rootfs=xfs --output /output --installer-payload-ref "$base" "$installer"
mapfile -t sources < <(find "$output/compose" -name '*.iso' -type f)
mapfile -t dtbs < <(find "$output/modules" -name x1e80100-microsoft-romulus13.dtb -type f)
printf 'Composed ISO candidates (%s):\n' "${#sources[@]}"
printf '  %s\n' "${sources[@]}"
printf 'Romulus13 DTB candidates (%s):\n' "${#dtbs[@]}"
printf '  %s\n' "${dtbs[@]}"
[[ ${#sources[@]} == 1 && ${#dtbs[@]} == 1 ]] || {
    echo 'Expected exactly one composed ISO and one Romulus13 DTB.' >&2
    exit 1
}
echo 'Preparing Surface boot configuration...'
# The reviewed patcher has a local-only guard. CI calls it only here, after
# auditing both firmware-free OCI inputs, and audits the final ISO below.
GITHUB_ACTIONS=false bash "$repo/surface/40-prepare-romulus-iso.sh" \
    "${sources[0]}" "${dtbs[0]}" "$output/surface.iso" --diagnostic
mkdir "$output/boot"
xorriso -osirrox on -indev "$output/surface.iso" \
    -extract /EFI/BOOT/grub.cfg "$output/boot/grub.cfg" \
    -extract /images/efiboot.img "$output/boot/efiboot.img"
python3 "$repo/surface/release_iso_grub.py" "$output/boot/grub.cfg"
grub2-script-check "$output/boot/grub.cfg"
mcopy -o -i "$output/boot/efiboot.img" "$output/boot/grub.cfg" ::/EFI/BOOT/grub.cfg
xorriso -indev "$output/surface.iso" -outdev "$output/azurefin-aarch64.iso" \
    -boot_image any replay \
    -map "$output/boot/grub.cfg" /EFI/BOOT/grub.cfg \
    -map "$output/boot/efiboot.img" /images/efiboot.img \
    -map "$bundle" /azurefin \
    -map "$repo/surface/release-installer.ks" /azurefin/install.ks \
    -append_partition 2 0xef "$output/boot/efiboot.img" \
    -boot_image any appended_part_as=gpt -commit -end
implantisomd5 --force "$output/azurefin-aarch64.iso"
checkisomd5 "$output/azurefin-aarch64.iso"
bash "$repo/surface/51-audit-release-iso.sh" "$output/azurefin-aarch64.iso" "$output/audit"
