#!/usr/bin/env bash
# Assert refusal on an initialized disposable snapshot without ownership metadata.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_FOREIGN_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u azurefin-nix-initialize -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
test -f /var/lib/azurefin/nix-before-foreign-test/state.json
[[ $(getenforce) == Enforcing ]]
systemctl is-active multi-user.target
systemctl is-active systemd-user-sessions.service
for ((attempt=0; attempt<90; attempt++)); do
    if systemctl is-failed --quiet azurefin-nix-initialize.service; then break; fi
    sleep 2
done
systemctl is-failed azurefin-nix-initialize.service
if systemctl is-active --quiet nix-daemon.service; then false; fi
if systemctl is-active --quiet azurefin-nix-ready.service; then false; fi
sha256sum --check /var/tmp/azurefin-nix-foreign-checksums
python3 /usr/share/azurefin/nix/initialize.py status | grep -Fx foreign
test ! -e /var/lib/azurefin/nix/state.json
journalctl -b -u azurefin-nix-initialize --no-pager | grep -F 'Refusing automatic changes: foreign'
echo AZUREFIN_NIX_FOREIGN_COMPLETE
sync
systemctl poweroff --no-block
