#!/usr/bin/env bash
set -euo pipefail
[[ $(rpm --eval '%{_arch}') == aarch64 ]]
if ! rpm -q python3 policycoreutils-python-utils curl zstd tar util-linux shadow-utils >/dev/null; then
    dnf5 install -y python3 policycoreutils-python-utils /usr/bin/curl zstd tar util-linux shadow-utils
    dnf5 clean all
fi
workspace=$(mktemp -d /tmp/azurefin-nix-build.XXXXXXXX)
trap 'rm -f "$workspace/installer" "$workspace/notices"; rmdir "$workspace"' EXIT
installer_url=$(python3 -c 'import json; print(json.load(open("/ctx/nix/artifacts.json"))["artifacts"]["aarch64-linux"]["url"])')
notices_url=$(python3 -c 'import json; print(json.load(open("/ctx/nix/artifacts.json"))["source_release"]["notices"]["url"])')
curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' "$installer_url" -o "$workspace/installer"
curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' "$notices_url" -o "$workspace/notices"
python3 /ctx/nix/stage_image.py --root / --installer "$workspace/installer" --notices "$workspace/notices"
# Never initialize /var, install build users, or run the installer at build time.
test ! -e /var/lib/nix
test ! -e /var/lib/azurefin/nix
test ! -L /nix
systemctl is-enabled azurefin-nix-ready.timer
