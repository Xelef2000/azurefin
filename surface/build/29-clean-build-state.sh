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
