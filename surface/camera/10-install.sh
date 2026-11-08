#!/usr/bin/env bash
set -euo pipefail
[[ $(rpm --eval '%{_arch}') == aarch64 ]]
# Do not silently enable the relay on an untested kernel or unsigned loopback.
rpm -q kernel-azurefin-7.4~rc1-2.0.2.fc44.aarch64
cd /camera-rpms
sha256sum --check /ctx/camera/SHA256SUMS
runtime=$PWD/azurefin-camera-0.1-2.fc44.aarch64.rpm
integration=$PWD/azurefin-camera-integration-0.1-2.fc44.aarch64.rpm
# The unpublished rebuilt RPM intentionally retains the old local NVR.
# Reinstall is necessary: plain install could leave the older payload in place.
if rpm -q azurefin-camera >/dev/null 2>&1; then
    dnf5 reinstall -y "$runtime"
else
    dnf5 install -y "$runtime"
fi
if rpm -q azurefin-camera-integration >/dev/null 2>&1; then
    dnf5 reinstall -y "$integration"
else
    dnf5 install -y "$integration"
fi
/usr/lib/azurefin-camera/bin/v4l2-relayd --help | grep -q -- --pause-state-file
systemd-sysusers /usr/lib/sysusers.d/azurefin-camera.conf
udevadm verify /usr/lib/udev/rules.d/71-azurefin-camera.rules
systemd-analyze verify /usr/lib/systemd/system/azurefin-camera.service \
    /usr/lib/systemd/system/azurefin-camera-sleep.service
test "$(readlink /usr/lib/systemd/system/sleep.target.requires/azurefin-camera-sleep.service)" = ../azurefin-camera-sleep.service
systemctl enable azurefin-camera.service
systemctl is-enabled azurefin-camera.service
dnf5 clean all
