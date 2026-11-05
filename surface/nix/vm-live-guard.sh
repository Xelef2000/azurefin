#!/usr/bin/env bash
# Exercise real systemd live-session conditions on a disposable installed overlay.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_LIVE_GUARD_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
grep -qw rd.live.image /proc/cmdline
[[ $(getenforce) == Enforcing ]]
systemctl is-active multi-user.target
systemctl is-active systemd-user-sessions.service
for unit in azurefin-nix-ready.timer azurefin-nix-directory.service nix.mount \
    azurefin-nix-initialize.service nix-daemon.service azurefin-nix-ready.service; do
    systemctl start "$unit"
    [[ $(systemctl show "$unit" -p ConditionResult --value) == no ]]
    if systemctl is-active --quiet "$unit"; then false; fi
done
if mountpoint -q /nix; then false; fi
sha256sum --check /var/tmp/azurefin-nix-live-checksums
echo AZUREFIN_NIX_LIVE_GUARD_COMPLETE
sync
systemctl poweroff --no-block
