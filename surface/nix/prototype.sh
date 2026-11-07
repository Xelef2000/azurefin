#!/usr/bin/env bash
# Disposable guest ONLY. Not a first-boot initializer or a host installer.
set -euo pipefail
if [[ ${AZUREFIN_NIX_DISPOSABLE_GUEST:-} != yes ]]; then
    echo 'Refusing: run only in an explicitly designated disposable test guest.' >&2
    exit 2
fi
if [[ $(id -u) != 0 ]] || [[ $(getenforce) != Enforcing ]]; then
    echo 'Prototype requires guest root with SELinux enforcing.' >&2
    exit 2
fi
resources=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
installer=${1:?verified installer path required}
case $(uname -m) in
    aarch64) architecture=aarch64-linux ;;
    x86_64) architecture=x86_64-linux ;;
    *) exit 2 ;;
esac
python3 "$resources/verify_artifact.py" "$architecture" "$installer"
if [[ -L /nix ]] || ! mountpoint -q /nix; then
    echo 'Provision the image-owned /nix mount point and persistent bind mount first.' >&2
    exit 2
fi
if [[ ! /nix -ef /var/lib/nix ]]; then
    echo '/nix does not refer to /var/lib/nix.' >&2
    exit 2
fi
if [[ $(stat -c '%u:%g:%a' /nix) != 0:0:755 ]]; then
    echo '/nix must be root:root mode 0755.' >&2
    exit 2
fi
if [[ -n $(find /nix -mindepth 1 -maxdepth 1 -print -quit) ]]; then
    echo 'Refusing to overwrite an existing or partial installation.' >&2
    exit 2
fi
# Phase 1 is intentionally fresh-only. Production recovery needs its own
# durable ownership marker and reviewed receipt handling, not --force.
if getent group nixbld >/dev/null || getent group 30000 >/dev/null; then
    echo 'Build group collision.' >&2
    exit 2
fi
for index in {1..32}; do
    if getent passwd "nixbld$index" >/dev/null || getent passwd "$((30000 + index))" >/dev/null; then
        echo 'Build user collision.' >&2
        exit 2
    fi
done
mkdir -p /etc/nix
python3 - "$resources/nix.conf" <<'PY'
import os
from pathlib import Path
import stat
import sys

target = Path('/etc/nix/nix.conf')
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
except FileExistsError:
    if not stat.S_ISREG(target.lstat().st_mode):
        raise SystemExit('Existing nix.conf is not a regular file; not replacing it')
else:
    with os.fdopen(fd, 'wb') as output:
        output.write(Path(sys.argv[1]).read_bytes())
        output.flush()
        os.fsync(output.fileno())
PY
before=$(sha256sum /etc/nix/nix.conf)
work=$(mktemp -d /var/tmp/azurefin-nix-prototype.XXXXXXXX)
printf 'Prototype evidence directory: %s\n' "$work"
"$installer" plan --out-file "$work/upstream-plan.json" linux \
    --init none --no-start-daemon --no-modify-profile --skip-nix-conf
python3 "$resources/adapt_plan.py" "$work/upstream-plan.json" "$work/plan.json"
# No network namespace, even if the VM has a NIC for console access.
unshare --net -- "$installer" install --no-confirm "$work/plan.json"
[[ $(sha256sum /etc/nix/nix.conf) == "$before" ]]
test -f /nix/receipt.json
test -x /nix/var/nix/profiles/default/bin/nix
/nix/var/nix/profiles/default/bin/nix --version
du -sh /nix
echo 'Bootstrap completed; daemon, users, SELinux AVCs and reboot still require validation.'
