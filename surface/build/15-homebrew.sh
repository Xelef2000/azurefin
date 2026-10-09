#!/usr/bin/env bash
set -euo pipefail

# The OCI integration is copied by the Containerfile; never run brew as root
# during image construction or populate mutable /var in an image layer.
dnf5 install -y git /usr/bin/curl file procps-ng tar zstd \
    gcc gcc-c++ glibc-devel make patch
dnf5 clean all
test -s /usr/share/homebrew.tar.zst
zstd --test /usr/share/homebrew.tar.zst
test -f /usr/lib/systemd/system/brew-setup.service
test -f /etc/profile.d/brew.sh
systemctl preset brew-setup.service brew-update.timer brew-upgrade.timer
systemctl is-enabled brew-setup.service brew-update.timer brew-upgrade.timer
