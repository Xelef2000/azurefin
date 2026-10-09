# Local prototype, tied to the explicitly prepared external workspace UUID.
# No unattended partitioning commands. Preserve the normal boot entry as fallback.
graphical
%pre --erroronfail --log=/tmp/azurefin-preparation.log
set -eu
workspace_uuid=REPLACE_WITH_PREPARED_WORKSPACE_UUID
workspace=/dev/disk/by-uuid/$workspace_uuid
test -b "$workspace"
disk=$(lsblk -dn -o PKNAME "$workspace" | xargs)
test "$(lsblk -dn -o TRAN "/dev/$disk" | xargs)" = usb
test "$(blockdev --getsize64 "/dev/$disk")" = 500107862016
mkdir -p /run/azurefin-work
mount -o rw,nosuid,nodev "$workspace" /run/azurefin-work
test "$(findmnt -n -o UUID -T /run/azurefin-work)" = "$workspace_uuid"
python3 /run/azurefin-work/support/installer_prepare.py "$disk"
%end
%include /run/azurefin-prepared.ks
