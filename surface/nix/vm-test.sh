#!/usr/bin/env bash
# Disposable VM diagnostic; not installed in release images.
set -euo pipefail
trap 'echo AZUREFIN_NIX_VM_FAILED; journalctl -b -k --no-pager | grep -i avc || true' ERR
echo AZUREFIN_NIX_VM_BEGIN
uname -m
getenforce
findmnt /
findmnt /nix
case ,$(findmnt -n -o OPTIONS /), in
    *,ro,*) ;;
    *) echo 'Root must be read-only for this test'; exit 1 ;;
esac
bash /usr/share/azurefin/nix-prototype/prototype.sh /usr/libexec/azurefin-nix-installer
echo AZUREFIN_NIX_VM_BOOTSTRAP_COMPLETE
