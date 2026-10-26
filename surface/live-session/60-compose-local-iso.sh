#!/usr/bin/env bash
# Local prototype only: reuse verified EFI boot layout, not installer payload.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-false} != true ]]
source_iso=$(realpath -e "${1:?source installer ISO required}")
artifacts=$(realpath -e "${2:?labelled live VM artifact directory required}")
output=$(realpath -m "${3:?NEW output ISO required}")
mode=${4:-desktop}
[[ $mode == desktop || $mode == installer ]]
[[ -f $source_iso && ! -e $output && ! -L $output && $output == *.iso ]]
for name in root.squashfs initrd vmlinuz smbios.mod romulus13.dtb; do test -s "$artifacts/$name"; done
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
work=$(mktemp -d -p "$(dirname "$output")" alpha3-live-iso.XXXXXXXX)
xorriso -osirrox on -indev "$source_iso" \
    -extract /images/efiboot.img "$work/efiboot.img"
python3 "$script_dir/iso_grub.py" "$work/grub.cfg"
grub2-script-check "$work/grub.cfg"
mcopy -o -i "$work/efiboot.img" "$work/grub.cfg" ::/EFI/BOOT/grub.cfg
mcopy -i "$work/efiboot.img" ::/EFI/BOOT/grub.cfg "$work/grub-verified.cfg"
cmp "$work/grub.cfg" "$work/grub-verified.cfg"
payload_args=()
if [[ $mode == desktop ]]; then
    payload_args=(-rm_r /azurefin --)
else
    # Keep the audited base OCI and its exact firmware tooling, but never
    # inherit stale provisioning code from the source installer's support bundle.
    mkdir "$work/support"
    xorriso -osirrox on -indev "$source_iso" \
        -extract /azurefin/support/firmware-tools "$work/support/firmware-tools"
    cp -a "$script_dir/../build" "$work/support/"
    for name in 28-prepare-installer-payload.sh Containerfile.provision installer_fix_fstab.py; do
        cp "$script_dir/../$name" "$work/support/"
    done
    python3 "$script_dir/../verify_installer_support.py" "$script_dir/.." "$work/support"
    payload_args=(-rm_r /azurefin/support -- -map "$work/support" /azurefin/support)
fi
# Accept both the original installer and a previously composed live ISO.
# The latter has already had these Anaconda-only files removed.
remove_args=()
for name in /osbuild.ks /osbuild-base.ks /images/install.img; do
    if xorriso -return_with WARNING 1 -indev "$source_iso" -ls "$name" >/dev/null 2>&1; then
        remove_args+=(-rm "$name" --)
    fi
done
xorriso -indev "$source_iso" -outdev "$output" -boot_image any replay \
    "${payload_args[@]}" "${remove_args[@]}" \
    -map "$artifacts/root.squashfs" /LiveOS/squashfs.img \
    -map "$artifacts/vmlinuz" /images/pxeboot/vmlinuz \
    -map "$artifacts/romulus13.dtb" /images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb \
    -map "$artifacts/initrd" /images/pxeboot/initrd.img \
    -map "$artifacts/smbios.mod" /boot/grub2/arm64-efi/smbios.mod \
    -map "$work/grub.cfg" /EFI/BOOT/grub.cfg \
    -map "$work/efiboot.img" /images/efiboot.img \
    -append_partition 2 0xef "$work/efiboot.img" \
    -boot_image any appended_part_as=gpt -commit -end
implantisomd5 --force "$output"
checkisomd5 "$output"
if [[ $mode == installer ]]; then
    xorriso -osirrox on -indev "$output" -extract /azurefin/support "$work/verified-support"
    python3 "$script_dir/../verify_installer_support.py" "$script_dir/.." "$work/verified-support"
fi
sha256sum "$output"
echo "LOCAL TEST ONLY: $mode mode; not for publication."
