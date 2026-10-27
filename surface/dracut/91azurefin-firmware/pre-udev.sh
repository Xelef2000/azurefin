#!/usr/bin/bash
# A failed loader never exposes unchecked firmware; retain diagnostics for
# recovery. Firmware-free installer boots can omit the opt-in kernel argument.
if ! timeout --kill-after=5 90 /usr/bin/bash /usr/libexec/azurefin-load-boot-firmware; then
    echo 'Azurefin: boot firmware load FAILED; see /run/azurefin-firmware.log' >/dev/console
    : >/run/azurefin-firmware.failed
fi
