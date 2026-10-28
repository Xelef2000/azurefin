#!/usr/bin/env bash
set -euo pipefail

# Bazaar is the app store. Keep shared dependencies such as Flatpak rather
# than letting removal of the previous store prune unrelated desktop packages.
dnf5 remove -y --setopt=clean_requirements_on_remove=False gnome-software
if rpm -q gnome-software >/dev/null 2>&1; then
    echo 'GNOME Software must not remain alongside Bazaar.' >&2
    exit 1
fi

# Follow Bluefin's runtime Flatpak preinstallation; do not populate /var or
# download applications/runtimes into the immutable image during its build.
flatpak preinstall --help >/dev/null
install -Dm644 /ctx/build/bazaar/bazaar.preinstall \
    /usr/share/flatpak/preinstall.d/bazaar.preinstall
install -Dm644 /ctx/build/bazaar/azurefin-flatpak-preinstall.service \
    /usr/lib/systemd/system/azurefin-flatpak-preinstall.service
install -Dm644 /ctx/build/bazaar/azurefin-flatpak-preinstall.timer \
    /usr/lib/systemd/system/azurefin-flatpak-preinstall.timer
systemctl enable azurefin-flatpak-preinstall.timer
