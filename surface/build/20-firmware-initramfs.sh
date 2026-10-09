#!/usr/bin/env bash
set -euo pipefail
case ${FIRMWARE_SOURCE:-msi} in
    msi) azurefin-extract-firmware /run/secrets/surface-msi / ;;
    download) azurefin-extract-firmware --download / ;;
    *) echo 'FIRMWARE_SOURCE must be msi or download' >&2; exit 2 ;;
esac
mapfile -t kernels < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d)
[[ ${#kernels[@]} -eq 1 ]] || {
    echo "bootc requires exactly one kernel; found ${#kernels[@]}" >&2
    exit 1
}
kver=${kernels[0]##*/}
[[ $kver == *-azurefin.* ]] || { echo "Wrong kernel: $kver" >&2; exit 1; }
test -s "/usr/lib/modules/$kver/dtb/qcom/x1e80100-microsoft-romulus13.dtb"

# Include dynamic remoteproc and GPU paths for display/keyboard before LUKS
# unlock. Do not bake in a host's root UUID, passphrase or Bluetooth address.
mapfile -t firmware < <(find /usr/lib/firmware/qcom/x1e80100/microsoft -type f)
for name in gen70500_gmu.bin gen70500_sqe.fw; do
    found=false
    for suffix in "" .zst .xz; do
        file="/usr/lib/firmware/qcom/$name$suffix"
        if [[ -f "$file" ]]; then
            firmware+=("$file")
            found=true
            break
        fi
    done
    "$found" || { echo "Missing early-display firmware: $name" >&2; exit 1; }
done
printf 'install_items+=" %s "\n' "${firmware[*]}" \
    > /usr/lib/dracut/dracut.conf.d/51-romulus-firmware.conf
depmod "$kver"
bash /usr/libexec/azurefin-check-initramfs preflight "$kver"
DRACUT_NO_XATTR=1 dracut --force --no-hostonly --add ostree \
    "/usr/lib/modules/$kver/initramfs.img" "$kver"
test -s "/usr/lib/modules/$kver/initramfs.img"
bash /usr/libexec/azurefin-check-initramfs verify-ostree "$kver" "/usr/lib/modules/$kver/initramfs.img"
