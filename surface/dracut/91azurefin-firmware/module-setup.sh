#!/usr/bin/bash
# Explicitly included in the public base; inactive without a local boot UUID.
# shellcheck disable=SC2154 # moddir is provided by dracut.
check() { return 255; }
depends() { echo 'bash dracut-systemd'; }
installkernel() { instmods nvme phy_qcom_qmp_pcie ext4; }
install() {
    inst_multiple bash blkid mount umount modprobe sha256sum stat find head sleep \
        mkdir cat mktemp mv timeout
    inst_simple /usr/share/azurefin/boot-firmware.sha256 /etc/azurefin/boot-firmware.sha256
    inst_script "$moddir/load-firmware.sh" /usr/libexec/azurefin-load-boot-firmware
    inst_hook pre-udev 00 "$moddir/pre-udev.sh"
    inst_simple "$moddir/modules-load.conf" \
        /etc/systemd/system/systemd-modules-load.service.d/azurefin-firmware.conf
}
