#!/usr/bin/env bash
# Narrowly scoped destructive hardware test: only the identified 500GB USB SSD.
set -euo pipefail
[[ $# == 3 && $3 == --erase-external-test-ssd && $EUID == 0 ]]
if [[ ${ROMULUS_GPT_PRIVATE:-0} != 1 ]]; then
    exec unshare --mount --propagation private env ROMULUS_GPT_PRIVATE=1 bash "$0" "$@"
fi
payload=$(realpath -e "$1")
prepared=$(realpath -e "$2")
disk=/dev/disk/by-id/usb-ITHOO_ASM236X_NVME_00000000000000000000-0:0
esp=/dev/disk/by-id/usb-ITHOO_ASM236X_NVME_00000000000000000000-0:0-part1
data=/dev/disk/by-id/usb-ITHOO_ASM236X_NVME_00000000000000000000-0:0-part2
[[ -b $disk && $(readlink -f "$disk") == /dev/sda ]]
[[ $(blockdev --getsize64 "$disk") == 500107862016 && $(blockdev --getro "$disk") == 0 ]]
[[ $(lsblk -dn -o SERIAL "$disk") == 00000000000000000000 ]]
[[ $(lsblk -dn -o TRAN "$disk") == usb ]]
[[ $(lsblk -dn -o MODEL "$disk" | xargs) == 'ASM236X NVME' ]]
[[ -z $(lsblk -nr -o MOUNTPOINTS "$disk" | tr -d '[:space:]') ]]
if lsblk -nr -o TYPE "$disk" | grep -Ev '^(disk|part)$'; then exit 1; fi
uuid=$(cat "$prepared/esp-uuid")
[[ $uuid =~ ^[A-F0-9]{4}-[A-F0-9]{4}$ ]]
(cd "$payload" && sha256sum --quiet -c "$prepared/payload.sha256")
(cd "$prepared/esp" && sha256sum --quiet -c "$prepared/esp.sha256")
for program in sgdisk mkfs.fat mkfs.ext4 mount umount fsck.fat e2fsck; do
    command -v "$program" >/dev/null
done
work=$(mktemp -d /tmp/romulus-gpt-write.XXXXXXXX)
mkdir "$work/esp" "$work/data"
cleanup() {
    mountpoint -q "$work/data" && umount "$work/data"
    mountpoint -q "$work/esp" && umount "$work/esp"
    rmdir "$work/data" "$work/esp" "$work" || true
}
trap cleanup EXIT
echo 'Replacing external test SSD with aligned GPT, 512MiB ESP and 12GiB installer data.'
wipefs --all "$disk"
sgdisk --zap-all "$disk"
sgdisk --clear --new=1:2048:+512M --typecode=1:ef00 --change-name=1:AZUREBOOT \
    --new=2:0:+12G --typecode=2:8300 --change-name=2:AZUREDATA "$disk"
blockdev --rereadpt "$disk"
udevadm settle
[[ $(readlink -f "$esp") == /dev/sda1 && $(readlink -f "$data") == /dev/sda2 ]]
[[ $(blockdev --getsize64 "$esp") == 536870912 ]]
[[ $(blockdev --getsize64 "$data") == 12884901888 ]]
mkfs.fat -F 32 -i "${uuid//-/}" -n AZUREBOOT "$esp"
mkfs.ext4 -F -m 0 -L AZUREDATA -E lazy_itable_init=0,lazy_journal_init=0 "$data"
mount -o nodev,nosuid,noexec "$esp" "$work/esp"
mount -o nodev,nosuid,noexec "$data" "$work/data"
cp -r "$prepared/esp/." "$work/esp/"
cp -a "$payload/." "$work/data/"
sync
umount "$work/data"
umount "$work/esp"
blockdev --flushbufs "$disk"
echo 'Copy complete; verifying all files from read-only remounts.'
mount -o ro,nodev,nosuid,noexec "$esp" "$work/esp"
mount -o ro,noload,nodev,nosuid,noexec "$data" "$work/data"
(cd "$work/esp" && sha256sum --quiet -c "$prepared/esp.sha256")
(cd "$work/data" && sha256sum --quiet -c "$prepared/payload.sha256")
umount "$work/data"
umount "$work/esp"
fsck.fat -n "$esp"
e2fsck -fn "$data"
sgdisk --verify "$disk"
lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS "$disk"
echo GPT_SSD_FILES_VERIFIED
