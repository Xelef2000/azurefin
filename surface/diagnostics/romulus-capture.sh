#!/usr/bin/bash
# Diagnostic image only. Never search or mount the internal NVMe drive.
set -u
expected_uuid=$(cat /etc/romulus-capture/uuid) || exit 1
expected_token=$(cat /etc/romulus-capture/token) || exit 1
[[ $expected_uuid =~ ^[A-F0-9]{4}-[A-F0-9]{4}$ ]] || exit 1
[[ $expected_token =~ ^[a-f0-9-]{36}$ ]] || exit 1
boot_id=$(cat /proc/sys/kernel/random/boot_id)
ram=/run/romulus-capture
target=/run/romulus-capture-media
mkdir -p "$ram" "$target"
mounted=false
loop_device=
finish() {
    if "$mounted"; then
        umount "$target" || true
    fi
    if [[ -n $loop_device ]]; then
        losetup -d "$loop_device" || true
    fi
}
trap finish EXIT
trap 'exit 0' TERM INT
echo 'Romulus diagnostic capture started; waiting for marked external media.'

# Bounded output: two alternating snapshots, at most 512 KiB each, plus state.
# A synchronous FAT mount makes completed writes survive an abrupt shutdown.
for ((sample=0; sample<120; sample++)); do
    dmesg | tail -c 262144 > "$ram/kernel.txt"
    timeout 2 journalctl -b -n 500 -o short-monotonic --no-pager 2>&1 |
        tail -c 262144 > "$ram/journal.txt"
    {
        echo "sample=$sample"
        cat /proc/uptime /proc/modules
        for d in /sys/class/power_supply/*; do
            echo "$d"
            for f in type status capacity online voltage_now current_now power_now energy_now energy_full; do
                if [[ -r $d/$f ]]; then
                    printf '%s=' "$f"
                    cat "$d/$f" 2>&1
                fi
            done
        done
        timeout 2 systemctl show systemd-battery-check.service dracut-pre-udev.service \
            -p Id -p ActiveState -p SubState -p Result -p ExecMainStatus
    } 2>&1 | tail -c 65536 > "$ram/state.txt"

    if ! "$mounted"; then
        for candidate in /dev/sd[a-z][0-9]*; do
            [[ -b $candidate ]] || continue
            [[ $(blkid -s UUID -o value "$candidate" 2>/dev/null) == "$expected_uuid" ]] || continue
            # Mount through a loop device: claiming the partition directly
            # prevents Anaconda from mounting the parent hybrid ISO disk.
            loop_device=$(losetup --find --show "$candidate") || continue
            if ! mount -t vfat -o ro,nodev,nosuid,noexec "$loop_device" "$target"; then
                losetup -d "$loop_device" || exit 1
                loop_device=
                continue
            fi
            if [[ $(cat "$target/romulus-capture-token" 2>/dev/null) != "$expected_token" ]]; then
                umount "$target" || exit 1
                losetup -d "$loop_device" || exit 1
                loop_device=
                continue
            fi
            if ! mount -o remount,rw,sync,nodev,nosuid,noexec "$target"; then
                umount "$target" || exit 1
                losetup -d "$loop_device" || exit 1
                loop_device=
                continue
            fi
            mounted=true
            mkdir -p "$target/romulus-logs/$boot_id" || exit 1
            echo 'Romulus capture: marked external media available.'
            break
        done
    fi
    if "$mounted"; then
        slot=$((sample % 2))
        for kind in kernel journal state; do
            cp "$ram/$kind.txt" "$target/romulus-logs/$boot_id/$kind-$slot.txt" || exit 1
        done
    fi
    sleep 2
done
