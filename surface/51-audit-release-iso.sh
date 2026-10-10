#!/usr/bin/env bash
# Inspect actual final artifacts, not just the image used to compose them.
set -Eeuo pipefail
status=0
trap 'status=$?; printf "ISO audit failed at line %s (exit %s): %s\n" "$LINENO" "$status" "$BASH_COMMAND" >&2; exit "$status"' ERR
[[ $EUID == 0 && $# == 2 ]]
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
cmp "$repo/surface/release-installer.ks" "$work/iso/azurefin/install.ks"
unsquashfs -s "$work/iso/images/install.img" | grep -qx 'Compression xz'
mount -t squashfs -o loop,ro,nosuid,nodev,noexec "$work/iso/images/install.img" "$work/live"
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
python3 - "$work/iso/EFI/BOOT/grub.cfg" "$repo/surface" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[2])
from release_iso_grub import patch
text = Path(sys.argv[1]).read_text()
assert patch(text) == text, 'Unexpected installer Kickstart'
assert 'set default=azurefin-install' in text
assert text.count('menuentry ') == 1 and 'submenu ' not in text
PY
echo FINAL_ISO_CONTENT_AUDIT_PASSED
