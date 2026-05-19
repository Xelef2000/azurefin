#!/usr/bin/bash

set -eoux pipefail

# Enable nullglob for all glob operations to prevent failures on empty matches
shopt -s nullglob

echo "::group:: Install ujust"

# Install just (ujust) for Surface-specific commands
dnf install -y just

# Install custom just files
mkdir -p /usr/share/ublue-os/just/
find /ctx/custom/ujust -iname '*.just' -exec cat {} \; >> /usr/share/ublue-os/just/60-custom.just

echo "::endgroup::"

echo "::group:: Copy Custom Files"

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
    fwupd

echo "::endgroup::"

echo "::group:: System Configuration"

systemctl enable podman.socket

echo "::endgroup::"

# Restore default glob behavior
shopt -u nullglob

echo "Custom build complete!"
