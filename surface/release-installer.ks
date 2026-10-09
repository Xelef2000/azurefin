# Public installer: no automatic disk partitioning or formatting.
graphical
%pre --erroronfail --log=/tmp/azurefin-preparation.log
set -eu
python3 /run/install/repo/azurefin/support/release_workspace.py
%end
%include /run/azurefin-prepared.ks
