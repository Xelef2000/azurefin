#!/usr/bin/env bash
# Execute with podman unshare. Only creates files in a NEW output directory.
set -euo pipefail
output=${1:?new output directory required}
mkdir -- "$output"
container=$(podman create --pull=never --network=none "${2:-localhost/azurefin:alpha3-live-enforcing}")
trap 'podman rm "$container" >/dev/null' EXIT
root=$(podman mount "$container")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
/usr/bin/python3 "$script_dir/selinux_pseudo.py" "$root" "$output/selinux.pseudo"
cp "$root"/usr/lib/modules/*/vmlinuz "$output/vmlinuz"
cp "$root"/usr/lib/modules/*/dtb/qcom/x1e80100-microsoft-romulus13.dtb "$output/romulus13.dtb"
if [[ -s $root/boot/azurefin-live.initrd ]]; then
    cp "$root/boot/azurefin-live.initrd" "$output/initrd"
else
    # Compatibility with the already-tested initial VM prototype.
    cp "$root/boot/azurefin-live-vm.initrd" "$output/initrd"
fi
cp "$root/usr/lib/grub/arm64-efi/smbios.mod" "$output/smbios.mod"
# The current Surface kernel has SQUASHFS_ZLIB/XZ, not SQUASHFS_ZSTD.
# gzip level 1 keeps this disposable local test quick; not a release recipe.
mksquashfs "$root" "$output/root.squashfs" -comp gzip -Xcompression-level 1 \
    -xattrs-exclude '^security.selinux$' -pf "$output/selinux.pseudo" \
    -processors 4 -noappend -no-progress -e sysroot/ostree
