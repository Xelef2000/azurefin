#!/usr/bin/env bash
# Install only code and approved hashes. Firmware stays on the user's boot disk.
set -euo pipefail
python3 /usr/libexec/azurefin/firmware_bundle.py \
    --policy /usr/share/azurefin/firmware-policy.json --emit-manifest \
    > /usr/share/azurefin/boot-firmware.sha256
test -s /usr/share/azurefin/boot-firmware.sha256
chmod 0644 /usr/share/azurefin/boot-firmware.sha256
chmod 0755 /usr/lib/dracut/modules.d/91azurefin-firmware/*.sh
install -d /usr/lib/dracut/dracut.conf.d
printf '%s\n' 'add_dracutmodules+=" azurefin-firmware "' \
    > /usr/lib/dracut/dracut.conf.d/52-azurefin-firmware-store.conf
# Do not bake a boot UUID into the image, provision files, change kernel args,
# enable updates, or install a trust policy here. Migration is a separate gate.
