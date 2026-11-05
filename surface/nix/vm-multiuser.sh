#!/usr/bin/env bash
# Disposable full-system guest only; never a production initialization helper.
set -euo pipefail
trap 'echo AZUREFIN_NIX_MULTIUSER_FAILED; journalctl -b -u nix-daemon --no-pager; journalctl -b -k --no-pager | grep -i avc || true; systemctl poweroff --no-block' ERR
[[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} == yes ]]
[[ $(getenforce) == Enforcing ]]
[[ /nix -ef /var/lib/nix ]]
case ,$(findmnt -n -o OPTIONS /), in
    *,ro,*) ;;
    *) exit 1 ;;
esac
echo AZUREFIN_NIX_MULTIUSER_BEGIN
restorecon /etc/profile.d/azurefin-nix.sh /etc/systemd/system/nix-daemon.service
systemctl daemon-reload
systemctl start nix-daemon.service
systemctl is-active nix-daemon.service
ls -Zd /nix /var/lib/nix /nix/store
ps -Z -p "$(pgrep -x nix-daemon | head -n1)"
touch /etc/azurefin-nix-host-only
busybox=(/nix/store/*-busybox-*/bin/busybox)
[[ ${#busybox[@]} == 1 && -x ${busybox[0]} ]]
builder=${busybox[0]%/bin/busybox}
for user in nix-test-one nix-test-two; do
    if getent passwd "$user"; then
        echo 'Test account already exists; refusing to reuse it.' >&2
        exit 1
    fi
    useradd --create-home "$user"
    # Login shell must find Nix without a manually supplied Nix PATH.
    runuser -l "$user" -c 'command -v nix; nix --version'
    expression="let bb = builtins.storePath \"$builder\"; in derivation {
      name = \"azurefin-$user-sandbox\"; system = \"aarch64-linux\";
      builder = bb + \"/bin/busybox\";
      args = [ \"sh\" \"-ec\" ''
        test ! -e /etc/azurefin-nix-host-only
        uid=\$(\${bb}/bin/busybox id -u)
        test \"\$uid\" -ge 30001
        test \"\$uid\" -le 30032
        printf 'sandbox uid=%s\\n' \"\$uid\" > \"\$out\"
      '' ];
    }"
    printf '%s\n' "$expression" > "/var/tmp/$user.nix"
    runuser -l "$user" -c "NIX_REMOTE=daemon nix build --offline --no-link --print-out-paths --file /var/tmp/$user.nix"
done
[[ $(getenforce) == Enforcing ]]
echo AZUREFIN_NIX_MULTIUSER_COMPLETE
journalctl -b -k --no-pager | grep -i avc || true
sync
systemctl poweroff --no-block
