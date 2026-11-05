#!/usr/bin/env bash
# Disposable two-boot test. The extra virtual disk MUST have the test serial.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_ENCRYPTED_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u azurefin-nix-initialize -u azurefin-nix-ready -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing ]]
[[ $(lsblk -dn -o SERIAL /dev/vdb | xargs) == NIX_ENCRYPTED_TEST ]]
[[ $(blockdev --getsize64 /dev/vdb) == 2147483648 ]]
state=/var/tmp/azurefin-nix-encrypted-test
systemctl is-active multi-user.target
for ((attempt=0; attempt<180; attempt++)); do
    if systemctl is-active --quiet azurefin-nix-ready.service; then break; fi
    if systemctl is-failed --quiet azurefin-nix-initialize.service azurefin-nix-ready.service; then false; fi
    sleep 2
done
systemctl is-active azurefin-nix-ready.service
if [[ ! -d $state ]]; then
    mkdir -m700 "$state"
    test ! -e /etc/azurefin-nix-test.key
    test -z "$(blkid -p /dev/vdb || true)"
    # Random key lives ONLY in this disposable guest, never a production image.
    (umask 077; head -c32 /dev/urandom > /etc/azurefin-nix-test.key)
    cryptsetup luksFormat --batch-mode --type luks2 --pbkdf pbkdf2 --iter-time 1000 \
        --key-file /etc/azurefin-nix-test.key /dev/vdb
    cryptsetup open --key-file /etc/azurefin-nix-test.key /dev/vdb nix-test-store
    mkfs.ext4 -q /dev/mapper/nix-test-store
    mkdir "$state/mount"
    mount /dev/mapper/nix-test-store "$state/mount"
    systemctl stop nix-daemon.service
    cp -a /var/lib/nix/. "$state/mount/"
    # ext4's generated lost+found is harmless existing data on this owned store.
    umount "$state/mount"
    uuid=$(cryptsetup luksUUID /dev/vdb)
    printf 'nix-test-store UUID=%s /etc/azurefin-nix-test.key luks\n' "$uuid" >> /etc/crypttab
    printf '/dev/mapper/nix-test-store /var/lib/nix ext4 defaults 0 2\n' >> /etc/fstab
    printf '\n# Administrator configuration retained across encrypted-store boot\n' >> /etc/nix/nix.conf
    sha256sum /etc/nix/nix.conf /etc/passwd /etc/group /var/lib/azurefin/nix/state.json \
        /var/lib/nix/receipt.json > "$state/checksums"
    echo AZUREFIN_NIX_ENCRYPTED_PREPARED
else
    [[ /nix -ef /var/lib/nix ]]
    [[ $(findmnt -n -o SOURCE /var/lib/nix) == /dev/mapper/nix-test-store ]]
    cryptsetup status nix-test-store
    sha256sum --check "$state/checksums"
    for user in nix-test-three nix-test-four; do
        runuser -l "$user" -c 'command -v nix; nix store info --store daemon'
        runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --file /var/tmp/$user.nix"
    done
    [[ $(getenforce) == Enforcing ]]
    echo AZUREFIN_NIX_ENCRYPTED_COMPLETE
fi
sync
systemctl poweroff --no-block
