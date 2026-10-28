#!/usr/bin/env bash
set -euo pipefail

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
