#!/usr/bin/env bash
# Test rollback to an image with no /nix support, then recovery, on a VM only.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_PREINTEGRATION_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
systemctl is-active multi-user.target
state=/var/tmp/azurefin-nix-preintegration-test
if [[ -e /usr/lib/systemd/system/azurefin-nix-ready.timer ]]; then
    for ((attempt=0; attempt<180; attempt++)); do
        if systemctl is-active --quiet azurefin-nix-ready.service; then break; fi
        if systemctl is-failed --quiet azurefin-nix-initialize.service azurefin-nix-ready.service; then false; fi
        sleep 2
    done
    systemctl is-active azurefin-nix-ready.service
    [[ /nix -ef /var/lib/nix ]]
    if [[ ! -d $state ]]; then
        mkdir -m700 "$state"
        sha256sum /etc/nix/nix.conf /var/lib/nix/receipt.json /etc/passwd /etc/group \
            /var/lib/azurefin/nix/state.json > "$state/checksums"
        [[ $(lsblk -dn -o SERIAL /dev/vdb | xargs) == NIX_PREBASE_SOURCE ]]
        mkdir "$state/source"
        mount -o ro /dev/vdb "$state/source"
        test -s "$state/source/base/index.json"
        bootc switch --transport oci "$state/source/base"
        touch "$state/staged"
        echo AZUREFIN_NIX_PREINTEGRATION_STAGED
    else
        test -f "$state/return-staged"
        sha256sum --check "$state/checksums"
        for user in nix-test-three nix-test-four; do
            runuser -l "$user" -c 'command -v nix; nix store info --store daemon'
            runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --file /var/tmp/$user.nix"
        done
        echo AZUREFIN_NIX_PREINTEGRATION_RECOVERED
    fi
else
    test -f "$state/staged"
    test ! -e /nix
    if systemctl is-active --quiet nix-daemon.service; then false; fi
    sha256sum --check "$state/checksums"
    # Integration is absent, but the persistent store and ownership state remain.
    test -d /var/lib/nix/store
    bootc rollback
    touch "$state/return-staged"
    echo AZUREFIN_NIX_PREINTEGRATION_PRESERVED
fi
sync
systemctl poweroff --no-block
