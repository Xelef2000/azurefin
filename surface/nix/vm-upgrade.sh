#!/usr/bin/env bash
# Three-boot upgrade/rollback test, only on a marked disposable VM overlay.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_UPGRADE_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u azurefin-nix-initialize -u azurefin-nix-ready -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
state=/var/tmp/azurefin-nix-upgrade-test
systemctl is-active multi-user.target
for ((attempt=0; attempt<180; attempt++)); do
    if systemctl is-active --quiet azurefin-nix-ready.service; then break; fi
    if systemctl is-failed --quiet azurefin-nix-initialize.service azurefin-nix-ready.service; then false; fi
    sleep 2
done
systemctl is-active azurefin-nix-ready.service
[[ /nix -ef /var/lib/nix ]]
if [[ ! -d $state ]]; then
    test ! -e /usr/share/azurefin/nix/vm-generation
    mkdir -m700 "$state"
    printf '\n# Administrator configuration retained through OS upgrade/rollback\n' >> /etc/nix/nix.conf
    runtime=$(readlink -f /nix/var/nix/profiles/default/bin/nix)
    runtime=${runtime%/bin/nix}
    for user in nix-test-three nix-test-four; do
        runuser -l "$user" -c "NIX_REMOTE=daemon nix-env --profile \"\$HOME/.nix-profile\" --set '$runtime'"
        # shellcheck disable=SC2016
        runuser -l "$user" -c 'readlink -f "$HOME/.nix-profile"' > "$state/$user.profile"
    done
    sha256sum /etc/nix/nix.conf /nix/receipt.json /etc/passwd /etc/group \
        /var/lib/azurefin/nix/state.json > "$state/checksums"
    [[ $(lsblk -dn -o SERIAL /dev/vdb | xargs) == NIX_UPGRADE_SOURCE ]]
    mkdir "$state/source"
    mount -o ro /dev/vdb "$state/source"
    test -s "$state/source/generation2/index.json"
    bootc switch --transport oci "$state/source/generation2"
    touch "$state/staged"
    echo AZUREFIN_NIX_UPGRADE_STAGED
else
    test -f "$state/staged"
    sha256sum --check "$state/checksums"
    for user in nix-test-three nix-test-four; do
        # shellcheck disable=SC2016
        profile=$(runuser -l "$user" -c 'readlink -f "$HOME/.nix-profile"')
        [[ $profile == "$(cat "$state/$user.profile")" ]]
        runuser -l "$user" -c 'command -v nix; nix store info --store daemon'
        runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --file /var/tmp/$user.nix"
    done
    if [[ ! -e $state/rollback-staged ]]; then
        grep -Fx generation2 /usr/share/azurefin/nix/vm-generation
        grep -F 'Generation two reference' /usr/share/azurefin/nix/nix.conf
        if grep -q 'Generation two reference' /etc/nix/nix.conf; then false; fi
        bootc rollback
        touch "$state/rollback-staged"
        echo AZUREFIN_NIX_ROLLBACK_STAGED
    else
        test ! -e /usr/share/azurefin/nix/vm-generation
        echo AZUREFIN_NIX_UPGRADE_ROLLBACK_COMPLETE
    fi
fi
sync
systemctl poweroff --no-block
