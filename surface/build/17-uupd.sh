#!/usr/bin/env bash
set -euo pipefail

# Use Universal Blue's packaged updater, not a fork of its update engine.
# Keep the COPR disabled outside this transaction, including on failure.
dnf5 copr enable -y ublue-os/packages
dnf5 copr disable -y ublue-os/packages
dnf5 install -y --setopt=install_weak_deps=False \
    --enablerepo=copr:copr.fedorainfracloud.org:ublue-os:packages \
    uupd-1.5.0-1.fc44.aarch64
dnf5 clean all

install -Dm644 /ctx/build/uupd/config.json /etc/uupd/config.json
install -Dm644 /ctx/build/uupd/application-updates.desktop \
    /usr/share/applications/azurefin-application-updates.desktop

# Package presets must not turn on unattended updates during this preview.
# OS updates remain disabled even for manual uupd runs: fresh installations
# still provision a private firmware image. The tested boot-store path must
# become the installation default before enabling the system module.
systemctl disable uupd.timer
systemctl mask uupd.timer
test "$(systemctl is-enabled uupd.timer)" = masked
uupd config-dump
