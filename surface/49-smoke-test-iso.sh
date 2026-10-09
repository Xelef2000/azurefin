#!/usr/bin/env bash
# Bounded ARM initrd/root-handoff test; not a Surface display or GUI test.
set -euo pipefail
[[ $# == 2 && ${GITHUB_ACTIONS:-false} != true ]]
iso=$(realpath -e "$1")
work=$(realpath -m "$2")
[[ -f $iso && ! -e $work && ! -L $work ]]
mkdir "$work"
checkisomd5 "$iso"
xorriso -osirrox on -indev "$iso" \
    -extract /images/pxeboot/vmlinuz "$work/vmlinuz" \
    -extract /images/pxeboot/initrd.img "$work/initrd.img" \
    -extract /images/romulus-capture.cpio "$work/capture.cpio"
# Host decompression keeps TCG runtime manageable; firmware loading is untested.
xz -dc "$work/initrd.img" > "$work/combined-initrd.img"
cat "$work/capture.cpio" >> "$work/combined-initrd.img"
qemu-img create -f qcow2 -F raw -b "$iso" "$work/usb.qcow2"
qemu-system-aarch64 -machine virt -cpu cortex-a76 -m 3G -smp 2 \
    -nographic -monitor none -no-reboot \
    -kernel "$work/vmlinuz" -initrd "$work/combined-initrd.img" \
    -append 'console=ttyAMA0 inst.stage2=hd:LABEL=Fedora-S-dvd-aarch64-44 rd.plymouth=0 plymouth.enable=0 panic=0' \
    -device virtio-rng-pci -device qemu-xhci \
    -drive "if=none,id=capture,file=$work/usb.qcow2,format=qcow2" \
    -device usb-storage,drive=capture > "$work/serial.log" 2>&1 &
vm_pid=$!
trap 'kill -TERM "$vm_pid" 2>/dev/null || true; wait "$vm_pid" 2>/dev/null || true' EXIT
for ((attempt=0; attempt<360; attempt++)); do
    if grep -q 'initrd-switch-root.service' "$work/serial.log" &&
       grep -q 'Successfully loaded SELinux policy' "$work/serial.log"; then
        echo VM_INSTALLER_ROOT_HANDOFF_VERIFIED
        exit 0
    fi
    if ! kill -0 "$vm_pid" 2>/dev/null; then
        echo VM_EXITED_BEFORE_VERIFIED_HANDOFF >&2
        exit 1
    fi
    sleep 5
done
echo VM_HANDOFF_TIMEOUT >&2
exit 1
