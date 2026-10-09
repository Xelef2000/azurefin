#!/usr/bin/env bash
# Prepare files only; never access a physical disk. Input is an extracted ISO.
set -euo pipefail
[[ $# == 2 && ${GITHUB_ACTIONS:-false} != true ]]
payload=$(realpath -e "$1")
output=$(realpath -m "$2")
[[ -d $payload && ! -e $output && ! -L $output ]]
mkdir "$output"
for path in images/pxeboot/vmlinuz images/pxeboot/initrd.img images/romulus-capture.cpio \
    images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb images/install.img osbuild.ks osbuild-base.ks; do
    [[ -f $payload/$path ]]
done
unsquashfs -s "$payload/images/install.img" | grep -qx 'Compression xz'
if grep -Eiq '^[[:space:]]*(clearpart|autopart|zerombr|part|partition|raid|volgroup|logvol|%pre)([[:space:]]|$)' \
    "$payload/osbuild.ks" "$payload/osbuild-base.ks"; then
    echo 'Unattended storage commands are forbidden.' >&2
    exit 1
fi
mkdir "$output/esp"
mcopy -s -i "$payload/images/efiboot.img" ::/EFI "$output/esp/"
mcopy -i "$payload/images/efiboot.img" ::/romulus-capture-token "$output/esp/"
mkdir -p "$output/esp/images/pxeboot" "$output/esp/images/dtbs/qcom"
cp "$payload/images/pxeboot/vmlinuz" "$payload/images/pxeboot/initrd.img" "$output/esp/images/pxeboot/"
cp "$payload/images/romulus-capture.cpio" "$output/esp/images/"
cp "$payload/images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb" "$output/esp/images/dtbs/qcom/"
# Preserve the capture UUID/token so the unchanged overlay recognizes the ESP.
uuid=$(blkid -p -s UUID -o value "$payload/images/efiboot.img")
[[ $uuid =~ ^[A-F0-9]{4}-[A-F0-9]{4}$ ]]
printf '%s\n' "$uuid" > "$output/esp-uuid"
sed -e "s/^search .*$/search --no-floppy --fs-uuid --set=root $uuid/" \
    -e 's/hd:LABEL=Fedora-S-dvd-aarch64-44/hd:LABEL=AZUREDATA/g' \
    -e 's/ rd.live.check//g' \
    "$payload/EFI/BOOT/grub.cfg" > "$output/esp/EFI/BOOT/grub.cfg"
grub2-script-check "$output/esp/EFI/BOOT/grub.cfg"
if grep -q 'Fedora-S-dvd-aarch64-44\|rd.live.check' "$output/esp/EFI/BOOT/grub.cfg"; then
    echo 'Old ISO lookup arguments remain in GRUB configuration.' >&2
    exit 1
fi
# All payload bytes remain original; only ESP GRUB selects the new data label.
(cd "$payload" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/payload.sha256"
(cd "$output/esp" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$output/esp.sha256"
echo GPT_TEST_FILES_PREPARED
