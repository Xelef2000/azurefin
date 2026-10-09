#!/usr/bin/env bash
# Patch a locally composed ISO for Surface Laptop 7 13-inch USB boot.
# This writes only a NEW image file, never a block device or the source ISO.
set -Eeuo pipefail
status=0
trap 'status=$?; printf "Surface ISO patch failed at line %s (exit %s): %s\n" "$LINENO" "$status" "$BASH_COMMAND" >&2; exit "$status"' ERR
if [[ ${GITHUB_ACTIONS:-false} == true || $# -lt 3 || $# -gt 4 ]]; then
    echo "Local-only usage: $0 SOURCE.iso ROMULUS13.dtb NEW_OUTPUT.iso [--diagnostic|--capture-logs]" >&2
    exit 1
fi
patch_args=()
capture_logs=false
if [[ $# == 4 ]]; then
    [[ $4 == --diagnostic || $4 == --capture-logs ]] || exit 2
    [[ $4 != --capture-logs ]] || capture_logs=true
    patch_args+=(--diagnostic)
fi
source_iso=$(realpath -e -- "$1")
dtb=$(realpath -e -- "$2")
output_iso=$(realpath -m -- "$3")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -f $source_iso && -f $dtb && $output_iso == *.iso && ! -e $output_iso && ! -L $output_iso ]]
[[ $(od -An -tx1 -N4 "$dtb" | tr -d ' \n') == d00dfeed ]]
for command in xorriso mcopy grub2-script-check implantisomd5 checkisomd5 python3; do
    command -v "$command" >/dev/null || {
        printf 'Missing ISO patch prerequisite: %s\n' "$command" >&2
        exit 1
    }
done
work_dir=$(mktemp -d -p "$(dirname -- "$output_iso")" .romulus-iso.XXXXXXXX)
echo "Inspection files retained at $work_dir"
xorriso -osirrox on -indev "$source_iso" \
    -extract /EFI/BOOT/grub.cfg "$work_dir/grub-original.cfg" \
    -extract /images/efiboot.img "$work_dir/efiboot.img" \
    -extract /osbuild.ks "$work_dir/osbuild.ks" \
    -extract /osbuild-base.ks "$work_dir/osbuild-base.ks"
# Refuse unattended partitioning in the generated kickstarts.
if grep -Eiq '^[[:space:]]*(clearpart|autopart|zerombr|part|partition|raid|volgroup|logvol|%pre)([[:space:]]|$)' \
    "$work_dir/osbuild.ks" "$work_dir/osbuild-base.ks"; then
    echo "Unsafe automatic storage configuration found; refusing to prepare ISO." >&2
    exit 1
fi
grep -Eq '^graphical[[:space:]]*$' "$work_dir/osbuild.ks"
PYTHONDONTWRITEBYTECODE=1 python3 "$script_dir/patch_installer_grub.py" "${patch_args[@]}" \
    < "$work_dir/grub-original.cfg" > "$work_dir/grub.cfg"
extra_maps=()
# Optional local repair of an already composed ISO; never alter its source.
if [[ -n ${ROMULUS_INSTALLER_SQUASHFS:-} ]]; then
    installer_squashfs=$(realpath -e -- "$ROMULUS_INSTALLER_SQUASHFS")
    [[ -f $installer_squashfs ]]
    unsquashfs -s "$installer_squashfs" > "$work_dir/installer-superblock.txt"
    grep -qx 'Compression xz' "$work_dir/installer-superblock.txt"
    extra_maps+=(-map "$installer_squashfs" /images/install.img)
fi
if "$capture_logs"; then
    for command in uuidgen mlabel cpio; do command -v "$command" >/dev/null; done
    overlay="$work_dir/capture-overlay"
    mkdir -p "$overlay/usr/libexec" "$overlay/etc/romulus-capture" \
        "$overlay/etc/systemd/system/sysinit.target.wants"
    install -m 0755 "$script_dir/diagnostics/romulus-capture.sh" "$overlay/usr/libexec/romulus-capture"
    install -m 0644 "$script_dir/diagnostics/romulus-capture.service" "$overlay/etc/systemd/system/romulus-capture.service"
    ln -s ../romulus-capture.service "$overlay/etc/systemd/system/sysinit.target.wants/romulus-capture.service"
    serial=$(uuidgen | cut -c 1-8 | tr 'a-f' 'A-F')
    printf '%s-%s\n' "${serial:0:4}" "${serial:4:4}" > "$overlay/etc/romulus-capture/uuid"
    uuidgen > "$overlay/etc/romulus-capture/token"
    mlabel -i "$work_dir/efiboot.img" -N "$serial" ::AZURELOG
    mcopy -i "$work_dir/efiboot.img" "$overlay/etc/romulus-capture/token" ::/romulus-capture-token
    (cd "$overlay" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --owner=0:0) \
        > "$work_dir/romulus-capture.cpio"
    # A second initrd archive adds only our diagnostic service and script.
    sed -i '\|^[[:space:]]*initrd\(efi\)\?[[:space:]]|s|$| /images/romulus-capture.cpio|' "$work_dir/grub.cfg"
    extra_maps+=(-map "$work_dir/romulus-capture.cpio" /images/romulus-capture.cpio)
fi
grub2-script-check "$work_dir/grub.cfg"
mcopy -o -i "$work_dir/efiboot.img" "$work_dir/grub.cfg" ::/EFI/BOOT/grub.cfg
mcopy -i "$work_dir/efiboot.img" ::/EFI/BOOT/grub.cfg "$work_dir/grub-efi-verified.cfg"
cmp "$work_dir/grub.cfg" "$work_dir/grub-efi-verified.cfg"

# Retain El Torito booting and append a matching GPT ESP for USB boot.
xorriso -indev "$source_iso" -outdev "$output_iso" \
    -boot_image any replay \
    -map "$work_dir/grub.cfg" /EFI/BOOT/grub.cfg \
    -map "$work_dir/efiboot.img" /images/efiboot.img \
    -map "$dtb" /images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb \
    "${extra_maps[@]}" \
    -append_partition 2 0xef "$work_dir/efiboot.img" \
    -boot_image any appended_part_as=gpt \
    -commit -end
implantisomd5 --force "$output_iso"
checkisomd5 "$output_iso"
sha256sum "$output_iso" | tee "$output_iso.sha256"
echo "ISO prepared; hardware boot and installed-system bootloader are not validated."
