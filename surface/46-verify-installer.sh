#!/usr/bin/env bash
# Full read-only content/metadata validation in a private mount namespace.
set -euo pipefail
[[ $EUID == 0 && $# == 2 ]] || exit 1
if [[ ${ROMULUS_VERIFY_PRIVATE:-0} != 1 ]]; then
    exec unshare --mount --propagation private env ROMULUS_VERIFY_PRIVATE=1 bash "$0" "$@"
fi
source_img=$(realpath -e -- "$1")
result_img=$(realpath -e -- "$2")
[[ -f $source_img && -f $result_img && $source_img != "$result_img" ]]
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
verify_dir=$(mktemp -d /tmp/romulus-squashfs-verify.XXXXXXXX)
mkdir "$verify_dir/source" "$verify_dir/result"
cleanup() {
    mountpoint -q "$verify_dir/result" && umount "$verify_dir/result"
    mountpoint -q "$verify_dir/source" && umount "$verify_dir/source"
    rmdir "$verify_dir/result" "$verify_dir/source" "$verify_dir"
}
trap cleanup EXIT
mount -t squashfs -o loop,ro,nodev,nosuid,noexec "$source_img" "$verify_dir/source"
mount -t squashfs -o loop,ro,nodev,nosuid,noexec "$result_img" "$verify_dir/result"
python3 "$script_dir/compare_installer_trees.py" "$verify_dir/source" "$verify_dir/result"
