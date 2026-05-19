#!/usr/bin/bash

set -eoux pipefail

###############################################################################
# Main Build Script
###############################################################################
# This script follows the @ublue-os/bluefin pattern for build scripts.
# It uses set -eoux pipefail for strict error handling and debugging.
###############################################################################

# Source helper functions
# shellcheck source=/dev/null
source /ctx/build/copr-helpers.sh

# Enable nullglob for all glob operations to prevent failures on empty matches
shopt -s nullglob

echo "::group:: Copy Bluefin Config from Common"

# Copy just files from @projectbluefin/common (includes 00-entry.just which imports 60-custom.just)
mkdir -p /usr/share/ublue-os/just/
shopt -s nullglob
cp -r /ctx/oci/common/bluefin/usr/share/ublue-os/just/* /usr/share/ublue-os/just/
shopt -u nullglob

echo "::endgroup::"

echo "::group:: Copy Custom Files"

# Copy Brewfiles to standard location
mkdir -p /usr/share/ublue-os/homebrew/
cp /ctx/custom/brew/*.Brewfile /usr/share/ublue-os/homebrew/

# Consolidate Just Files
find /ctx/custom/ujust -iname '*.just' -exec printf "\n\n" \; -exec cat {} \; >> /usr/share/ublue-os/just/60-custom.just

# Copy Flatpak preinstall files
mkdir -p /etc/flatpak/preinstall.d/
cp /ctx/custom/flatpaks/*.preinstall /etc/flatpak/preinstall.d/

echo "::endgroup::"

echo "::group:: Copy System Files"

# Copy custom /etc, /lib, /usr files from the custom/ directory
if [ -d /ctx/custom/etc ]; then
    cp -r /ctx/custom/etc/. /etc/ 2>/dev/null || true
fi
if [ -d /ctx/custom/lib ]; then
    cp -r /ctx/custom/lib/. /lib/ 2>/dev/null || true
fi
if [ -d /ctx/custom/usr ]; then
    cp -r /ctx/custom/usr/. /usr/ 2>/dev/null || true
fi

# Make sleep hooks and libexec scripts executable
chmod +x /usr/libexec/ec_reboot.py 2>/dev/null || true
chmod +x /usr/local/bin/ec-reboot 2>/dev/null || true
chmod +x /lib/systemd/system-sleep/display-fix 2>/dev/null || true
chmod +x /lib/systemd/system-sleep/trackpad 2>/dev/null || true

echo "::endgroup::"

echo "::group:: Install Packages"

dnf install -y \
    msitools \
    python3 \
    python3-pip \
    curl \
    wget \
    kbd \
    fwupd \
    dkms \
    kernel-devel

echo "::endgroup::"

echo "::group:: System Configuration"

systemctl enable podman.socket

echo "::endgroup::"

# Restore default glob behavior
shopt -u nullglob

echo "Custom build complete!"
