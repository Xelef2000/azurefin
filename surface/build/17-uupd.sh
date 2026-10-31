#!/usr/bin/env bash
set -euo pipefail

# Use Universal Blue's packaged updater, not a fork of its update engine.
# Keep the COPR disabled outside this transaction, including on failure.
dnf5 copr enable -y ublue-os/packages
dnf5 copr disable -y ublue-os/packages
dnf5 install -y --setopt=install_weak_deps=False \
    --enablerepo=copr:copr.fedorainfracloud.org:ublue-os:packages \
    uupd-1.5.2-1.fc44.aarch64 just
dnf5 clean all

install -Dm644 /ctx/build/uupd/config.json /etc/uupd/config.json
install -Dm644 /ctx/build/uupd/system-update.desktop /usr/share/applications/azurefin-system-update.desktop
install -Dm755 /ctx/build/uupd/ujust /usr/bin/ujust
install -Dm644 /ctx/build/uupd/00-entry.just /usr/share/ublue-os/just/00-entry.just
install -Dm644 /ctx/build/uupd/update.just /usr/share/ublue-os/just/update.just
install -Dm644 /ctx/build/uupd/20-azurefin-safety.conf /usr/lib/systemd/system/uupd.service.d/20-azurefin-safety.conf
install -Dm644 /ctx/build/uupd/20-azurefin-schedule.conf /usr/lib/systemd/system/uupd.timer.d/20-azurefin-schedule.conf

# Use one scheduler for OS, Flatpak and Homebrew updates. Keep brew-setup.service
# for initial provisioning; uupd replaces only its recurring update timers.
systemctl disable brew-update.timer brew-upgrade.timer
systemctl unmask uupd.timer
systemctl enable uupd.timer
test "$(systemctl is-enabled uupd.timer)" = enabled
test "$(systemctl is-enabled brew-update.timer)" = disabled
test "$(systemctl is-enabled brew-upgrade.timer)" = disabled
uupd config-dump
