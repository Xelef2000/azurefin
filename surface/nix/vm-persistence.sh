#!/usr/bin/env bash
# Two-boot diagnostic for the existing disposable VM, never a host initializer.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_PERSISTENCE_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
[[ $(getenforce) == Enforcing && /nix -ef /var/lib/nix ]]
case ,$(findmnt -n -o OPTIONS /), in *,ro,*) ;; *) exit 1 ;; esac
state=/var/lib/azurefin-nix-persistence-test
systemctl start nix-daemon.service
runtime=$(readlink -f /nix/var/nix/profiles/default/bin/nix)
runtime=${runtime%/bin/nix}
if [[ ! -e $state ]]; then
    mkdir -m700 "$state"
    # Simulate an administrator customization without weakening sandbox policy.
    printf '\n# Azurefin persistence test: administrator-owned configuration\n' >> /etc/nix/nix.conf
    for user in nix-test-three nix-test-four; do
        runuser -l "$user" -c "NIX_REMOTE=daemon nix-env --profile \"\$HOME/.nix-profile\" --set '$runtime'"
        # Expand HOME in the target user's shell, not the root test service.
        # shellcheck disable=SC2016
        runuser -l "$user" -c 'readlink -f "$HOME/.nix-profile"' > "$state/$user.profile"
        output=$(runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --print-out-paths --file /var/tmp/$user.nix")
        [[ $output == /nix/store/* && $output != *$'\n'* ]]
        sha256sum "$output" >> "$state/checksums"
    done
    sha256sum /etc/nix/nix.conf /nix/receipt.json /etc/passwd /etc/group >> "$state/checksums"
    cat /proc/sys/kernel/random/boot_id > "$state/boot-id"
    touch "$state/prepared"
    echo AZUREFIN_NIX_PERSISTENCE_PREPARED
else
    test -f "$state/prepared"
    [[ $(cat "$state/boot-id") != "$(cat /proc/sys/kernel/random/boot_id)" ]]
    sha256sum -c "$state/checksums"
    for user in nix-test-three nix-test-four; do
        # shellcheck disable=SC2016
        profile=$(runuser -l "$user" -c 'readlink -f "$HOME/.nix-profile"')
        [[ $profile == "$(cat "$state/$user.profile")" ]]
        runuser -l "$user" -c 'command -v nix; nix --version; NIX_REMOTE=daemon nix store ping'
        runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --file /var/tmp/$user.nix"
    done
    # The fresh-only prototype must refuse an existing store without changes.
    if bash /usr/share/azurefin/nix-prototype/prototype.sh /usr/libexec/azurefin-nix-installer > "$state/retry.log" 2>&1; then
        echo 'ERROR: fresh-only bootstrap accepted an existing installation'
        false
    fi
    grep -F 'Refusing to overwrite an existing or partial installation.' "$state/retry.log"
    sha256sum -c "$state/checksums"
    [[ $(getenforce) == Enforcing ]]
    echo AZUREFIN_NIX_PERSISTENCE_COMPLETE
fi
journalctl -b -k --no-pager | grep -i avc || true
sync
systemctl poweroff --no-block
