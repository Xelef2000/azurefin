#!/usr/bin/env bash
# Boot the actual ISO as a read-only USB device through ARM64 UEFI.
set -euo pipefail
iso=$(realpath -e "${1:?local ISO required}")
output=${2:?NEW VM output directory required}
mode=${3:-desktop}
[[ $mode == desktop || $mode == install ]]
test -f "$iso"
mkdir -- "$output"
output=$(realpath "$output")
cp /usr/share/edk2/aarch64/QEMU_EFI-qemuvars-pflash.raw "$output/vars.raw"
disk_args=()
if [[ $mode == install ]]; then
    # The NEW output directory guarantees that no existing disk is overwritten.
    qemu-img create -f qcow2 "$output/install.qcow2" 64G
    disk_args=(-drive "file=$output/install.qcow2,format=qcow2,if=virtio")
fi
exec qemu-system-aarch64 \
    -machine virt -cpu max -accel tcg -smp 4 -m 6144 \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw \
    -drive "if=pflash,format=raw,file=$output/vars.raw" \
    -smbios type=1,manufacturer=AzurefinVM \
    -device qemu-xhci -drive "file=$iso,format=raw,if=none,id=liveusb,readonly=on" \
    -device usb-storage,drive=liveusb,bootindex=1 \
    "${disk_args[@]}" \
    -device virtio-gpu-pci -device virtio-keyboard-pci -device virtio-tablet-pci \
    -nic none -display none \
    -chardev "socket,id=serial,path=$output/serial.sock,server=on,wait=off,logfile=$output/serial.log" \
    -serial chardev:serial \
    -monitor "unix:$output/monitor.sock,server=on,wait=off" \
    -qmp "unix:$output/qmp.sock,server=on,wait=off"
