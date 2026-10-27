#!/usr/bin/bash
set -euo pipefail
exec >>/run/azurefin-firmware.log 2>&1
echo "Loader started at $(cat /proc/uptime)"
boot_uuid=''
read -r -a arguments </proc/cmdline
for argument in "${arguments[@]}"; do
    case "$argument" in
        azurefin.boot_uuid=*)
            [[ -z "$boot_uuid" ]] || { echo 'Duplicate boot UUID'; exit 1; }
            boot_uuid=${argument#*=}
            [[ "$boot_uuid" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]
            ;;
    esac
done
[[ -n "$boot_uuid" ]] || { echo 'No boot store requested'; exit 0; }
manifest=/etc/azurefin/boot-firmware.sha256
read -r bundle_id _ < <(sha256sum "$manifest")
[[ "$bundle_id" =~ ^[0-9a-f]{64}$ ]]
modprobe phy_qcom_qmp_pcie
modprobe nvme
modprobe ext4
bootdev=''
for ((attempt=0; attempt<20; attempt++)); do
    bootdev=$(blkid -U "$boot_uuid" || true)
    [[ -n "$bootdev" ]] && break
    sleep 1
done
[[ -n "$bootdev" ]]
mountpoint=$(mktemp -d /run/azurefin-firmware-mount.XXXXXX)
mounted=false
cleanup() {
    status=$?
    if "$mounted"; then umount "$mountpoint" || true; fi
    echo "Loader exit=$status at $(cat /proc/uptime)"
}
trap cleanup EXIT
mount -t ext4 -o ro,noload,nodev,nosuid,noexec "$bootdev" "$mountpoint"
mounted=true
store="$mountpoint/azurefin/firmware/$bundle_id"
for directory in "$mountpoint/azurefin" "$mountpoint/azurefin/firmware" "$store"; do
    [[ -d "$directory" && ! -L "$directory" ]]
done
[[ -z $(find "$store" -type l -print -quit) ]]
temporary=$(mktemp -d /run/azurefin-firmware-copy.XXXXXX)
total=0
while read -r hash target; do
    [[ "$hash" =~ ^[0-9a-f]{64}$ ]]
    # This manifest is generated from policy in the image, never read from disk.
    [[ "$target" == qcom/* && "$target" != *'..'* && "$target" != *'//'* ]]
    [[ "$target" =~ ^[a-zA-Z0-9_./-]+$ ]]
    [[ -f "$store/$target" && ! -L "$store/$target" ]]
    size=$(stat -c %s "$store/$target")
    ((size > 0 && size <= 67108864))
    total=$((total + size))
    ((total <= 134217728))
    mkdir -p "$temporary/${target%/*}"
    head -c 67108865 "$store/$target" >"$temporary/$target"
done <"$manifest"
(cd "$temporary" && sha256sum -c "$manifest")
umount "$mountpoint"
mounted=false
runtime=/run/azurefin-firmware
[[ ! -e "$runtime" && ! -L "$runtime" ]]
mv -T "$temporary" "$runtime"
printf %s "$runtime" >/sys/module/firmware_class/parameters/path
echo "Verified bundle $bundle_id exposed at $(cat /proc/uptime)"
