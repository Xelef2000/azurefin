#!/usr/bin/env bash
# This runs in the packages stage, before any Microsoft input is mounted.
set -euo pipefail
for path in /usr/lib/firmware/qcom/x1e80100/microsoft \
    /etc/romulus-bluetooth-address; do
    if [[ -e $path || -L $path ]]; then
        echo "Private firmware or per-device configuration in public base: $path" >&2
        exit 1
    fi
done
azurefin-extract-firmware --help | grep -q -- '--download'
azurefin-extract-firmware --help | grep -q -- '--bluetooth-address'
echo FIRMWARE_FREE_ASSEMBLY_BASE_VERIFIED
