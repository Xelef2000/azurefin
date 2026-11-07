#!/usr/bin/env bash
# Read-only assertions on an already interrupted disposable installation.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_BOOT_FAILURE_TEST_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u azurefin-nix-initialize -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
systemctl is-active multi-user.target
systemctl is-active systemd-user-sessions.service
echo AZUREFIN_NIX_BOOT_FAILURE_LOGIN_AVAILABLE
for ((attempt=0; attempt<90; attempt++)); do
    if systemctl is-failed --quiet azurefin-nix-initialize.service; then break; fi
    sleep 2
done
systemctl is-failed azurefin-nix-initialize.service
if systemctl is-active --quiet nix-daemon.service; then false; fi
if systemctl is-active --quiet azurefin-nix-ready.service; then false; fi
sha256sum --check /var/tmp/azurefin-nix-failure-checksums
python3 /var/tmp/azurefin-nix-initializer/initialize.py status | grep -Fx needs-reconciliation
journalctl -b -u azurefin-nix-initialize --no-pager | grep -F 'Guided manual repair is required'
echo AZUREFIN_NIX_BOOT_FAILURE_COMPLETE
sync
systemctl poweroff --no-block
