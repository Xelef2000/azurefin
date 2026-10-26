#!/usr/bin/python3
"""Single live entry; the VM SMBIOS marker avoids replacing QEMU's own DTB."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patch_installer_grub import EARLY_DISPLAY_DRIVERS

CONFIG = '''insmod all_video
set gfxpayload=keep
insmod gzio
insmod part_gpt
insmod iso9660
search --no-floppy --set=root -l 'Fedora-S-dvd-aarch64-44'
set timeout=5
set default=azurefin-live
menuentry 'Try Azurefin (local alpha 3 test)' --id azurefin-live {
  set azurefin_manufacturer=unknown
  insmod /boot/grub2/arm64-efi/smbios.mod
  smbios --type 1 --get-string 4 --set azurefin_manufacturer
  linux /images/pxeboot/vmlinuz root=live:LABEL=Fedora-S-dvd-aarch64-44 rd.live.image rd.live.overlay.overlayfs=1 azurefin.live=1 enforcing=1 console=tty0 console=ttyAMA0 clk_ignore_unused pd_ignore_unused rd.plymouth=0 plymouth.enable=0 rd.driver.pre=DRIVERS
  if [ "$azurefin_manufacturer" != "AzurefinVM" ]; then
    devicetree /images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb
  fi
  initrd /images/pxeboot/initrd.img
}
'''.replace('DRIVERS', ','.join(EARLY_DISPLAY_DRIVERS))

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(CONFIG)
