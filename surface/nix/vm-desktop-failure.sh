#!/usr/bin/env bash
# Graphical login availability with a refused foreign store, disposable VM only.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_DESKTOP_FAILURE_TEST_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u gdm -u azurefin-nix-initialize --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
for unit in graphical.target systemd-user-sessions.service gdm.service; do
    systemctl is-active "$unit"
done
for ((attempt=0; attempt<180; attempt++)); do
    if systemctl is-failed --quiet azurefin-nix-initialize.service; then break; fi
    sleep 2
done
systemctl is-failed azurefin-nix-initialize.service
for unit in nix-daemon.service azurefin-nix-ready.service; do
    if systemctl is-active --quiet "$unit"; then false; fi
done
sha256sum --check /var/tmp/azurefin-nix-desktop-checksums
python3 /usr/share/azurefin/nix/initialize.py status | grep -Fx foreign
greeter_available() {
    local session rest kind
    while read -r session rest; do
        [[ $(loginctl show-session "$session" -p Class --value) == greeter ]] || continue
        kind=$(loginctl show-session "$session" -p Type --value)
        [[ $kind == wayland || $kind == x11 ]] || continue
        [[ $(loginctl show-session "$session" -p Active --value) == yes ]] || continue
        return 0
    done < <(loginctl list-sessions --no-legend)
    return 1
}
for ((attempt=0; attempt<180; attempt++)); do
    if greeter_available; then break; fi
    sleep 2
done
greeter_available
loginctl list-sessions --no-legend
echo AZUREFIN_NIX_DESKTOP_FAILURE_GREETER_AVAILABLE
# Leave a brief window for the host to capture the virtual display.
sleep 30
echo AZUREFIN_NIX_DESKTOP_FAILURE_COMPLETE
sync
systemctl poweroff --no-block
