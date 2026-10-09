#!/usr/bin/env bash
# Local-only metadata-preserving conversion of an installer SquashFS to XZ.
# Uses root to retain numeric owners, capabilities and SELinux xattrs.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-false} != true && $EUID == 0 && $# == 2 ]] || {
    echo "Usage (as root, locally): $0 SOURCE.img NEW_WORK_DIRECTORY" >&2
    exit 1
}
source_img=$(realpath -e -- "$1")
work_dir=$(realpath -m -- "$2")
[[ -f $source_img && ! -e $work_dir && ! -L $work_dir ]]
mkdir -m 0700 "$work_dir"
unsquashfs -s "$source_img" > "$work_dir/source-superblock.txt"
grep -qx 'Compression zstd' "$work_dir/source-superblock.txt"
# Abort on any extraction failure rather than silently losing metadata.
unsquashfs -strict-errors -no-progress -processors 2 -d "$work_dir/root" "$source_img"
mksquashfs "$work_dir/root" "$work_dir/install-xz.img" -noappend \
    -comp xz -processors 2 -mem 512M -no-progress \
    -mkfs-time "$(unsquashfs -mkfs-time "$source_img")"
unsquashfs -s "$work_dir/install-xz.img" > "$work_dir/result-superblock.txt"
grep -qx 'Compression xz' "$work_dir/result-superblock.txt"
# Compare paths, permissions, numeric owners, sizes, link targets and times.
unsquashfs -lln "$source_img" | sed '/^$/d' > "$work_dir/source-list.txt"
unsquashfs -lln "$work_dir/install-xz.img" | sed '/^$/d' > "$work_dir/result-list.txt"
# Directory sizes and physical inode sharing can change during recompression.
# Validate actual contents and semantic metadata rather than on-disk layout.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bash "$script_dir/46-verify-installer.sh" "$source_img" "$work_dir/install-xz.img"
sha256sum "$work_dir/install-xz.img" > "$work_dir/install-xz.img.sha256"
echo 'XZ_INSTALLER_RECOMPRESSED'
