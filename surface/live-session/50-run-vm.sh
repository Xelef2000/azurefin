#!/usr/bin/env bash
# No networking or host disks; live root is read-only with an in-RAM overlay.
set -euo pipefail
output=$(realpath "${1:?VM artifact directory required}")
test -s "$output/root.squashfs"
exec qemu-system-aarch64 \
    -machine virt -cpu max -accel tcg -smp 4 -m 6144 \
    -kernel "$output/vmlinuz" -initrd "$output/initrd" \
    -append 'console=ttyAMA0 root=live:/dev/vda rd.live.image rd.live.overlay.overlayfs=1 azurefin.live=1 enforcing=1 systemd.show_status=1' \
    -drive "file=$output/root.squashfs,format=raw,if=virtio,readonly=on" \
    -device virtio-gpu-pci -device virtio-keyboard-pci -device virtio-tablet-pci \
    -nic none -display none -serial "file:$output/serial.log" \
    -monitor "unix:$output/monitor.sock,server=on,wait=off"
