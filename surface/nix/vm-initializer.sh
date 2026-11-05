#!/usr/bin/env bash
# Destructive fixture reset ONLY on the disposable copy-on-write VM overlay.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_INITIALIZER_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; journalctl -b -u nix-daemon --no-pager; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
test -f /var/tmp/azurefin-nix-overlay-only
[[ $(getenforce) == Enforcing && /nix -ef /var/lib/nix ]]
test ! -e /var/lib/nix-before-initializer-test
# Preserve all old store data in this isolated test disk. No host data is touched.
systemctl stop nix-daemon.service
mv /var/lib/nix /var/lib/nix-before-initializer-test
install -d -m755 /var/lib/nix
# Keep the mount unit active: stopping it also stops this dependent service.
mount --bind /var/lib/nix /nix
for index in {1..32}; do
    [[ $(id -u "nixbld$index") == "$((30000 + index))" ]]
    userdel "nixbld$index"
done
[[ $(getent group nixbld | cut -d: -f3) == 30000 ]]
groupdel nixbld
before=$(sha256sum /etc/nix/nix.conf)
resources=/var/tmp/azurefin-nix-initializer
python3 "$resources/initialize.py" initialize
[[ $(sha256sum /etc/nix/nix.conf) == "$before" ]]
systemctl start nix-daemon.service
python3 "$resources/initialize.py" finalize
python3 "$resources/initialize.py" status
receipt=$(sha256sum /nix/receipt.json)
python3 "$resources/initialize.py" initialize
python3 "$resources/initialize.py" finalize
[[ $(sha256sum /nix/receipt.json) == "$receipt" ]]
[[ $(sha256sum /etc/nix/nix.conf) == "$before" ]]
echo AZUREFIN_NIX_INITIALIZER_COMPLETE
journalctl -b -k --no-pager | grep -i avc || true
sync
systemctl poweroff --no-block
