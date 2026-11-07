#!/usr/bin/env bash
# Disposable ARM64 VM only; install the separate OCI payload via real Anaconda.
set -euo pipefail
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
[[ $(systemd-detect-virt) == qemu ]]
grep -qw rd.live.image /proc/cmdline
[[ $(getenforce) == Enforcing ]]
[[ $(lsblk -dn -o SERIAL /dev/vda | xargs) == NIX_INSTALL_TEST ]]
[[ $(blockdev --getsize64 /dev/vda) == 68719476736 ]]
# Only permit automatic shutdown after identifying the disposable guest/disk.
status=0
trap 'status=$?; echo "AZUREFIN_NIX_ANACONDA_FAILED status=$status line=$LINENO"; tail -n 100 /tmp/anaconda.log /tmp/program.log /tmp/packaging.log 2>/dev/null || true; systemctl poweroff --no-block; exit "$status"' ERR
[[ $(findmnt -n -o FSTYPE -T /run/overlayfs) == tmpfs ]]
test -s /run/initramfs/live/azurefin/base-oci/index.json
test -s /run/initramfs/live/azurefin/base-image-id
test ! -e /var/lib/nix
mkdir -p /run/install/repo
mount --bind /run/initramfs/live /run/install/repo
mount -o remount,bind,ro /run/install/repo
echo AZUREFIN_NIX_ANACONDA_BEGIN
/usr/bin/anaconda --text --kickstart=/run/install/repo/azurefin/vm-test.ks
