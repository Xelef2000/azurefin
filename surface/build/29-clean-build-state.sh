#!/usr/bin/env bash
# Run only inside the image build, never against the installed host.
set -euo pipefail
[[ -e /run/.containerenv || ${container:-} == oci || ${container:-} == podman ]] || {
    echo 'Refusing build-state cleanup outside a container' >&2
    exit 1
}
# These are rebuildable package-manager caches, not the RPM database or
# provisioning workspace. Keep the actual bootc lint checks enabled.
dnf5 clean all
rm -rf -- /run/dnf /var/cache/libdnf5 /var/lib/dnf/repos
rm -f -- /var/log/dnf5.log /var/cache/ldconfig/aux-cache
# AppStream's package triggers leave generated catalogs after store removal.
# These belong to runtime cache, not the immutable image's /var seed.
rm -f -- /var/cache/swcatalog/cache/C-local-metainfo.xb \
    /var/cache/swcatalog/cache/C-os-catalog.xb
rmdir --ignore-fail-on-non-empty /var/cache/swcatalog/cache /var/cache/swcatalog 2>/dev/null || true
# Repeated package transactions can rotate the log before this final cleanup.
# Match only DNF's numbered rotations, not other image logs.
find /var/log -maxdepth 1 -type f -regextype posix-extended \
    -regex '/var/log/dnf5\.log\.[0-9]+(\.gz)?' -delete
