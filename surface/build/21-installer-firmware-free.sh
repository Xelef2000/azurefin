#!/usr/bin/env bash
# Firmware-free bootstrap initramfs. Installed mode additionally needs OSTree.
set -euo pipefail
mode=${1:-live}
[[ $mode == live || $mode == installed ]]
dracut_args=()
verify=verify
if [[ $mode == installed ]]; then
    dracut_args=(--add ostree)
    verify='verify-ostree'
fi
bash /usr/libexec/azurefin-check-firmware-free
mapfile -t kernels < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d)
[[ ${#kernels[@]} == 1 ]]
kver=${kernels[0]##*/}
[[ $kver == *-azurefin.* ]]
# Keep the distribution-provided GPU microcode, but no Microsoft-extracted
# remoteproc/GPU blobs. Hardware fallback still needs a real boot test.
firmware=()
for name in gen70500_gmu.bin gen70500_sqe.fw; do
    found=false
    for suffix in '' .zst .xz; do
        path="/usr/lib/firmware/qcom/$name$suffix"
        if [[ -s $path ]]; then
            firmware+=("$path")
            found=true
            break
        fi
    done
    "$found"
done
printf 'install_items+=" %s "\n' "${firmware[*]}" > /usr/lib/dracut/dracut.conf.d/51-romulus-firmware.conf
depmod "$kver"
bash /usr/libexec/azurefin-check-initramfs preflight "$kver"
DRACUT_NO_XATTR=1 dracut --force --no-hostonly "${dracut_args[@]}" "/usr/lib/modules/$kver/initramfs.img" "$kver"
bash /usr/libexec/azurefin-check-initramfs "$verify" "$kver" "/usr/lib/modules/$kver/initramfs.img"
listing=$(lsinitrd "/usr/lib/modules/$kver/initramfs.img")
if grep -Eq 'qcom/x1e80100/microsoft|romulus-bluetooth-address|SurfaceLaptop.*\.msi' <<< "$listing"; then
    echo 'Private provisioning data found in installer initramfs' >&2
    exit 1
fi
bash /usr/libexec/azurefin-check-firmware-free
echo MICROSOFT_FIRMWARE_FREE_INSTALLER_INITRAMFS_VERIFIED
