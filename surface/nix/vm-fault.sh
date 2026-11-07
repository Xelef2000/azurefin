#!/usr/bin/env bash
# Fault injection ONLY in a marked copy-on-write disposable VM overlay.
set -euo pipefail
trap 'printf "AZUREFIN_NIX_FAULT_FAILED line=%s status=%s command=%s\n" "$LINENO" "$?" "$BASH_COMMAND"; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes && $(id -u) == 0 ]]
test -f /var/tmp/azurefin-nix-overlay-only
mode=$(cat /var/tmp/azurefin-nix-fault-mode)
[[ $mode == full || $mode == killed ]]
[[ $(getenforce) == Enforcing && /nix -ef /var/lib/nix ]]
test ! -e /var/lib/nix-before-fault-test
systemctl stop nix-daemon.service
mv /var/lib/nix /var/lib/nix-before-fault-test
install -d -m755 /var/lib/nix
if [[ $mode == full ]]; then
    mount -t tmpfs -o size=8M,mode=755 tmpfs /var/lib/nix
fi
mount --bind /var/lib/nix /nix
for index in {1..32}; do
    [[ $(id -u "nixbld$index") == "$((30000 + index))" ]]
    userdel "nixbld$index"
done
[[ $(getent group nixbld | cut -d: -f3) == 30000 ]]
groupdel nixbld
before=$(sha256sum /etc/nix/nix.conf)
resources=/var/tmp/azurefin-nix-initializer
if [[ $mode == full ]]; then
    if python3 "$resources/initialize.py" initialize > /var/tmp/nix-fault.log 2>&1; then
        echo 'Unexpected initialization success on undersized store'
        false
    fi
    cat /var/tmp/nix-fault.log
    grep -i 'No space left on device' /var/tmp/nix-fault.log
else
    setsid python3 "$resources/initialize.py" initialize > /var/tmp/nix-fault.log 2>&1 &
    child=$!
    reached=no
    for _ in {1..600}; do
        if python3 -c 'import json; assert json.load(open("/var/lib/azurefin/nix/state.json"))["phase"] == "installing"' 2>/dev/null; then
            reached=yes
            break
        fi
        kill -0 "$child"
        sleep 0.1
    done
    [[ $reached == yes ]]
    kill -KILL -- "-$child"
    if wait "$child"; then false; fi
    cat /var/tmp/nix-fault.log
fi
python3 "$resources/initialize.py" status | grep -x needs-reconciliation
store_before=$(du -sb /nix)
state_before=$(sha256sum /var/lib/azurefin/nix/state.json)
if python3 "$resources/initialize.py" initialize > /var/tmp/nix-retry.log 2>&1; then
    echo 'Unexpected replay of interrupted installation'
    false
fi
grep -F 'Refusing automatic changes: needs-reconciliation' /var/tmp/nix-retry.log
[[ $(sha256sum /etc/nix/nix.conf) == "$before" ]]
[[ $(sha256sum /var/lib/azurefin/nix/state.json) == "$state_before" ]]
[[ $(du -sb /nix) == "$store_before" ]]
echo "AZUREFIN_NIX_FAULT_COMPLETE mode=$mode"
sync
systemctl poweroff --no-block
