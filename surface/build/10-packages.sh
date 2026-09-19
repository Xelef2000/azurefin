#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=packages.env
source /ctx/build/packages.env
[[ $(rpm --eval '%{_arch}') == aarch64 ]] || {
    echo "This image requires aarch64 userspace." >&2
    exit 1
}
dnf5 install -y dnf5-plugins
copr_install_isolated() {
    local project=$1
    shift
    local repo_id="copr:copr.fedorainfracloud.org:${project//\//:}"
    dnf5 copr enable -y "$project"
    dnf5 copr disable -y "$project"
    dnf5 install -y --enablerepo="$repo_id" "$@"
}

# Remove only stock Fedora kernel RPMs in this container image. The custom
# RPM installs the single bootc kernel without invoking host bootloader hooks.
mapfile -t stock < <(rpm -qa --qf '%{NAME}\n' |
    grep -Ex 'kernel|kernel-core|kernel-modules|kernel-modules-core|kernel-modules-extra' || true)
if [[ ${#stock[@]} -gt 0 ]]; then
    dnf5 remove -y "${stock[@]}"
fi
copr_install_isolated xelef2000/azurefin-kernel "$KERNEL_PACKAGE"
# Install IPTSD first so the integration package dependency resolves with its
# repo disabled afterwards.
copr_install_isolated xelef2000/azurefin-iptsd "$IPTSD_PACKAGE"
copr_install_isolated xelef2000/azurefin-romulus "$ROMULUS_PACKAGE"
copr_install_isolated xelef2000/azurefin-firmware-tools "$FIRMWARE_TOOLS_PACKAGE"
dnf5 install -y linux-firmware dracut dracut-network cryptsetup plymouth bluez
dnf5 clean all

# Do not copy the legacy restart-only touchpad/display or CPU-parking hooks.
# Hardware integration is owned by the versioned RPMs above.
