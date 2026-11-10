#!/usr/bin/env bash
# Run only in the immutable-v35 test image; preserve every userspace RPM.
set -euo pipefail
[[ -e /run/.containerenv || ${container:-} == oci || ${container:-} == podman ]]
[[ $(rpm --eval '%{_arch}') == aarch64 ]]
old=7.4.0-rc1-azurefin.2.0.2.fc44
new=7.4.0-rc1-azurefin.2.0.3.fc44
[[ $(rpm -q kernel-azurefin) == kernel-azurefin-7.4~rc1-2.0.2.fc44.aarch64 ]]
mapfile -t kernels < <(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d)
[[ ${#kernels[@]} == 1 && ${kernels[0]} == /usr/lib/modules/"$old" ]]
inventory=$(mktemp -d)
trap 'rm -rf -- "$inventory"' EXIT
rpm -qa | grep -v '^kernel-azurefin-' | sort > "$inventory/before"
project=xelef2000/azurefin-kernel:custom:sleep-qce-sync
repo_id="copr:copr.fedorainfracloud.org:${project//\//:}"
dnf5 copr enable -y "$project"
dnf5 copr disable -y "$project"
dnf5 install -y --disablerepo='*' --enablerepo="$repo_id" \
    kernel-azurefin-7.4~rc1-2.0.3.fc44.aarch64
[[ $(rpm -q kernel-azurefin) == kernel-azurefin-7.4~rc1-2.0.3.fc44.aarch64 ]]
rpm -qa | grep -v '^kernel-azurefin-' | sort > "$inventory/after"
diff -u "$inventory/before" "$inventory/after"
test -s "/usr/lib/modules/$new/vmlinuz"
# The old generated initramfs, devicetree and depmod files are not RPM-owned.
# Remove only the verified old kernel directory inside this build container.
rm -rf -- "/usr/lib/modules/$old"
echo KERNEL_ONLY_PACKAGE_CHANGE_VERIFIED
