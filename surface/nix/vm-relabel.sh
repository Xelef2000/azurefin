#!/usr/bin/env bash
# Disposable VM only: verify SELinux labels through the persistent backing path.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_RELABEL_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -k --no-pager | grep -i avc || true; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
[[ $(getenforce) == Enforcing && /nix -ef /var/lib/nix ]]
case ,$(findmnt -n -o OPTIONS /), in *,ro,*) ;; *) exit 1 ;; esac
echo AZUREFIN_NIX_RELABEL_BEGIN
daemon=$(readlink -f /nix/var/nix/profiles/default/bin/nix-daemon)
backing=/var/lib/nix/${daemon#/nix/}
matchpathcon "$daemon" "$backing"
# Preserve the upstream path rules when restorecon walks the backing store.
# This is a fresh diagnostic VM mapping, not an override of an admin mapping.
semanage fcontext -a -e /nix /var/lib/nix
restorecon -RF /var/lib/nix
matchpathcon -V "$daemon" "$backing"
[[ $(stat -c %C "$daemon") == "$(stat -c %C "$backing")" ]]
systemctl start nix-daemon.service
for user in nix-test-three nix-test-four; do
    # Force rebuilding the existing derivation rather than just reading a cache.
    runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --rebuild --no-link --file /var/tmp/$user.nix"
done
[[ $(getenforce) == Enforcing ]]
echo AZUREFIN_NIX_RELABEL_COMPLETE
journalctl -b -k --no-pager | grep -i avc || true
sync
systemctl poweroff --no-block
