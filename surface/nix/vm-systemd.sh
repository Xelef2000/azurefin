#!/usr/bin/env bash
# Test fixture for an explicitly marked disposable overlay only.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_SYSTEMD_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u azurefin-nix-initialize -u azurefin-nix-ready -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
resources=/var/tmp/azurefin-nix-initializer
if [[ ! -f /var/tmp/azurefin-nix-systemd-prepared ]]; then
    [[ /nix -ef /var/lib/nix ]]
    test ! -e /var/lib/nix-before-systemd-test
    test ! -e /var/lib/azurefin/nix
    systemctl stop nix-daemon.service
    mv /var/lib/nix /var/lib/nix-before-systemd-test
    install -d -m755 /var/lib/nix
    for index in {1..32}; do
        [[ $(id -u "nixbld$index") == "$((30000 + index))" ]]
        userdel "nixbld$index"
    done
    [[ $(getent group nixbld | cut -d: -f3) == 30000 ]]
    groupdel nixbld
    install -m644 "$resources"/systemd/* /etc/systemd/system/
    install -d /etc/systemd/system/azurefin-nix-initialize.service.d /etc/systemd/system/azurefin-nix-ready.service.d
    install -d /etc/systemd/system/azurefin-nix-directory.service.d
    install -m644 "$resources/vm-directory.conf" /etc/systemd/system/azurefin-nix-directory.service.d/test.conf
    install -m644 "$resources/vm-initialize.conf" /etc/systemd/system/azurefin-nix-initialize.service.d/test.conf
    install -m644 "$resources/vm-finalize.conf" /etc/systemd/system/azurefin-nix-ready.service.d/test.conf
    install -m644 "$resources/vm-systemd.service" /etc/systemd/system/azurefin-nix-vm-test.service
    restorecon -RF /etc/systemd/system
    sha256sum /etc/nix/nix.conf > /var/tmp/azurefin-nix-systemd-config.sha256
    systemctl enable azurefin-nix-ready.timer
    touch /var/tmp/azurefin-nix-systemd-prepared
    echo AZUREFIN_NIX_SYSTEMD_PREPARED
else
    # This service has no dependency on Nix: ordinary boot must finish while
    # initialization runs asynchronously through the timer.
    systemctl is-active multi-user.target
    echo AZUREFIN_NIX_SYSTEMD_BOOT_USABLE
    for ((attempt=0; attempt<180; attempt++)); do
        if systemctl is-active --quiet azurefin-nix-ready.service; then break; fi
        if systemctl is-failed --quiet azurefin-nix-initialize.service azurefin-nix-ready.service; then
            false
        fi
        sleep 2
    done
    systemctl is-active azurefin-nix-ready.service
    python3 -c 'import json; assert json.load(open("/var/lib/azurefin/nix/state.json"))["phase"] == "complete"'
    sha256sum --check /var/tmp/azurefin-nix-systemd-config.sha256
    [[ /nix -ef /var/lib/nix ]]
    for user in nix-test-three nix-test-four; do
        runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --file /var/tmp/$user.nix"
        runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --rebuild --no-link --file /var/tmp/$user.nix"
        runuser -l "$user" -c 'nix store info --store daemon'
    done
    echo AZUREFIN_NIX_SYSTEMD_COMPLETE
    journalctl -b -k --no-pager | grep -i avc || true
fi
sync
systemctl poweroff --no-block
