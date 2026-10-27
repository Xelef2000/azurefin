#!/usr/bin/env bash
set -euo pipefail
# Reviewed upstream release asset digest; update version and hash together.
[[ $(uname -m) == aarch64 ]]
dnf5 install -y skopeo
curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
    https://github.com/sigstore/cosign/releases/download/v3.1.4/cosign-linux-arm64 \
    -o /usr/bin/cosign
printf '%s  /usr/bin/cosign\n' \
    ade83b7aac62e131cacfe96d958948b2150cc9efec46a570a2649b8e27dedad2 | sha256sum -c -
chmod 0755 /usr/bin/cosign
cosign version
dnf5 clean all
