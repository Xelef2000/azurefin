#!/usr/bin/env bash
# Validate the actual kernel/archive, not just dracut's exit status.
set -euo pipefail
[[ $# -ge 2 && $# -le 3 ]] || exit 2
mode=$1
kver=$2
[[ $mode == preflight || $mode == verify || $mode == verify-ostree ]] || exit 2
ostree_required=false
if [[ $mode == verify-ostree ]]; then
    ostree_required=true
    mode=verify
fi
grep -qx 'CONFIG_PCIE_QCOM=y' "/usr/lib/modules/$kver/config"
add_drivers=
install_items=
# shellcheck source=/dev/null
source /usr/lib/dracut/dracut.conf.d/50-romulus.conf
[[ -n $add_drivers ]]
archive_list=
if [[ $mode == verify ]]; then
    [[ $# -eq 3 ]]
    archive_listing=$(lsinitrd "$3")
    archive_list=$(awk '{print $NF}' <<< "$archive_listing")
    # shellcheck source=/dev/null
    source /usr/lib/dracut/dracut.conf.d/51-romulus-firmware.conf
    [[ -n $install_items ]]
fi
check_path() {
    local path
    path=$(readlink -f -- "$1")
    path=${path#/}
    if [[ $mode == verify ]] && ! grep -Fxq "$path" <<< "$archive_list"; then
        echo "Missing from initramfs: $path" >&2
        exit 1
    fi
}
if "$ostree_required"; then
    for path in /usr/lib/ostree/ostree-prepare-root \
        /usr/lib/ostree/prepare-root.conf \
        /usr/lib/systemd/system/ostree-prepare-root.service; do
        test -s "$path"
        check_path "$path"
    done
    grep -Fq 'initrd-root-fs.target.wants/ostree-prepare-root.service ->' <<< "$archive_listing" || {
        echo 'Missing enabled ostree-prepare-root.service in initramfs' >&2
        exit 1
    }
    add_drivers+=' erofs overlay'
fi
for driver in $add_drivers; do
    # Abort on any unknown module, even when dracut would return success.
    modinfo -k "$kver" "$driver" >/dev/null
    dependencies=$(modprobe --show-depends --set-version "$kver" "$driver")
    while read -r action path _; do
        [[ $action != insmod ]] || check_path "$path"
    done <<< "$dependencies"
done
for firmware in $install_items; do
    test -s "$firmware"
    check_path "$firmware"
done
echo "Romulus initramfs $mode passed for $kver"
