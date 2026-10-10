# Public installer: no automatic disk partitioning or formatting.
graphical
# Install the audited bootstrap payload without network or firmware preparation.
ostreecontainer --url=/run/install/repo/azurefin/base-oci --transport=oci
%post --nochroot --erroronfail --log=/tmp/azurefin-postinstall-seed.log
set -eu
# Preserve the exact base and tools on the installed disk for offline setup.
destination=/mnt/sysroot/var/lib/azurefin/installer
test ! -e "$destination"
mkdir -p "$destination"
cp -a /run/install/repo/azurefin/base-oci /run/install/repo/azurefin/base-image-id /run/install/repo/azurefin/support "$destination/"
chmod 0700 "$destination"
%end
%post --erroronfail --log=/var/log/azurefin-fstab-post.log
set -eu
python3 /usr/libexec/azurefin-installer-fix-fstab.py
%end
