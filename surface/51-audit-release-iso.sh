#!/usr/bin/env bash
# Inspect actual final artifacts, not just the image used to compose them.
set -Eeuo pipefail
status=0
trap 'status=$?; printf "ISO audit failed at line %s (exit %s): %s\n" "$LINENO" "$status" "$BASH_COMMAND" >&2; exit "$status"' ERR
[[ $EUID == 0 && ( $# == 2 || $# == 3 ) ]]
mode=${3:-installer}
[[ $mode == installer || $mode == live ]]
if [[ ${AZUREFIN_AUDIT_PRIVATE:-0} != 1 ]]; then
    exec unshare --mount --propagation private env AZUREFIN_AUDIT_PRIVATE=1 bash "$0" "$@"
fi
iso=$(realpath -e "$1") work=$(realpath -m "$2")
[[ -f $iso && ! -e $work ]]
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
policy="$repo/surface/firmware-policy.json"
mkdir -p "$work/iso" "$work/live" "$work/efi"
mounts=()
cleanup() {
    local index
    for ((index=${#mounts[@]}-1; index>=0; index--)); do umount "${mounts[index]}"; done
}
trap cleanup EXIT
mount -o loop,ro,nosuid,nodev,noexec "$iso" "$work/iso"
mounts+=("$work/iso")
checkisomd5 "$iso"
python3 "$repo/surface/verify_installer_support.py" "$repo/surface" "$work/iso/azurefin/support"
audit_tree() {
    python3 "$repo/scripts/audit-release.py" tree "$1" "$policy"
    while IFS= read -r -d '' layout; do
        python3 "$repo/scripts/audit-release.py" oci "$(dirname "$layout")" "$policy"
    done < <(find "$1" -type f -name oci-layout -print0)
}
audit_initrd() {
    local archive=$1 target=$2
    mkdir -p "$target/main" "$target/early"
    (cd "$target/main" && lsinitrd --unpack "$archive")
    # Early cpio may be absent. Main archive must not be empty.
    (cd "$target/early" && lsinitrd --unpackearly "$archive")
    audit_tree "$target/main"
    if [[ -n $(find "$target/early" -mindepth 1 -print -quit) ]]; then audit_tree "$target/early"; fi
}
audit_tree "$work/iso"
test -s "$work/iso/azurefin/base-oci/index.json"
# Our sole boot entry uses release-installer.ks and its /azurefin/base-oci.
# The composer's unused /container copy must not inflate release downloads.
test ! -e "$work/iso/container"
cmp "$repo/surface/release-installer.ks" "$work/iso/azurefin/install.ks"
if [[ $mode == live ]]; then
    squashfs="$work/iso/LiveOS/squashfs.img"
    test ! -e "$work/iso/images/install.img"
else
    squashfs="$work/iso/images/install.img"
    unsquashfs -s "$squashfs" | grep -qx 'Compression xz'
fi
mount -t squashfs -o loop,ro,nosuid,nodev,noexec "$squashfs" "$work/live"
mounts+=("$work/live")
audit_tree "$work/live"
root="$work/live"
if [[ -f $root/LiveOS/rootfs.img ]]; then
    mkdir "$work/root"
    mount -o loop,ro,nosuid,nodev,noexec "$root/LiveOS/rootfs.img" "$work/root"
    mounts+=("$work/root")
    root="$work/root"
    audit_tree "$root"
fi
test -d "$root/usr/lib/modules"
if ! python3 "$repo/surface/verify_iso_kernel.py" "$root" "$work/iso" "$mode"; then
    printf 'Boot kernel/DTB verification failed (mode=%s).\n' "$mode" >&2
    echo 'Kernel directories and symlinks:' >&2
    find "$root/usr/lib/modules" -maxdepth 2 -printf '%y %p -> %l\n' >&2
    echo 'Romulus DTB and kernel/initramfs inventory (without following symlinks):' >&2
    find "$root/usr/lib/modules" "$root/boot" \
        \( -name '*romulus*' -o -name 'vmlinuz*' -o -name 'initramfs*' -o -name 'dtb' \) \
        -printf '%y %s %p -> %l\n' >&2
    echo 'Regular Romulus13 DTB checksums:' >&2
    find "$root/usr/lib/modules" "$root/boot" -type f \
        -name x1e80100-microsoft-romulus13.dtb -exec sha256sum {} + >&2
    sha256sum "$work/iso/images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb" >&2
    exit 1
fi
audit_initrd "$work/iso/images/pxeboot/initrd.img" "$work/boot-initrd"
index=0
while IFS= read -r -d '' initrd; do
    audit_initrd "$initrd" "$work/module-initrd-$index"
    index=$((index+1))
done < <(find "$root/usr/lib/modules" -type f -name initramfs.img -print0)
(( index >= 1 ))
mount -t vfat -o loop,ro,nosuid,nodev,noexec "$work/iso/images/efiboot.img" "$work/efi"
mounts+=("$work/efi")
audit_tree "$work/efi"
cmp "$work/efi/EFI/BOOT/grub.cfg" "$work/iso/EFI/BOOT/grub.cfg"
python3 - "$work/iso/EFI/BOOT/grub.cfg" "$repo/surface" "$mode" <<'PY'
from pathlib import Path
import runpy
import sys
sys.path.insert(0, sys.argv[2])
text = Path(sys.argv[1]).read_text()
if sys.argv[3] == 'live':
    expected = runpy.run_path(str(Path(sys.argv[2]) / 'live-session/iso_grub.py'))['CONFIG']
    assert text == expected, 'Unexpected live boot configuration'
else:
    from release_iso_grub import patch
    assert patch(text) == text, 'Unexpected installer Kickstart'
    assert 'set default=azurefin-install' in text
assert text.count('menuentry ') == 1 and 'submenu ' not in text
PY
echo FINAL_ISO_CONTENT_AUDIT_PASSED
