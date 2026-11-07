#!/usr/bin/env bash
# Fresh disposable image validation, not an installed-system helper.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_IMAGE_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u azurefin-nix-initialize -u azurefin-nix-ready -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
systemctl is-active multi-user.target
echo AZUREFIN_NIX_IMAGE_BOOT_USABLE
for ((attempt=0; attempt<300; attempt++)); do
    if systemctl is-active --quiet azurefin-nix-ready.service; then break; fi
    if systemctl is-failed --quiet azurefin-nix-initialize.service azurefin-nix-ready.service; then false; fi
    sleep 2
done
systemctl is-active azurefin-nix-ready.service
python3 -c 'import json; assert json.load(open("/var/lib/azurefin/nix/state.json"))["phase"] == "complete"'
bash /usr/share/azurefin/nix/vm-multiuser.sh
