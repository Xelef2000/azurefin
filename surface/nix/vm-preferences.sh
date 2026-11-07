#!/usr/bin/env bash
# Disposable overlay only: evaluate policy, never fetch/build unfree software.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_PREFERENCES_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
source=/var/tmp/nixpkgs-source
test -f "$source/flake.nix"
systemctl start azurefin-nix-ready.service
before=$(sha256sum /etc/nix/nix.conf)
for user in nix-test-three nix-test-four; do
    home=$(getent passwd "$user" | cut -d: -f6)
    test ! -e "$home/.config/nix/nix.conf"
    test ! -e "$home/.config/nixpkgs/config.nix"
    install -d -o "$user" -g "$user" "$home/.config" "$home/.config/nix" "$home/.config/nixpkgs"
    jobs=1
    allow=false
    if [[ $user == nix-test-four ]]; then jobs=2; allow=true; fi
    printf 'max-jobs = %s\n' "$jobs" > "$home/.config/nix/nix.conf"
    printf '{ allowUnfree = %s; }\n' "$allow" > "$home/.config/nixpkgs/config.nix"
    chown "$user:$user" "$home/.config/nix/nix.conf" "$home/.config/nixpkgs/config.nix"
    [[ $(runuser -l "$user" -c 'nix config show max-jobs') == "$jobs" ]]
    runuser -l "$user" -c 'nix store info --store daemon' 2>&1 | grep -Fx 'Trusted: 0'
    command="env -u NIXPKGS_ALLOW_UNFREE -u NIXPKGS_CONFIG NIX_REMOTE=daemon nix-instantiate --eval --strict --expr '(import $source { system = \"aarch64-linux\"; }).unrar.drvPath'"
    if [[ $allow == true ]]; then
        runuser -l "$user" -c "$command" | grep -E '^"/nix/store/.*unrar.*\.drv"$'
    else
        if runuser -l "$user" -c "$command" > /var/tmp/nix-preferences-denied.log 2>&1; then false; fi
        grep -F 'unfree license' /var/tmp/nix-preferences-denied.log
    fi
done
# A pure flake evaluation must not inherit the second user's unfree opt-in.
if runuser -l nix-test-four -c "env -u NIXPKGS_ALLOW_UNFREE -u NIXPKGS_CONFIG NIX_REMOTE=daemon nix eval --offline --no-write-lock-file --raw path:$source#legacyPackages.aarch64-linux.unrar.drvPath" > /var/tmp/nix-preferences-pure.log 2>&1; then false; fi
grep -F 'unfree license' /var/tmp/nix-preferences-pure.log
[[ $(sha256sum /etc/nix/nix.conf) == "$before" ]]
echo AZUREFIN_NIX_PREFERENCES_COMPLETE
sync
systemctl poweroff --no-block
