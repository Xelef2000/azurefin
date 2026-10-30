#!/usr/bin/env bash
# Run before the expensive compose, not only during post-processing.
set -euo pipefail
missing=0
for tool in podman python3 xorriso mcopy grub2-script-check implantisomd5 \
    checkisomd5 unsquashfs lsinitrd mount umount unshare find od sha256sum split; do
    if ! command -v "$tool" >/dev/null; then
        printf 'Missing ISO build prerequisite: %s\n' "$tool" >&2
        missing=1
    fi
done
(( missing == 0 ))
if [[ -e /var/lib/containers/storage/overlay/.has-mount-program ]]; then
    python3 - <<'PY'
import os
try:
    fd = os.open('/dev/fuse', os.O_RDWR)
except OSError as error:
    raise SystemExit(f'ISO builder requires accessible /dev/fuse for its FUSE image store: {error}')
else:
    os.close(fd)
PY
fi
