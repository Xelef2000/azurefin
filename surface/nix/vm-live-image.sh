#!/usr/bin/env bash
# Local diagnostic derivative only: exercise exclusions in a real RAM-backed live root.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_LIVE_IMAGE_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; systemctl poweroff --no-block' ERR
grep -qw rd.live.image /proc/cmdline
[[ $(getenforce) == Enforcing ]]
[[ $(findmnt -n -o FSTYPE /) == overlay ]]
python3 /usr/libexec/azurefin-live-vm-check.py
for unit in azurefin-nix-ready.timer azurefin-nix-directory.service nix.mount \
    azurefin-nix-initialize.service nix-daemon.service azurefin-nix-ready.service; do
    systemctl start "$unit"
    [[ $(systemctl show "$unit" -p ConditionResult --value) == no ]]
    if systemctl is-active --quiet "$unit"; then false; fi
done
if mountpoint -q /nix; then false; fi
test ! -e /var/lib/nix
test ! -e /var/lib/azurefin/nix/state.json
test ! -e /etc/nix/nix.conf
# Expand PATH inside the live user's login shell, not this root test process.
# shellcheck disable=SC2016
runuser -u liveuser -- bash -lc '
    case ":$PATH:" in *:/nix/var/nix/profiles/default/bin:*) ;; *) exit 1 ;; esac
    ! command -v nix
'
echo AZUREFIN_NIX_LIVE_IMAGE_COMPLETE
sync
systemctl poweroff --no-block
